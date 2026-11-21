"""Testy v0.3 na fikcyjnych odpowiedziach API: lista dozwolonych ścieżek (zero danych osobowych),
formularze, zdrowie bazy, adres nadawcy, przychód, PDF, drzewo kroków MailerLite."""
import os
import sys
import tempfile
import unittest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts"))
import audyt_getresponse as G  # noqa: E402
import raport_pdf  # noqa: E402

sys.path.insert(0, os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts"))
import audyt_mailerlite as M  # noqa: E402


class FakeGR:
    """Udaje klienta GR: zwraca przygotowane odpowiedzi, sprawdza listę dozwolonych ścieżek."""
    def __init__(self, odp):
        self.odp, self.niedostepne, self.ostrzezenia, self.zapytan = odp, [], [], 0

    def get(self, sciezka, params=None, opcjonalny=False):
        assert G.sciezka_dozwolona(sciezka, params), sciezka
        if self.odp.get(sciezka) == 403:
            self.niedostepne.append(sciezka + " (brak uprawnień klucza)")
            return None, {"_403": True}
        return self.odp.get(sciezka), {}

    def wszystkie(self, sciezka, params=None, opcjonalny=False, **_):
        d, _ = self.get(sciezka, params, opcjonalny)
        return d or []


class ZeroDanychOsobowych(unittest.TestCase):
    def test_gr_blokuje_kontakty_i_koszyki(self):
        for zla in ("/contacts", "/contacts/abc", "/shops/x/carts", "/accounts", "/accounts/login-history", "/subscribers"):
            self.assertFalse(G.sciezka_dozwolona(zla), zla)

    def test_gr_zamowienia_tylko_z_bezpiecznymi_polami(self):
        self.assertTrue(G.sciezka_dozwolona("/shops/AB1/orders", {"fields": "orderId,totalPrice,processedAt,contactId,status"}))
        self.assertFalse(G.sciezka_dozwolona("/shops/AB1/orders", {"fields": "orderId,billingAddress"}))
        self.assertFalse(G.sciezka_dozwolona("/shops/AB1/orders", {}))

    def test_gr_get_przerywa_na_niedozwolonej(self):
        gr = G.GR("x", "https://api.getresponse.com/v3")
        with self.assertRaises(SystemExit):
            gr.get("/contacts", {"perPage": 1})

    def test_ml_blokuje_subskrybentow_zamowienia_konto(self):
        for zla in ("/subscribers", "/subscribers/1", "/ecommerce/shops/1/orders", "/account", "/ecommerce/shops/1/customers"):
            self.assertFalse(M.sciezka_dozwolona(M.API + zla), zla)
        self.assertTrue(M.sciezka_dozwolona(M.API + "/automations?limit=100"))
        self.assertTrue(M.sciezka_dozwolona(M.API + "/forms/popup"))

    def test_kod_nie_wola_zakazanych_sciezek(self):
        for plik in ("skills/audyt-getresponse/scripts/audyt_getresponse.py", "skills/audyt-mailerlite/scripts/audyt_mailerlite.py"):
            kod = open(os.path.join(KORZEN, plik), encoding="utf-8").read()
            for zla in ('"/contacts"', "/subscribers\"", "/orders\")", '"/account"'):
                self.assertNotIn(zla, kod, f"{plik}: {zla}")


class Formularze(unittest.TestCase):
    def test_konwersja_i_uwagi(self):
        gr = FakeGR({"/forms": [
            {"name": "Stopka", "status": "enabled", "visitors": 5000, "subscribed": 20, "subscriptionRate": 0.4},
            {"name": "Pop-up", "status": "enabled", "visitors": 0, "subscribed": 0, "subscriptionRate": 0},
            {"name": "Dobry", "status": "enabled", "visitors": 1000, "subscribed": 50, "subscriptionRate": 5},
        ]})
        w = {x["nazwa"]: x for x in G.formularze(gr)}
        self.assertIn("niska konwersja", " ".join(w["Stopka"]["uwagi"]))
        self.assertIn("bez odwiedzin", " ".join(w["Pop-up"]["uwagi"]))
        self.assertEqual(w["Dobry"]["uwagi"], [])

    def test_brak_uprawnien(self):
        self.assertIsNone(G.formularze(FakeGR({"/forms": 403})))


class ZdrowieBazy(unittest.TestCase):
    def test_sumy(self):
        import datetime as dt
        gr = FakeGR({
            "/campaigns/statistics/list-size": [{"totalSubscribers": 900, "addedSubscribers": 120, "removedSubscribers": 30, "createdOn": "total"}],
            "/campaigns/statistics/subscriptions": {"A": {"total": {"www": 70, "api": 50, "import": 0, "summary": 120}}},
            "/campaigns/statistics/removals": {"A": {"total": {"unsubscribe": 25, "bounce": 5}}, "B": {"total": {"unsubscribe": 0}}},
        })
        z = G.zdrowie_bazy(gr, ["A", "B"], dt.date(2026, 1, 1), dt.date(2026, 2, 1))
        self.assertEqual((z["dodani"], z["usunieci"]), (120, 30))
        self.assertEqual(z["zrodla"], {"www": 70, "api": 50})
        self.assertEqual(z["powody_usuniec"], {"unsubscribe": 25, "bounce": 5})


class Nadawcy(unittest.TestCase):
    def test_alarmy(self):
        gr = FakeGR({"/from-fields": [
            {"email": "sklep@dobra.pl", "isActive": "true", "isDefault": "true", "domain": {"status": "confirmed", "DKIMWarning": None, "hasDMARCWarning": "false"}},
            {"email": "info@zla.pl", "isActive": "true", "isDefault": "false", "domain": {"status": "unconfirmed", "DKIMWarning": "not_authenticated", "hasDMARCWarning": "true"}},
            {"email": "x@stara.pl", "isActive": "false", "isDefault": "false", "domain": {"status": "unconfirmed", "DKIMWarning": "at_risk"}},
        ]})
        w = {x["domena"]: x for x in G.nadawcy(gr)}
        self.assertEqual(w["dobra.pl"]["uwagi"], [])
        self.assertEqual(len(w["zla.pl"]["uwagi"]), 3)
        self.assertEqual(w["stara.pl"]["uwagi"], [], "nieaktywny adres nie daje alarmu")
        self.assertNotIn("email", w["zla.pl"], "adres nadawcy nie jest zapisywany, tylko domena")


class Przychod(unittest.TestCase):
    def test_suma_szeregu_i_porownanie(self):
        D = {"sklep_podany": {"zamowienia": 1000, "przychod": None},
             "sklepy": [{"nazwa": "S", "zamowienia": 400, "bez_kontaktu_proc": 0}],
             "lista_kontrolna": [], "automaty": [], "maile_automatow": [], "newslettery": [], "okno_dni": 30}
        self.assertIn("przychod_rozjazd", G.klucze_problemow(D))
        D["sklepy"][0]["zamowienia"] = 980
        self.assertNotIn("przychod_rozjazd", G.klucze_problemow(D))
        self.assertEqual(G.suma_pola([{"revenue": 10.5}, {"revenue": 4}], "revenue"), 14.5)


class DrzewoKrokowML(unittest.TestCase):
    def test_kolejnosc_po_rodzicu_nie_po_liscie(self):
        kroki = [{"id": "e3", "type": "email", "parent_id": "d2"},
                 {"id": "d2", "type": "delay", "parent_id": "e2", "value": 3, "unit": "days"},
                 {"id": "e1", "type": "email", "parent_id": None},
                 {"id": "d1", "type": "delay", "parent_id": "e1", "value": 2, "unit": "days"},
                 {"id": "e2", "type": "email", "parent_id": "d1"}]
        d = M.dni_krokow(kroki)
        self.assertEqual((d["e1"], d["e2"], d["e3"]), (0, 2, 5))

    def test_po_warunku_nieznany(self):
        kroki = [{"id": "c", "type": "condition", "parent_id": None}, {"id": "e", "type": "email", "parent_id": "c"}]
        self.assertIsNone(M.dni_krokow(kroki)["e"])


class PDF(unittest.TestCase):
    def test_html_z_tabela_naglowkiem_i_stopka(self):
        h = raport_pdf.dokument("# Audyt X\n\n## Najważniejsze\n\n1. **Raz** ok\n2. Dwa\n\n| A | B |\n|---|---|\n| 1 | <b>2</b> |\n")
        self.assertIn("<table>", h)
        self.assertIn("<ol>", h)
        self.assertIn("marketingkrokpokroku.pl/audyt-mailingu", h)
        self.assertIn("&lt;b&gt;", h, "HTML z treści raportu musi być escapowany")
        self.assertIn("#2e070b", h)

    def test_bez_przegladarki_zostaje_html(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "r.md")
            open(md, "w").write("# T\n\ntekst\n")
            stara = raport_pdf.przegladarka
            raport_pdf.przegladarka = lambda: None
            sys.argv = ["x", md]
            try:
                raport_pdf.main()
            finally:
                raport_pdf.przegladarka = stara
            self.assertTrue(os.path.exists(os.path.join(d, "r.html")))


if __name__ == "__main__":
    unittest.main()
