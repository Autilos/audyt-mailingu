#!/usr/bin/env python3
"""Audyt e-mail marketingu w MailerLite — TYLKO ODCZYT.

Sprawdza: automatyzacje (wyzwalacz, czy działają, czy są zepsute, każdy mail z wynikami,
link do wypisu), kampanie z ostatnich N dni, sklep (liczba zamówień i przychód z raportu zbiorczego sklepu,
w tym część z kampanii i automatów — bez pojedynczych zamówień),
ustawienia liczenia sprzedaży i listę kontrolną automatów sklepu internetowego.

Nie zmienia niczego na koncie. Wywołuje wyłącznie zapytania GET.
Nie pobiera adresów e-mail ani danych subskrybentów i kupujących — tylko liczby zbiorcze. Z każdej odpowiedzi API
od razu zostają wyłącznie pola potrzebne audytowi (WZORY_ODPOWIEDZI); reszta jest odrzucana, zanim trafi na dysk.

Użycie:
  export MAILERLITE_API_KEY=...        # MailerLite → Integracje → MailerLite API → Wygeneruj nowy token
  python3 audyt_mailerlite.py --dni 90 --raport raport.md
Działa z nowym MailerLite (konta od 22.03.2022). MailerLite Classic ma inne API — nieobsługiwane.
"""
import argparse
import datetime as dt
import http.client
import json
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seria_powitalna import klasyfikuj, wniosek_serii  # noqa: E402
from rekomendacje import rekomendacja_serii, uloz, sekcja_dla_ai  # noqa: E402
from wspolne import Postep, Pamiec, klucz_z_env_albo_pliku, przytnij, maskuj_wszystko  # noqa: E402

API = "https://connect.mailerlite.com/api"
HOST_API = "connect.mailerlite.com"
PRZERWA = 0.55  # limit MailerLite: 120 zapytań na minutę


class _BezPrzekierowan(urllib.request.HTTPRedirectHandler):
    """Przekierowanie = błąd. urllib przy przekierowaniu wysyła nagłówki (z kluczem) pod nowy adres."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OTWIERACZ = urllib.request.build_opener(_BezPrzekierowan)

# Zero danych osobowych: wyłącznie te ścieżki (statystyki, ustawienia, treść maili).
# Celowo brak /subscribers, /ecommerce/shops/{id}/orders (zamówienia mają dane kupującego), /account (adres firmy/właściciela).
# /ecommerce/shops/{id}/reports/stats = raport zbiorczy sklepu: same liczby (zamówienia, przychód, podział dzienny
# na kampanie i automaty), sprawdzony na żywym koncie 23.11.2026 — bez danych kupujących.
DOZWOLONE_SCIEZKI = [re.compile(x) for x in (
    r"^/groups$", r"^/ecommerce/settings$", r"^/ecommerce/shops$", r"^/automations$", r"^/campaigns$",
    r"^/forms/(popup|embedded|promotion)$", r"^/ecommerce/shops/[0-9]+/reports/stats$",
)]
MAKS_DNI_RAPORTU_SKLEPU = 365  # API odrzuca dłuższy okres (sprawdzone: 365 dni działa, 366 — błąd 422)


def sciezka_dozwolona(url):
    if not url.startswith(API + "/"):
        return False
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.netloc != HOST_API:
        return False
    sciezka = u.path[len(urllib.parse.urlsplit(API).path):]
    return any(r.match(sciezka) for r in DOZWOLONE_SCIEZKI)


# Z odpowiedzi zostają WYŁĄCZNIE te pola (wspolne.przytnij) — wszystko inne, np. adresy nadawcy (from, reply_to),
# dane dostępowe sklepu czy pola, które MailerLite doda w przyszłości, jest odrzucane od razu po odebraniu strony.
_STAWKA = {"float": True, "string": True}
_STRONA = {"next": True}
_STATY_MAILA = {k: _STAWKA for k in ("open_rate", "click_rate", "unsubscribe_rate", "spam_rate", "hard_bounce_rate")}
_STATY_MAILA["sent"] = True
_TRESC = {"html": True, "plain": True}


def _liczba_albo_nic(v):
    """Raport sklepu: przechodzi wyłącznie liczba (także zapisana jako tekst, np. "40.00"); cokolwiek innego — nic."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v.replace(",", "."))
        except ValueError:
            return None
    return None


_ZAMOWIENIA_DZIENNIE = {k: _liczba_albo_nic for k in ("campaign_orders_count", "automation_orders_count", "campaign_revenue", "automation_revenue")}
WZORY_ODPOWIEDZI = [
    (r"^/groups$", {"data": {k: True for k in ("name", "active_count", "unsubscribed_count", "bounced_count", "junk_count", "unconfirmed_count")},
                    "links": _STRONA}),
    (r"^/forms/(popup|embedded|promotion)$", {"data": {"name": True, "active": True, "is_broken": True, "opens_count": True,
                                                       "conversions_count": True, "conversion_rate": _STAWKA}, "links": _STRONA}),
    (r"^/ecommerce/settings$", {"data": {"ecommerce_tracking_in_campaigns": True, "ecommerce_tracking_in_automations": True,
                                         "ecommerce_attribution_window": True}}),
    (r"^/ecommerce/shops$", {"data": {"id": True, "name": True, "platform": True, "enabled": True, "internal": True, "currency": True}, "links": _STRONA}),
    # Raport zbiorczy sklepu: wyłącznie liczby; data dnia i wszystko inne odpada.
    (r"^/ecommerce/shops/[0-9]+/reports/stats$", {"data": {
        "ecommerce": {k: _liczba_albo_nic for k in ("orders_count", "revenue", "average_order_value")},
        "series": _ZAMOWIENIA_DZIENNIE}}),
    (r"^/automations$", {"data": {
        "name": True, "enabled": True, "created_at": True, "broken": True, "complete": True,
        "warnings": {"type": True, "message": True, "code": True},  # napis przechodzi; ze słownika tylko te pola
        "stats": {"completed_subscribers_count": True, "subscribers_in_queue_count": True, "sent": True,
                  "click_rate": _STAWKA, "unsubscribe_rate": _STAWKA},
        "triggers": {"type": True}, "trigger_data": {"track_ecommerce": True},
        "steps": {"id": True, "parent_id": True, "type": True, "value": True, "unit": True, "delay": {"value": True, "unit": True},
                  "subject": True, "content": _TRESC, "has_unsubscribe_url": True, "has_unlinked_buttons": True, "broken": True,
                  "email": {"subject": True, "content": _TRESC, "html": True, "plain_text": True, "stats": _STATY_MAILA}},
    }, "links": _STRONA}),
    (r"^/campaigns$", {"data": {"name": True, "finished_at": True, "started_at": True, "scheduled_for": True,
                                "settings": {"ecommerce_tracking": True},
                                "emails": {"subject": True, "stats": _STATY_MAILA}}, "links": _STRONA}),
]
WZORY_ODPOWIEDZI = [(re.compile(r), w) for r, w in WZORY_ODPOWIEDZI]


def przytnij_odpowiedz(url, d):
    """Odpowiedź API → tylko potrzebne pola. Ścieżka bez wzoru = nic nie zostaje (bezpieczny domyślny wybór)."""
    sciezka = urllib.parse.urlsplit(url).path[len(urllib.parse.urlsplit(API).path):]
    wzor = next((w for r, w in WZORY_ODPOWIEDZI if r.match(sciezka)), None)
    return przytnij(d, wzor) if wzor is not None else None

# Lista kontrolna wg WYZWALACZA automatu (API MailerLite go pokazuje). Wyzwalacze ogólne
# (formularz, grupa, segment, pole) rozstrzyga nazwa automatu.
KOSZYK = {"abandoned_cart", "abandoned_checkout"}
ZAKUP = {"purchased_any_product", "purchased_from_category", "purchased_specific_product"}
PONOWNY = {"purchase_frequency"}
SLOWA = {
    "Po zakupie": ["po zakup", "post-purchase", "dziękujemy za zakup", "dziękujemy za zamówienie", "opini", "recenz", "kupił", "kupil"],
    "Porzucony koszyk": ["koszyk", "cart", "porzuc"],
    "Drugi zakup / reaktywacja": ["ponowny zakup", "ponowne zamów", "ponownego zakupu", "drugi zakup", "kolejne zamów", "replenish", "uzupełn", "reaktyw", "win-back", "winback", "tęsknimy", "dawno cię", "dawno nie"],
    "Powitanie": ["powital", "powitan", "welcome", "witaj", "po zapisie", "za zapis", "onboard"],
}
LISTA = ["Powitanie", "Porzucony koszyk", "Po zakupie", "Drugi zakup / reaktywacja"]


class ML:
    def __init__(self, klucz, pamiec=None):
        self.pamiec = pamiec
        self.h = {"Authorization": "Bearer " + klucz, "Accept": "application/json"}
        self.zapytan = 0
        self.niedostepne = []
        self.ostrzezenia = []

    def get(self, sciezka, params=None):
        url = sciezka if sciezka.startswith("https://") else API + sciezka
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="[]")
        u = urllib.parse.urlsplit(url)
        if not url.startswith(API + "/") or u.scheme != "https" or u.netloc != HOST_API:
            sys.exit("Nieoczekiwany adres spoza API MailerLite — przerwano, token nie zostanie wysłany.")
        if not sciezka_dozwolona(url):
            sys.exit(f"Ścieżka spoza listy dozwolonych ({url.split('?')[0]}) — przerwano. Audyt nie czyta danych osobowych.")
        z_pamieci = self.pamiec.czytaj(url) if self.pamiec else None
        if z_pamieci is not None:
            return przytnij_odpowiedz(url, z_pamieci)  # pamięć ze starszej wersji też przechodzi przez sito
        for proba in range(5):
            time.sleep(PRZERWA)
            self.zapytan += 1
            try:
                r = _OTWIERACZ.open(urllib.request.Request(url, headers=self.h), timeout=120)
                surowe = r.read() or b"null"
                try:
                    d = przytnij_odpowiedz(url, json.loads(surowe))
                except ValueError:
                    sys.exit("API zwróciło odpowiedź, która nie jest JSON-em — przerwano (treści odpowiedzi nie pokazujemy).")
                finally:
                    surowe = None  # surowa odpowiedź nie jest nigdzie zapisywana ani wypisywana
                if self.pamiec:
                    self.pamiec.zapisz(url, d)
                return d
            except (socket.timeout, TimeoutError, http.client.IncompleteRead, ConnectionError):
                if proba < 4:
                    time.sleep(5 * (proba + 1))
                    continue
                sys.exit("Połączenie z API MailerLite zrywa się — przerwano. Uruchom ponownie za kilka minut.")
            except urllib.error.HTTPError as e:
                e.close()  # treść odpowiedzi z błędem nie jest czytana ani wypisywana (mogłaby zawierać dane)
                if 300 <= e.code < 400:
                    sys.exit(f"API odpowiedziało przekierowaniem ({e.code}) — przerwano, token nie został wysłany pod inny adres.")
                if e.code == 429:
                    try:
                        czekaj = int(e.headers.get("Retry-After") or 60)
                    except ValueError:
                        czekaj = 60
                    print(f"  limit zapytań — czekam {czekaj} s", file=sys.stderr)
                    time.sleep(min(czekaj, 300))
                    continue
                if e.code == 401:
                    sys.exit("Błąd 401: token API nieprawidłowy albo usunięty (MailerLite → Integracje → MailerLite API).")
                if e.code in (403, 404):
                    if sciezka not in self.niedostepne:
                        self.niedostepne.append(sciezka)
                    return None
                if e.code >= 500 and proba < 4:
                    time.sleep(3 * (proba + 1))
                    continue
                sys.exit(f"API MailerLite zwróciło błąd {e.code} dla {sciezka.split('?')[0]} — przerwano.")
            except urllib.error.URLError:
                if proba < 4:
                    time.sleep(3 * (proba + 1))
                    continue
                sys.exit("Brak połączenia z API MailerLite (sieć, proxy albo zapora) — przerwano.")
        sys.exit(f"API MailerLite nie odpowiedziało po 5 próbach ({sciezka.split('?')[0]}) — przerwano, żeby raport nie był oparty na brakujących danych.")

    def wszystkie(self, sciezka, params=None, max_stron=50):
        wynik, nastepna = [], None
        p = dict(params or {}, limit=100)
        for strona in range(1, max_stron + 1):
            d = self.get(nastepna) if nastepna else self.get(sciezka, p)
            if not isinstance(d, dict):
                if strona > 1:
                    self.ostrzezenia.append(f"{sciezka}: kolejna strona niedostępna — dane mogą być niepełne.")
                break
            wynik += d.get("data") or []
            nastepna = (d.get("links") or {}).get("next")
            if not nastepna:
                break
        else:
            self.ostrzezenia.append(f"{sciezka}: pobrano maksymalnie {max_stron * 100} pozycji — reszta pominięta.")
        return wynik


def raport_sklepu(ml, id_sklepu, od, do):
    """Liczby zbiorcze sklepu z /ecommerce/shops/{id}/reports/stats: zamówienia, przychód i część z maili.
    Pusty słownik = API nie podało raportu (wtedy raport mówi „nieznane”, a nie „0”)."""
    if not re.fullmatch(r"[0-9]+", str(id_sklepu or "")):
        return {}
    d = ml.get(f"/ecommerce/shops/{id_sklepu}/reports/stats", {"start_date": od, "end_date": do})
    dane = (d or {}).get("data") if isinstance(d, dict) else None
    if not isinstance(dane, dict) or not isinstance(dane.get("ecommerce"), dict):
        return {}
    e = dane["ecommerce"]
    if e.get("orders_count") is None:
        return {}
    seria = [x for x in dane.get("series") or [] if isinstance(x, dict)]

    def suma(klucz):
        return sum(liczba(x.get(klucz)) for x in seria) if seria else None
    return {"zamowienia": int(liczba(e.get("orders_count"))), "przychod": liczba(e.get("revenue")),
            "srednie_zamowienie": None if e.get("average_order_value") is None else liczba(e.get("average_order_value")),
            "z_kampanii_zamowienia": None if suma("campaign_orders_count") is None else int(suma("campaign_orders_count")),
            "z_kampanii_przychod": suma("campaign_revenue"),
            "z_automatow_zamowienia": None if suma("automation_orders_count") is None else int(suma("automation_orders_count")),
            "z_automatow_przychod": suma("automation_revenue")}


def liczba(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def stawka(s, klucz):
    """MailerLite podaje stawki jako {"float": 0.12, "string": "12%"} — zwraca procent."""
    v = (s or {}).get(klucz)
    if isinstance(v, dict):
        v = v.get("float") if v.get("float") is not None else v.get("string")
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return round(float(v.strip().rstrip("%").replace(",", ".")), 2)
        except ValueError:
            return None
    return round(100.0 * liczba(v), 2)


def czysc(t):
    t = unicodedata.normalize("NFKC", str(t) if t else "")
    return re.sub(r"\{\$?[a-z_]+[^}]*\}|\{\{[^}]*\}\}", "…", t).strip()


def dopasuj(tekst, slowa):
    t = czysc(tekst).lower()
    return any(s in t for s in slowa)


def wyniki_maila(stats):
    s = stats or {}
    return {"wyslane": int(liczba(s.get("sent"))),
            "otwarcia_proc": stawka(s, "open_rate"),
            "klikniecia_proc": stawka(s, "click_rate"),
            "wypisy_proc": stawka(s, "unsubscribe_rate"),
            "skargi_proc": stawka(s, "spam_rate"),
            "odbicia_proc": stawka(s, "hard_bounce_rate")}


def problemy_maila(m):
    p = []
    if m["wyslane"] == 0:
        return ["jeszcze nie wysłany"]
    if m["wyslane"] >= 200:
        if (m["wypisy_proc"] or 0) > 0.5:
            p.append("dużo wypisów " + f(m["wypisy_proc"]))
        if (m["skargi_proc"] or 0) >= 0.3:
            p.append("skargi na spam " + f(m["skargi_proc"]) + " — przekroczony próg Google 0,3%")
        elif (m["skargi_proc"] or 0) > 0.1:
            p.append("skargi na spam " + f(m["skargi_proc"]) + " — powyżej zalecanych przez Google 0,1%")
        if (m["odbicia_proc"] or 0) > 2:
            p.append("odbicia " + f(m["odbicia_proc"]))
        if m["klikniecia_proc"] is not None and m["klikniecia_proc"] < 0.5:
            p.append("prawie nikt nie klika (" + f(m["klikniecia_proc"]) + ")")
    return p


def kategoria(automat):
    typy = {t.get("type") for t in automat.get("triggers") or []}
    if typy & KOSZYK:
        return "Porzucony koszyk"
    if typy & ZAKUP:
        return "Po zakupie"
    if typy & PONOWNY:
        return "Drugi zakup / reaktywacja"
    for k in ("Porzucony koszyk", "Po zakupie", "Drugi zakup / reaktywacja", "Powitanie"):
        if dopasuj(automat.get("name"), SLOWA[k]):
            return k
    if typy & {"form_completed", "subscriber_joins_group"}:
        return "Powitanie"  # nowy subskrybent z formularza/grupy — zwykle seria powitalna
    return None


def opoznienie_dni(k):
    """Krok „delay” → liczba dni. Pola MailerLite: value + unit (minutes/hours/days/weeks); inaczej None."""
    try:
        v = float(k.get("value") or (k.get("delay") or {}).get("value"))
    except (TypeError, ValueError):
        return None
    u = str(k.get("unit") or (k.get("delay") or {}).get("unit") or "").lower()
    for klucz, mnoznik in (("min", 1 / 1440), ("hour", 1 / 24), ("day", 1), ("week", 7), ("month", 30)):
        if klucz in u:
            return v * mnoznik
    return None


def dni_krokow(kroki):
    """Dzień każdego kroku liczony po drzewie parent_id (kolejność w API nie jest kolejnością w automacie).
    Po rozgałęzieniu (warunek, test A/B) dzień jest nieznany (None)."""
    po_id = {k.get("id"): k for k in kroki}
    wynik = {}

    def dzien(k, glebokosc=0):
        kid = k.get("id")
        if kid in wynik:
            return wynik[kid]
        if glebokosc > 200:
            return None
        rodzic = po_id.get(k.get("parent_id"))
        baza = 0.0 if rodzic is None else dzien(rodzic, glebokosc + 1)
        if baza is not None and rodzic is not None and rodzic.get("type") in ("condition", "split", "ab_test"):
            baza = None
        if baza is not None and k.get("type") == "delay":
            d = opoznienie_dni(k)
            baza = None if d is None else baza + d
        wynik[kid] = baza
        return baza

    for k in kroki:
        dzien(k)
    return wynik


def main():
    ap = argparse.ArgumentParser(description="Audyt MailerLite (tylko odczyt)")
    ap.add_argument("--dni", type=int, default=30, help="okres audytu kampanii w dniach (domyślnie 30; pełne 90 na prośbę)")
    ap.add_argument("--postep", default=None, help="plik postępu (domyślnie obok raportu: <raport>.postep.txt)")
    ap.add_argument("--plik-klucza", default="~/.config/audyt-mailingu/mailerlite.key", help="plik z tokenem, gdy nie ma zmiennej MAILERLITE_API_KEY")
    ap.add_argument("--bez-pamieci", action="store_true", help="nie używaj pamięci odpowiedzi API (pobierz wszystko od nowa)")
    ap.add_argument("--test-polaczenia", action="store_true", help="tylko sprawdź, czy token działa (jedno zapytanie), i zakończ")
    ap.add_argument("--raport", default="audyt-mailerlite.md")
    ap.add_argument("--json", default="")
    ap.add_argument("--pokaz", action="store_true", help="tryb pokazowy: bez tokena i bez internetu, na zmyślonych danych sklepu z herbatą")
    a = ap.parse_args()
    if a.dni < 1:
        sys.exit("--dni musi być co najmniej 1.")
    postep = Postep(a.postep or (os.path.splitext(a.raport)[0] + ".postep.txt"))
    if a.pokaz:
        from pokaz_ml import PokazML
        ml = PokazML()
    else:
        klucz = klucz_z_env_albo_pliku("MAILERLITE_API_KEY", a.plik_klucza)
        if not klucz:
            sys.exit("Brak tokena: nie ma zmiennej MAILERLITE_API_KEY ani pliku " + a.plik_klucza + ". Token: MailerLite → Integracje → MailerLite API → Wygeneruj nowy token. "
                     "Chcesz najpierw zobaczyć przykładowy raport bez tokena? Uruchom z --pokaz.")
        ml = ML(klucz, Pamiec("mailerlite", klucz, wlaczona=not a.bez_pamieci))
        if a.test_polaczenia:
            d = ml.get("/groups", {"limit": 1})
            print("Połączenie działa — token ma dostęp do konta (odczyt grup)." if d is not None else "API odpowiedziało, ale bez danych.")
            return
    dzis = dt.date.today()
    od = (dzis - dt.timedelta(days=a.dni)).isoformat()
    D = {"data_audytu": dzis.isoformat(), "okno_dni": a.dni, "od": od, "pokaz": a.pokaz}

    postep("1/5 grupy")
    D["grupy"] = sorted(({"nazwa": g.get("name"), "aktywni": int(liczba(g.get("active_count"))),
                          "wypisani": int(liczba(g.get("unsubscribed_count"))), "odbicia": int(liczba(g.get("bounced_count"))),
                          "spam": int(liczba(g.get("junk_count"))), "niepotwierdzeni": int(liczba(g.get("unconfirmed_count")))}
                         for g in ml.wszystkie("/groups")), key=lambda x: -x["aktywni"])

    postep("1/5 formularze")
    D["formularze"] = []
    for typ in ("popup", "embedded", "promotion"):
        for x in ml.wszystkie(f"/forms/{typ}"):
            odw, zap = int(liczba(x.get("opens_count"))), int(liczba(x.get("conversions_count")))
            konw = stawka(x, "conversion_rate") if odw else None
            uwagi = []
            if x.get("is_broken"):
                uwagi.append("zepsuty")
            if x.get("active") and zap == 0 and odw == 0:
                uwagi.append("włączony, ale bez wyświetleń i zapisów")
            elif odw >= 200 and konw is not None and konw < 1.0:
                uwagi.append(f"niska konwersja ({f(konw)})")
            D["formularze"].append({"nazwa": czysc(x.get("name")), "typ": typ, "aktywny": bool(x.get("active")),
                                    "wyswietlenia": odw, "zapisy": zap, "konwersja_proc": konw, "uwagi": uwagi})

    postep("2/5 ustawienia sprzedaży i sklepy")
    ust = (ml.get("/ecommerce/settings") or {}).get("data") or {}
    D["ustawienia"] = {"sledzenie_kampanie": ust.get("ecommerce_tracking_in_campaigns"),
                       "sledzenie_automaty": ust.get("ecommerce_tracking_in_automations"),
                       "okno_przypisania_dni": ust.get("ecommerce_attribution_window")}
    D["sklepy"] = []
    # Raport sklepu obejmuje najwyżej 365 dni wstecz (limit API); przy dłuższym okresie audytu — ostatnie 365 dni.
    od_sklep = max(od, (dzis - dt.timedelta(days=MAKS_DNI_RAPORTU_SKLEPU)).isoformat())
    D["sklep_od"] = od_sklep
    for s in ml.wszystkie("/ecommerce/shops"):
        # Pojedynczych zamówień NIE pobieramy: API MailerLite zwraca je z danymi kupującego i nie pozwala ograniczyć pól.
        # Bierzemy tylko raport zbiorczy sklepu (same liczby).
        sklep = {"nazwa": czysc(s.get("name")) or "—", "platforma": s.get("platform"), "wlaczony": s.get("enabled"),
                 "wewnetrzny": bool(s.get("internal")),  # sklep MailerLite zakładany automatycznie
                 "waluta": s.get("currency")}
        sklep.update(raport_sklepu(ml, s.get("id"), od_sklep, dzis.isoformat()))
        D["sklepy"].append(sklep)

    postep("3/5 automatyzacje")
    D["automaty"] = []
    for x in ml.wszystkie("/automations"):
        st = x.get("stats") or {}
        zak, kol = int(liczba(st.get("completed_subscribers_count"))), int(liczba(st.get("subscribers_in_queue_count")))
        wys = int(liczba(st.get("sent")))
        utw = str(x.get("created_at") or "")[:10]
        uwagi = []
        if x.get("broken"):
            uwagi.append("zepsuty (MailerLite oznacza go jako broken)")
        if not x.get("complete"):
            uwagi.append("niedokończony")
        for w in x.get("warnings") or []:
            uwagi.append("ostrzeżenie: " + czysc(w if isinstance(w, str) else json.dumps(w, ensure_ascii=False))[:80])
        if not x.get("stats"):
            uwagi.append("API nie podało statystyk")
        elif x.get("enabled") and zak + kol + wys == 0:
            mlody = utw and (dzis - dt.date.fromisoformat(utw)).days < 14
            uwagi.append("włączony < 14 dni, za wcześnie na ocenę" if mlody else "włączony, ale nikt do niego nie wszedł")
        sklep_jest = any(s["wlaczony"] and not s["wewnetrzny"] for s in D["sklepy"])
        if sklep_jest and not (x.get("trigger_data") or {}).get("track_ecommerce"):
            uwagi.append("bez śledzenia sprzedaży")
        maile = []
        dni_kroku = dni_krokow(x.get("steps") or [])
        for k in x.get("steps") or []:
            if k.get("type") != "email":
                continue
            e = k.get("email") or {}
            m = wyniki_maila(e.get("stats"))
            m["temat"] = czysc(k.get("subject") or e.get("subject"))
            m["dzien"] = None if dni_kroku.get(k.get("id")) is None else int(dni_kroku[k.get("id")])
            tresc = e.get("content") or e.get("html") or k.get("content") or e.get("plain_text") or ""
            if isinstance(tresc, dict):
                tresc = tresc.get("html") or tresc.get("plain") or ""
            m["klasa"], m["powod"] = klasyfikuj(m["temat"], tresc)
            if not tresc:
                m["powod"] += " — API nie podało treści, ocena tylko z tematu"
            m["problemy"] = problemy_maila(m)
            if k.get("has_unsubscribe_url") is False:
                m["problemy"].append("BRAK LINKU DO WYPISU")
            if k.get("has_unlinked_buttons"):
                m["problemy"].append("przycisk bez linku")
            if k.get("broken"):
                m["problemy"].append("mail zepsuty")
            maile.append(m)
        D["automaty"].append({"nazwa": czysc(x.get("name")) or "—", "wlaczony": bool(x.get("enabled")), "utworzony": utw,
                              "wyzwalacze": [t.get("type") for t in x.get("triggers") or []],
                              "kategoria": kategoria(x), "zakonczyli": zak, "w_kolejce": kol, "wyslane": wys,
                              "klikniecia_proc": stawka(st, "click_rate"), "wypisy_proc": stawka(st, "unsubscribe_rate"),
                              "uwagi": uwagi, "maile": maile})

    postep(f"4/5 kampanie z {a.dni} dni")
    D["kampanie"] = []
    D["kampanie_bez_daty"] = 0
    for c in ml.wszystkie("/campaigns", {"filter[status]": "sent"}):
        kiedy = str(c.get("finished_at") or c.get("started_at") or c.get("scheduled_for") or "")[:10]
        if not kiedy:
            D["kampanie_bez_daty"] += 1
            continue
        if kiedy < od:
            continue
        e = (c.get("emails") or [{}])[0]
        m = wyniki_maila(e.get("stats"))
        m.update({"temat": czysc(e.get("subject") or c.get("name")), "wyslany": kiedy,
                  "sledzi_sprzedaz": bool((c.get("settings") or {}).get("ecommerce_tracking"))})
        m["problemy"] = problemy_maila(m)
        D["kampanie"].append(m)
    D["kampanie"].sort(key=lambda x: x["wyslany"], reverse=True)

    D["seria_powitalna"] = []
    for x in D["automaty"]:
        if x["kategoria"] != "Powitanie" or not x["maile"]:
            continue
        poz = [{"temat": m["temat"], "dzien": m.get("dzien"), "wlaczony": x["wlaczony"], "wyslane": m["wyslane"],
                "otwarcia_proc": m["otwarcia_proc"], "klikniecia_proc": m["klikniecia_proc"],
                "klasa": m["klasa"], "powod": m["powod"]} for m in x["maile"]]
        poz.sort(key=lambda m: (m["dzien"] is None, m["dzien"] or 0))
        D["seria_powitalna"].append({"automat": x["nazwa"], "maile": poz, "wnioski": wniosek_serii(poz)})

    postep("5/5 lista kontrolna i raport")
    D["lista_kontrolna"] = []
    for k in LISTA:
        tr = [x for x in D["automaty"] if x["kategoria"] == k]
        if any(x["wlaczony"] and x["zakonczyli"] + x["w_kolejce"] + x["wyslane"] > 0 for x in tr):
            stan = "działa"
        elif tr:
            stan = "jest, ale nie działa (wyłączony albo nikt nie wchodzi)"
        elif k in ("Porzucony koszyk", "Drugi zakup / reaktywacja") and not any(s["wlaczony"] and not s["wewnetrzny"] for s in D["sklepy"]):
            stan = "brak (wymaga podłączonego sklepu)"
        else:
            stan = "brak"
        D["lista_kontrolna"].append({"automat": k, "stan": stan, "trafienia": [x["nazwa"] for x in tr][:3]})
    D["zapytan_api"] = ml.zapytan
    D["niedostepne"] = ml.niedostepne
    D["ostrzezenia"] = ml.ostrzezenia

    D = maskuj_wszystko(D)  # e-mail albo telefon wpisany w nazwę grupy, automatu czy temat → zamaskowany
    with open(a.raport, "w", encoding="utf-8") as plik:
        plik.write(raport(D))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as plik:
            json.dump(D, plik, ensure_ascii=False, indent=1)
    postep(f"Gotowe: {a.raport} ({ml.zapytan} zapytań do API)")


def tn(x):
    return "nieznane" if x is None else ("tak" if x else "nie")


def odm(n, jeden, kilka, wiele):
    if n == 1:
        return jeden
    return kilka if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else wiele


def f(x, suf="%"):
    return "—" if x is None else f"{str(x).replace('.', ',')}{suf}"


def zl(x):
    if x is None:
        return "—"
    try:
        return f"{float(x):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(x)


STOPKA_GWIAZDKA = "Audyt się przydał? Zostaw gwiazdkę: https://github.com/Autilos/audyt-mailingu albo krótką opinię: https://github.com/Autilos/audyt-mailingu/discussions/3"
STOPKA_RAPORTU = "To podstawowy audyt. Chcesz pełny audyt albo wdrożenie poprawek? Napisz do mnie: https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=raport#kontakt (Wojciech Nowak) albo wnowak@autilo.eu"

KLUCZ_LISTY = {"Powitanie": "powitanie_brak", "Porzucony koszyk": "koszyk_brak", "Po zakupie": "po_zakupie_brak",
               "Drugi zakup / reaktywacja": "drugi_zakup_brak"}


def sekcja_rekomendacji(D):
    k = {}
    for x in D["lista_kontrolna"]:
        if x["stan"] != "działa":
            k[KLUCZ_LISTY[x["automat"]]] = ""
            if x["automat"] == "Drugi zakup / reaktywacja":
                k["reaktywacja_brak"] = ""
    bez_wypisu = sum(1 for a in D["automaty"] for m in a["maile"] if "BRAK LINKU DO WYPISU" in m["problemy"])
    if bez_wypisu:
        k["brak_wypisu"] = f"{bez_wypisu} {odm(bez_wypisu, 'mail', 'maile', 'maili')}"
    zepsute = [a["nazwa"] for a in D["automaty"] if any(u.startswith("zepsuty") or u == "niedokończony" for u in a["uwagi"])]
    if zepsute:
        k["automat_zepsuty"] = "; ".join(zepsute[:3])
    martwe = [a["nazwa"] for a in D["automaty"] if "włączony, ale nikt do niego nie wszedł" in a["uwagi"]]
    if martwe:
        k["automat_martwy"] = "; ".join(martwe[:3])
    sklepy_wl = [s for s in D["sklepy"] if s["wlaczony"] and not s["wewnetrzny"]]
    if not sklepy_wl:
        k["brak_sklepu"] = ""
    puste = [s["nazwa"] for s in sklepy_wl if s.get("zamowienia") == 0]
    if puste:
        k["sklep_bez_zamowien"] = "; ".join(puste[:3])
    zywe = [m for a in D["automaty"] if a["wlaczony"] for m in a["maile"]] + D["kampanie"]
    if any(p.startswith("skargi") for m in zywe for p in m["problemy"]):
        k["skargi_spam"] = ""
    if any(p.startswith("dużo wypisów") for m in zywe for p in m["problemy"]):
        k["duzo_wypisow"] = ""
    if sklepy_wl and (D["ustawienia"].get("sledzenie_kampanie") is False or any(not x["sledzi_sprzedaz"] for x in D["kampanie"])):
        k["bez_sledzenia"] = ""
    n_tyg = len(D["kampanie"]) / (D["okno_dni"] / 7)
    if n_tyg > 3:
        k["za_czesto"] = ""
    elif n_tyg < 0.5 and not D.get("kampanie_bez_daty"):
        k["brak_newsletterow"] = ""
    fb = [x["nazwa"] for x in D.get("formularze") or [] if any("bez wyświetleń" in u or u == "zepsuty" for u in x["uwagi"])]
    if fb:
        k["formularz_bez_ruchu"] = "; ".join(fb[:3])
    fn = [x["nazwa"] for x in D.get("formularze") or [] if any(u.startswith("niska") for u in x["uwagi"])]
    if fn:
        k["formularz_niska_konwersja"] = "; ".join(fn[:3])
    serie, dobre = [], []
    for g in D.get("seria_powitalna") or []:
        rs = rekomendacja_serii(g["maile"])
        (serie.append((rs[0], rs[1], g["automat"])) if rs else dobre.append(g["automat"]))
    lista = uloz(k, serie)
    D["_rekomendacje"] = lista
    L = ["## Rekomendacje — co zrobić i w jakiej kolejności", "",
         "Kolejność: najpierw dane (bez nich automaty nie działają), potem dostarczalność, potem automaty od najbardziej dochodowych. Rekomendacje dotyczą tylko tego, co wykrył audyt.", ""]
    for i, (tyt, tresc, szcz) in enumerate(lista, 1):
        L.append(f"{i}. **{tyt}**" + (f" ({szcz})" if szcz else "") + f". {tresc}")
    if dobre:
        L.append(f"{len(lista) + 1}. **Seria powitalna wygląda dobrze** ({', '.join(dobre)}) — ma kilka maili i łączy ofertę z treścią. Nie zmieniaj jej bez testu.")
    if not lista and not dobre:
        L.append("Audyt nie wykrył problemów, które wymagają zmian.")
    return L + [""]


def okres_sklepu(D):
    od = D.get("sklep_od") or D["od"]
    return f"od {od} do {D['data_audytu']}" + (" (MailerLite podaje raport sklepu najwyżej za 365 dni)" if od != D["od"] else "")


def kwota(x, waluta):
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "—"
    t = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    if t.endswith(",00"):
        t = t[:-3]
    return f"{t} {waluta or ''}".strip()


def linie_sklepu(s, D):
    if s.get("zamowienia") is None:
        return [f"- Raport sprzedaży sklepu: API go nie podało (funkcja może nie wchodzić w plan) — liczby zamówień i przychodu sprawdź w panelu: E-commerce."]
    w = s.get("waluta")
    n = s["zamowienia"]
    L = [f"- Zamówienia przesłane do MailerLite ({okres_sklepu(D)}): **{zl(n)}**, przychód: **{kwota(s.get('przychod'), w)}**"
         + (f", średnie zamówienie: {kwota(s.get('srednie_zamowienie'), w)}" if n and s.get("srednie_zamowienie") is not None else "") + "."]
    zk, za = s.get("z_kampanii_zamowienia"), s.get("z_automatow_zamowienia")
    if zk is not None or za is not None:
        zm = (zk or 0) + (za or 0)
        okno = (D.get("ustawienia") or {}).get("okno_przypisania_dni")
        L.append(f"- Przypisane do maili (zakup po kliknięciu w mail" + (f", do {okno} dni po kliknięciu" if okno else "") + f"): **{zl(zm)}** {odm(zm, 'zamówienie', 'zamówienia', 'zamówień')} na {kwota((s.get('z_kampanii_przychod') or 0) + (s.get('z_automatow_przychod') or 0), w)} — "
                 f"z kampanii {zl(zk or 0)} ({kwota(s.get('z_kampanii_przychod') or 0, w)}), z automatów {zl(za or 0)} ({kwota(s.get('z_automatow_przychod') or 0, w)}).")
    if n == 0 and not s["wewnetrzny"] and s["wlaczony"]:
        L.append("- Zero zamówień przy podłączonym sklepie: jeśli sklep w tym czasie sprzedawał, integracja najpewniej nie przesyła zamówień. Zrób zamówienie testowe i sprawdź, czy pojawi się w MailerLite (E-commerce → zamówienia).")
    return L


def raport(D):
    L = [f"# Audyt e-mail marketingu — MailerLite ({D['data_audytu']})", ""]
    if D.get("pokaz"):
        L += ["> **Raport pokazowy — dane zmyślone.** Fikcyjny sklep z herbatą, bez połączenia z żadnym kontem. Tak wygląda raport z prawdziwego konta.", ""]
    L += [f"Okres audytu kampanii: ostatnie {D['okno_dni']} dni (od {D['od']}). Tylko odczyt, wyłącznie statystyki, ustawienia i treść maili — bez danych osobowych.", ""]
    naj = []
    brak = [x for x in D["lista_kontrolna"] if x["stan"] != "działa"]
    if brak:
        naj.append(f"Brakuje albo nie działa {len(brak)} z {len(D['lista_kontrolna'])} podstawowych automatów: "
                   + ", ".join(x["automat"].lower() for x in brak) + ".")
    bez_wypisu = sum(1 for a in D["automaty"] for m in a["maile"] if "BRAK LINKU DO WYPISU" in m["problemy"])
    if bez_wypisu:
        naj.append(f"{bez_wypisu} {odm(bez_wypisu, 'mail w automatach nie ma', 'maile w automatach nie mają', 'maili w automatach nie ma')} linku do wypisu — to wymóg prawny i sygnał spamu dla Gmaila. Popraw w pierwszej kolejności.")
    zepsute = [a for a in D["automaty"] if any(u.startswith("zepsuty") or u == "niedokończony" for u in a["uwagi"])]
    if zepsute:
        naj.append(f"{len(zepsute)} {odm(len(zepsute), 'automat jest zepsuty albo niedokończony', 'automaty są zepsute albo niedokończone', 'automatów jest zepsutych albo niedokończonych')}: " + ", ".join(a["nazwa"] for a in zepsute[:3]) + ".")
    martwe = [a for a in D["automaty"] if "włączony, ale nikt do niego nie wszedł" in a["uwagi"]]
    if martwe:
        naj.append(f"{len(martwe)} {odm(len(martwe), 'automat jest włączony', 'automaty są włączone', 'automatów jest włączonych')}, ale nikt do {odm(len(martwe), 'niego', 'nich', 'nich')} nie wszedł — sprawdź wyzwalacz.")
    sklepy_wl = [s for s in D["sklepy"] if s["wlaczony"] and not s["wewnetrzny"]]
    if not sklepy_wl:
        naj.append("API nie pokazuje żadnego podłączonego zewnętrznego sklepu — porzucony koszyk, przypomnienie o ponownym zakupie i liczenie sprzedaży z maili nie mają danych. "
                   "Jeśli masz sklep (np. WooCommerce, Shopify), podłącz go w MailerLite: Integracje → e-commerce.")
    for s in sklepy_wl:
        if s.get("zamowienia") == 0:
            naj.append(f"Sklep „{s['nazwa']}” jest podłączony, ale MailerLite nie ma z niego żadnego zamówienia w okresie {okres_sklepu(D)}. "
                       "Jeśli sklep w tym czasie sprzedawał, integracja najpewniej nie przesyła zamówień — a bez nich nie działają porzucony koszyk, maile po zakupie i liczenie przychodu z maili.")
    u = D["ustawienia"]
    if sklepy_wl and u.get("sledzenie_kampanie") is False:
        naj.append("Nowe kampanie mają domyślnie wyłączone liczenie sprzedaży — nie wiesz, ile zarabia każdy newsletter. Włącz w ustawieniach e-commerce.")
    kp = D["kampanie"]
    n_tyg = len(kp) / (D["okno_dni"] / 7)
    if not kp and not D.get("kampanie_bez_daty"):
        naj.append(f"W ostatnich {D['okno_dni']} dniach nie wyszła żadna kampania (newsletter).")
    elif n_tyg > 3:
        naj.append(f"Kampanie: średnio {n_tyg:.1f} tygodniowo — ryzyko zmęczenia bazy.".replace(".", ",", 1))
    L += ["## Najważniejsze", ""] + [f"{i}. {t}" for i, t in enumerate(naj or ["Nie znaleziono poważnych problemów w danych dostępnych przez API."], 1)] + [""]
    D["_najwazniejsze"] = naj
    L += sekcja_rekomendacji(D)

    L += ["## Lista kontrolna automatów sklepu", "", "| Automat | Stan | Znalezione |", "|---|---|---|"]
    for x in D["lista_kontrolna"]:
        ik = "✅" if x["stan"] == "działa" else ("⚠️" if x["stan"].startswith("jest") or "wymaga" in x["stan"] else "❌")
        L.append(f"| {x['automat']} | {ik} {x['stan']} | {'; '.join(x['trafienia']) or '—'} |")
    L += ["", "Rozpoznanie po wyzwalaczu automatu (koszyk, zakup, częstotliwość zakupów); przy wyzwalaczach ogólnych (formularz, grupa) — po nazwie. "
          "Automatu „porzucone przeglądanie” MailerLite nie oferuje, więc go nie sprawdzamy.", "Porzucony koszyk i maile po zakupie może wysyłać sam sklep albo inny serwis (maile transakcyjne sklepu, wtyczka). Jeśli tak jest, brak takiego automatu tutaj nie jest problemem — nie warto go dublować.", ""]

    L += ["## Automatyzacje", "", "| Automat | Wyzwalacz | Włączony | Zakończyli | W kolejce | Wysłane | Kliknięcia | Uwagi |", "|---|---|---|---|---|---|---|---|"]
    for x in sorted(D["automaty"], key=lambda x: (not x["wlaczony"], -x["wyslane"])):
        L.append(f"| {x['nazwa']} | {', '.join(x['wyzwalacze']) or '—'} | {'tak' if x['wlaczony'] else 'nie'} | {zl(x['zakonczyli'])} | {zl(x['w_kolejce'])} | {zl(x['wyslane'])} | {f(x['klikniecia_proc'])} | {'; '.join(x['uwagi'])} |")
    L += ["", "### Maile w automatach", "", "Otwarcia w MailerLite obejmują też automatyczne otwarcia programów pocztowych — oceniaj po kliknięciach.", "",
          "| Automat | Temat | Wysłane | Otwarcia | Kliknięcia | Wypisy | Problemy |", "|---|---|---|---|---|---|---|"]
    for x in D["automaty"]:
        for m in x["maile"]:
            L.append(f"| {x['nazwa']} | {m['temat'] or '—'} | {zl(m['wyslane'])} | {f(m['otwarcia_proc'])} | {f(m['klikniecia_proc'])} | {f(m['wypisy_proc'])} | {', '.join(m['problemy'])} |")
    L += [""]

    L += ["## Seria powitalna (sprzedażowe vs wartościowe)", "",
          "Podział to **ocena po słowach i elementach maila — może się pomylić**. Liczona z tematu i treści maila (kod rabatowy, procent, kwota, „kup/zamów/promocja”, link do produktu lub koszyka = sprzedaż; poradnik, historia marki, opinie, dłuższy tekst = wartość). Może się mylić — zwłaszcza przy mailach złożonych z samych obrazków. "
          "Dzień liczony z kroków opóźnienia w automacie; po rozgałęzieniu — nieznany.", ""]
    if not D.get("seria_powitalna"):
        L += ["Nie znaleziono automatu powitalnego z mailami.", ""]
    for g in D.get("seria_powitalna") or []:
        L += [f"**{g['automat']}**", ""] + [f"- {w}" for w in g["wnioski"]] + ["",
              "| Dzień | Temat | Wysłane | Otwarcia | Kliknięcia | Klasa | Dlaczego |", "|---|---|---|---|---|---|---|"]
        for m in g["maile"]:
            L.append(f"| {'—' if m['dzien'] is None else m['dzien']} | {m['temat'] or '—'} | {zl(m['wyslane'])} | {f(m['otwarcia_proc'])} | {f(m['klikniecia_proc'])} | {m['klasa'].lower()} | {m['powod']} |")
        L += [""]

    L += [f"## Kampanie — ostatnie {D['okno_dni']} dni", ""]
    if kp:
        L += [f"- Wysłanych kampanii: **{len(kp)}** (średnio {n_tyg:.1f} tygodniowo).".replace(".", ",", 1),
              f"- Z liczeniem sprzedaży: {sum(1 for x in kp if x['sledzi_sprzedaz'])} z {len(kp)}.", "",
              "| Data | Temat | Wysłane | Kliknięcia | Wypisy | Problemy |", "|---|---|---|---|---|---|"]
        for x in kp[:25]:
            L.append(f"| {x['wyslany']} | {x['temat']} | {zl(x['wyslane'])} | {f(x['klikniecia_proc'])} | {f(x['wypisy_proc'])} | {', '.join(x['problemy'] + ([] if x['sledzi_sprzedaz'] else ['bez liczenia sprzedaży']))} |")
    else:
        L.append("Brak wysłanych kampanii w tym okresie.")
    if D.get("kampanie_bez_daty"):
        L.append(f"Uwaga: {D['kampanie_bez_daty']} wysłanych kampanii nie ma daty w API — pominięte w zestawieniu.")
    L += [""]

    L += ["## Baza kontaktów (stan na dziś)", ""]
    if D["grupy"]:
        L += ["| Grupa | Aktywni | Wypisani | Odbicia | Spam | Niepotwierdzeni |", "|---|---|---|---|---|---|"]
        for g in D["grupy"][:20]:
            L.append(f"| {g['nazwa']} | {zl(g['aktywni'])} | {zl(g['wypisani'])} | {zl(g['odbicia'])} | {zl(g['spam'])} | {zl(g['niepotwierdzeni'])} |")
        L += ["", "Jedna osoba może być w kilku grupach, więc sum nie dodawaj. Przyrostu i odpływu w czasie (dzień po dniu, źródła zapisów) API MailerLite nie udostępnia — zobacz w panelu: Subskrybenci → statystyki.", ""]
    else:
        L += ["Brak grup.", ""]
    L += ["## Formularze zapisu", ""]
    if D.get("formularze"):
        L += ["| Formularz | Typ | Włączony | Wyświetlenia | Zapisy | Konwersja | Uwagi |", "|---|---|---|---|---|---|---|"]
        for x in sorted(D["formularze"], key=lambda x: -x["wyswietlenia"])[:20]:
            L.append(f"| {x['nazwa']} | {x['typ']} | {'tak' if x['aktywny'] else 'nie'} | {zl(x['wyswietlenia'])} | {zl(x['zapisy'])} | {f(x['konwersja_proc'])} | {', '.join(x['uwagi'])} |")
        L += ["", "Wyświetlenia formularzy osadzonych MailerLite liczy tylko w niektórych przypadkach — przy zerze wyświetleń i zapisach > 0 konwersja jest nieznana. Próg niskiej konwersji (poniżej 1% przy co najmniej 200 wyświetleniach) to orientacyjna granica z praktyki.", ""]
    else:
        L += ["Brak formularzy.", ""]
    L += ["## Dostarczalność", "", "Statusu domeny nadawcy (DKIM, SPF, DMARC) audyt nie sprawdza: MailerLite pokazuje go tylko w danych konta, razem z adresem firmy, a ten audyt nie czyta takich danych. Zobacz w panelu: Ustawienia → Domeny.", ""]

    L += ["## Sklep i liczenie sprzedaży", "",
          f"- Liczenie sprzedaży w nowych kampaniach: **{tn(u.get('sledzenie_kampanie'))}**, w nowych automatach: **{tn(u.get('sledzenie_automaty'))}**, czas przypisania sprzedaży: {u.get('okno_przypisania_dni') or '—'} dni po kliknięciu."]
    for s in D["sklepy"]:
        L.append(f"- Sklep „{s['nazwa']}” ({'wewnętrzny sklep MailerLite' if s['wewnetrzny'] else s['platforma']}, {'włączony' if s['wlaczony'] else 'wyłączony'}).")
        L += linie_sklepu(s, D)
    if D["sklepy"]:
        L.append("- Liczby pochodzą z raportu zbiorczego sklepu w MailerLite. **Pojedynczych zamówień audyt nie pobiera**: API MailerLite zwraca je razem z danymi kupującego (e-mail, imię) i nie pozwala ograniczyć pól, a ten audyt nie czyta danych osobowych. "
                 "Przychód przypisany do maili to sprzedaż po kliknięciu w mail, a nie cały przychód sklepu. Przychód z poszczególnych kampanii i automatów zobaczysz w panelu: raporty kampanii i automatów (kolumna przychodu).")
    if not D["sklepy"]:
        L.append("- Brak podłączonego sklepu.")
    L += ["", "## Czego ten audyt nie widzi", "",
          "- Czy oferta w mailach ma sens — treść maili służy tylko do podziału serii powitalnej na sprzedażowe i wartościowe.",
          "- Pojedynczych zamówień i przychodu z poszczególnych kampanii czy automatów — widzimy tylko liczby zbiorcze sklepu (API zwraca zamówienia z danymi kupującego, więc ich nie pobieramy).",
          "- Statusu domeny nadawcy i przyrostu bazy w czasie.",
          "- Progi w kolumnie „Problemy” (wypisy > 0,5%, kliknięcia < 0,5%, odbicia > 2%, ocena od 200 wysłanych) to orientacyjne granice z praktyki. Skargi: Google wymaga poniżej 0,3% i zaleca poniżej 0,1%.", ""]
    if D.get("niedostepne"):
        L += ["**Niedostępne na tym koncie (403/404 — funkcja może nie wchodzić w plan):** " + ", ".join(f"`{x}`" for x in D["niedostepne"][:8]), ""]
    if D.get("ostrzezenia"):
        L += ["**Ostrzeżenia:**", ""] + [f"- {x}" for x in D["ostrzezenia"]] + [""]
    L += [f"_Zapytań do API: {D['zapytan_api']}._", ""]
    L += sekcja_dla_ai(D.get("_najwazniejsze") or [], D.get("_rekomendacje") or [], ["Pojedynczych zamówień i przychodu z poszczególnych kampanii i automatów (widzimy tylko liczby zbiorcze sklepu).", "Statusu domeny nadawcy i przyrostu bazy w czasie.", "Czy oferta w mailach ma sens — treść maili służy tylko do podziału serii powitalnej."])
    L += ["---", "", STOPKA_RAPORTU, "", STOPKA_GWIAZDKA, ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
