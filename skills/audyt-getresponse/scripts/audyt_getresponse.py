#!/usr/bin/env python3
"""Audyt e-mail marketingu w GetResponse — TYLKO ODCZYT.

Sprawdza: automatyzacje (czy działają, czy ktoś przez nie przechodzi), maile z automatów,
newslettery z ostatnich N dni, sklep (zamówienia, ile bez kontaktu, przychód przypisany do maili)
i listę kontrolną automatów, które powinien mieć każdy sklep internetowy.

Nie zmienia niczego na koncie. Wywołuje wyłącznie zapytania GET.
Nie zapisuje adresów e-mail ani danych osobowych — tylko liczby zbiorcze.

Użycie:
  export GETRESPONSE_API_KEY=...            # Menu → Integracje i API → API
  python3 audyt_getresponse.py --dni 90 --raport raport.md --json dane.json

GetResponse MAX: dodaj --max-domena twojadomena.pl oraz --api https://api3.getresponse360.pl/v3
(albo https://api3.getresponse360.com/v3 — zależnie od środowiska konta).
"""
import argparse
import http.client
import re
import socket
import datetime as dt
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seria_powitalna import klasyfikuj, wniosek_serii  # noqa: E402
from rekomendacje import rekomendacja_serii, uloz  # noqa: E402

PRZERWA = 0.3  # s między zapytaniami; limit GR to 80/s, ale w praktyce ~4/s bez 429
MAX_STRON_ZAMOWIEN = 120  # 120 × 500 zamówień — bezpiecznik dla bardzo dużych sklepów
# Klucz idzie wyłącznie do oficjalnych adresów API GetResponse (zwykłe konto i GetResponse MAX).
DOZWOLONE_API = ("https://api.getresponse.com/v3", "https://api3.getresponse360.pl/v3", "https://api3.getresponse360.com/v3")


class _BezPrzekierowan(urllib.request.HTTPRedirectHandler):
    """Przekierowanie = błąd. urllib przy przekierowaniu wysyła nagłówki (z kluczem) pod nowy adres."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OTWIERACZ = urllib.request.build_opener(_BezPrzekierowan)

# Zero danych osobowych: skrypt może czytać WYŁĄCZNIE te ścieżki (statystyki, ustawienia, treść maili).
# Celowo brak /contacts, /contacts/{id}, /shops/{id}/carts, /accounts (dane właściciela) itp.
DOZWOLONE_SCIEZKI = [re.compile(x) for x in (
    r"^/campaigns$", r"^/campaigns/statistics/(list-size|subscriptions|removals)$",
    r"^/workflow$", r"^/workflow/[A-Za-z0-9]+$",
    r"^/newsletters$", r"^/newsletters/[A-Za-z0-9]+$", r"^/newsletters/[A-Za-z0-9]+/statistics$",
    r"^/autoresponders$", r"^/autoresponders/[A-Za-z0-9]+$", r"^/autoresponders/[A-Za-z0-9]+/statistics$",
    r"^/shops$", r"^/shops/[A-Za-z0-9]+/orders$",
    r"^/statistics/ecommerce/(performance|revenue)$",
    r"^/forms$", r"^/from-fields$",
)]
# Zamówienia: tylko te pola (bez danych kupującego). contactId = sam identyfikator, liczymy tylko, czy jest.
POLA_ZAMOWIEN = {"orderId", "totalPrice", "processedAt", "contactId", "status"}


def sciezka_dozwolona(sciezka, params=None):
    if not any(r.match(sciezka) for r in DOZWOLONE_SCIEZKI):
        return False
    if re.match(r"^/shops/[^/]+/orders$", sciezka):
        pola = set(str((params or {}).get("fields") or "").split(","))
        return bool(pola) and pola <= POLA_ZAMOWIEN
    return True

# Automaty, które powinien mieć sklep internetowy. Wykrywane po NAZWIE automatu i tematach maili —
# API GetResponse nie pokazuje warunków ani wyzwalaczy automatu, więc „nie znaleziono” = sprawdź w panelu.
LISTA_KONTROLNA = [
    ("Powitanie nowego subskrybenta", ["powital", "powitan", "welcome", "witaj", "po zapisie", "za zapis", "nowy subskrybent", "onboard"]),
    ("Porzucony koszyk", ["koszyk", "cart", "porzuc"]),
    ("Po zakupie (podziękowanie, opinia, kolejny produkt)", ["po zakup", "post-purchase", "postpurchase", "dziękujemy za zakup", "dziękujemy za zamówienie", "opini", "recenz"]),
    ("Porzucone przeglądanie (oglądał produkt, nie dodał do koszyka)", ["porzucone przegląd", "porzucone przeglad", "przeglądał", "przegladal", "oglądany produkt", "ogladany produkt", "odwiedzony produkt", "odwiedzone produkty", "browse abandon", "browse", "oglądał", "ogladal"]),
    ("Drugi / ponowny zakup (przypomnienie o uzupełnieniu)", ["ponown", "drugi zakup", "drugie zamów", "kolejne zamów", "kolejny zakup", "po 1. zakup", "po pierwszym zakup", "replenish", "uzupełn", "uzupeln", "dokup"]),
    ("Reaktywacja nieaktywnych klientów", ["reaktyw", "win-back", "winback", "tęsknimy", "tesknimy", "wróć do nas", "wroc do nas", "dawno cię", "dawno cie", "dawno nie"]),
]


class GR:
    def __init__(self, klucz, api, max_domena=None):
        self.api = api.rstrip("/")
        self.h = {"X-Auth-Token": "api-key " + klucz, "Accept": "application/json"}
        if max_domena:
            self.h["X-Domain"] = max_domena
        self.zapytan = 0
        self.niedostepne = []  # endpointy z 404 — funkcja niedostępna na koncie/planie
        self.ostrzezenia = []

    def get(self, sciezka, params=None, opcjonalny=False):
        url = self.api + sciezka
        if self.api not in DOZWOLONE_API:
            sys.exit("Nieoczekiwany adres API — przerwano, klucz nie zostanie wysłany.")
        if not sciezka_dozwolona(sciezka, params):
            sys.exit(f"Ścieżka spoza listy dozwolonych ({sciezka}) — przerwano. Audyt nie czyta danych osobowych.")
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="[]")
        for proba in range(5):
            time.sleep(PRZERWA)
            self.zapytan += 1
            try:
                r = _OTWIERACZ.open(urllib.request.Request(url, headers=self.h), timeout=240)
                surowe = r.read() or b"null"
                try:
                    return json.loads(surowe), {k.lower(): v for k, v in r.headers.items()}
                except ValueError:
                    sys.exit(f"API zwróciło odpowiedź, która nie jest JSON-em ({sciezka}). Sprawdź adres --api i połączenie (proxy, zapora).")
            except (socket.timeout, TimeoutError, http.client.IncompleteRead, ConnectionError):
                if proba < 4:
                    print("  serwer odpowiada wolno — ponawiam", file=sys.stderr)
                    time.sleep(5 * (proba + 1))
                    continue
                raise
            except urllib.error.HTTPError as e:
                if 300 <= e.code < 400:
                    sys.exit(f"API odpowiedziało przekierowaniem ({e.code}, {sciezka}) — przerwano, klucz nie został wysłany pod inny adres.")
                if e.code == 429:
                    czekaj = int(e.headers.get("X-RateLimit-Reset") or 30)
                    print(f"  limit zapytań — czekam {czekaj} s", file=sys.stderr)
                    time.sleep(min(czekaj, 600))
                    continue
                if e.code == 403 and opcjonalny:
                    if sciezka not in self.niedostepne:
                        self.niedostepne.append(sciezka + " (brak uprawnień klucza)")
                    return None, {"_403": True}
                if e.code in (401, 403):
                    sys.exit(f"Błąd {e.code}: klucz API nieprawidłowy, wygasł albo nie ma dostępu ({sciezka}).")
                if e.code == 404:
                    if sciezka not in self.niedostepne:
                        self.niedostepne.append(sciezka)
                    return None, {"_404": True}
                if e.code >= 500 and proba < 4:
                    time.sleep(3 * (proba + 1))
                    continue
                raise
            except urllib.error.URLError:
                if proba < 4:
                    time.sleep(3 * (proba + 1))
                    continue
                raise
        sys.exit(f"API GetResponse nie odpowiedziało po 5 próbach ({sciezka}) — przerwano, żeby raport nie był oparty na brakujących danych. Uruchom ponownie za kilka minut.")

    def wszystkie(self, sciezka, params=None, per_page=100, max_stron=50, opcjonalny=False):
        wynik = []
        for strona in range(1, max_stron + 1):
            p = dict(params or {}, perPage=per_page, page=strona)
            d, h = self.get(sciezka, p, opcjonalny=opcjonalny)
            if not d:
                break
            wynik += d
            if "totalpages" not in h:
                if len(d) >= per_page:
                    self.ostrzezenia.append(f"{sciezka}: API nie podało liczby stron — pobrano tylko pierwszą stronę ({len(d)} pozycji).")
                break
            if strona >= int(h["totalpages"]):
                break
        else:
            self.ostrzezenia.append(f"{sciezka}: pobrano maksymalnie {max_stron * per_page} pozycji — reszta pominięta.")
        return wynik


def liczba(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def proc(a, b):
    return round(100.0 * a / b, 2) if b else None


def stat_maila(gr, nid):
    d, _ = gr.get(f"/newsletters/{nid}/statistics", {"query[groupBy]": "total"})
    s = (d or [{}])[0] if isinstance(d, list) else {}
    wys = liczba(s.get("sent"))
    return {
        "wyslane": int(wys),
        "otwarcia_ludzi_proc": proc(liczba(s.get("uniqueHumanOpened")), wys),
        "klikniecia_ludzi_proc": proc(liczba(s.get("uniqueHumanClicked")), wys),
        "wypisy_proc": proc(liczba(s.get("unsubscribed")), wys),
        "skargi_proc": proc(liczba(s.get("complaints")), wys),
        "odbicia_proc": proc(liczba(s.get("bounced")), wys),
        "okres": s.get("timeInterval", ""),
    }


def problemy_maila(m):
    p = []
    if m["wyslane"] == 0:
        p.append("nigdy nie wysłany")
        return p
    if m["wyslane"] >= 200:
        if (m["wypisy_proc"] or 0) > 0.5:
            p.append("dużo wypisów " + f(m["wypisy_proc"]))
        if (m["skargi_proc"] or 0) >= 0.3:
            p.append("skargi na spam " + f(m["skargi_proc"]) + " — przekroczony próg Google 0,3%")
        elif (m["skargi_proc"] or 0) > 0.1:
            p.append("skargi na spam " + f(m["skargi_proc"]) + " — powyżej zalecanych przez Google 0,1%")
        if (m["odbicia_proc"] or 0) > 2:
            p.append("odbicia " + f(m["odbicia_proc"]))
        if m["klikniecia_ludzi_proc"] is not None and m["klikniecia_ludzi_proc"] < 0.5:
            p.append("prawie nikt nie klika (" + f(m["klikniecia_ludzi_proc"]) + ")")
    if not m.get("liczy_przychod"):
        p.append("bez śledzenia e-commerce")
    if "bez tytułu" in (m.get("nazwa") or "").lower() or "untitled" in (m.get("nazwa") or "").lower():
        p.append("nazwa robocza")
    return p


def czysc(t):
    """[[firstname fallback=…]] → „…” — temat czytelny w raporcie."""
    t = unicodedata.normalize("NFKC", str(t) if t else "")  # „𝗘𝗸𝘀𝗸𝗹𝘂𝘇𝘆𝘄𝗻𝘆” → „Ekskluzywny”
    return re.sub(r"\[\[[^\]]*\]\]", "…", t).strip()


def dopasuj(tekst, slowa):
    t = czysc(tekst).lower()
    return any(s in t for s in slowa)


def suma_pola(d, pole):
    """Sumuje liczbowe pole w odpowiedzi statystyk (lista wierszy albo słownik lista→wiersze)."""
    if isinstance(d, dict):
        return sum(suma_pola(v, pole) for v in d.values())
    if isinstance(d, list):
        return sum(liczba(x.get(pole)) if isinstance(x, dict) else 0 for x in d)
    return 0


def sumy_zrodel(d):
    """{lista: {"total": {źródło: n}}} albo listy wierszy → {źródło: suma}."""
    wynik = {}
    def dodaj(w):
        for k, v in (w or {}).items():
            if isinstance(v, (int, float)) and k != "createdOn":
                wynik[k] = wynik.get(k, 0) + v
            elif isinstance(v, dict):
                dodaj(v)
    if isinstance(d, dict):
        for v in d.values():
            for w in (v if isinstance(v, list) else [v]):
                dodaj(w if isinstance(w, dict) else {})
    elif isinstance(d, list):
        for w in d:
            dodaj(w if isinstance(w, dict) else {})
    return wynik


def zdrowie_bazy(gr, ids, od, dzis):
    """Przyrost, odpływ (z powodami) i źródła zapisów w oknie — wyłącznie liczby zbiorcze."""
    if not ids:
        return None
    q = {"query[campaignId]": ",".join(ids), "query[groupBy]": "total",
         "query[createdOn][from]": od.isoformat(), "query[createdOn][to]": dzis.isoformat()}
    ls, _ = gr.get("/campaigns/statistics/list-size", q, opcjonalny=True)
    zap, _ = gr.get("/campaigns/statistics/subscriptions", q, opcjonalny=True)
    usu, _ = gr.get("/campaigns/statistics/removals", q, opcjonalny=True)
    if ls is None and zap is None and usu is None:
        return None
    zr = sumy_zrodel(zap)
    zr.pop("summary", None)
    pw = sumy_zrodel(usu)
    pw.pop("summary", None)
    return {"dodani": int(suma_pola(ls, "addedSubscribers")), "usunieci": int(suma_pola(ls, "removedSubscribers")),
            "zrodla": {k: int(v) for k, v in sorted(zr.items(), key=lambda x: -x[1]) if v},
            "powody_usuniec": {k: int(v) for k, v in sorted(pw.items(), key=lambda x: -x[1]) if v}}


PROG_KONWERSJI_FORMULARZA = 1.0   # % zapisów z odwiedzin — orientacyjny próg praktyczny, nie norma
MIN_ODWIEDZIN_FORMULARZA = 200


def formularze(gr):
    """Formularze zapisu: odwiedziny, zapisy, konwersja (statystyki, bez kontaktów). None = brak dostępu."""
    lista = gr.wszystkie("/forms", {"fields": "formId,name,status,visitors,uniqueVisitors,subscribed,subscriptionRate,createdOn"},
                         opcjonalny=True)
    if any(x.startswith("/forms") for x in gr.niedostepne):
        return None
    wynik = []
    for x in lista:
        odw, zap = int(liczba(x.get("visitors"))), int(liczba(x.get("subscribed")))
        konw = liczba(x.get("subscriptionRate")) if x.get("subscriptionRate") is not None else proc(zap, odw)
        aktywny = (x.get("status") or "") in ("enabled", "published", "active")
        uwagi = []
        if aktywny and odw == 0:
            uwagi.append("włączony, ale bez odwiedzin")
        elif odw >= MIN_ODWIEDZIN_FORMULARZA and konw is not None and konw < PROG_KONWERSJI_FORMULARZA:
            uwagi.append(f"niska konwersja ({f(round(konw, 2))})")
        wynik.append({"nazwa": czysc(x.get("name")), "status": x.get("status"), "odwiedziny": odw, "zapisy": zap,
                      "konwersja_proc": None if konw is None else round(konw, 2), "uwagi": uwagi})
    return sorted(wynik, key=lambda x: -x["odwiedziny"])


def nadawcy(gr):
    """Adresy nadawcy (dane firmy): status domeny, ostrzeżenia DKIM i DMARC. Zapisujemy tylko domenę."""
    d, _ = gr.get("/from-fields", opcjonalny=True)
    if d is None:
        return None
    wynik = []
    for x in d:
        dom = x.get("domain") if isinstance(x.get("domain"), dict) else {}
        aktywny = str(x.get("isActive")).lower() == "true"
        domena = (str(x.get("email") or "").split("@")[-1] or "—").lower()
        uwagi = []
        if aktywny and (dom.get("status") or "") not in ("confirmed", ""):
            uwagi.append(f"domena niepotwierdzona (status: {dom.get('status')})")
        if aktywny and dom.get("DKIMWarning"):
            uwagi.append(f"ostrzeżenie DKIM — {DKIM.get(dom.get('DKIMWarning'), dom.get('DKIMWarning'))}")
        if aktywny and str(dom.get("hasDMARCWarning")).lower() == "true":
            uwagi.append("ostrzeżenie DMARC")
        wynik.append({"domena": domena, "aktywny": aktywny, "domyslny": str(x.get("isDefault")).lower() == "true",
                      "status_domeny": dom.get("status"), "dkim": dom.get("DKIMWarning"),
                      "dmarc_ostrzezenie": str(dom.get("hasDMARCWarning")).lower() == "true", "uwagi": uwagi})
    return wynik


MAX_MAILI_SERII = 20  # ile treści maili pobrać do klasyfikacji (każdy = 1 zapytanie)


def seria(gr, D):
    """Seria powitalna: klasyczne autorespondery (cykl od dnia zapisu, grupowane po liście) oraz maile
    z automatów o nazwie/temacie powitalnym. Każdy mail klasyfikowany heurystycznie z tematu i treści HTML."""
    slowa = LISTA_KONTROLNA[0][1]
    grupy = {}
    for x in D["autorespondery"]:
        if x["wyslane"] == 0 and x["status"] != "enabled":
            continue
        grupy.setdefault(("autorespondery", x.get("lista") or "—"), []).append(x)
    for x in D["maile_automatow"]:
        if x.get("typ") == "automat" and dopasuj((x["nazwa"] or "") + " " + (x["temat"] or ""), slowa) \
                and not (x["wyslane"] == 0 and x["status"] != "enabled"):
            grupy.setdefault(("automat", ""), []).append(x)
    wynik, pobrane = [], 0
    for (zrodlo, lista), maile in sorted(grupy.items(), key=lambda kv: -sum(m["wyslane"] for m in kv[1])):
        maile.sort(key=lambda m: (m.get("dzien_cyklu") is None, m.get("dzien_cyklu") or 0, -m["wyslane"]))
        pozycje = []
        for m in maile:
            html_tresc = None
            if pobrane < MAX_MAILI_SERII and m.get("id"):
                sciezka = f"/autoresponders/{m['id']}" if zrodlo == "autorespondery" else f"/newsletters/{m['id']}"
                d, _ = gr.get(sciezka, {"fields": "content,subject"})
                pobrane += 1
                html_tresc = ((d or {}).get("content") or {}).get("html") or ((d or {}).get("content") or {}).get("plain") or ""
            if html_tresc is None:
                klasa, powod = "NIEOKREŚLONY", "nie pobrano treści (limit zapytań w audycie)"
            else:
                klasa, powod = klasyfikuj(m["temat"] or m["nazwa"], html_tresc)
            pozycje.append({"temat": m["temat"] or m["nazwa"], "dzien": m.get("dzien_cyklu"), "wlaczony": m["status"] == "enabled",
                            "wyslane": m["wyslane"], "otwarcia_ludzi_proc": m["otwarcia_ludzi_proc"],
                            "klikniecia_ludzi_proc": m["klikniecia_ludzi_proc"], "klasa": klasa, "powod": powod})
        wnioski = wniosek_serii(pozycje)
        if zrodlo == "automat":
            # API nie łączy maila z automatem i nie podaje opóźnień — dni i kolejność nieznane
            wnioski = [w for w in wnioski if "dniu" not in w and "ten sam dzień" not in w] + \
                ["Dni wysyłki i kolejności maili z automatów API GetResponse nie podaje — sprawdź w panelu automatu."]
        wynik.append({"zrodlo": zrodlo, "lista": lista, "maile": pozycje, "wnioski": wnioski})
    return wynik


def main():
    ap = argparse.ArgumentParser(description="Audyt GetResponse (tylko odczyt)")
    ap.add_argument("--dni", type=int, default=90, help="okno dla newsletterów i zamówień (domyślnie 90)")
    ap.add_argument("--raport", default="audyt-getresponse.md", help="plik raportu Markdown")
    ap.add_argument("--json", default="", help="opcjonalnie: surowe dane zbiorcze do pliku JSON")
    ap.add_argument("--api", default="https://api.getresponse.com/v3")
    ap.add_argument("--max-domena", default=None, help="tylko GetResponse MAX: domena konta (nagłówek X-Domain)")
    ap.add_argument("--bez-zamowien", action="store_true", help="pomiń liczenie zamówień (szybciej przy ogromnych sklepach)")
    ap.add_argument("--przychod-sklepu", type=float, default=None, help="opcjonalnie: przychód sklepu w tym samym oknie (brutto, z panelu sklepu) — do porównania z GetResponse")
    ap.add_argument("--zamowienia-sklepu", type=int, default=None, help="opcjonalnie: liczba zamówień sklepu w oknie (bez anulowanych) — do porównania")
    ap.add_argument("--test-polaczenia", action="store_true", help="tylko sprawdź, czy klucz działa (jedno zapytanie), i zakończ")
    a = ap.parse_args()

    a.api = a.api.rstrip("/")
    if a.api not in DOZWOLONE_API:
        sys.exit("--api musi być jednym z oficjalnych adresów API GetResponse: " + ", ".join(DOZWOLONE_API))
    if a.dni < 1:
        sys.exit("--dni musi być co najmniej 1.")
    klucz = os.environ.get("GETRESPONSE_API_KEY")
    if not klucz:
        sys.exit("Brak zmiennej GETRESPONSE_API_KEY. Klucz: GetResponse → Menu → Integracje i API → API.")
    gr = GR(klucz, a.api, a.max_domena)
    if a.test_polaczenia:
        d, _ = gr.get("/campaigns", {"perPage": 1, "fields": "campaignId"})
        print("Połączenie działa — klucz ma dostęp do konta (odczyt list)." if d is not None else "API odpowiedziało, ale bez danych.")
        return
    dzis = dt.date.today()
    od = dzis - dt.timedelta(days=a.dni)
    teraz = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    D = {"data_audytu": dzis.isoformat(), "okno_dni": a.dni, "od": od.isoformat(),
         "sklep_podany": {"przychod": a.przychod_sklepu, "zamowienia": a.zamowienia_sklepu}}

    print("1/6 listy kontaktów…", file=sys.stderr)
    listy = gr.wszystkie("/campaigns", {"fields": "campaignId,name"})
    D["listy"] = []
    for l in listy:
        # liczba kontaktów ze statystyk listy (bez czytania kontaktów)
        d, _ = gr.get("/campaigns/statistics/list-size", {"query[campaignId]": l["campaignId"], "query[groupBy]": "total"})
        D["listy"].append({"nazwa": l.get("name"), "kontakty": int(suma_pola(d, "totalSubscribers"))})
    D["listy"].sort(key=lambda x: -x["kontakty"])
    D["zdrowie_bazy"] = zdrowie_bazy(gr, [l["campaignId"] for l in listy], od, dzis)

    print("   formularze i adresy nadawcy…", file=sys.stderr)
    D["formularze"] = formularze(gr)
    D["nadawcy"] = nadawcy(gr)
    nazwy_list = {l["campaignId"]: l.get("name") for l in listy}

    print("2/6 automatyzacje…", file=sys.stderr)
    wf = gr.wszystkie("/workflow")
    D["automaty"] = []
    for w in wf:
        d, _ = gr.get(f"/workflow/{w['workflowId']}")
        w = d or w
        st = w.get("subscriberStatistics") or {}
        start = (w.get("dateStart") or "")[:10]
        aktywny = w.get("status") == "active"
        zakonczyli, w_trakcie = int(st.get("completedCount") or 0), int(st.get("inProgressCount") or 0)
        uwagi = []
        if aktywny and zakonczyli == 0 and w_trakcie == 0:
            mlody = start and (dzis - dt.date.fromisoformat(start)).days < 14
            uwagi.append("włączony < 14 dni, za wcześnie na ocenę" if mlody else "włączony, ale nikt przez niego nie przeszedł")
        D["automaty"].append({"nazwa": w.get("name"), "aktywny": aktywny, "start": start,
                              "zakonczyli": zakonczyli, "w_trakcie": w_trakcie, "uwagi": uwagi})

    print("3/6 maile z automatów…", file=sys.stderr)
    maile = gr.wszystkie("/newsletters", {"query[type]": "automation",
                                          "fields": "newsletterId,name,subject,status,flags,createdOn"})
    D["maile_automatow"] = []
    for n in maile:
        m = stat_maila(gr, n["newsletterId"])
        m.update({"nazwa": n.get("name"), "temat": czysc(n.get("subject")), "status": n.get("status"),
                  "utworzony": (n.get("createdOn") or "")[:10], "id": n["newsletterId"], "typ": "automat",
                  "liczy_przychod": "ecommerce_tracking" in (n.get("flags") or "")})
        m["problemy"] = problemy_maila(m)
        D["maile_automatow"].append(m)
    D["maile_automatow"].sort(key=lambda x: -x["wyslane"])

    print("4/6 autorespondery (klasyczne)…", file=sys.stderr)
    ar = gr.wszystkie("/autoresponders")
    D["autorespondery"] = []
    for x in ar:
        d, _ = gr.get(f"/autoresponders/{x['autoresponderId']}/statistics", {"query[groupBy]": "total"})
        s = (d or [{}])[0] if isinstance(d, list) else {}
        wys = liczba(s.get("sent"))
        m = {"wyslane": int(wys),
             "otwarcia_ludzi_proc": proc(liczba(s.get("uniqueHumanOpened")), wys),
             "klikniecia_ludzi_proc": proc(liczba(s.get("uniqueHumanClicked")), wys),
             "wypisy_proc": proc(liczba(s.get("unsubscribed")), wys),
             "skargi_proc": proc(liczba(s.get("complaints")), wys),
             "odbicia_proc": proc(liczba(s.get("bounced")), wys),
             "okres": s.get("timeInterval", ""),
             "nazwa": x.get("name"), "temat": czysc(x.get("subject")), "status": x.get("status"),
             "utworzony": (x.get("createdOn") or "")[:10], "typ": "autoresponder",
             "dzien_cyklu": (x.get("triggerSettings") or {}).get("dayOfCycle"),
             "id": x.get("autoresponderId"),
             "lista": nazwy_list.get(x.get("campaignId") or (x.get("campaign") or {}).get("campaignId")
                                     or ((x.get("triggerSettings") or {}).get("subscribedCampaign") or {}).get("campaignId"), "—"),
             "liczy_przychod": "ecommerce_tracking" in (x.get("flags") or [])}
        m["problemy"] = problemy_maila(m)
        D["autorespondery"].append(m)
    D["maile_automatow"] += D["autorespondery"]
    D["maile_automatow"].sort(key=lambda x: -x["wyslane"])

    print(f"5/6 newslettery z {a.dni} dni…", file=sys.stderr)
    bc = gr.wszystkie("/newsletters", {"query[type]": "broadcast", "query[sendOn][from]": od.isoformat(),
                                       "sort[sendOn]": "desc",
                                       "fields": "newsletterId,name,subject,status,flags,sendOn"})
    D["newslettery"] = []
    for n in bc:
        if not n.get("sendOn") or n["sendOn"][:19] > teraz:
            continue  # zaplanowane na przyszłość
        m = stat_maila(gr, n["newsletterId"])
        m.update({"nazwa": n.get("name"), "temat": czysc(n.get("subject")), "wyslany": n["sendOn"][:10],
                  "liczy_przychod": "ecommerce_tracking" in (n.get("flags") or "")})
        m["problemy"] = problemy_maila(m)
        D["newslettery"].append(m)

    print("6/6 sklep…", file=sys.stderr)
    D["sklepy"] = []
    for s in gr.wszystkie("/shops") or []:
        sid = s["shopId"]
        q = {"query[shopId]": sid, "query[orderDate][from]": od.isoformat(), "query[orderDate][to]": dzis.isoformat()}
        pf, _ = gr.get("/statistics/ecommerce/performance", q)
        rv, _ = gr.get("/statistics/ecommerce/revenue", q)
        szereg = (rv or {}).get("timeSeries") or [] if isinstance(rv, dict) else []
        sk = {"nazwa": s.get("name"), "waluta": s.get("currency"),
              "raport_zamowienia": ((pf or {}).get("order") or {}).get("orders"),
              "raport_przychod": ((pf or {}).get("revenue") or {}).get("revenue"),
              "przychod_gr": round(sum(liczba(x.get("revenue")) for x in szereg), 2) if szereg else None,
              "zamowienia_gr_statystyka": int(sum(liczba(x.get("orders")) for x in szereg)) if szereg else None}
        if not a.bez_zamowien:
            n = suma = bez = 0
            stop = False
            for strona in range(1, MAX_STRON_ZAMOWIEN + 1):
                d, h = gr.get(f"/shops/{sid}/orders", {"perPage": 500, "page": strona, "sort[createdOn]": "desc",
                                                       "query[processedAt][from]": od.isoformat(),
                                                       "fields": "orderId,totalPrice,processedAt,contactId,status"})
                if not d:
                    break
                for o in d:
                    t = (o.get("processedAt") or "")[:10]
                    if t and t < od.isoformat():
                        stop = True
                        break
                    if t and (o.get("status") or "") not in ("cancelled", "refunded"):
                        n += 1
                        suma += liczba(o.get("totalPrice"))
                        bez += 0 if o.get("contactId") else 1
                if stop or strona >= int(h.get("totalpages") or 1):
                    break
            obciete = strona == MAX_STRON_ZAMOWIEN and not stop and bool(d)
            sk.update({"zamowienia": n, "suma": round(suma, 2), "bez_kontaktu": bez,
                       "bez_kontaktu_proc": proc(bez, n), "obciete": obciete})
            if n == 0:
                d, _ = gr.get(f"/shops/{sid}/orders", {"perPage": 1, "sort[createdOn]": "desc", "fields": "orderId,processedAt"})
                sk["ostatnie_zamowienie"] = ((d or [{}])[0].get("processedAt") or "")[:10] if d else None
        D["sklepy"].append(sk)

    # lista kontrolna
    D["lista_kontrolna"] = []
    for nazwa, slowa in LISTA_KONTROLNA:
        auto = [x for x in D["automaty"] if dopasuj(x["nazwa"], slowa)]
        maile_tr = [x for x in D["maile_automatow"] if dopasuj((x["nazwa"] or "") + " " + (x["temat"] or ""), slowa)]
        if nazwa.startswith("Powitanie"):
            # klasyczny autoresponder = cykl maili liczony od dnia zapisu, czyli z definicji seria powitalna
            maile_tr += [x for x in D["autorespondery"] if x.get("dzien_cyklu") == 0 and x not in maile_tr]
        maile_tr.sort(key=lambda x: (x["status"] != "enabled", -x["wyslane"]))
        if any(x["aktywny"] and (x["zakonczyli"] + x["w_trakcie"]) > 0 for x in auto) or \
                any(x["wyslane"] > 0 and x["status"] == "enabled" for x in maile_tr):
            stan = "działa"
        elif auto or maile_tr:
            stan = "jest, ale nie działa (wyłączony albo nikt nie przechodzi)"
        else:
            stan = "nie znaleziono po nazwie — sprawdź w panelu"
        D["lista_kontrolna"].append({"automat": nazwa, "stan": stan,
                                     "trafienia": [x["nazwa"] for x in auto][:3] + [x["temat"] for x in maile_tr][:2]})
    print("seria powitalna…", file=sys.stderr)
    D["seria_powitalna"] = seria(gr, D)
    D["zapytan_api"] = gr.zapytan
    D["niedostepne"] = gr.niedostepne
    D["ostrzezenia"] = gr.ostrzezenia

    with open(a.raport, "w", encoding="utf-8") as plik:
        plik.write(raport(D))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as plik:
            json.dump(D, plik, ensure_ascii=False, indent=1)
    print(f"Gotowe: {a.raport} ({gr.zapytan} zapytań do API)", file=sys.stderr)


def odm(n, jeden, kilka, wiele):
    if n == 1:
        return jeden
    return kilka if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else wiele


def tyg(x):
    return f"{x:.1f}".replace(".", ",")


def f(x, suf="%"):
    return "—" if x is None else f"{str(x).replace('.', ',')}{suf}"


def zl(x):
    if x is None:
        return "—"
    try:
        return f"{float(x):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(x)


ZRODLA = {"www": "formularze na stronie", "api": "integracje (np. sklep)", "import": "import", "panel": "dodani ręcznie",
          "sale": "sprzedaż", "landing_page": "landing page", "copy": "kopiowanie między listami", "email": "zapis mailem",
          "leads": "leady", "survey": "ankiety", "mobile": "aplikacja mobilna", "webinar": "webinary", "chat": "czat"}
POWODY = {"unsubscribe": "wypis", "bounce": "odbicia", "api": "usunięci przez integrację", "user": "usunięci ręcznie",
          "spam": "skargi na spam", "complaint": "skargi na spam", "blacklisted": "blokada", "cleaner": "czyszczenie listy"}
STATUS_DOMENY = {"confirmed": "potwierdzona", "unconfirmed": "niepotwierdzona", "can_not_be_used": "nie może być użyta",
                 "dns_configuration_pending": "czeka na konfigurację DNS"}

DARMOWE_DOMENY = {"gmail.com", "googlemail.com", "wp.pl", "o2.pl", "onet.pl", "op.pl", "interia.pl", "poczta.fm", "yahoo.com",
                  "outlook.com", "hotmail.com", "live.com", "icloud.com", "me.com", "gazeta.pl", "tlen.pl", "vp.pl"}
DKIM = {"not_recommended": "niezalecana konfiguracja", "can_not_be_used": "nie może być użyta",
        "not_authenticated": "domena nieuwierzytelniona (brak DKIM)", "at_risk": "zagrożona"}

STOPKA_RAPORTU = "To podstawowy audyt. Chcesz pełny audyt albo wdrożenie poprawek? Napisz do mnie: https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=raport#kontakt (Wojciech Nowak) albo wnowak@autilo.eu"

KLUCZ_LISTY = ["powitanie_brak", "koszyk_brak", "po_zakupie_brak", "przegladanie_brak", "drugi_zakup_brak", "reaktywacja_brak"]


def klucze_problemow(D):
    """Znaleziska audytu → klucze rekomendacji (z modułu rekomendacje). Tylko to, co wykryto."""
    k = {}
    for i, x in enumerate(D["lista_kontrolna"]):
        if x["stan"] != "działa":
            k[KLUCZ_LISTY[i]] = ""
    martwe = [x["nazwa"] for x in D["automaty"] if "nikt przez niego nie przeszedł" in " ".join(x["uwagi"])]
    if martwe:
        k["automat_martwy"] = "; ".join(martwe[:3])
    robocze = [x["nazwa"] for x in D["automaty"] if x["aktywny"] and re.match(r"(?i)(szkic|draft|bez tytułu|untitled)", (x["nazwa"] or "").strip())]
    if robocze:
        k["nazwa_robocza"] = "; ".join(robocze[:3])
    for s in D["sklepy"]:
        if s.get("zamowienia") == 0:
            k["sklep_bez_zamowien"] = s["nazwa"] or ""
        sp = D.get("sklep_podany") or {}
        if sp.get("zamowienia") and s.get("zamowienia") and s["zamowienia"] < 0.9 * sp["zamowienia"]:
            k["przychod_rozjazd"] = f"{zl(s['zamowienia'])} z {zl(sp['zamowienia'])} zamówień"
        if (s.get("bez_kontaktu_proc") or 0) >= 10:
            k["zamowienia_bez_kontaktu"] = f"{f(s['bez_kontaktu_proc'])} zamówień"
    # tylko maile, które dalej wychodzą (włączone automaty i newslettery z okna) — wyłączonych nie naprawiamy
    zywe = [x for x in D["maile_automatow"] if x["status"] == "enabled"] + D["newslettery"]
    skargi = [x["temat"] for x in zywe if any(p.startswith("skargi") for p in x["problemy"])]
    if skargi:
        k["skargi_spam"] = "; ".join(skargi[:3])
    wypisy = [x["temat"] for x in zywe if any(p.startswith("dużo wypisów") for p in x["problemy"])]
    if wypisy:
        k["duzo_wypisow"] = "; ".join(wypisy[:3])
    if any(x["wyslane"] > 0 and not x["liczy_przychod"] for x in zywe):
        n_bs = sum(1 for x in zywe if x["wyslane"] > 0 and not x["liczy_przychod"])
        k["bez_sledzenia"] = f"{n_bs} {odm(n_bs, 'mail', 'maile', 'maili')}"
    nigdy = [x["temat"] for x in D["maile_automatow"] if x["status"] == "enabled" and x["wyslane"] == 0]
    if nigdy:
        k["mail_nigdy_niewyslany"] = f"{len(nigdy)} {odm(len(nigdy), 'mail', 'maile', 'maili')}"
    for n in D.get("nadawcy") or []:
        if any(u.startswith("domena") for u in n["uwagi"]):
            k["domena_nadawcy"] = n["domena"]
        if any(u.startswith("ostrzeżenie") for u in n["uwagi"]):
            k["nadawca_darmowy" if n["domena"] in DARMOWE_DOMENY else "dkim_dmarc"] = n["domena"]
    zb = D.get("zdrowie_bazy")
    if zb and zb["usunieci"] > zb["dodani"] and zb["usunieci"] > 0:
        k["odplyw_bazy"] = f"+{zl(zb['dodani'])} / −{zl(zb['usunieci'])}"
    fb = [x["nazwa"] for x in D.get("formularze") or [] if "bez odwiedzin" in " ".join(x["uwagi"])]
    if fb:
        k["formularz_bez_ruchu"] = "; ".join(fb[:3])
    fn = [x["nazwa"] for x in D.get("formularze") or [] if "niska konwersja" in " ".join(x["uwagi"])]
    if fn:
        k["formularz_niska_konwersja"] = "; ".join(fn[:3])
    nl = D["newslettery"]
    n_tyg = len(nl) / (D["okno_dni"] / 7) if D["okno_dni"] else 0
    if n_tyg > 3:
        k["za_czesto"] = ""
    elif n_tyg < 0.5:
        k["brak_newsletterow"] = ""
    return k


def sekcja_rekomendacji(D):
    serie, dobre = [], []
    for g in D.get("seria_powitalna") or []:
        if not any(m["wyslane"] for m in g["maile"]):
            continue  # seria, która nigdy nic nie wysłała — obsługuje ją rada „maile, które nigdy nie wyszły”
        gdzie = f"lista „{g['lista']}”" if g["zrodlo"] == "autorespondery" else "maile z automatów"
        rs = rekomendacja_serii(g["maile"])
        if rs:
            serie.append((rs[0], rs[1], gdzie))
        else:
            dobre.append(gdzie)
    lista = uloz(klucze_problemow(D), serie)
    L = ["## Rekomendacje — co zrobić i w jakiej kolejności", "",
         "Kolejność: najpierw dane (bez nich automaty nie działają), potem dostarczalność, potem automaty od najbardziej dochodowych. Rekomendacje dotyczą tylko tego, co wykrył audyt.", ""]
    for i, (tyt, tresc, szcz) in enumerate(lista, 1):
        L.append(f"{i}. **{tyt}**" + (f" ({szcz})" if szcz else "") + f". {tresc}")
    if dobre:
        L.append(f"{len(lista) + 1}. **Seria powitalna wygląda dobrze** ({', '.join(dobre)}) — ma kilka maili i łączy ofertę z treścią. Nie zmieniaj jej bez testu.")
    if not lista and not dobre:
        L.append("Audyt nie wykrył problemów, które wymagają zmian.")
    return L + [""]


def raport(D):
    L = [f"# Audyt e-mail marketingu — GetResponse ({D['data_audytu']})", "",
         f"Okres audytu newsletterów i zamówień: ostatnie {D['okno_dni']} dni (od {D['od']}). Tylko odczyt, dane zbiorcze, bez danych osobowych.", ""]

    # najważniejsze
    naj = []
    brak = [x for x in D["lista_kontrolna"] if x["stan"] != "działa"]
    if brak:
        naj.append(f"Brakuje albo nie działa {len(brak)} z {len(D['lista_kontrolna'])} podstawowych automatów: "
                   + ", ".join(x["automat"].split(" (")[0].lower() for x in brak) + ".")
    martwe = [x for x in D["automaty"] if "nikt przez niego nie przeszedł" in " ".join(x["uwagi"])]
    if martwe:
        naj.append(f"{len(martwe)} {odm(len(martwe), 'automat jest włączony', 'automaty są włączone', 'automatów jest włączonych')}, ale nikt przez {odm(len(martwe), 'niego', 'nie', 'nie')} nie przeszedł. Sprawdź w panelu warunek startu.")
    for s in D["sklepy"]:
        if s.get("zamowienia") == 0:
            kiedy = f"ostatnie zwrócone zamówienie: {s['ostatnie_zamowienie']}" if s.get("ostatnie_zamowienie") else "ani żadnego z całej historii"
            naj.append(f"Sklep „{s['nazwa']}” jest podłączony do GetResponse, ale API nie zwróciło zamówień z tego okresu ({kiedy}). Jeśli sklep w tym czasie sprzedawał, integracja najpewniej nie przesyła zamówień — wtedy automaty koszyka i po zakupie oraz liczenie przychodu nie mają na czym działać. Sprawdź integrację sklepu w panelu.")
        if (s.get("bez_kontaktu_proc") or 0) >= 10:
            naj.append(f"Sklep „{s['nazwa']}”: {f(s['bez_kontaktu_proc'])} zamówień jest w GetResponse bez przypisanego kontaktu. Może to być klient bez zgody na maile (wtedy w porządku) albo błąd synchronizacji — sprawdź na kilku zamówieniach z zaznaczoną zgodą, czy kupujący jest kontaktem w GetResponse.")
    for n in D.get("nadawcy") or []:
        if n["uwagi"]:
            if n["domena"] in DARMOWE_DOMENY:
                naj.append(f"Na koncie jest aktywny adres nadawcy w darmowej poczcie ({n['domena']}{', domyślny' if n['domyslny'] else ', niedomyślny'}): {', '.join(n['uwagi'])}. Maile z takiego adresu częściej trafiają do spamu — wysyłaj tylko z własnej domeny.")
            else:
                naj.append(f"Adres nadawcy w domenie {n['domena']}: {', '.join(n['uwagi'])}. To bezpośrednio wpływa na to, czy maile trafiają do skrzynki odbiorczej — popraw w pierwszej kolejności (GetResponse → Adresy nadawcy / Domeny).")
    zb = D.get("zdrowie_bazy")
    if zb and zb["usunieci"] > zb["dodani"] and zb["usunieci"] > 0:
        naj.append(f"Baza się kurczy: w tym okresie przybyło {zl(zb['dodani'])} kontaktów, ubyło {zl(zb['usunieci'])}.")
    fz = [x for x in (D.get("formularze") or []) if x["uwagi"]]
    if fz:
        naj.append(f"{len(fz)} {odm(len(fz), 'formularz zapisu ma', 'formularze zapisu mają', 'formularzy zapisu ma')} problem (brak odwiedzin albo niska konwersja) — szczegóły w sekcji Formularze.")
    wszystkie = D["maile_automatow"] + D["newslettery"]
    wysylane = [x for x in wszystkie if x["wyslane"] > 0]
    bez_przych = [x for x in wysylane if not x["liczy_przychod"]]
    if bez_przych:
        naj.append(f"{len(bez_przych)} z {len(wysylane)} wysyłanych maili nie ma włączonego śledzenia e-commerce (ustawienie w wiadomości) — sprzedaż z nich najpewniej nie jest przypisywana. Sprawdź w ustawieniach wiadomości: Śledzenie.")
    nl = D["newslettery"]
    if D["okno_dni"] and nl:
        n_tyg = len(nl) / (D["okno_dni"] / 7)
        if n_tyg > 3:
            naj.append(f"Newslettery: średnio {tyg(n_tyg)} tygodniowo — ryzyko zmęczenia bazy (sprawdź wypisy niżej).")
        elif n_tyg < 0.5:
            naj.append(f"Newslettery: średnio {tyg(n_tyg)} tygodniowo — baza praktycznie nie dostaje maili.")
    elif not nl:
        naj.append(f"W ostatnich {D['okno_dni']} dniach nie wyszedł żaden newsletter.")
    L += ["## Najważniejsze", ""] + [f"{i}. {t}" for i, t in enumerate(naj or ["Nie znaleziono poważnych problemów w danych dostępnych przez API."], 1)] + [""]
    L += sekcja_rekomendacji(D)

    L += ["## Lista kontrolna automatów sklepu", "",
          "| Automat | Stan | Znalezione po nazwie |", "|---|---|---|"]
    for x in D["lista_kontrolna"]:
        ik = "✅" if x["stan"] == "działa" else ("⚠️" if x["stan"].startswith("jest") else "❓")
        L.append(f"| {x['automat']} | {ik} {x['stan']} | {'; '.join(t for t in x['trafienia'] if t) or '—'} |")
    L += ["", "API GetResponse nie pokazuje warunków ani wyzwalaczy automatów — automat nazwany nietypowo może istnieć mimo „❓”.", ""]

    L += ["## Automatyzacje", "", "| Automat | Włączony | Zakończyli | W trakcie | Uwagi |", "|---|---|---|---|---|"]
    for x in sorted(D["automaty"], key=lambda x: (not x["aktywny"], -(x["zakonczyli"] + x["w_trakcie"]))):
        L.append(f"| {x['nazwa']} | {'tak' if x['aktywny'] else 'nie'} | {zl(x['zakonczyli'])} | {zl(x['w_trakcie'])} | {'; '.join(x['uwagi']) or ''} |")
    if D["autorespondery"]:
        L += ["", f"Klasyczne autorespondery (maile w cyklu po zapisie): {len(D['autorespondery'])}, włączone: {sum(1 for x in D['autorespondery'] if x['status'] == 'enabled')}. Ich wyniki są w tabeli maili niżej."]
    L += [""]

    L += ["## Maile z automatów (całe życie maila)", "",
          "Otwarcia i kliknięcia liczone bez botów (GetResponse odsiewa automatyczne otwarcia, np. Apple Mail). Powiązania mail → automat API nie podaje.", "",
          "| Temat | Wysłane | Otwarcia | Kliknięcia | Wypisy | Problemy |", "|---|---|---|---|---|---|"]
    for x in D["maile_automatow"]:
        if x["wyslane"] == 0 and x["status"] != "enabled":
            continue  # nieużywany szkic
        typ = f" _(autoresponder, dzień {x['dzien_cyklu']})_" if x.get("typ") == "autoresponder" else ""
        L.append(f"| {(x['temat'] or x['nazwa'])}{typ}{'' if x['status'] == 'enabled' else ' _(wyłączony)_'} | {zl(x['wyslane'])} | {f(x['otwarcia_ludzi_proc'])} | {f(x['klikniecia_ludzi_proc'])} | {f(x['wypisy_proc'])} | {', '.join(x['problemy'])} |")
    L += [""]

    L += ["## Seria powitalna (sprzedażowe vs wartościowe)", "",
          "Podział to **ocena po słowach i elementach maila — może się pomylić**. Liczona z tematu i treści maila (kod rabatowy, procent, kwota, „kup/zamów/promocja”, link do produktu lub koszyka = sprzedaż; poradnik, historia marki, opinie, dłuższy tekst = wartość). Może się mylić — zwłaszcza przy mailach złożonych z samych obrazków.", ""]
    if not D.get("seria_powitalna"):
        L += ["Nie znaleziono serii powitalnej (ani klasycznych autoresponderów, ani maili z automatów o nazwie powitalnej).", ""]
    for g in D.get("seria_powitalna") or []:
        tyt = f"Autorespondery na liście „{g['lista']}”" if g["zrodlo"] == "autorespondery" else "Maile z automatów o nazwie lub temacie powitalnym"
        L += [f"**{tyt}**", ""] + [f"- {w}" for w in g["wnioski"]] + ["",
              "| Dzień | Temat | Włączony | Wysłane | Otwarcia | Kliknięcia | Klasa | Dlaczego |", "|---|---|---|---|---|---|---|---|"]
        for m in g["maile"]:
            L.append(f"| {'—' if m['dzien'] is None else m['dzien']} | {m['temat']} | {'tak' if m['wlaczony'] else 'nie'} | {zl(m['wyslane'])} | "
                     f"{f(m['otwarcia_ludzi_proc'])} | {f(m['klikniecia_ludzi_proc'])} | {m['klasa'].lower()} | {m['powod']} |")
        L += [""]

    L += [f"## Newslettery — ostatnie {D['okno_dni']} dni", ""]
    if nl:
        w = sum(x["wyslane"] for x in nl)
        def sr(k):
            war = [(x[k], x["wyslane"]) for x in nl if x[k] is not None and x["wyslane"]]
            return round(sum(a * b for a, b in war) / sum(b for _, b in war), 2) if war else None
        L += [f"- Wysłanych newsletterów: **{len(nl)}** (średnio {tyg(len(nl) / (D['okno_dni'] / 7))} tygodniowo), łącznie {zl(w)} maili.",
              f"- Średnio (ważone liczbą wysłanych): otwarcia ludzi {f(sr('otwarcia_ludzi_proc'))}, kliknięcia {f(sr('klikniecia_ludzi_proc'))}, wypisy {f(sr('wypisy_proc'))}, skargi {f(sr('skargi_proc'))}, odbicia {f(sr('odbicia_proc'))}.",
              f"- Ze śledzeniem e-commerce: {sum(1 for x in nl if x['liczy_przychod'])} z {len(nl)}.", "",
              "| Data | Temat | Wysłane | Kliknięcia | Wypisy | Problemy |", "|---|---|---|---|---|---|"]
        for x in nl[:25]:
            L.append(f"| {x['wyslany']} | {x['temat']} | {zl(x['wyslane'])} | {f(x['klikniecia_ludzi_proc'])} | {f(x['wypisy_proc'])} | {', '.join(x['problemy'])} |")
        if len(nl) > 25:
            L.append(f"| … | jeszcze {len(nl) - 25} | | | | |")
    else:
        L.append("Brak wysłanych newsletterów w tym okresie.")
    L += [""]

    L += ["## Baza kontaktów", ""]
    if D.get("listy"):
        L += ["| Lista | Kontakty |", "|---|---|"] + [f"| {x['nazwa']} | {zl(x['kontakty'])} |" for x in D["listy"] if x["kontakty"]]
        puste = sum(1 for x in D["listy"] if not x["kontakty"])
        if puste:
            L.append(f"| {puste} {odm(puste, 'pusta lista', 'puste listy', 'pustych list')} | 0 |")
        L.append("")
    zb = D.get("zdrowie_bazy")
    if zb:
        L += [f"- W ostatnich {D['okno_dni']} dniach przybyło **{zl(zb['dodani'])}** kontaktów, ubyło **{zl(zb['usunieci'])}** (bilans {'+' if zb['dodani'] >= zb['usunieci'] else ''}{zl(zb['dodani'] - zb['usunieci'])}).",
              "- Źródła zapisów: " + (", ".join(f"{ZRODLA.get(k, k)} {zl(v)}" for k, v in zb["zrodla"].items()) or "brak") + ".",
              "- Powody usunięć: " + (", ".join(f"{POWODY.get(k, k)} {zl(v)}" for k, v in zb["powody_usuniec"].items()) or "brak") + ".", ""]
    else:
        L += ["Statystyk przyrostu i odpływu bazy API nie zwróciło.", ""]

    L += ["## Formularze zapisu", ""]
    if D.get("formularze") is None:
        L += ["Klucz API nie ma uprawnień do formularzy (GetResponse zwrócił „brak dostępu”) — sprawdź w panelu: Formularze. Nowe pop-upy GetResponse API pokazuje osobno i ten audyt ich nie liczy.", ""]
    elif not D["formularze"]:
        L += ["Na koncie nie ma formularzy (klasycznych). Nowe pop-upy GetResponse API pokazuje osobno i ten audyt ich nie liczy.", ""]
    else:
        L += ["| Formularz | Stan | Odwiedziny | Zapisy | Konwersja | Uwagi |", "|---|---|---|---|---|---|"]
        for x in D["formularze"][:20]:
            L.append(f"| {x['nazwa']} | {x['status']} | {zl(x['odwiedziny'])} | {zl(x['zapisy'])} | {f(x['konwersja_proc'])} | {', '.join(x['uwagi'])} |")
        L += ["", f"Próg „niska konwersja” (poniżej {f(PROG_KONWERSJI_FORMULARZA)} przy co najmniej {MIN_ODWIEDZIN_FORMULARZA} odwiedzinach) to orientacyjna granica z praktyki. Liczby obejmują całe życie formularza. Nowe pop-upy GetResponse nie są tu liczone.", ""]

    L += ["## Dostarczalność — adres nadawcy", ""]
    if D.get("nadawcy") is None:
        L += ["API nie zwróciło adresów nadawcy.", ""]
    else:
        L += ["| Domena nadawcy | Aktywny | Domyślny | Status domeny | DKIM | DMARC |", "|---|---|---|---|---|---|"]
        for n in D["nadawcy"]:
            L.append(f"| {n['domena']} | {'tak' if n['aktywny'] else 'nie'} | {'tak' if n['domyslny'] else 'nie'} | {STATUS_DOMENY.get(n['status_domeny'], n['status_domeny'] or '—')} | {DKIM.get(n['dkim'], n['dkim']) if n['dkim'] else 'bez ostrzeżeń'} | {'ostrzeżenie' if n['dmarc_ostrzezenie'] else 'bez ostrzeżeń'} |")
        L += ["", "GetResponse podaje tu status domeny i ostrzeżenia DKIM i DMARC. Pełnego sprawdzenia SPF i DMARC API nie daje.", ""]

    L += ["## Sklep", ""]
    if not D["sklepy"]:
        L += ["API nie zwróciło żadnego podłączonego sklepu. Jeśli sklep jest podłączony w panelu, sprawdź uprawnienia klucza; jeśli nie — automaty koszyka i po zakupie nie mają danych.", ""]
    for s in D["sklepy"]:
        L += [f"**{s['nazwa']}** ({s['waluta']})", ""]
        if s.get("zamowienia") == 0:
            L += [f"- Zamówienia w GetResponse w tym okresie: **0**" + (f" (ostatnie zwrócone: {s['ostatnie_zamowienie']})" if s.get("ostatnie_zamowienie") else " (żadnego w całej historii)") + "."]
        elif "zamowienia" in s:
            L += [f"- Zamówienia w GetResponse w tym okresie (bez anulowanych i zwróconych): **{zl(s['zamowienia'])}** na {zl(s['suma'])} {s['waluta']}"
                  + (" (liczenie przerwane bezpiecznikiem — sklep bardzo duży)" if s.get("obciete") else "") + ".",
                  f"- Bez przypisanego kontaktu: **{zl(s['bez_kontaktu'])} ({f(s['bez_kontaktu_proc'])})** — klient bez zgody na maile albo błąd synchronizacji; sprawdź na zamówieniach z zaznaczoną zgodą."]
        if s.get("zamowienia") != 0: L += [f"- Raport sprzedaży GetResponse w tym okresie: {zl(s['raport_zamowienia'])} {odm(int(s['raport_zamowienia'] or 0), 'zamówienie', 'zamówienia', 'zamówień')}, {zl(s['raport_przychod'])} {s['waluta']}. "
              "Jeśli to dużo mniej niż zamówienia powyżej, raport liczy tylko przychód przypisany do maili (zakup po kliknięciu w link) — porównaj z panelem: Raporty → E-commerce."]
        if s.get("przychod_gr") is not None:
            L.append(f"- Przychód przypisany do maili według GetResponse (statystyka dzień po dniu): {zl(s['przychod_gr'])} {s['waluta']}, {zl(s['zamowienia_gr_statystyka'])} {odm(int(s['zamowienia_gr_statystyka'] or 0), 'zamówienie', 'zamówienia', 'zamówień')}. To sprzedaż po kliknięciu w mail, nie cały przychód sklepu.")
        sp = D.get("sklep_podany") or {}
        if sp.get("przychod") or sp.get("zamowienia"):
            ref_z, ref_p = s.get("zamowienia"), s.get("suma")
            czesci = []
            if sp.get("zamowienia") and ref_z is not None:
                czesci.append(f"zamówienia: sklep {zl(sp['zamowienia'])}, GetResponse {zl(ref_z)} ({f(proc(ref_z, sp['zamowienia']))} sklepu)")
            if sp.get("przychod") and ref_p is not None:
                czesci.append(f"przychód: sklep {zl(sp['przychod'])}, GetResponse {zl(ref_p)} ({f(proc(ref_p, sp['przychod']))} sklepu)")
            if czesci:
                L.append("- Porównanie z danymi sklepu podanymi przy uruchomieniu — " + "; ".join(czesci) + ". Różnica do kilku procent to zwykle anulacje, zwroty i strefy czasowe; duża różnica = zamówienia nie dochodzą.")
        L.append("")

    L += ["## Czego ten audyt nie widzi (sprawdź w panelu)", "",
          "- Warunków, opóźnień i rozgałęzień w automatach — API GetResponse ich nie udostępnia.",
          "- Który mail należy do którego automatu.",
          "- Przypisanego przychodu per automat (kolumna „Przypisany przychód” na liście automatów).",
          "- Czy na stronie działa śledzenie (Web Connect) potrzebne do automatów przeglądania produktów.", "",
          "- Progi w kolumnie „Problemy” (wypisy > 0,5%, kliknięcia < 0,5%, odbicia > 2%, ocena od 200 wysłanych) to orientacyjne granice z praktyki, nie normy. Skargi: Google wymaga poniżej 0,3% i zaleca poniżej 0,1%.", ""]
    if D.get("niedostepne"):
        L += ["**Niedostępne na tym koncie (API zwróciło 404 — funkcja może nie wchodzić w plan):** " + ", ".join(f"`{x}`" for x in D["niedostepne"][:8]), ""]
    if D.get("ostrzezenia"):
        L += ["**Ostrzeżenia:**", ""] + [f"- {x}" for x in D["ostrzezenia"]] + [""]
    L += [f"_Zapytań do API: {D['zapytan_api']}._", "", "---", "", STOPKA_RAPORTU, ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
