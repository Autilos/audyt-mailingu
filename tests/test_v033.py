"""Testy v0.3.3: pamięć odpowiedzi (wznawianie), plik postępu, klucz z pliku, powitanie na największej liście,
komunikat o formularzach, domyślne 30 dni, --test-polaczenia w MailerLite."""
import filecmp
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR = os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts")
ML = os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts")
sys.path.insert(0, GR)
import audyt_getresponse as A  # noqa: E402
import wspolne  # noqa: E402


class Odpowiedz(io.BytesIO):
    headers = {"TotalPages": "1"}


class PamiecIWznawianie(unittest.TestCase):
    def test_drugie_zapytanie_z_pamieci(self):
        with tempfile.TemporaryDirectory() as d, mock.patch("tempfile.gettempdir", return_value=d):
            pam = wspolne.Pamiec("test", "falszywy-klucz")
            gr = A.GR("falszywy-klucz", "https://api.getresponse.com/v3", pamiec=pam)
            with mock.patch.object(A._OTWIERACZ, "open", return_value=Odpowiedz(b'[{"campaignId": "X"}]')) as siec, \
                    mock.patch("time.sleep"):
                d1, h1 = gr.get("/campaigns", {"perPage": 1})
                d2, h2 = gr.get("/campaigns", {"perPage": 1})
            self.assertEqual(siec.call_count, 1, "drugie zapytanie ma przyjść z pamięci")
            self.assertEqual(d1, d2)
            self.assertEqual(h2.get("totalpages"), "1")
            self.assertEqual(pam.trafien, 1)
            pliki = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs]
            self.assertTrue(all(oct(os.stat(p).st_mode)[-3:] == "600" for p in pliki))
            self.assertFalse(any("falszywy" in p for p in pliki), "klucz nie trafia do nazw plików")

    def test_wylaczona_pamiec(self):
        self.assertIsNone(wspolne.Pamiec("x", "k", wlaczona=False).czytaj("u"))


class PostepIKlucz(unittest.TestCase):
    def test_plik_postepu(self):
        with tempfile.TemporaryDirectory() as d:
            p = wspolne.Postep(os.path.join(d, "p.txt"))
            with mock.patch("sys.stderr", io.StringIO()):
                p("2/6 automatyzacje 10/40")
            self.assertIn("2/6 automatyzacje 10/40", open(os.path.join(d, "p.txt"), encoding="utf-8").read())

    def test_klucz_z_pliku_gdy_brak_zmiennej(self):
        with tempfile.TemporaryDirectory() as d:
            plik = os.path.join(d, "k.key")
            open(plik, "w").write("abc123\n")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(wspolne.klucz_z_env_albo_pliku("GETRESPONSE_API_KEY", plik), "abc123")
            with mock.patch.dict(os.environ, {"GETRESPONSE_API_KEY": "z_env"}):
                self.assertEqual(wspolne.klucz_z_env_albo_pliku("GETRESPONSE_API_KEY", plik), "z_env")

    def test_pokaz_zapisuje_postep(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, os.path.join(GR, "audyt_getresponse.py"), "--pokaz", "--raport", "r.md"],
                           check=True, capture_output=True, cwd=d)
            postep = open(os.path.join(d, "r.postep.txt"), encoding="utf-8").read()
            for etap in ("1/6", "3/6 maile z automatów", "6/6 sklep", "Gotowe"):
                self.assertIn(etap, postep)

    def test_domyslnie_30_dni(self):
        with tempfile.TemporaryDirectory() as d:
            for skrypt in (os.path.join(GR, "audyt_getresponse.py"), os.path.join(ML, "audyt_mailerlite.py")):
                subprocess.run([sys.executable, skrypt, "--pokaz", "--raport", "r.md"], check=True, capture_output=True, cwd=d)
                self.assertIn("ostatnie 30 dni", open(os.path.join(d, "r.md"), encoding="utf-8").read())

    def test_ml_ma_test_polaczenia(self):
        wynik = subprocess.run([sys.executable, os.path.join(ML, "audyt_mailerlite.py"), "--help"], capture_output=True, text=True)
        self.assertIn("--test-polaczenia", wynik.stdout)

    def test_wspolne_identyczne(self):
        self.assertTrue(filecmp.cmp(os.path.join(GR, "wspolne.py"), os.path.join(ML, "wspolne.py"), shallow=False))


class Powitanie(unittest.TestCase):
    def D(self, glowna_wlaczona):
        return {"listy": [{"nazwa": "Główna", "kontakty": 500}, {"nazwa": "Mała", "kontakty": 16}],
                "seria_powitalna": [
                    {"zrodlo": "autorespondery", "lista": "Główna", "maile": [{"wlaczony": glowna_wlaczona, "wyslane": 300}]},
                    {"zrodlo": "autorespondery", "lista": "Mała", "maile": [{"wlaczony": True, "wyslane": 12}]}],
                "lista_kontrolna": [{"automat": "Powitanie nowego subskrybenta", "stan": "działa", "trafienia": []}]}

    def test_wylaczone_na_glownej_to_nie_dziala(self):
        D = self.D(False)
        A.popraw_powitanie(D)
        stan = D["lista_kontrolna"][0]["stan"]
        self.assertTrue(stan.startswith("jest, ale na największej liście „Główna”"))
        self.assertIn("działa tylko na: Mała", stan)

    def test_wlaczone_na_glownej_zostaje(self):
        D = self.D(True)
        A.popraw_powitanie(D)
        self.assertEqual(D["lista_kontrolna"][0]["stan"], "działa")


class Formularze(unittest.TestCase):
    def test_komunikat_po_ludzku(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable, os.path.join(GR, "audyt_getresponse.py"), "--pokaz", "--raport", "r.md"],
                           check=True, capture_output=True, cwd=d)
        D = {"formularze": None}
        tekst = "Tę część audyt pominął"
        self.assertIn(tekst, open(os.path.join(GR, "audyt_getresponse.py"), encoding="utf-8").read())
        self.assertNotIn("Niedostępne na tym koncie (API zwróciło 404", open(os.path.join(GR, "audyt_getresponse.py"), encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
