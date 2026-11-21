"""Tryb pokazowy: zmyślone odpowiedzi API GetResponse dla fikcyjnego sklepu z herbatą.

Bez klucza i bez internetu. Dane wymyślone tak, żeby raport pokazał wszystkie funkcje audytu:
seria powitalna z samych rabatów, brak porzuconego koszyka, automat, przez który nikt nie przechodzi,
mail bez śledzenia sprzedaży, nadawca w darmowej poczcie, dobre i słabe wyniki maili, formularz z niską konwersją.
"""
import datetime as dt

DZIS = dt.date.today()


def _dzien(n):
    return (DZIS - dt.timedelta(days=n)).isoformat()


LISTY = [{"campaignId": "L1", "name": "Newsletter herbaciarni"}, {"campaignId": "L2", "name": "Klienci sklepu"}]
ROZMIAR = {"L1": 3420, "L2": 1860}

AUTOMATY = [
    {"workflowId": "W1", "name": "Powitanie nowego subskrybenta", "status": "active", "dateStart": _dzien(400),
     "subscriberStatistics": {"completedCount": 1180, "inProgressCount": 42}},
    {"workflowId": "W2", "name": "Po zakupie — prośba o opinię", "status": "active", "dateStart": _dzien(300),
     "subscriberStatistics": {"completedCount": 640, "inProgressCount": 35}},
    {"workflowId": "W3", "name": "Drugi zakup — uzupełnij zapas herbaty", "status": "active", "dateStart": _dzien(200),
     "subscriberStatistics": {"completedCount": 0, "inProgressCount": 0}},
    {"workflowId": "W4", "name": "Szkic 2026-03-02 10:15:00", "status": "inactive", "dateStart": "",
     "subscriberStatistics": {"completedCount": 0, "inProgressCount": 0}},
]

STOPKA = "<p>Herbaciarnia Przykładowa · Nie chcesz już takich wiadomości? Wypisz się.</p>"
MAILE = {
    "N1": ("Witaj! Twój kod −10% na pierwsze zakupy",
           "<p>Cześć! Dziękujemy za zapis. Twój kod: WITAJ10 daje −10% na pierwsze zamówienie.</p>"
           "<a href='https://herbaciarnia.example/koszyk'>Kup teraz</a>" + STOPKA, True, (1240, 610, 76, 6, 0)),
    "N2": ("Witaj ponownie — ostatni dzień kodu −10%",
           "<p>Twój kod WITAJ10 wygasa dziś. Zamów teraz, ceny od 19 zł.</p>"
           "<a href='https://herbaciarnia.example/sklep'>Do sklepu</a>" + STOPKA, True, (1105, 420, 38, 9, 1)),
    "N3": ("Jak się parzy Twoja herbata?",
           "<p>Minęły dwa tygodnie od zakupu. Napisz opinię — pomoże innym wybrać.</p>" + STOPKA, True, (690, 310, 41, 2, 0)),
    "N4": ("Uzupełnij zapas herbaty",
           "<p>Kończy się herbata? Zamów teraz z kodem ZAPAS5.</p>" + STOPKA, True, (0, 0, 0, 0, 0)),
    "N5": ("Dziękujemy za zakup",
           "<p>Dziękujemy za zamówienie. Wkrótce wyślemy paczkę.</p>" + STOPKA, False, (980, 520, 12, 1, 0)),
}

NEWSLETTERY = [
    ("B1", 4, "Zimowe herbaty rozgrzewające — nowości", True, (5120, 1210, 168, 7, 0)),
    ("B2", 11, "Jak wybrać herbatę na wieczór — krótki poradnik", True, (5090, 1340, 214, 4, 0)),
    ("B3", 18, "Tylko dziś −20% na wszystko", True, (5075, 980, 21, 41, 3)),
    ("B4", 25, "Nowa dostawa zielonych herbat", False, (5040, 1020, 96, 6, 0)),
    ("B5", 39, "Black Week w herbaciarni", True, (5010, 1150, 140, 12, 1)),
    ("B6", 53, "Herbata a kawa — porównanie", True, (4990, 1090, 120, 5, 0)),
]

NADAWCY = [
    {"email": "sklep@herbaciarnia.example", "isActive": "true", "isDefault": "true",
     "domain": {"status": "confirmed", "DKIMWarning": None, "hasDMARCWarning": "false"}},
    {"email": "herbaciarnia.przyklad@gmail.com", "isActive": "true", "isDefault": "false",
     "domain": {"status": "confirmed", "DKIMWarning": "can_not_be_used", "hasDMARCWarning": "false"}},
]

FORMULARZE = [
    {"name": "Pop-up: −10% na start", "status": "enabled", "visitors": 8400, "subscribed": 352, "subscriptionRate": 4.19},
    {"name": "Stopka strony", "status": "enabled", "visitors": 6100, "subscribed": 31, "subscriptionRate": 0.51},
    {"name": "Stary formularz z bloga", "status": "enabled", "visitors": 0, "subscribed": 0, "subscriptionRate": 0},
]


def _stat(sent, opened, clicked, unsub, compl):
    return [{"sent": sent, "uniqueHumanOpened": opened, "uniqueHumanClicked": clicked, "unsubscribed": unsub,
             "complaints": compl, "bounced": round(sent * 0.004), "timeInterval": "total"}]


def _zamowienia():
    """~220 zamówień w ostatnich 90 dniach; co trzecie bez kontaktu (klient bez zgody)."""
    wynik = []
    for i in range(220):
        wynik.append({"orderId": f"O{i}", "totalPrice": 58 + (i * 37) % 140, "processedAt": _dzien(i * 90 // 220) + "T12:00:00+0000",
                      "contactId": None if i % 3 == 0 else f"C{i}", "status": "cancelled" if i % 25 == 0 else "processed"})
    return wynik


class PokazGR:
    """Udaje klienta GR: te same metody co prawdziwy, odpowiedzi z pamięci."""

    def __init__(self):
        self.zapytan = 0
        self.niedostepne = []
        self.ostrzezenia = []

    def get(self, sciezka, params=None, opcjonalny=False):
        self.zapytan += 1
        p = params or {}
        if sciezka == "/campaigns":
            return LISTY, {}
        if sciezka == "/campaigns/statistics/list-size":
            if "query[createdOn][from]" in p:
                return [{"totalSubscribers": 5280, "addedSubscribers": 512, "removedSubscribers": 87, "createdOn": "total"}], {}
            return [{"totalSubscribers": ROZMIAR.get(p.get("query[campaignId]"), 0), "createdOn": "total"}], {}
        if sciezka == "/campaigns/statistics/subscriptions":
            return {"L1": {"total": {"www": 383, "api": 129, "import": 0, "summary": 512}}}, {}
        if sciezka == "/campaigns/statistics/removals":
            return {"L1": {"total": {"unsubscribe": 71, "bounce": 12, "api": 4}}}, {}
        if sciezka == "/forms":
            return FORMULARZE, {}
        if sciezka == "/from-fields":
            return NADAWCY, {}
        if sciezka == "/workflow":
            return [{"workflowId": w["workflowId"]} for w in AUTOMATY], {}
        if sciezka.startswith("/workflow/"):
            return next(w for w in AUTOMATY if w["workflowId"] == sciezka.split("/")[-1]), {}
        if sciezka == "/newsletters":
            if p.get("query[type]") == "automation":
                return [{"newsletterId": k, "name": v[0], "subject": v[0], "status": "enabled",
                         "flags": "ecommerce_tracking" if v[2] else "", "createdOn": _dzien(300)} for k, v in MAILE.items()], {}
            return [{"newsletterId": k, "name": t, "subject": t, "status": "sent", "flags": "ecommerce_tracking" if sl else "",
                     "sendOn": _dzien(d) + "T09:00:00+0000"} for k, d, t, sl, _ in NEWSLETTERY], {}
        if sciezka.startswith("/newsletters/") and sciezka.endswith("/statistics"):
            nid = sciezka.split("/")[2]
            if nid in MAILE:
                return _stat(*MAILE[nid][3]), {}
            return _stat(*next(s for k, _, _, _, s in NEWSLETTERY if k == nid)), {}
        if sciezka.startswith("/newsletters/"):
            nid = sciezka.split("/")[2]
            return {"newsletterId": nid, "subject": MAILE[nid][0], "content": {"html": MAILE[nid][1]}}, {}
        if sciezka == "/autoresponders":
            return [], {}
        if sciezka == "/shops":
            return [{"shopId": "S1", "name": "Herbaciarnia Przykładowa", "currency": "PLN"}], {}
        if sciezka == "/shops/S1/orders":
            return (_zamowienia() if str(p.get("page", 1)) == "1" else []), {"totalpages": "1"}
        if sciezka == "/statistics/ecommerce/performance":
            return {"currency": "PLN", "order": {"orders": 31}, "revenue": {"revenue": 3920.5}}, {}
        if sciezka == "/statistics/ecommerce/revenue":
            return {"currency": "PLN", "timeSeries": [{"revenue": 3920.5, "orders": 31}]}, {}
        return None, {"_404": True}

    def wszystkie(self, sciezka, params=None, per_page=100, max_stron=50, opcjonalny=False):
        d, _ = self.get(sciezka, params, opcjonalny)
        return d or []
