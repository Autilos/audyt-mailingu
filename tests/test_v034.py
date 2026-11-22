"""Testy v0.3.4: prywatność „nawet przypadkiem”.

Udajemy API, które do każdej odpowiedzi dokleja dane osobowe (FIKCYJNE: kupująca, telefon, IP, adres nadawcy,
dane dostępowe sklepu, całe zamówienie MailerLite z danymi kupującego w formacie z dokumentacji).
Sprawdzamy, że nic z tego nie trafia do: raportu .md, pliku JSON, pliku postępu, ekranu (stdout/stderr),
pamięci odpowiedzi na dysku ani komunikatów o błędach. Żadnych prawdziwych kluczy — tylko „falszywy-klucz”.
"""
import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest import mock

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR_DIR = os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts")
ML_DIR = os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts")
sys.path.insert(0, GR_DIR)
sys.path.insert(0, ML_DIR)
import audyt_mailerlite as M  # noqa: E402
import audyt_getresponse as G  # noqa: E402
import wspolne  # noqa: E402

# Fikcyjne dane osobowe — żadna z tych wartości nie może wyjść poza skrypt.
EMAIL = "zofia.kupujaca@przyklad-kupujacy.example"
IMIE, NAZWISKO = "Zofiaqq", "Kupujacaqq"
TELEFON = "+48 601 234 567"
IP = "192.0.2.44"
SEKRET_SKLEPU = "ck_sekret_woocommerce_qq"
NADAWCA = "jan.wlasciciel@herbaciarnia.example"
ZAKAZANE = [EMAIL, IMIE, NAZWISKO, "601 234 567", "601234567", IP, SEKRET_SKLEPU, "jan.wlasciciel", "falszywy-klucz"]

KLIENT = {"id": "319868430643456756", "email": EMAIL, "accepts_marketing": True, "total_spent": 123.4,
          "subscriber": {"id": "1", "email": EMAIL, "ip_address": IP, "optin_ip": IP,
                         "fields": {"name": IMIE, "last_name": NAZWISKO, "phone": TELEFON, "city": "Krakówqq"}}}
# Zamówienie MailerLite w kształcie z dokumentacji (developers.mailerlite.com/ecommerce/orders), dane fikcyjne.
ZAMOWIENIE_ML = {"id": "31986843064993537", "customer": KLIENT, "total": 123.4, "status": "complete",
                 "attribution": {"email_id": "31986843064993540", "type": "campaign"},
                 "created_at": "2026-11-01 14:03:50", "completed_at": "2026-11-01 14:03:50"}
DOKLEJKA = {"customer": KLIENT, "order": ZAMOWIENIE_ML, "from": NADAWCA, "reply_to": NADAWCA,
            "access_data": SEKRET_SKLEPU, "subscriber": KLIENT["subscriber"], "ip_address": IP}


def doklej(x):
    """Dokleja dane osobowe do każdego słownika w odpowiedzi (też zagnieżdżonego)."""
    if isinstance(x, dict):
        return dict({k: doklej(v) for k, v in x.items()}, **DOKLEJKA)
    if isinstance(x, list):
        return [doklej(v) for v in x]
    return x


class Odpowiedz(io.BytesIO):
    def __init__(self, dane, naglowki=None):
        super().__init__(json.dumps(dane).encode())
        self.headers = naglowki or {}


def bez_sieci(*a, **k):
    raise AssertionError("próba połączenia z siecią")


class Wspolne(unittest.TestCase):
    def test_przytnij_zostawia_tylko_wzor(self):
        sklep = doklej({"name": "Sklep", "platform": "woocommerce", "enabled": True, "group": {"name": "g"}})
        wynik = wspolne.przytnij(sklep, {"name": True, "platform": True, "enabled": True})
        self.assertEqual(wynik, {"name": "Sklep", "platform": "woocommerce", "enabled": True})

    def test_true_nie_przepuszcza_slownika(self):
        self.assertEqual(wspolne.przytnij({"name": {"email": EMAIL}}, {"name": True}), {})

    def test_sciezka_bez_wzoru_nic_nie_zwraca(self):
        self.assertIsNone(M.przytnij_odpowiedz(M.API + "/ecommerce/shops/1/orders", {"data": [ZAMOWIENIE_ML]}))
        self.assertIsNone(G.przytnij_odpowiedz("/contacts", [KLIENT]))

    def test_maskowanie(self):
        t = wspolne.maskuj(f"Lista {EMAIL}, tel. {TELEFON} i 601234567; Szkic 2026-03-02 10:15:00; 1 240 zł; WITAJ10")
        self.assertNotIn(EMAIL, t)
        self.assertNotIn("601", t)
        self.assertIn("2026-03-02 10:15:00", t)
        self.assertIn("1 240 zł", t)
        self.assertIn("WITAJ10", t)


class MailerLiteSzczelnosc(unittest.TestCase):
    def odpowiedz_ml(self, req, timeout=None):
        u = urllib.parse.urlsplit(req.full_url)
        s = u.path[len("/api"):]
        if s == "/groups":
            d = {"data": [{"name": f"Klienci {EMAIL} {TELEFON}", "active_count": 120, "unsubscribed_count": 3}]}
        elif s == "/ecommerce/settings":
            d = {"data": {"ecommerce_tracking_in_campaigns": True, "ecommerce_tracking_in_automations": True,
                          "ecommerce_attribution_window": 5}}
        elif s == "/ecommerce/shops":
            d = {"data": [{"id": "1", "name": "Herbaciarnia", "platform": "woocommerce", "enabled": True,
                           "internal": False, "currency": "PLN", "orders": [ZAMOWIENIE_ML]}]}
        elif s == "/automations":
            d = {"data": [{"name": "Powitanie", "enabled": True, "complete": True, "created_at": "2025-01-01 10:00:00",
                           "triggers": [{"type": "subscriber_joins_group", "groups": [{"name": IMIE}]}],
                           "trigger_data": {"track_ecommerce": True},
                           "stats": {"completed_subscribers_count": 10, "sent": 300, "click_rate": {"float": 0.05}},
                           "steps": [{"id": "e1", "type": "email", "subject": "Witaj",
                                      "email": {"subject": "Witaj", "from": NADAWCA, "reply_to": NADAWCA,
                                                "plain_text": "Kod WITAJ10 −10%. Kup teraz.",
                                                "stats": {"sent": 300, "click_rate": {"float": 0.05}}}}]}]}
        elif s == "/campaigns":
            d = {"data": [{"name": "Nowości", "finished_at": "2099-01-01 09:00:00", "from": NADAWCA,
                           "settings": {"ecommerce_tracking": True},
                           "emails": [{"subject": f"Zadzwoń {TELEFON}", "from": NADAWCA, "stats": {"sent": 500}}]}]}
        elif s.startswith("/forms/"):
            d = {"data": []}
        else:
            raise AssertionError("skrypt poprosił o ścieżkę spoza listy: " + s)
        d = doklej(d)
        d["links"] = {"next": None}
        return Odpowiedz(d)

    def test_wyjscie_bez_danych_osobowych(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("tempfile.gettempdir", return_value=tmp), \
                mock.patch.object(M._OTWIERACZ, "open", side_effect=self.odpowiedz_ml), mock.patch("time.sleep"), \
                mock.patch.dict(os.environ, {"MAILERLITE_API_KEY": "falszywy-klucz"}):
            raport, js = os.path.join(tmp, "audyt-ml.md"), os.path.join(tmp, "audyt-ml.json")
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(sys, "argv", ["x", "--raport", raport, "--json", js]), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                M.main()
            wszystko = out.getvalue() + err.getvalue()
            for r, _, pliki in os.walk(tmp):
                for p in pliki:
                    wszystko += open(os.path.join(r, p), encoding="utf-8").read()
            self.assertIn("Herbaciarnia", wszystko)
            self.assertIn("[e-mail ukryty]", wszystko)
            for zle in ZAKAZANE:
                self.assertNotIn(zle, wszystko, zle)
            # pole "email" w krokach automatu MailerLite to sam mail (temat, statystyki), nie adres — adresy sprawdza ZAKAZANE
            for pole in ('"phone"', '"last_name"', '"customer"', '"subscriber"', '"ip_address"', '"access_data"', '"reply_to"', '"from"'):
                self.assertNotIn(pole, wszystko, pole)

    def test_link_next_do_innego_hosta_przerywa(self):
        ml = M.ML("falszywy-klucz")
        with mock.patch.object(M._OTWIERACZ, "open", side_effect=bez_sieci), mock.patch("time.sleep"):
            for zly in ("https://connect.mailerlite.com.zly.example/api/groups", "https://zly.example/api/groups",
                        "http://connect.mailerlite.com/api/groups", "https://connect.mailerlite.com:8443/api/groups"):
                with self.assertRaises(SystemExit):
                    ml.get(zly)

    def test_blad_api_nie_pokazuje_tresci_odpowiedzi(self):
        ml = M.ML("falszywy-klucz")
        cialo = io.BytesIO(json.dumps({"message": "zle", "customer": KLIENT}).encode())
        blad = urllib.error.HTTPError(M.API + "/groups", 422, "Unprocessable", {}, cialo)
        with mock.patch.object(M._OTWIERACZ, "open", side_effect=blad), mock.patch("time.sleep"):
            with self.assertRaises(SystemExit) as e:
                ml.get("/groups")
        for zle in ZAKAZANE:
            self.assertNotIn(zle, str(e.exception.code))


class GetResponseSzczelnosc(unittest.TestCase):
    def odpowiedz_gr(self, req, timeout=None):
        s = urllib.parse.urlsplit(req.full_url).path[len("/v3"):]
        h = {"TotalPages": "1"}
        if s == "/campaigns":
            d = [{"campaignId": "L1", "name": f"Lista {EMAIL}"}]
        elif s.startswith("/campaigns/statistics/"):
            d = [{"totalSubscribers": 100, "addedSubscribers": 5, "removedSubscribers": 1}]
        elif s == "/forms":
            d = []
        elif s == "/from-fields":
            d = [{"email": NADAWCA, "name": "Jan Właściciel", "isActive": "true", "isDefault": "true",
                  "domain": {"status": "confirmed", "hasDMARCWarning": "false"}}]
        elif s == "/workflow":
            d = [{"workflowId": "W1"}]
        elif s == "/workflow/W1":
            d = {"workflowId": "W1", "name": "Powitanie", "status": "active", "dateStart": "2025-01-01",
                 "subscriberStatistics": {"completedCount": 10, "inProgressCount": 1}}
        elif s == "/newsletters":
            d = [{"newsletterId": "N1", "name": "Witaj", "subject": f"Witaj, zadzwoń {TELEFON}", "status": "enabled",
                  "flags": ["ecommerce_tracking"], "createdOn": "2025-01-01", "sendOn": "2025-01-01T09:00:00+0000"}]
        elif s.endswith("/statistics"):
            d = [{"sent": 300, "uniqueHumanOpened": 100, "uniqueHumanClicked": 10}]
        elif s.startswith("/newsletters/"):
            d = {"subject": "Witaj", "content": {"html": "<p>Kod WITAJ10 −10%</p>"}}
        elif s == "/autoresponders":
            d = []
        elif s == "/shops":
            d = [{"shopId": "S1", "name": "Herbaciarnia", "currency": "PLN"}]
        elif s == "/shops/S1/orders":
            d = [{"orderId": "O1", "totalPrice": 100, "processedAt": "2099-01-01", "contactId": "C1", "status": "new"}]
        elif s.startswith("/statistics/ecommerce/"):
            d = {"order": {"orders": 1}, "revenue": {"revenue": 100}}
        else:
            raise AssertionError("skrypt poprosił o ścieżkę spoza listy: " + s)
        if not s.startswith("/campaigns/statistics/") and not s.endswith("/statistics") and not s.startswith("/statistics/"):
            d = doklej(d)
        return Odpowiedz(d, h)

    def test_wyjscie_bez_danych_osobowych(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch("tempfile.gettempdir", return_value=tmp), \
                mock.patch.object(G._OTWIERACZ, "open", side_effect=self.odpowiedz_gr), mock.patch("time.sleep"), \
                mock.patch.dict(os.environ, {"GETRESPONSE_API_KEY": "falszywy-klucz"}):
            raport, js = os.path.join(tmp, "audyt-gr.md"), os.path.join(tmp, "audyt-gr.json")
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.object(sys, "argv", ["x", "--raport", raport, "--json", js]), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                G.main()
            wszystko = out.getvalue() + err.getvalue()
            for r, _, pliki in os.walk(tmp):
                for p in pliki:
                    wszystko += open(os.path.join(r, p), encoding="utf-8").read()
            self.assertIn("herbaciarnia.example", wszystko, "domena nadawcy zostaje")
            for zle in ZAKAZANE + ["Jan Właściciel"]:
                self.assertNotIn(zle, wszystko, zle)
            for pole in ('"phone"', '"last_name"', '"customer"', '"ip_address"', '"access_data"', '"reply_to"'):
                self.assertNotIn(pole, wszystko, pole)

    def test_blad_api_bez_tracebacku_i_tresci(self):
        gr = G.GR("falszywy-klucz", "https://api.getresponse.com/v3")
        cialo = io.BytesIO(json.dumps({"message": "zle", "contact": KLIENT}).encode())
        blad = urllib.error.HTTPError("https://api.getresponse.com/v3/campaigns", 400, "Bad Request", {}, cialo)
        with mock.patch.object(G._OTWIERACZ, "open", side_effect=blad), mock.patch("time.sleep"):
            with self.assertRaises(SystemExit) as e:
                gr.get("/campaigns")
        self.assertIn("400", str(e.exception.code))
        for zle in ZAKAZANE:
            self.assertNotIn(zle, str(e.exception.code))


class PokazBezSieciIKlucza(unittest.TestCase):
    def test_pokaz_nie_dotyka_sieci(self):
        for modul in (M, G):
            with tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(socket, "socket", side_effect=bez_sieci), \
                    mock.patch.object(socket, "create_connection", side_effect=bez_sieci), \
                    mock.patch.object(modul._OTWIERACZ, "open", side_effect=bez_sieci), \
                    mock.patch.object(modul, "klucz_z_env_albo_pliku", side_effect=AssertionError("pokaz czyta klucz")), \
                    mock.patch("sys.stderr", io.StringIO()):
                raport = os.path.join(tmp, "audyt-pokaz.md")
                with mock.patch.object(sys, "argv", ["x", "--pokaz", "--raport", raport]):
                    modul.main()
                self.assertIn("Raport pokazowy", open(raport, encoding="utf-8").read())


class PdfIInstrukcje(unittest.TestCase):
    def test_pdf_blokuje_zasoby_z_sieci(self):
        sys.path.insert(0, ML_DIR)
        import raport_pdf
        h = raport_pdf.dokument("# T\n\n![x](https://zly.example/piksel.png?e=" + EMAIL + ")\n\n<img src='https://zly.example/a.png'>")
        self.assertIn("Content-Security-Policy", h)
        self.assertIn("default-src 'none'", h)
        self.assertNotIn("<img", h)

    def test_skille_maja_zasady_dla_claude(self):
        for sk in ("audyt-getresponse", "audyt-mailerlite", "audyt-pomoc"):
            t = open(os.path.join(KORZEN, "skills", sk, "SKILL.md"), encoding="utf-8").read()
            self.assertIn("Zasady dla Claude — prywatność i klucz", t, sk)
            for zakaz in ("printenv", "curl", "subskrybent", "kupując"):
                self.assertIn(zakaz, t, f"{sk}: {zakaz}")

    def test_gitignore_chroni_wyniki_i_klucze(self):
        t = open(os.path.join(KORZEN, ".gitignore"), encoding="utf-8").read()
        for wzor in ("audyt*.md", "audyt*.json", "audyt*.pdf", "audyt*.html", "*.postep.txt", "*.key"):
            self.assertIn(wzor, t)


if __name__ == "__main__":
    unittest.main()
