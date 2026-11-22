"""Testy v0.3.5: liczby sklepu MailerLite z raportu zbiorczego (/ecommerce/shops/{id}/reports/stats).

Odpowiedź API jest FIKCYJNA, w kształcie sprawdzonym na żywym koncie (same nazwy pól i typy, bez wartości klienta),
z doklejonymi fikcyjnymi danymi osobowymi — sito ma je odrzucić. Pojedynczych zamówień (/orders) nadal nie czytamy.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from unittest import mock

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_DIR = os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts")
sys.path.insert(0, ML_DIR)
import audyt_mailerlite as M  # noqa: E402

EMAIL = "kupujacy.testowy@przyklad-kupujacy.example"
IMIE = "Bronislawqq"
TELEFON = "+48 602 345 678"
IP = "198.51.100.7"
ZAKAZANE = [EMAIL, IMIE, "602 345 678", IP, "falszywy-klucz", "Ulica Testowaqq"]
OSOBOWE = {"email": EMAIL, "name": IMIE, "phone": TELEFON, "ip_address": IP,
           "customer": {"email": EMAIL, "first_name": IMIE, "address": "Ulica Testowaqq 1"},
           "last_order": {"customer": {"email": EMAIL}, "total": 99.0}}


def statystyki(zamowienia=4, przychod=40, srednia=10, seria=None):
    """Kształt z żywego API: data.ecommerce (3 liczby) + data.series (jeden wpis na dzień), plus fikcyjne dane osobowe."""
    seria = [{"date": "2026-11-01", "campaign_orders_count": 1, "automation_orders_count": 2,
              "campaign_revenue": 12.5, "automation_revenue": "20.00", **OSOBOWE}] if seria is None else seria
    return {"data": {"ecommerce": {"orders_count": zamowienia, "revenue": przychod, "average_order_value": srednia,
                                   "conversion_rate": "0%", **OSOBOWE},
                     "series": seria, **OSOBOWE}, **OSOBOWE}


class Odpowiedz(io.BytesIO):
    def __init__(self, dane):
        super().__init__(json.dumps(dane).encode())
        self.headers = {}


class Sito(unittest.TestCase):
    def test_sciezka_raportu_dozwolona_zamowienia_nie(self):
        self.assertTrue(M.sciezka_dozwolona(M.API + "/ecommerce/shops/123/reports/stats?start_date=2026-10-24&end_date=2026-11-23"))
        for zla in ("/ecommerce/shops/123/orders", "/ecommerce/shops/123/customers", "/ecommerce/shops/123/reports/orders",
                    "/ecommerce/shops/abc/reports/stats", "/ecommerce/shops/1/reports/stats/x", "/ecommerce/shops/1/carts"):
            self.assertFalse(M.sciezka_dozwolona(M.API + zla), zla)

    def test_sito_zostawia_tylko_liczby(self):
        d = M.przytnij_odpowiedz(M.API + "/ecommerce/shops/1/reports/stats", statystyki())
        self.assertEqual(d, {"data": {"ecommerce": {"orders_count": 4, "revenue": 40, "average_order_value": 10},
                                      "series": [{"campaign_orders_count": 1, "automation_orders_count": 2,
                                                  "campaign_revenue": 12.5, "automation_revenue": 20.0}]}})
        tekst = json.dumps(d, ensure_ascii=False)
        for zle in ZAKAZANE + ["date", "conversion_rate", "customer", "email"]:
            self.assertNotIn(zle, tekst, zle)

    def test_tekst_zamiast_liczby_odpada(self):
        d = M.przytnij_odpowiedz(M.API + "/ecommerce/shops/1/reports/stats",
                                 statystyki(zamowienia=EMAIL, przychod={"email": EMAIL}, srednia=True))
        self.assertEqual(d["data"]["ecommerce"], {"orders_count": None, "revenue": None, "average_order_value": None})

    def test_sklepy_przepuszczaja_id(self):
        d = M.przytnij_odpowiedz(M.API + "/ecommerce/shops", {"data": [{**OSOBOWE, "id": "77", "name": "S"}]})
        self.assertEqual(d["data"][0]["id"], "77")
        self.assertNotIn(EMAIL, json.dumps(d))


class Raport(unittest.TestCase):
    def setUp(self):
        self.zapytania = []

    def odpowiedz(self, stat):
        def f(req, timeout=None):
            u = urllib.parse.urlsplit(req.full_url)
            s = u.path[len("/api"):]
            self.zapytania.append((s, urllib.parse.parse_qs(u.query)))
            if s == "/ecommerce/shops":
                d = {"data": [{**OSOBOWE, "id": "1", "name": "Herbaciarnia", "platform": "woocommerce", "enabled": True,
                               "internal": False, "currency": "PLN"}], "links": {"next": None}}
            elif s == "/ecommerce/shops/1/reports/stats":
                d = stat
            elif s == "/ecommerce/settings":
                d = {"data": {"ecommerce_tracking_in_campaigns": True, "ecommerce_attribution_window": 7}}
            elif s in ("/groups", "/automations", "/campaigns") or s.startswith("/forms/"):
                d = {"data": [], "links": {"next": None}}
            else:
                raise AssertionError("skrypt poprosił o ścieżkę spoza listy: " + s)
            return Odpowiedz(d)
        return f

    def uruchom(self, stat, *arg):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("tempfile.gettempdir", return_value=tmp), \
                mock.patch.object(M._OTWIERACZ, "open", side_effect=self.odpowiedz(stat)), mock.patch("time.sleep"), \
                mock.patch.dict(os.environ, {"MAILERLITE_API_KEY": "falszywy-klucz"}):
            md, js = os.path.join(tmp, "r.md"), os.path.join(tmp, "r.json")
            out = io.StringIO()
            with mock.patch.object(sys, "argv", ["x", "--raport", md, "--json", js, "--bez-pamieci", *arg]), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                M.main()
            with open(md, encoding="utf-8") as p1, open(js, encoding="utf-8") as p2:
                return p1.read(), p2.read() + out.getvalue()

    def test_liczby_sklepu_w_raporcie(self):
        md, reszta = self.uruchom(statystyki())
        self.assertIn("Zamówienia przesłane do MailerLite", md)
        self.assertIn("**4**, przychód: **40 PLN**", md)
        self.assertIn("**3** zamówienia na 32,50 PLN", md)
        self.assertIn("z kampanii 1 (12,50 PLN), z automatów 2 (20 PLN)", md)
        self.assertIn("do 7 dni po kliknięciu", md)
        self.assertNotIn("Napraw przesyłanie zamówień", md)
        for zle in ZAKAZANE:
            self.assertNotIn(zle, md + reszta, zle)
        sciezka, q = [z for z in self.zapytania if z[0].endswith("/reports/stats")][0]
        self.assertEqual(set(q), {"start_date", "end_date"})

    def test_zero_zamowien_przy_podlaczonym_sklepie(self):
        md, _ = self.uruchom(statystyki(zamowienia=0, przychod=0, srednia=0, seria=[]))
        self.assertIn("jest podłączony, ale MailerLite nie ma z niego żadnego zamówienia", md)
        self.assertIn("Napraw przesyłanie zamówień ze sklepu", md)

    def test_okres_zgodny_z_audytem_i_limit_365(self):
        import datetime as dt
        dzis = dt.date.today()
        self.uruchom(statystyki())
        q = [z for z in self.zapytania if z[0].endswith("/reports/stats")][0][1]
        self.assertEqual(q["start_date"], [(dzis - dt.timedelta(days=30)).isoformat()])
        self.assertEqual(q["end_date"], [dzis.isoformat()])
        self.zapytania = []
        md, _ = self.uruchom(statystyki(), "--dni", "500")
        q = [z for z in self.zapytania if z[0].endswith("/reports/stats")][0][1]
        self.assertEqual(q["start_date"], [(dzis - dt.timedelta(days=365)).isoformat()])
        self.assertIn("najwyżej za 365 dni", md)

    def test_brak_raportu_to_nieznane_a_nie_zero(self):
        md, _ = self.uruchom({"data": None})
        self.assertIn("API go nie podało", md)
        self.assertNotIn("Napraw przesyłanie zamówień", md)

    def test_kod_nie_czyta_zamowien(self):
        kod = open(os.path.join(ML_DIR, "audyt_mailerlite.py"), encoding="utf-8").read()
        self.assertNotIn('/orders"', kod)
        self.assertNotIn("/orders?", kod)


class Pokaz(unittest.TestCase):
    def test_pokaz_ma_liczby_sklepu(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "r.md")
            env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
            w = subprocess.run([sys.executable, os.path.join(ML_DIR, "audyt_mailerlite.py"), "--pokaz", "--raport", md],
                               capture_output=True, text=True, env=env, cwd=d, timeout=60)
            self.assertEqual(w.returncode, 0, w.stderr)
            with open(md, encoding="utf-8") as p:
                t = p.read()
        self.assertIn("**148**, przychód: **18 640 PLN**", t)
        self.assertIn("z kampanii 21", t)


if __name__ == "__main__":
    unittest.main()
