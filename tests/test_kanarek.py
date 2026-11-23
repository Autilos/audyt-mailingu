"""Test „kanarek” — dowód, że adresy e-mail, telefony i numery IP kontaktów oraz kupujących nie wychodzą poza skrypt.

Uruchom sam (bez klucza, bez internetu, bez Claude):

    python3 tests/test_kanarek.py -v

Jak to działa:
- Udajemy API GetResponse i MailerLite dla KAŻDEJ ścieżki z listy dozwolonych (DOZWOLONE_SCIEZKI). Prawdziwej sieci
  nie ma: każde połączenie poza atrapą kończy test błędem.
- W KAŻDE pole tekstowe każdej odpowiedzi (także nieużywane) dopisujemy „kanarka”: unikalne, zmyślone dane osobowe
  z numerem pola, np. „Jan Kanarek17, ul. Kanarkowa 17, kanarek-17@example.com, tel. +48 600 000 017, IP 203.0.113.17”.
  Do każdego obiektu doklejamy też dodatkowe pola, jakie mogłyby się kiedyś pojawić w API: e-mail, imię, nazwisko,
  telefon, adres, IP, cały „subscriber” i „customer”. Adresy i telefony mają różne zapisy (z +48, z kreskami, ciągiem,
  zakodowane w adresie WWW jako %40, w HTML jako &#64;, pełnej szerokości „＠”), numery IP — IPv4 i IPv6.
- Uruchamiamy pełny audyt obu systemów (dwa przebiegi: kanarek we wszystkich polach i kanarek tylko w polach opisowych,
  żeby przeszły też gałęzie kodu zależne od statusów) i robimy PDF.
- Sprawdzamy, że ŻADEN kanarek e-mail, telefon ani IP nie występuje w: wyjściu na ekran (stdout, stderr), raporcie .md,
  pliku JSON, HTML i PDF, pliku postępu, pamięci odpowiedzi na dysku ani w adresach wysłanych zapytań; i że klucz API
  nie trafia nigdzie poza nagłówek zapytania do oficjalnego adresu API.
- Imię i nazwisko: tekstu „Jan Kowalski” nie da się odróżnić od nazwy produktu, więc może przejść tam, gdzie
  właściciel konta sam je wpisał — w nazwie listy, automatu, formularza, sklepu, w temacie maila. Test wypisuje,
  w których polach kanarek-nazwisko przeszedł, i pilnuje, żeby były to WYŁĄCZNIE te pola (znana, opisana granica).
"""
import contextlib
import datetime as dt
import io
import json
import os
import re
import shutil
import socket
import subprocess
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
import audyt_getresponse as G  # noqa: E402
import audyt_mailerlite as M  # noqa: E402
import raport_pdf  # noqa: E402

KLUCZ = "klucz-kanarek-SEKRET-0000"
DZIS = dt.date.today()
WCZORAJ = (DZIS - dt.timedelta(days=1)).isoformat()


# --- Kanarki ---------------------------------------------------------------------------------------------------

def _email(n):
    wzory = ["kanarek-{n}@example.com", "Kanarek.{n}+tag@Example.COM", "kanarek_{n}@sub.example.co.uk",
             "kanarek-{n}%40example.com", "kanarek-{n}&#64;example.pl", "kanarek-{n}＠example.com",
             "<kanarek-{n}@przykład.pl>"]
    return wzory[n % len(wzory)].format(n=n)


def _telefon(n):
    c = f"{n:03d}"
    wzory = [f"+48 600 000 {c}", f"600-000-{c}", f"600000{c}", f"+48600000{c}", f"(+48) 600 000 {c}",
             f"0048 600 000 {c}", f"600.000.{c}", f"12 {c} 67 89"]
    return wzory[n % len(wzory)]


def _ip(n):
    if n % 3 == 0:
        return f"2001:db8::{n:x}"
    return f"203.{n // 250}.113.{n % 250 + 1}"


class Kanarki:
    """Numeruje kanarki: każdy numer = jedno pole jednej odpowiedzi API (system, ścieżka, pole)."""

    def __init__(self):
        self.pola = {}

    def nowy(self, system, sciezka, pole):
        n = len(self.pola) + 1
        self.pola[n] = (system, sciezka, re.sub(r"\[\d+\]", "[]", pole))
        return n

    @staticmethod
    def tekst(n):
        return f"Jan Kanarek{n}, ul. Kanarkowa {n}, {_email(n)}, tel. {_telefon(n)}, IP {_ip(n)}"

    @staticmethod
    def wycieki_kontaktu(n, tekst):
        """Co z kanarka n (e-mail, telefon, IP) widać w tekście."""
        znalezione = []
        if re.search(rf"kanarek[-._]{n}(?!\d)", tekst, re.IGNORECASE):
            znalezione.append("e-mail")
        tel = _telefon(n)
        cyfry = re.sub(r"\D", "", tel)
        if re.search(r"(?<![\w])" + re.escape(tel) + r"(?!\d)", tekst) or re.search(r"(?<!\d)" + cyfry + r"(?!\d)", tekst):
            znalezione.append("telefon")
        if re.search(rf"(?<![\w.:]){re.escape(_ip(n))}(?![\w:]|\.\d)", tekst, re.IGNORECASE):
            znalezione.append("IP")
        return znalezione

    @staticmethod
    def nazwisko(n, tekst):
        return bool(re.search(rf"Kanarek{n}(?!\d)|Kanarkowa {n}(?!\d)", tekst))

    @staticmethod
    def kandydaci_kontaktu(tekst):
        """Szybki przesiew: numery kanarków, których e-mail, telefon albo IP MOŻE być w tekście (potem dokładne sprawdzenie)."""
        n = {int(x) for x in re.findall(r"kanarek[-._](\d+)", tekst, re.IGNORECASE)}
        n |= {int(a) * 250 + int(b) - 1 for a, b in re.findall(r"203\.(\d+)\.113\.(\d+)", tekst)}
        n |= {int(x, 16) for x in re.findall(r"2001:db8::([0-9a-f]+)", tekst, re.IGNORECASE)}
        bez_odstepow = re.sub(r"[\s().-]", "", tekst)
        n |= {int(x) for x in re.findall(r"600000(\d{3,4})", bez_odstepow)}
        n |= {int(x) for x in re.findall(r"12(\d{3,4})6789", bez_odstepow)}
        return n

    @staticmethod
    def kandydaci_nazwiska(tekst):
        return {int(a or b) for a, b in re.findall(r"Kanarek(\d+)|Kanarkowa (\d+)", tekst)}


def dodatkowe_pola(K, system, sciezka, pole):
    """Pola, których audyt nie potrzebuje, a które API mogłoby kiedyś dołożyć do dowolnego obiektu."""
    def n(nazwa):
        return K.nowy(system, sciezka, f"{pole}.{nazwa}+" if pole else f"{nazwa}+")
    osoba = lambda m: {"email": _email(m), "first_name": "Jan", "last_name": f"Kanarek{m}", "name": f"Jan Kanarek{m}",
                       "phone": _telefon(m), "ip_address": _ip(m), "optin_ip": _ip(m),
                       "address": {"street": f"ul. Kanarkowa {m}", "city": "Kanarkowo", "zip": "00-001"},
                       "fields": {"name": "Jan", "last_name": f"Kanarek{m}", "phone": _telefon(m)}}
    return {
        "email": _email(n("email")), "phone": _telefon(n("phone")), "ip_address": _ip(n("ip_address")),
        "first_name": "Jan", "last_name": f"Kanarek{n('last_name')}",
        "address": f"ul. Kanarkowa {n('address')}, 00-001 Kanarkowo",
        "reply_to": _email(n("reply_to")), "from": {"email": _email(n("from.email")), "name": f"Jan Kanarek{n('from.name')}"},
        "subscriber": osoba(n("subscriber")), "customer": osoba(n("customer")),
        "notatki": [Kanarki.tekst(n("notatki[]")), Kanarki.tekst(n("notatki[]"))],
        "pole_z_przyszlosci": Kanarki.tekst(n("pole_z_przyszlosci")),
    }


# Pola, w których kanarka NIE dopisujemy: identyfikatory (trafiają do ścieżki zapytania) i link do kolejnej strony.
ID = {"campaignId", "workflowId", "newsletterId", "autoresponderId", "shopId", "formId", "fromFieldId", "orderId",
      "contactId", "id", "parent_id", "next"}
# W przebiegu „opisowym” zostają też nietknięte statusy, typy i daty, żeby przeszły wszystkie gałęzie kodu.
STRUKTURA = ID | {"status", "type", "unit", "platform", "currency", "isActive", "isDefault", "createdOn", "sendOn",
                  "dateStart", "created_at", "finished_at", "started_at", "scheduled_for", "processedAt", "flags",
                  "DKIMWarning", "hasDMARCWarning", "float", "string"}


def zatruj(x, K, system, sciezka, nie_ruszaj, pole=""):
    if isinstance(x, dict):
        wynik = {}
        for k, v in x.items():
            p = f"{pole}.{k}" if pole else k
            wynik[k] = v if k in nie_ruszaj else zatruj(v, K, system, sciezka, nie_ruszaj, p)
        for k, v in dodatkowe_pola(K, system, sciezka, pole).items():
            wynik.setdefault(k, v)  # dokładamy tylko pola, których obiekt nie ma — prawdziwych nie nadpisujemy
        return wynik
    if isinstance(x, list):
        return [zatruj(v, K, system, sciezka, nie_ruszaj, f"{pole}[]") for v in x]
    if isinstance(x, str):
        return x + " " + Kanarki.tekst(K.nowy(system, sciezka, pole))
    return x


# --- Atrapy API: czyste odpowiedzi w kształcie z dokumentacji, dla każdej dozwolonej ścieżki ----------------------

def _stat_gr(sent):
    return [{"sent": sent, "uniqueHumanOpened": sent // 3, "uniqueHumanClicked": sent // 30, "unsubscribed": 1,
             "complaints": 0, "bounced": 2, "timeInterval": f"{WCZORAJ}/{DZIS.isoformat()}"}]


GR_ODPOWIEDZI = [
    (r"^/campaigns$", "/campaigns", lambda q: [{"campaignId": "L1", "name": "Klienci sklepu"},
                                                {"campaignId": "L2", "name": "Newsletter"}]),
    (r"^/campaigns/statistics/list-size$", "/campaigns/statistics/list-size",
     lambda q: {"L1": [{"totalSubscribers": 1200, "addedSubscribers": 40, "removedSubscribers": 5, "createdOn": WCZORAJ}]}),
    (r"^/campaigns/statistics/subscriptions$", "/campaigns/statistics/subscriptions",
     lambda q: {"L1": [{"createdOn": WCZORAJ, "import": 3, "api": 20, "forms": 17, "summary": 40}]}),
    (r"^/campaigns/statistics/removals$", "/campaigns/statistics/removals",
     lambda q: {"L1": [{"createdOn": WCZORAJ, "unsubscribe": 4, "bounce": 1, "summary": 5}]}),
    (r"^/forms$", "/forms", lambda q: [{"formId": "F1", "name": "Formularz w stopce", "status": "enabled", "visitors": 900,
                                         "uniqueVisitors": 800, "subscribed": 4, "subscriptionRate": 0.4, "createdOn": "2025-01-01"}]),
    (r"^/from-fields$", "/from-fields", lambda q: [{"fromFieldId": "FF1", "email": "sklep@herbaciarnia.example",
                                                     "name": "Herbaciarnia", "isActive": "true", "isDefault": "true",
                                                     "domain": {"status": "confirmed", "DKIMWarning": "", "hasDMARCWarning": "false"}}]),
    (r"^/workflow$", "/workflow", lambda q: [{"workflowId": "W1", "name": "Powitanie nowych", "status": "active",
                                               "dateStart": "2025-01-01T10:00:00+0000",
                                               "subscriberStatistics": {"completedCount": 10, "inProgressCount": 2}},
                                              {"workflowId": "W2", "name": "Porzucony koszyk", "status": "active",
                                               "dateStart": "2025-01-01T10:00:00+0000",
                                               "subscriberStatistics": {"completedCount": 0, "inProgressCount": 0}}]),
    (r"^/workflow/[A-Za-z0-9]+$", "/workflow/{id}", lambda q: {"workflowId": "W1", "name": "Powitanie nowych", "status": "active",
                                                                "dateStart": "2025-01-01T10:00:00+0000",
                                                                "subscriberStatistics": {"completedCount": 10, "inProgressCount": 2}}),
    (r"^/newsletters$", "/newsletters", lambda q: (
        [{"newsletterId": "NA1", "name": "Powitanie mail 1", "subject": "Witaj w sklepie", "status": "enabled",
          "flags": ["ecommerce_tracking"], "createdOn": "2025-01-01T10:00:00+0000"}]
        if q.get("query[type]") == "automation" else
        [{"newsletterId": "NB1", "name": "Nowości", "subject": "Nowe herbaty", "status": "sent",
          "flags": ["ecommerce_tracking"], "sendOn": WCZORAJ + "T10:00:00+0000"}])),
    (r"^/newsletters/[A-Za-z0-9]+/statistics$", "/newsletters/{id}/statistics", lambda q: _stat_gr(600)),
    (r"^/newsletters/[A-Za-z0-9]+$", "/newsletters/{id}", lambda q: {
        "subject": "Witaj w sklepie", "content": {"html": "<p>Dzień dobry [[firstname]]! Kod WITAJ10 −10%. Kup teraz.</p>",
                                                  "plain": "Dzień dobry! Kod WITAJ10 −10%. Kup teraz."}}),
    (r"^/autoresponders$", "/autoresponders", lambda q: [{"autoresponderId": "AR1", "name": "Dzień 0", "subject": "Dziękujemy za zapis",
                                                          "status": "enabled", "createdOn": "2025-01-01T10:00:00+0000",
                                                          "flags": ["ecommerce_tracking"], "campaignId": "L1",
                                                          "campaign": {"campaignId": "L1", "name": "Klienci sklepu"},
                                                          "triggerSettings": {"dayOfCycle": 0, "subscribedCampaign": {"campaignId": "L1"}}}]),
    (r"^/autoresponders/[A-Za-z0-9]+/statistics$", "/autoresponders/{id}/statistics", lambda q: _stat_gr(400)),
    (r"^/autoresponders/[A-Za-z0-9]+$", "/autoresponders/{id}", lambda q: {
        "subject": "Dziękujemy za zapis", "content": {"html": "<p>Poradnik parzenia herbaty: temperatura i czas.</p>", "plain": ""}}),
    (r"^/shops$", "/shops", lambda q: [{"shopId": "S1", "name": "Herbaciarnia", "currency": "PLN"}]),
    (r"^/shops/[A-Za-z0-9]+/orders$", "/shops/{id}/orders", lambda q: [
        {"orderId": "O1", "totalPrice": "120.50", "processedAt": WCZORAJ + "T12:00:00+0000", "contactId": "C1", "status": "complete",
         "billingAddress": {"firstName": "Jan", "lastName": "Kanarek", "phone": "+48 600 000 999", "address1": "ul. Kanarkowa 1"}},
        {"orderId": "O2", "totalPrice": "80.00", "processedAt": WCZORAJ + "T13:00:00+0000", "contactId": "", "status": "complete"}]),
    (r"^/statistics/ecommerce/performance$", "/statistics/ecommerce/performance",
     lambda q: {"order": {"orders": 2}, "revenue": {"revenue": 200.5}}),
    (r"^/statistics/ecommerce/revenue$", "/statistics/ecommerce/revenue",
     lambda q: {"timeSeries": [{"date": WCZORAJ, "revenue": 200.5, "orders": 2}]}),
]


def _stawka(x):
    return {"float": x, "string": f"{x * 100:.1f}%"}


def _staty_ml(sent):
    return {"sent": sent, "open_rate": _stawka(0.4), "click_rate": _stawka(0.05), "unsubscribe_rate": _stawka(0.003),
            "spam_rate": _stawka(0.0), "hard_bounce_rate": _stawka(0.002)}


ML_ODPOWIEDZI = [
    (r"^/groups$", "/groups", lambda q: {"data": [{"id": "1", "name": "Klienci", "active_count": 1200, "unsubscribed_count": 30,
                                                    "bounced_count": 5, "junk_count": 1, "unconfirmed_count": 3}],
                                         "links": {"next": None}}),
    (r"^/forms/(popup|embedded|promotion)$", "/forms/{typ}", lambda q: {
        "data": [{"id": "2", "name": "Pop-up rabat", "active": True, "is_broken": False, "opens_count": 900,
                  "conversions_count": 5, "conversion_rate": _stawka(0.005)}], "links": {"next": None}}),
    (r"^/ecommerce/settings$", "/ecommerce/settings", lambda q: {"data": {
        "ecommerce_tracking_in_campaigns": True, "ecommerce_tracking_in_automations": True, "ecommerce_attribution_window": 5}}),
    (r"^/ecommerce/shops$", "/ecommerce/shops", lambda q: {"data": [{"id": "1", "name": "Herbaciarnia", "platform": "woocommerce",
                                                                     "enabled": True, "internal": False, "currency": "PLN",
                                                                     "url": "https://herbaciarnia.example", "access_data": "ck_sekret"}],
                                                           "links": {"next": None}}),
    (r"^/ecommerce/shops/[0-9]+/reports/stats$", "/ecommerce/shops/{id}/reports/stats", lambda q: {"data": {
        "ecommerce": {"orders_count": 4, "revenue": "400.00", "average_order_value": "100.00"},
        "series": [{"date": WCZORAJ, "campaign_orders_count": 1, "automation_orders_count": 2,
                    "campaign_revenue": "100.00", "automation_revenue": "200.00"}]}}),
    (r"^/automations$", "/automations", lambda q: {"data": [{
        "id": "3", "name": "Powitanie po zapisie", "enabled": True, "created_at": "2025-01-01 10:00:00", "broken": False, "complete": False,
        "warnings": ["Krok bez treści", {"type": "email", "message": "Brak tematu", "code": "W1"}],
        "stats": {"completed_subscribers_count": 10, "subscribers_in_queue_count": 2, "sent": 300,
                  "click_rate": _stawka(0.05), "unsubscribe_rate": _stawka(0.004)},
        "triggers": [{"type": "subscriber_joins_group", "group_ids": ["1"]}], "trigger_data": {"track_ecommerce": True},
        "steps": [{"id": "e1", "parent_id": None, "type": "email", "subject": "Witaj!", "has_unsubscribe_url": True,
                   "has_unlinked_buttons": False, "broken": False,
                   "email": {"subject": "Witaj!", "from": "sklep@herbaciarnia.example", "from_name": "Herbaciarnia",
                             "reply_to": "sklep@herbaciarnia.example", "plain_text": "Kod WITAJ10 −10%. Kup teraz.",
                             "html": "<p>Kod WITAJ10 −10%. Kup teraz.</p>", "stats": _staty_ml(300)}},
                  {"id": "d1", "parent_id": "e1", "type": "delay", "value": 2, "unit": "days", "delay": {"value": 2, "unit": "days"}},
                  {"id": "e2", "parent_id": "d1", "type": "email", "subject": "Jak parzyć herbatę", "has_unsubscribe_url": False,
                   "email": {"subject": "Jak parzyć herbatę", "content": {"html": "<p>Poradnik: temperatura i czas.</p>"},
                             "stats": _staty_ml(280)}}]}],
        "links": {"next": None}}),
    (r"^/campaigns$", "/campaigns", lambda q: {"data": [{
        "id": "4", "name": "Nowości", "finished_at": WCZORAJ + " 09:00:00", "started_at": WCZORAJ + " 08:00:00",
        "scheduled_for": WCZORAJ + " 08:00:00", "settings": {"ecommerce_tracking": True},
        "emails": [{"subject": "Nowe herbaty", "from": "sklep@herbaciarnia.example", "stats": _staty_ml(900)}]}],
        "links": {"next": None}}),
]


class Odpowiedz(io.BytesIO):
    def __init__(self, dane, naglowki=None):
        super().__init__(json.dumps(dane, ensure_ascii=False).encode())
        self.headers = naglowki or {}


def bez_sieci(*a, **k):
    raise AssertionError("próba połączenia z prawdziwą siecią")


class Atrapa:
    """Udaje API: dla dozwolonej ścieżki zwraca zatrutą odpowiedź, zapisuje adresy i nagłówki zapytań."""

    def __init__(self, system, odpowiedzi, prefiks, nie_ruszaj):
        self.system, self.odpowiedzi, self.prefiks, self.nie_ruszaj = system, odpowiedzi, prefiks, nie_ruszaj
        self.K = Kanarki()
        self.zapytania = []
        self.sciezki = set()

    def __call__(self, req, timeout=None):
        self.zapytania.append((req.full_url, dict(req.header_items())))
        u = urllib.parse.urlsplit(req.full_url)
        sciezka = u.path[len(self.prefiks):]
        q = dict(urllib.parse.parse_qsl(u.query))
        for wzor, etykieta, fn in self.odpowiedzi:
            if re.match(wzor, sciezka):
                self.sciezki.add(sciezka)
                return Odpowiedz(zatruj(fn(q), self.K, self.system, etykieta, self.nie_ruszaj), {"TotalPages": "1"})
        raise AssertionError(f"atrapa nie zna ścieżki {sciezka}")


def tekst_pdf(pdf):
    """Tekst z PDF (pdftotext, jeśli jest) + surowe bajty (metadane, tytuł)."""
    with open(pdf, "rb") as plik:
        wynik = plik.read().decode("latin-1")
    if shutil.which("pdftotext"):
        wynik += subprocess.run(["pdftotext", "-enc", "UTF-8", pdf, "-"], capture_output=True, text=True).stdout
    return wynik


# Znana granica: imię i nazwisko przechodzi tylko w tekstach, które właściciel konta sam nazwał lub napisał.
GRANICA_NAZW = {
    "getresponse": {"/campaigns": {"[].name"}, "/workflow": {"[].name"}, "/workflow/{id}": {"name"},
                    "/newsletters": {"[].name", "[].subject"}, "/autoresponders": {"[].name", "[].subject"},
                    "/forms": {"[].name"}, "/shops": {"[].name"}},
    "mailerlite": {"/groups": {"data[].name"}, "/forms/{typ}": {"data[].name"}, "/ecommerce/shops": {"data[].name"},
                   "/automations": {"data[].name", "data[].warnings[]", "data[].warnings[].message",
                                    "data[].steps[].subject", "data[].steps[].email.subject"},
                   "/campaigns": {"data[].name", "data[].emails[].subject"}},
}


class TestKanarek(unittest.TestCase):
    """Pełny audyt na zatrutych danych → żaden e-mail, telefon ani IP nie wychodzi poza skrypt."""

    podsumowanie = {}

    def przebieg(self, system, nie_ruszaj, nazwa):
        modul = G if system == "getresponse" else M
        odp, prefiks = (GR_ODPOWIEDZI, "/v3") if system == "getresponse" else (ML_ODPOWIEDZI, "/api")
        zmienna = "GETRESPONSE_API_KEY" if system == "getresponse" else "MAILERLITE_API_KEY"
        atrapa = Atrapa(system, odp, prefiks, nie_ruszaj)
        with tempfile.TemporaryDirectory() as tmp:
            pamiec_dir = os.path.join(tmp, "tmp")
            os.makedirs(pamiec_dir)
            raport = os.path.join(tmp, f"audyt-{system}.md")
            js = os.path.join(tmp, f"audyt-{system}.json")
            postep = os.path.join(tmp, f"audyt-{system}.postep.txt")
            out, err = io.StringIO(), io.StringIO()
            argv = ["x", "--raport", raport, "--json", js, "--postep", postep]
            with mock.patch("tempfile.gettempdir", return_value=pamiec_dir), \
                    mock.patch.object(modul._OTWIERACZ, "open", side_effect=atrapa), \
                    mock.patch.object(socket, "create_connection", side_effect=bez_sieci), \
                    mock.patch("time.sleep"), mock.patch.dict(os.environ, {zmienna: KLUCZ}), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                for _ in range(2):  # drugi raz: odpowiedzi z pamięci na dysku
                    with mock.patch.object(sys, "argv", argv):
                        modul.main()
                html_plik, pdf = os.path.join(tmp, "r.html"), os.path.join(tmp, "r.pdf")
                with mock.patch.object(sys, "argv", ["x", raport, "--pdf", pdf, "--html", html_plik]):
                    raport_pdf.main()
            pliki = {"stdout": out.getvalue(), "stderr": err.getvalue()}
            for etykieta, p in (("raport .md", raport), ("JSON", js), ("plik postępu", postep), ("HTML", html_plik)):
                with open(p, encoding="utf-8") as plik:
                    pliki[etykieta] = plik.read()
            if os.path.exists(pdf):
                pliki["PDF"] = tekst_pdf(pdf)
            for kat, _, nazwy in os.walk(pamiec_dir):
                for n in nazwy:
                    with open(os.path.join(kat, n), encoding="utf-8") as plik:
                        pliki[f"pamięć: {n[:12]}…"] = plik.read()
                    self.assertNotIn(KLUCZ, n)
            pliki["adresy zapytań"] = "\n".join(u for u, _ in atrapa.zapytania)

        # 1. Każda dozwolona ścieżka została odpytana (atrapa pokrywa całą listę).
        nieodpytane = [r.pattern for r in modul.DOZWOLONE_SCIEZKI if not any(r.match(x) for x in atrapa.sciezki)]
        self.assertEqual(nieodpytane, [], "audyt nie odpytał wszystkich dozwolonych ścieżek")
        for r in modul.DOZWOLONE_SCIEZKI:  # każdy wariant w nawiasie (list-size|subscriptions|removals) też
            for wariant in re.findall(r"\(([a-z|-]+)\)", r.pattern):
                for w in wariant.split("|"):
                    self.assertTrue(any(w in x and r.match(x) for x in atrapa.sciezki), f"nieodpytany wariant {w} w {r.pattern}")
        self.assertTrue(any(k.startswith("pamięć") for k in pliki), "pamięć odpowiedzi nie powstała")
        # 2. Klucz: tylko w nagłówku zapytania do oficjalnego API; nigdzie w plikach i na ekranie.
        for url, naglowki in atrapa.zapytania:
            self.assertTrue(url.startswith(("https://api.getresponse.com/v3/", "https://connect.mailerlite.com/api/")), url)
        for gdzie, t in pliki.items():
            self.assertNotIn(KLUCZ, t, f"klucz API w: {gdzie}")
        # 3. Żaden kanarek e-mail / telefon / IP.
        wycieki = []
        for gdzie, t in pliki.items():
            for n in sorted(Kanarki.kandydaci_kontaktu(t) & set(atrapa.K.pola)):
                co = Kanarki.wycieki_kontaktu(n, t)
                if co:
                    sys_, sciezka, pole = atrapa.K.pola[n]
                    wycieki.append(f"{'/'.join(co)} z {sys_} {sciezka} pole „{pole}” → {gdzie}")
        self.assertEqual(wycieki, [], "WYCIEK:\n" + "\n".join(wycieki[:40]))
        # 4. Imię/nazwisko: gdzie przechodzi (widać dla AI: ekran, raport, JSON, HTML, PDF, plik postępu).
        widoczne = {k: v for k, v in pliki.items() if not k.startswith("pamięć") and k != "adresy zapytań"}
        nazwy = {}
        for t in widoczne.values():
            for n in Kanarki.kandydaci_nazwiska(t) & set(atrapa.K.pola):
                _, sciezka, pole = atrapa.K.pola[n]
                nazwy.setdefault(sciezka, set()).add(pole)
        poza = {s: p - GRANICA_NAZW[system].get(s, set()) for s, p in nazwy.items()}
        poza = {s: p for s, p in poza.items() if p}
        self.assertEqual(poza, {}, f"imię/nazwisko przeszło w nieoczekiwanym polu: {poza}")
        TestKanarek.podsumowanie[f"{system} ({nazwa})"] = (len(atrapa.K.pola), len(atrapa.zapytania), sorted(pliki), nazwy)

    def test_getresponse_wszystkie_pola(self):
        self.przebieg("getresponse", ID, "kanarek we wszystkich polach")

    def test_getresponse_pola_opisowe(self):
        self.przebieg("getresponse", STRUKTURA, "kanarek w polach opisowych")

    def test_mailerlite_wszystkie_pola(self):
        self.przebieg("mailerlite", ID, "kanarek we wszystkich polach")

    def test_mailerlite_pola_opisowe(self):
        self.przebieg("mailerlite", STRUKTURA, "kanarek w polach opisowych")

    def test_kanarek_naprawde_wykrywa_wyciek(self):
        """Sprawdzian samego testu: z celowo wyłączonym ukrywaniem test MUSI zgłosić wyciek."""
        import wspolne
        with mock.patch.object(wspolne, "maskuj", side_effect=lambda t: t):
            with self.assertRaises(AssertionError) as e:
                TestKanarek("test_getresponse_pola_opisowe").przebieg("getresponse", STRUKTURA, "sprawdzian")
        self.assertIn("WYCIEK", str(e.exception))
        TestKanarek.podsumowanie.pop("getresponse (sprawdzian)", None)

    def test_blad_api_z_kanarkiem_w_tresci(self):
        """Odpowiedź z błędem pełna danych osobowych → komunikat bez nich."""
        for modul, sciezka in ((G, "/campaigns"), (M, "/groups")):
            def blad(req, timeout=None):
                raise urllib.error.HTTPError(req.full_url, 400, Kanarki.tekst(1), {}, io.BytesIO(Kanarki.tekst(2).encode()))
            err = io.StringIO()
            with mock.patch.object(modul._OTWIERACZ, "open", side_effect=blad), mock.patch("time.sleep"), \
                    contextlib.redirect_stderr(err):
                klient = modul.GR(KLUCZ, "https://api.getresponse.com/v3") if modul is G else modul.ML(KLUCZ)
                with self.assertRaises(SystemExit) as e:
                    klient.get(sciezka)
            tekst = str(e.exception.code) + err.getvalue()
            for n in (1, 2):
                self.assertEqual(Kanarki.wycieki_kontaktu(n, tekst), [], tekst)
                self.assertFalse(Kanarki.nazwisko(n, tekst), tekst)
            self.assertNotIn(KLUCZ, tekst)

    @classmethod
    def tearDownClass(cls):
        if not cls.podsumowanie:
            return
        print("\n\n=== Test kanarek — podsumowanie ===", file=sys.stderr)
        for nazwa, (kanarkow, zapytan, miejsca, nazwy) in sorted(cls.podsumowanie.items()):
            print(f"\n{nazwa}: {kanarkow} kanarków w {zapytan} odpowiedziach API.", file=sys.stderr)
            print("  Sprawdzone miejsca: " + ", ".join(m for m in miejsca if not m.startswith("pamięć"))
                  + f", pamięć na dysku ({sum(m.startswith('pamięć') for m in miejsca)} plików).", file=sys.stderr)
            print("  E-mail, telefon, IP: NIGDZIE.", file=sys.stderr)
            print("  Imię/nazwisko przechodzi tylko w tekstach nazwanych przez właściciela konta:", file=sys.stderr)
            for s, p in sorted(nazwy.items()):
                print(f"    {s}: {', '.join(sorted(p))}", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
