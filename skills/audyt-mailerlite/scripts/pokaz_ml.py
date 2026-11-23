"""Tryb pokazowy: zmyślone odpowiedzi API MailerLite dla fikcyjnego sklepu z herbatą.

Bez tokena i bez internetu. Pokazuje: serię powitalną z samych rabatów (dzień 0 i 2), brak porzuconego koszyka,
mail bez linku do wypisu, automat niedokończony, kampanie bez liczenia sprzedaży, formularz z niską konwersją, liczby sklepu (zamówienia, przychód, część z maili).
"""
import datetime as dt

DZIS = dt.date.today()


def _dzien(n):
    return (DZIS - dt.timedelta(days=n)).isoformat() + " 09:00:00"


def _stat(sent, open_rate, click_rate, unsub_rate, spam_rate=0.0, extra=None):
    s = {"sent": sent, "open_rate": {"float": open_rate}, "click_rate": {"float": click_rate},
         "unsubscribe_rate": {"float": unsub_rate}, "spam_rate": {"float": spam_rate}, "hard_bounce_rate": {"float": 0.003}}
    s.update(extra or {})
    return s


def _mail(eid, parent, temat, tekst, staty, wypis=True):
    return {"id": eid, "type": "email", "parent_id": parent, "subject": temat, "has_unsubscribe_url": wypis,
            "has_unlinked_buttons": False, "broken": False,
            "email": {"subject": temat, "plain_text": tekst + " Nie chcesz już takich wiadomości? Wypisz się.", "stats": staty}}


AUTOMATY = [
    {"name": "Powitanie po zapisie", "enabled": True, "complete": True, "created_at": _dzien(500),
     "triggers": [{"type": "subscriber_joins_group"}], "trigger_data": {"track_ecommerce": True},
     "stats": {"completed_subscribers_count": 960, "subscribers_in_queue_count": 28, "sent": 1890,
               "click_rate": {"float": 0.052}, "unsubscribe_rate": {"float": 0.006}},
     "steps": [_mail("e1", None, "Witaj! Kod −10% na pierwsze zakupy", "Dziękujemy za zapis. Kod WITAJ10 daje −10% na pierwsze zamówienie. Kup teraz.",
                     _stat(980, 0.52, 0.071, 0.004)),
               {"id": "d1", "type": "delay", "parent_id": "e1", "value": 2, "unit": "days"},
               _mail("e2", "d1", "Twój kod −10% wygasa jutro", "Zostały 24 godziny na kod WITAJ10. Zamów teraz, herbaty od 19 zł.",
                     _stat(910, 0.41, 0.032, 0.009))]},
    {"name": "Podziękowanie po zakupie", "enabled": True, "complete": True, "created_at": _dzien(400),
     "triggers": [{"type": "purchased_any_product"}], "trigger_data": {"track_ecommerce": True},
     "stats": {"completed_subscribers_count": 410, "subscribers_in_queue_count": 9, "sent": 420,
               "click_rate": {"float": 0.044}, "unsubscribe_rate": {"float": 0.002}},
     "steps": [_mail("p1", None, "Dziękujemy za zakup", "Dziękujemy za zamówienie. Jak parzyć Twoją herbatę: krótki poradnik krok po kroku.",
                     _stat(420, 0.58, 0.044, 0.002), wypis=False)]},
    {"name": "Porzucony koszyk", "enabled": False, "complete": False, "created_at": _dzien(90),
     "triggers": [{"type": "abandoned_cart"}], "trigger_data": {"track_ecommerce": False},
     "stats": {"completed_subscribers_count": 0, "subscribers_in_queue_count": 0, "sent": 0},
     "steps": []},
]

KAMPANIE = [
    ("Zimowe herbaty rozgrzewające", 6, True, _stat(2410, 0.38, 0.034, 0.002)),
    ("Jak wybrać herbatę na wieczór", 14, True, _stat(2395, 0.41, 0.046, 0.001)),
    ("Tylko dziś −20% na wszystko", 22, False, _stat(2380, 0.33, 0.004, 0.009, 0.0012)),
    ("Nowa dostawa zielonych herbat", 35, True, _stat(2350, 0.36, 0.027, 0.002)),
    ("Black Week w herbaciarni", 49, False, _stat(2330, 0.35, 0.029, 0.003)),
    ("Herbata a kawa — porównanie", 63, True, _stat(2300, 0.37, 0.031, 0.001)),
    ("Jesienne nowości", 77, True, _stat(2280, 0.36, 0.028, 0.002)),
]

GRUPY = [
    {"name": "Newsletter", "active_count": 2410, "unsubscribed_count": 186, "bounced_count": 22, "junk_count": 3, "unconfirmed_count": 41},
    {"name": "Klienci", "active_count": 980, "unsubscribed_count": 54, "bounced_count": 6, "junk_count": 0, "unconfirmed_count": 0},
]

FORMULARZE = {
    "popup": [{"name": "Pop-up −10% na start", "active": True, "opens_count": 9200, "conversions_count": 380, "conversion_rate": {"float": 0.0413}}],
    "embedded": [{"name": "Stopka strony", "active": True, "opens_count": 5400, "conversions_count": 27, "conversion_rate": {"float": 0.005}}],
    "promotion": [],
}


class PokazML:
    """Udaje klienta MailerLite: te same metody co prawdziwy, odpowiedzi z pamięci."""

    def __init__(self):
        self.zapytan = 0
        self.niedostepne = []
        self.ostrzezenia = []

    def get(self, sciezka, params=None):
        self.zapytan += 1
        if sciezka == "/ecommerce/shops/1/reports/stats":
            # Zmyślone liczby zbiorcze sklepu z herbatą: zamówienia, przychód i część z kampanii i automatów.
            seria = [{"date": _dzien(d)[:10], "campaign_orders_count": zk, "campaign_revenue": pk,
                      "automation_orders_count": za, "automation_revenue": pa}
                     for d, zk, pk, za, pa in ((22, 9, 1170.0, 12, 1530.5), (14, 7, 905.0, 11, 1402.0), (6, 5, 655.0, 11, 1477.5))]
            return {"data": {"ecommerce": {"orders_count": 148, "revenue": 18640.0, "average_order_value": 125.95}, "series": seria}}
        if sciezka == "/ecommerce/settings":
            return {"data": {"ecommerce_tracking_in_campaigns": False, "ecommerce_tracking_in_automations": True,
                             "ecommerce_attribution_window": 5}}
        return None

    def wszystkie(self, sciezka, params=None, max_stron=50):
        self.zapytan += 1
        if sciezka == "/groups":
            return GRUPY
        if sciezka == "/ecommerce/shops":
            return [{"id": "1", "name": "Herbaciarnia Przykładowa", "platform": "woocommerce", "enabled": True,
                     "internal": False, "currency": "PLN"}]
        if sciezka == "/automations":
            return AUTOMATY
        if sciezka == "/campaigns":
            return [{"name": t, "finished_at": _dzien(d), "settings": {"ecommerce_tracking": sl},
                     "emails": [{"subject": t, "stats": s}]} for t, d, sl, s in KAMPANIE]
        if sciezka.startswith("/forms/"):
            return FORMULARZE.get(sciezka.split("/")[-1], [])
        return []
