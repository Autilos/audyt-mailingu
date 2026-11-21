"""Testy rekomendacji: pojawiają się tylko dla wykrytych problemów i w ustalonej kolejności."""
import filecmp
import os
import sys
import unittest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR = os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts")
ML = os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts")
sys.path.insert(0, GR)

from rekomendacje import REKOMENDACJE, rekomendacja_serii, uloz  # noqa: E402


def m(dzien, klasa, wl=True, wys=10):
    return {"dzien": dzien, "klasa": klasa, "wlaczony": wl, "wyslane": wys}


class Seria(unittest.TestCase):
    def test_dobra_seria_bez_rady(self):
        self.assertIsNone(rekomendacja_serii([m(0, "SPRZEDAŻOWY"), m(2, "WARTOŚCIOWY"), m(4, "MIESZANY"), m(7, "SPRZEDAŻOWY")]))

    def test_jeden_mail_dostaje_uklad(self):
        tyt, tresc = rekomendacja_serii([m(0, "SPRZEDAŻOWY")])
        self.assertIn("dzień 2", tresc)

    def test_same_oferty_dostaja_mail_z_trescia(self):
        _, tresc = rekomendacja_serii([m(0, "SPRZEDAŻOWY"), m(5, "SPRZEDAŻOWY")])
        self.assertIn("bez oferty", tresc)
        self.assertNotIn("Rozciągnij", tresc)

    def test_wylaczona(self):
        self.assertEqual(rekomendacja_serii([m(0, "WARTOŚCIOWY", wl=False)])[0], "Włącz albo zbuduj serię powitalną")


class Kolejnosc(unittest.TestCase):
    def test_dane_przed_automatami(self):
        tyt = [t for t, _, _ in uloz({"koszyk_brak": "", "bez_sledzenia": "", "sklep_bez_zamowien": "X"})]
        self.assertEqual(tyt[0], REKOMENDACJE["sklep_bez_zamowien"][1])
        self.assertEqual(tyt[-1], REKOMENDACJE["bez_sledzenia"][1])

    def test_rada_serii_zastepuje_ogolne_powitanie(self):
        wynik = uloz({"powitanie_brak": ""}, [("Popraw serię powitalną", "…", "lista A")])
        self.assertEqual([t for t, _, _ in wynik], ["Popraw serię powitalną"])

    def test_nic_nie_wykryto(self):
        self.assertEqual(uloz({}), [])

    def test_nieznany_klucz_pomijany(self):
        self.assertEqual(uloz({"cos_innego": ""}), [])

    def test_bez_obietnic_wzrostu_i_czasu(self):
        for _, tyt, tresc in REKOMENDACJE.values():
            for zle in ("wzrost o", "zwiększy o", "tygodni wdrożenia", "godzin pracy", "prawnik"):
                self.assertNotIn(zle, (tyt + tresc).lower())

    def test_kopia_w_mailerlite_identyczna(self):
        self.assertTrue(filecmp.cmp(os.path.join(GR, "rekomendacje.py"), os.path.join(ML, "rekomendacje.py"), shallow=False))


if __name__ == "__main__":
    unittest.main()
