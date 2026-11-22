"""Wspólne dla obu audytów: plik postępu, pamięć odpowiedzi API (wznawianie) i klucz z pliku.

Pamięć odpowiedzi trzyma wyłącznie PRZYCIĘTE odpowiedzi z dozwolonych ścieżek (tylko pola potrzebne audytowi —
bez danych osobowych) w katalogu tymczasowym systemu, z prawami tylko dla właściciela. Dzięki niej przerwany
audyt uruchomiony ponownie nie zaczyna od zera: odpowiedzi pobrane wcześniej czyta z dysku.
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile
import time

WAZNOSC_PAMIECI_H = 12


class Postep:
    """Wypisuje etapy na ekran (stderr) i do pliku postępu, który Claude może czytać, gdy skrypt działa w tle."""

    def __init__(self, plik=None):
        self.plik = plik
        if plik:
            with open(plik, "w", encoding="utf-8") as f:
                f.write("")

    def __call__(self, tekst):
        linia = f"{dt.datetime.now().strftime('%H:%M:%S')} {tekst}"
        print(linia, file=sys.stderr, flush=True)
        if self.plik:
            with open(self.plik, "a", encoding="utf-8") as f:
                f.write(linia + "\n")


# --- Prywatność: tylko potrzebne pola, maskowanie adresów i telefonów -------------------------------------

CALOSC = "*"  # tylko dla odpowiedzi statystycznych (same liczby zbiorcze) — przepuszcza całą odpowiedź


def przytnij(obiekt, wzor):
    """Zostawia z odpowiedzi API WYŁĄCZNIE pola z wzoru — reszta (np. dane osobowe) jest odrzucana od razu,
    zanim cokolwiek trafi do pamięci na dysku, raportu albo na ekran.

    Wzór: słownik {pole: True | wzór | funkcja}. True = tylko wartość prosta (tekst, liczba, tak/nie);
    słownik/lista przechodzi wyłącznie przez zagnieżdżony wzór. Wartość prosta pod polem z zagnieżdżonym wzorem
    też przechodzi (np. treść maila raz jako tekst, raz jako {"html": …}). Funkcja przekształca wartość.
    Lista: wzór stosowany do każdego elementu. CALOSC = bez zmian (tylko statystyki).
    Każdy zachowany tekst przechodzi przez maskuj() — adres e-mail albo telefon w nazwie listy nie trafi nawet na dysk."""
    if wzor == CALOSC:
        return obiekt
    if callable(wzor):
        return wzor(obiekt)
    if isinstance(obiekt, list):
        return [przytnij(x, wzor) for x in obiekt]
    if isinstance(obiekt, str):
        return maskuj(obiekt)
    if obiekt is None or isinstance(obiekt, (int, float, bool)):
        return obiekt
    if isinstance(obiekt, dict) and isinstance(wzor, dict):
        wynik = {}
        for k, w in wzor.items():
            if k not in obiekt:
                continue
            v = obiekt[k]
            if w is True:
                if v is None or isinstance(v, (str, int, float, bool)):
                    wynik[k] = maskuj(v)
            else:
                wynik[k] = przytnij(v, w)
        return wynik
    return None


RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.UNICODE)
# Numer telefonu: 9 cyfr w grupach 3-3-3 (opcjonalnie +48 / 0048) albo 9–11 cyfr ciągiem. Daty i godziny (2026-03-02 10:15) nie pasują.
RE_TELEFON = re.compile(r"(?<![\w+])(?:(?:\+|00)\d{2}[\s.-]?)?(?:\d{3}[\s.-]\d{3}[\s.-]\d{3}|\d{9,11})(?!\w)")


def maskuj(tekst):
    """Adres e-mail i numer telefonu w dowolnym tekście z konta (nazwa listy, automatu, temat) → zamaskowany."""
    if not isinstance(tekst, str):
        return tekst
    return RE_TELEFON.sub("[telefon ukryty]", RE_EMAIL.sub("[e-mail ukryty]", tekst))


def maskuj_wszystko(obiekt):
    """Maskuje adresy e-mail i telefony we wszystkich tekstach (nie w kluczach) — przed zapisem raportu i JSON."""
    if isinstance(obiekt, str):
        return maskuj(obiekt)
    if isinstance(obiekt, list):
        return [maskuj_wszystko(x) for x in obiekt]
    if isinstance(obiekt, tuple):
        return tuple(maskuj_wszystko(x) for x in obiekt)
    if isinstance(obiekt, dict):
        return {k: maskuj_wszystko(v) for k, v in obiekt.items()}
    return obiekt


class Pamiec:
    """Pamięć odpowiedzi API na dysku, ważna kilka godzin. Klucz w nazwie katalogu jest tylko skrótem SHA-256."""

    def __init__(self, system, klucz, wlaczona=True):
        self.katalog = None
        self.trafien = 0
        if not wlaczona or not klucz:
            return
        skrot = hashlib.sha256((system + ":" + klucz).encode()).hexdigest()[:16]
        katalog = os.path.join(tempfile.gettempdir(), "audyt-mailingu-pamiec", skrot)
        os.makedirs(katalog, mode=0o700, exist_ok=True)
        if hasattr(os, "getuid"):
            st = os.stat(katalog)
            if st.st_uid != os.getuid():
                print("  pamięć odpowiedzi wyłączona: katalog tymczasowy należy do innego użytkownika", file=sys.stderr)
                return
            os.chmod(katalog, 0o700)
        self.katalog = katalog

    def _plik(self, url):
        return os.path.join(self.katalog, hashlib.sha256(url.encode()).hexdigest() + ".json")

    def czytaj(self, url):
        if not self.katalog:
            return None
        p = self._plik(url)
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < WAZNOSC_PAMIECI_H * 3600:
            try:
                with open(p, encoding="utf-8") as f:
                    self.trafien += 1
                    return json.load(f)
            except (OSError, ValueError):
                return None
        return None

    def zapisz(self, url, wartosc):
        if not self.katalog:
            return
        p = self._plik(url)
        tmp = p + ".tmp"
        with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as f:
            json.dump(wartosc, f, ensure_ascii=False)
        os.replace(tmp, p)


def klucz_z_env_albo_pliku(zmienna, plik):
    """Klucz ze zmiennej środowiskowej, a gdy jej nie ma — z pliku (zapisanego przez użytkownika komendą read -rs)."""
    k = os.environ.get(zmienna)
    if k:
        return k.strip()
    plik = os.path.expanduser(plik)
    if os.path.exists(plik):
        with open(plik, encoding="utf-8") as f:
            return f.read().strip() or None
    return None
