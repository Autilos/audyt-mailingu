"""Wspólne dla obu audytów: plik postępu, pamięć odpowiedzi API (wznawianie) i klucz z pliku.

Pamięć odpowiedzi trzyma wyłącznie odpowiedzi z dozwolonych ścieżek (statystyki, ustawienia, treść maili —
bez danych osobowych) w katalogu tymczasowym systemu, z prawami tylko dla właściciela. Dzięki niej przerwany
audyt uruchomiony ponownie nie zaczyna od zera: odpowiedzi pobrane wcześniej czyta z dysku.
"""
import datetime as dt
import hashlib
import json
import os
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


class Pamiec:
    """Pamięć odpowiedzi API na dysku, ważna kilka godzin. Klucz w nazwie katalogu jest tylko skrótem SHA-256."""

    def __init__(self, system, klucz, wlaczona=True):
        self.katalog = None
        self.trafien = 0
        if not wlaczona or not klucz:
            return
        skrot = hashlib.sha256((system + ":" + klucz).encode()).hexdigest()[:16]
        self.katalog = os.path.join(tempfile.gettempdir(), "audyt-mailingu-pamiec", skrot)
        os.makedirs(self.katalog, mode=0o700, exist_ok=True)

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
