"""Testy v0.3.6: poprawki po niezależnym przeglądzie prywatności (dane zmyślone, żadnych prawdziwych kluczy)."""
import io
import os
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest import mock

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts"))
sys.path.insert(0, os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts"))
import audyt_getresponse as G  # noqa: E402
import audyt_mailerlite as M  # noqa: E402
import wspolne  # noqa: E402


class Maskowanie(unittest.TestCase):
    def test_telefony_w_roznych_zapisach(self):
        for t in ("+48 600 12 34 56", "600 12 34 56", "12 345 67 89", "(12) 345-67-89", "+48(600)123456",
                  "+48 12 345 67 89", "+44 7700 900123", "600-000-001", "0048 600 000 001", "600000001"):
            self.assertEqual(wspolne.maskuj(f"Hurt tel. {t}"), "Hurt tel. [telefon ukryty]", t)

    def test_daty_kwoty_i_kody_zostaja(self):
        for t in ("Szkic 2026-03-02 10:15:00", "23.11.2026, 10:00", "2026-11-01 2026-11-23", "1 240 zł", "WITAJ10 −10%",
                  "Black Friday 2026 −14%", "v0.3.6", "2026-10-24T00:00:00+0000"):
            self.assertEqual(wspolne.maskuj(t), t)

    def test_emaile_nietypowe(self):
        for t in ("jan＠sklep.pl", "jan@sklep．pl", "kontakt[at]sklep.pl", "jan at sklep dot pl", "jan%40sklep.pl",
                  "jan&#64;sklep.pl", "Jan.Kowalski+vip@Przykład.PL"):
            self.assertEqual(wspolne.maskuj(f"Lista {t}"), "Lista [e-mail ukryty]", t)

    def test_ip(self):
        for t in ("203.0.113.7", "2001:db8::5", "fe80:0:0:0:1:2:3:4"):
            self.assertEqual(wspolne.maskuj(f"z {t}"), "z [IP ukryty]", t)

    def test_nazwy_pol_tez_maskowane(self):
        self.assertEqual(wspolne.maskuj_wszystko({"jan.kowalski@x.pl": 3}), {"[e-mail ukryty]": 3})

    def test_statystyki_tylko_liczby_i_kody(self):
        d = wspolne.przytnij({"L1": [{"sent": 5, "timeInterval": "2026-11-01/2026-11-23", "notatka": "Jan Kowalski, ul. Długa 5",
                                      "jan@x.pl": 1}]}, wspolne.CALOSC)
        self.assertEqual(d, {"L1": [{"sent": 5, "timeInterval": "2026-11-01/2026-11-23", "notatka": None}]})

    def test_wynik_funkcji_we_wzorze_maskowany(self):
        self.assertEqual(G._FLAGI(["ecommerce_tracking", "jan.kowalski@gmail.com"]), ["ecommerce_tracking"])  # e-mail to nie kod — odpada
        self.assertEqual(wspolne.przytnij({"f": "jan@x.pl"}, {"f": lambda v: v}), {"f": "[e-mail ukryty]"})

    def test_kod_odrzuca_zdania(self):
        self.assertEqual(wspolne.KOD("enabled"), "enabled")
        self.assertEqual(wspolne.KOD("2025-01-01 10:00:00"), "2025-01-01 10:00:00")
        self.assertIsNone(wspolne.KOD("Jan Kowalski"))


class Sito(unittest.TestCase):
    def test_contact_id_zamowienia_tylko_tak_nie(self):
        d = G.przytnij_odpowiedz("/shops/S1/orders", [{"orderId": "O1", "contactId": "Vp7d", "totalPrice": "10.00"},
                                                      {"orderId": "O2", "contactId": ""}])
        self.assertEqual([o["contactId"] for o in d], [True, False])

    def test_status_z_nazwiskiem_odpada(self):
        d = G.przytnij_odpowiedz("/forms", [{"formId": "F1", "name": "Stopka", "status": "Jan Kowalski"}])
        self.assertEqual(d, [{"formId": "F1", "name": "Stopka", "status": None}])


class Klucz(unittest.TestCase):
    def test_klucz_z_nowa_linia_bez_pokazania(self):
        with tempfile.TemporaryDirectory() as tmp:
            plik = os.path.join(tmp, "k.key")
            with open(plik, "w") as f:
                f.write("falszywy\nklucz-SEKRET")
            with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(SystemExit) as e:
                wspolne.klucz_z_env_albo_pliku("BRAK_ZMIENNEJ", plik)
            self.assertNotIn("SEKRET", str(e.exception.code))

    def test_klucz_poprawny(self):
        with mock.patch.dict(os.environ, {"X_KLUCZ": "  abc-DEF_123.xyz \n"}):
            self.assertEqual(wspolne.klucz_z_env_albo_pliku("X_KLUCZ", "/nie/ma"), "abc-DEF_123.xyz")


class Pamiec(unittest.TestCase):
    def test_przeterminowane_odpowiedzi_usuwane(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("tempfile.gettempdir", return_value=tmp):
            p = wspolne.Pamiec("x", "falszywy-klucz")
            p.zapisz("https://a/b", {"d": 1})
            stary = p._plik("https://a/b")
            dawno = time.time() - (wspolne.WAZNOSC_PAMIECI_H + 1) * 3600
            os.utime(stary, (dawno, dawno))
            wspolne.Pamiec("x", "falszywy-klucz", wlaczona=False)  # także z --bez-pamieci
            self.assertFalse(os.path.exists(stary))


class MailerLite(unittest.TestCase):
    def test_niedostepne_bez_kursora(self):
        def blad(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 404, "x", {}, io.BytesIO(b""))
        ml = M.ML("falszywy-klucz")
        with mock.patch.object(M._OTWIERACZ, "open", side_effect=blad), mock.patch("time.sleep"):
            ml.get(M.API + "/campaigns?cursor=abc123&limit=100")
        self.assertEqual(ml.niedostepne, ["/campaigns"])


class SkillMd(unittest.TestCase):
    def test_zakaz_innych_polaczen_i_klucz_z_pliku(self):
        for sk in ("audyt-getresponse", "audyt-mailerlite"):
            with open(os.path.join(KORZEN, "skills", sk, "SKILL.md"), encoding="utf-8") as f:
                t = f.read()
            self.assertIn("Nie używaj też żadnych innych połączeń z GetResponse ani MailerLite", t)
            self.assertIn("Nie zalecaj ustawiania zmiennej", t)


if __name__ == "__main__":
    unittest.main()
