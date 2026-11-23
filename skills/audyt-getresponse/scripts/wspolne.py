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
import unicodedata

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
    Lista: wzór stosowany do każdego elementu. CALOSC = cała odpowiedź (tylko statystyki), ale z napisów zostają
    wyłącznie krótkie kody bez spacji (KOD), np. daty — nazwisko czy zdanie odpada.
    Każdy zachowany tekst przechodzi przez maskuj() — adres e-mail albo telefon w nazwie listy nie trafi nawet na dysk."""
    if wzor == CALOSC:
        return tylko_liczby_i_kody(obiekt)  # statystyki: liczby, a z napisów tylko krótkie kody i daty
    if callable(wzor):
        return maskuj_wszystko(wzor(obiekt))  # wynik funkcji też przechodzi przez maskowanie
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


RE_KOD = re.compile(r"[\w.:+/-]{1,64}|\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?")  # kod albo data „2026-11-23 10:00:00”


def KOD(v):
    """Pole słownikowe API (status, waluta, platforma, typ, data): przechodzi tylko krótki kod bez spacji, np.
    „enabled”, „PLN”, „woocommerce”, „2026-11-23T10:00:00+0000”. Zdanie, nazwisko czy adres — nic nie zostaje."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str) and RE_KOD.fullmatch(v):
        return maskuj(v)
    return None


def tylko_liczby_i_kody(obiekt):
    """Odpowiedź statystyczna: liczby bez zmian, napisy tylko jako KOD, nazwy pól też tylko jako kod."""
    if isinstance(obiekt, list):
        return [tylko_liczby_i_kody(x) for x in obiekt]
    if isinstance(obiekt, dict):
        return {k: tylko_liczby_i_kody(v) for k, v in obiekt.items() if isinstance(k, str) and RE_KOD.fullmatch(k) and maskuj(k) == k}
    return KOD(obiekt)


# Adres e-mail: zwykły, zakodowany w adresie WWW (%40) albo w HTML (&#64;, &#x40;), a także zapis „jan [at] sklep.pl”
# i „jan at sklep dot pl”. Tekst jest najpierw sprowadzany do zwykłych znaków (NFKC), więc „＠”, „．” i cyfry
# pisane innym krojem też są wykrywane.
_MALPA = r"(?:@|%40|&#0*64;|&#x0*40;|\s?[\[(]at[\])]\s?|\s+at\s+)"
_KROPKA = r"(?:\.|\s?[\[(]dot[\])]\s?|\s+dot\s+|\s+kropka\s+)"
RE_EMAIL = re.compile(rf"[\w.+-]+{_MALPA}[\w-]+(?:{_KROPKA}[\w-]+)+", re.UNICODE | re.IGNORECASE)
# Numer telefonu: ciąg cyfr ze spacjami, kreskami, kropkami i nawiasami, z numerem kraju (+48, 0048) albo bez,
# w dowolnym podziale na grupy (600 123 456, 600 12 34 56, 12 345 67 89, (12) 345-67-89, +48(600)123456).
# Liczy się suma cyfr: 9–13. Daty (2026-03-02, 23.11.2026) i godziny nie są ukrywane.
RE_TELEFON = re.compile(r"(?<![\w+])(?:\+|00)?\(?\d[\d\s().-]{7,20}\d(?!\w)")
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4}")
# Numer IP: IPv4 (cztery liczby 0–255) i IPv6 (co najmniej cztery grupy albo skrót „::”). Godzina 10:15:00 nie pasuje.
RE_IP = re.compile(r"(?<![\w.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.]*\d)"
                   r"|(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}(?![\w:])"
                   r"|(?<![\w:])(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4}){0,5})?(?![\w:])")


def _telefon(m):
    t = m.group(0)
    cyfry = sum(c.isdigit() for c in t)
    if not 9 <= cyfry <= 13 or (RE_DATA.search(t) and not t.lstrip("(").startswith(("+", "00"))):
        return t
    # Kwota „600 123 456 zł” wygląda jak numer telefonu — też ją ukrywamy (bezpieczniej ukryć kwotę niż pokazać numer).
    return "[telefon ukryty]"


def maskuj(tekst):
    """Adres e-mail, numer telefonu i numer IP w dowolnym tekście z konta (nazwa listy, automatu, temat) → zamaskowany."""
    if not isinstance(tekst, str):
        return tekst
    t = unicodedata.normalize("NFKC", tekst)
    t = RE_EMAIL.sub("[e-mail ukryty]", t)
    t = RE_IP.sub("[IP ukryty]", t)
    return RE_TELEFON.sub(_telefon, t)


def czysty_klucz(klucz):
    """Klucz API: tylko znaki dozwolone w nagłówku HTTP. Inaczej przerwij — bez pokazywania klucza
    (biblioteka HTTP przy złym znaku wypisałaby go w komunikacie o błędzie)."""
    if klucz is None:
        return None
    klucz = klucz.strip()
    if not klucz:
        return None
    if not re.fullmatch(r"[\x21-\x7e]+", klucz):
        sys.exit("Klucz API zawiera niedozwolone znaki (np. spację, nową linię albo polską literę) — zapisz go ponownie, "
                 "kopiując z panelu sam klucz. Klucza nie wyświetlamy.")
    return klucz


def maskuj_wszystko(obiekt):
    """Maskuje adresy e-mail, telefony i numery IP we wszystkich tekstach (także w nazwach pól) — przed zapisem raportu i JSON."""
    if isinstance(obiekt, str):
        return maskuj(obiekt)
    if isinstance(obiekt, list):
        return [maskuj_wszystko(x) for x in obiekt]
    if isinstance(obiekt, tuple):
        return tuple(maskuj_wszystko(x) for x in obiekt)
    if isinstance(obiekt, dict):
        return {maskuj(k): maskuj_wszystko(v) for k, v in obiekt.items()}
    return obiekt


class Pamiec:
    """Pamięć odpowiedzi API na dysku, ważna kilka godzin. Klucz w nazwie katalogu jest tylko skrótem SHA-256."""

    def __init__(self, system, klucz, wlaczona=True):
        self.katalog = None
        self.trafien = 0
        nadrzedny = os.path.join(tempfile.gettempdir(), "audyt-mailingu-pamiec")
        if not wlaczona or not klucz:
            if os.path.isdir(nadrzedny) and not os.path.islink(nadrzedny) and \
                    (not hasattr(os, "getuid") or os.lstat(nadrzedny).st_uid == os.getuid()):
                self.sprzataj(nadrzedny)  # także z --bez-pamieci: stare odpowiedzi nie leżą dłużej niż 12 godzin
            return
        skrot = hashlib.sha256((system + ":" + klucz).encode()).hexdigest()[:16]
        katalog = os.path.join(nadrzedny, skrot)
        os.makedirs(katalog, mode=0o700, exist_ok=True)
        if hasattr(os, "getuid"):
            for k in (nadrzedny, katalog):  # oba katalogi muszą być nasze — inaczej ktoś mógłby podmienić odpowiedzi
                if os.lstat(k).st_uid != os.getuid() or os.path.islink(k):
                    print("  pamięć odpowiedzi wyłączona: katalog tymczasowy należy do innego użytkownika", file=sys.stderr)
                    return
                os.chmod(k, 0o700)
        self.katalog = katalog
        self.sprzataj(nadrzedny)

    @staticmethod
    def sprzataj(nadrzedny):
        """Usuwa przeterminowane odpowiedzi (starsze niż WAZNOSC_PAMIECI_H) ze wszystkich audytów tego użytkownika."""
        granica = time.time() - WAZNOSC_PAMIECI_H * 3600
        for kat, _, pliki in os.walk(nadrzedny):
            for n in pliki:
                p = os.path.join(kat, n)
                try:
                    if os.path.getmtime(p) < granica:
                        os.remove(p)
                except OSError:
                    pass

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
    if k and k.strip():
        return czysty_klucz(k)
    plik = os.path.expanduser(plik)
    if os.path.exists(plik):
        with open(plik, encoding="utf-8", errors="replace") as f:
            return czysty_klucz(f.read())
    return None
