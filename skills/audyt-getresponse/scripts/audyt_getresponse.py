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

PRZERWA = 0.3  # s między zapytaniami; limit GR to 80/s, ale w praktyce ~4/s bez 429
MAX_STRON_ZAMOWIEN = 120  # 120 × 500 zamówień — bezpiecznik dla bardzo dużych sklepów

# Automaty, które powinien mieć sklep internetowy. Wykrywane po NAZWIE automatu i tematach maili —
# API GetResponse nie pokazuje warunków ani wyzwalaczy automatu, więc „nie znaleziono” = sprawdź w panelu.
LISTA_KONTROLNA = [
    ("Powitanie nowego subskrybenta", ["powital", "powitan", "welcome", "witaj", "zapis", "onboard"]),
    ("Porzucony koszyk", ["koszyk", "cart", "porzuc"]),
    ("Po zakupie (podziękowanie, opinia, cross-sell)", ["po zakup", "post-purchase", "postpurchase", "dziękujemy za zakup", "dziękujemy za zamówienie", "jak się nosi", "jak sie nosi", "opini", "recenz"]),
    ("Porzucone przeglądanie (oglądał produkt, nie dodał do koszyka)", ["przegląd", "przeglad", "odwiedz", "browse", "oglądał", "ogladal", "visited"]),
    ("Drugi / ponowny zakup (przypomnienie o uzupełnieniu)", ["ponown", "drugi zakup", "drugie zamów", "drugi zapach", "kolejne zamów", "kolejny zakup", "dni po 1", "po pierwszym zakup", "replenish", "uzupełn", "uzupeln", "kończy się", "konczy sie", "dokup"]),
    ("Reaktywacja nieaktywnych klientów (win-back)", ["reaktyw", "win-back", "winback", "tęsknimy", "tesknimy", "wróć do nas", "wroc do nas", "dawno cię", "dawno cie", "dawno nie"]),
]


class GR:
    def __init__(self, klucz, api, max_domena=None):
        self.api = api.rstrip("/")
        self.h = {"X-Auth-Token": "api-key " + klucz, "Accept": "application/json"}
        if max_domena:
            self.h["X-Domain"] = max_domena
        self.zapytan = 0

    def get(self, sciezka, params=None):
        url = self.api + sciezka
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="[]")
        for proba in range(5):
            time.sleep(PRZERWA)
            self.zapytan += 1
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers=self.h), timeout=240)
                return json.loads(r.read() or b"null"), {k.lower(): v for k, v in r.headers.items()}
            except (socket.timeout, TimeoutError, http.client.IncompleteRead, ConnectionError):
                if proba < 4:
                    print("  serwer odpowiada wolno — ponawiam", file=sys.stderr)
                    time.sleep(5 * (proba + 1))
                    continue
                raise
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    czekaj = int(e.headers.get("X-RateLimit-Reset") or 30)
                    print(f"  limit zapytań — czekam {czekaj} s", file=sys.stderr)
                    time.sleep(min(czekaj, 600))
                    continue
                if e.code in (401, 403):
                    sys.exit(f"Błąd {e.code}: klucz API nieprawidłowy, wygasł albo nie ma dostępu ({sciezka}).")
                if e.code == 404:
                    return None, {}
                if e.code >= 500 and proba < 4:
                    time.sleep(3 * (proba + 1))
                    continue
                raise
            except urllib.error.URLError:
                if proba < 4:
                    time.sleep(3 * (proba + 1))
                    continue
                raise
        return None, {}

    def wszystkie(self, sciezka, params=None, per_page=100, max_stron=50):
        wynik = []
        for strona in range(1, max_stron + 1):
            p = dict(params or {}, perPage=per_page, page=strona)
            d, h = self.get(sciezka, p)
            if not d:
                break
            wynik += d
            if strona >= int(h.get("totalpages") or 1):
                break
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
        if (m["skargi_proc"] or 0) > 0.1:
            p.append("skargi na spam " + f(m["skargi_proc"]) + " (Google wymaga poniżej 0,3%)")
        if (m["odbicia_proc"] or 0) > 2:
            p.append("odbicia " + f(m["odbicia_proc"]))
        if m["klikniecia_ludzi_proc"] is not None and m["klikniecia_ludzi_proc"] < 0.5:
            p.append("prawie nikt nie klika (" + f(m["klikniecia_ludzi_proc"]) + ")")
    if not m.get("liczy_przychod"):
        p.append("przychód nieliczony")
    if "bez tytułu" in (m.get("nazwa") or "").lower() or "untitled" in (m.get("nazwa") or "").lower():
        p.append("nazwa robocza")
    return p


def czysc(t):
    """[[firstname fallback=…]] → „…” — temat czytelny w raporcie."""
    t = unicodedata.normalize("NFKC", t or "")  # „𝗘𝗸𝘀𝗸𝗹𝘂𝘇𝘆𝘄𝗻𝘆” → „Ekskluzywny”
    return re.sub(r"\[\[[^\]]*\]\]", "…", t).strip()


def dopasuj(tekst, slowa):
    t = czysc(tekst).lower()
    return any(s in t for s in slowa)


def main():
    ap = argparse.ArgumentParser(description="Audyt GetResponse (tylko odczyt)")
    ap.add_argument("--dni", type=int, default=90, help="okno dla newsletterów i zamówień (domyślnie 90)")
    ap.add_argument("--raport", default="audyt-getresponse.md", help="plik raportu Markdown")
    ap.add_argument("--json", default="", help="opcjonalnie: surowe dane zbiorcze do pliku JSON")
    ap.add_argument("--api", default="https://api.getresponse.com/v3")
    ap.add_argument("--max-domena", default=None, help="tylko GetResponse MAX: domena konta (nagłówek X-Domain)")
    ap.add_argument("--bez-zamowien", action="store_true", help="pomiń liczenie zamówień (szybciej przy ogromnych sklepach)")
    a = ap.parse_args()

    klucz = os.environ.get("GETRESPONSE_API_KEY")
    if not klucz:
        sys.exit("Brak zmiennej GETRESPONSE_API_KEY. Klucz: GetResponse → Menu → Integracje i API → API.")
    gr = GR(klucz, a.api, a.max_domena)
    dzis = dt.date.today()
    od = dzis - dt.timedelta(days=a.dni)
    teraz = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    D = {"data_audytu": dzis.isoformat(), "okno_dni": a.dni, "od": od.isoformat()}

    print("1/6 listy kontaktów…", file=sys.stderr)
    listy = gr.wszystkie("/campaigns", {"fields": "campaignId,name"})
    D["listy"] = []
    for l in listy:
        _, h = gr.get("/contacts", {"query[campaignId]": l["campaignId"], "perPage": 1, "fields": "contactId"})
        D["listy"].append({"nazwa": l.get("name"), "kontakty": int(h.get("totalcount") or 0)})
    D["listy"].sort(key=lambda x: -x["kontakty"])

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
                  "utworzony": (n.get("createdOn") or "")[:10],
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
        sk = {"nazwa": s.get("name"), "waluta": s.get("currency"),
              "raport_zamowienia": ((pf or {}).get("order") or {}).get("orders"),
              "raport_przychod": ((pf or {}).get("revenue") or {}).get("revenue")}
        if not a.bez_zamowien:
            n = suma = bez = 0
            stop = False
            for strona in range(1, MAX_STRON_ZAMOWIEN + 1):
                d, h = gr.get(f"/shops/{sid}/orders", {"perPage": 500, "page": strona, "sort[createdOn]": "desc",
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
            sk.update({"zamowienia": n, "suma": round(suma, 2), "bez_kontaktu": bez,
                       "bez_kontaktu_proc": proc(bez, n), "obciete": not stop and n > 0})
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
            maile_tr += [x for x in D["autorespondery"] if x not in maile_tr]
        if any(x["aktywny"] and (x["zakonczyli"] + x["w_trakcie"]) > 0 for x in auto) or \
                any(x["wyslane"] > 0 and x["status"] == "enabled" for x in maile_tr):
            stan = "działa"
        elif auto or maile_tr:
            stan = "jest, ale nie działa (wyłączony albo nikt nie przechodzi)"
        else:
            stan = "nie znaleziono po nazwie — sprawdź w panelu"
        D["lista_kontrolna"].append({"automat": nazwa, "stan": stan,
                                     "trafienia": [x["nazwa"] for x in auto][:3] + [x["temat"] for x in maile_tr][:2]})
    D["zapytan_api"] = gr.zapytan

    open(a.raport, "w", encoding="utf-8").write(raport(D))
    if a.json:
        json.dump(D, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
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
    return "—" if x is None else f"{x:,.0f}".replace(",", " ")


def raport(D):
    L = [f"# Audyt e-mail marketingu — GetResponse ({D['data_audytu']})", "",
         f"Okno newsletterów i zamówień: ostatnie {D['okno_dni']} dni (od {D['od']}). Tylko odczyt, dane zbiorcze, bez danych osobowych.", ""]

    # najważniejsze
    naj = []
    brak = [x for x in D["lista_kontrolna"] if x["stan"] != "działa"]
    if brak:
        naj.append(f"Brakuje albo nie działa {len(brak)} z {len(D['lista_kontrolna'])} podstawowych automatów: "
                   + ", ".join(x["automat"].split(" (")[0].lower() for x in brak) + ".")
    martwe = [x for x in D["automaty"] if "nikt przez niego nie przeszedł" in " ".join(x["uwagi"])]
    if martwe:
        naj.append(f"{len(martwe)} {odm(len(martwe), 'automat jest włączony', 'automaty są włączone', 'automatów jest włączonych')}, ale nikt przez {odm(len(martwe), 'niego', 'nie', 'nie')} nie przeszedł — {odm(len(martwe), 'wygląda na działający', 'wyglądają na działające', 'wyglądają na działające')}, a nic nie wysyła.")
    for s in D["sklepy"]:
        if s.get("zamowienia") == 0:
            kiedy = f"ostatnie zamówienie dotarło {s['ostatnie_zamowienie']}" if s.get("ostatnie_zamowienie") else "nie dotarło do niego jeszcze żadne zamówienie"
            naj.append(f"Sklep „{s['nazwa']}” jest podłączony do GetResponse, ale w oknie nie ma żadnych zamówień ({kiedy}). Integracja nie przesyła sprzedaży — automaty koszyka i po zakupie oraz liczenie przychodu nie mają na czym działać.")
        if (s.get("bez_kontaktu_proc") or 0) >= 10:
            naj.append(f"Sklep „{s['nazwa']}”: {f(s['bez_kontaktu_proc'])} zamówień trafia do GetResponse bez kontaktu. Część to klienci bez zgody na maile (tak ma być), ale sprawdź, czy każdy, kto zaznaczył zgodę, ma kontakt — inaczej nie dostanie maili po zakupie.")
    wszystkie = D["maile_automatow"] + D["newslettery"]
    wysylane = [x for x in wszystkie if x["wyslane"] > 0]
    bez_przych = [x for x in wysylane if not x["liczy_przychod"]]
    if bez_przych:
        naj.append(f"{len(bez_przych)} z {len(wysylane)} wysyłanych maili nie ma włączonego liczenia przychodu — nie wiadomo, ile sprzedają.")
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

    L += [f"## Newslettery — ostatnie {D['okno_dni']} dni", ""]
    if nl:
        w = sum(x["wyslane"] for x in nl)
        def sr(k):
            war = [(x[k], x["wyslane"]) for x in nl if x[k] is not None and x["wyslane"]]
            return round(sum(a * b for a, b in war) / sum(b for _, b in war), 2) if war else None
        L += [f"- Wysłanych newsletterów: **{len(nl)}** (średnio {tyg(len(nl) / (D['okno_dni'] / 7))} tygodniowo), łącznie {zl(w)} maili.",
              f"- Średnio (ważone liczbą wysłanych): otwarcia ludzi {f(sr('otwarcia_ludzi_proc'))}, kliknięcia {f(sr('klikniecia_ludzi_proc'))}, wypisy {f(sr('wypisy_proc'))}, skargi {f(sr('skargi_proc'))}, odbicia {f(sr('odbicia_proc'))}.",
              f"- Z liczeniem przychodu: {sum(1 for x in nl if x['liczy_przychod'])} z {len(nl)}.", "",
              "| Data | Temat | Wysłane | Kliknięcia | Wypisy | Problemy |", "|---|---|---|---|---|---|"]
        for x in nl[:25]:
            L.append(f"| {x['wyslany']} | {x['temat']} | {zl(x['wyslane'])} | {f(x['klikniecia_ludzi_proc'])} | {f(x['wypisy_proc'])} | {', '.join(x['problemy'])} |")
        if len(nl) > 25:
            L.append(f"| … | jeszcze {len(nl) - 25} | | | | |")
    else:
        L.append("Brak wysłanych newsletterów w tym okresie.")
    L += [""]

    L += ["## Sklep", ""]
    if not D["sklepy"]:
        L += ["Do GetResponse nie jest podłączony żaden sklep — automaty koszyka, po zakupie i liczenie przychodu nie mają danych.", ""]
    for s in D["sklepy"]:
        L += [f"**{s['nazwa']}** ({s['waluta']})", ""]
        if "zamowienia" in s:
            L += [f"- Zamówienia w GetResponse w oknie (bez anulowanych i zwróconych): **{zl(s['zamowienia'])}** na {zl(s['suma'])} {s['waluta']}"
                  + (" (liczenie przerwane bezpiecznikiem — sklep bardzo duży)" if s.get("obciete") else "") + ".",
                  f"- Bez przypisanego kontaktu: **{zl(s['bez_kontaktu'])} ({f(s['bez_kontaktu_proc'])})** — część to klienci bez zgody na maile; problem jest wtedy, gdy brakuje kontaktu klientom ze zgodą."]
        L += [f"- Raport e-commerce GetResponse (API) w tym oknie: {zl(s['raport_zamowienia'])} {odm(int(s['raport_zamowienia'] or 0), 'zamówienie', 'zamówienia', 'zamówień')}, {zl(s['raport_przychod'])} {s['waluta']}. "
              "Jeśli to dużo mniej niż zamówienia powyżej, raport liczy tylko przychód przypisany do maili (zakup po kliknięciu w link) — porównaj z panelem: Raporty → E-commerce.", ""]

    L += ["## Czego ten audyt nie widzi (sprawdź w panelu)", "",
          "- Warunków, opóźnień i rozgałęzień w automatach — API GetResponse ich nie udostępnia.",
          "- Który mail należy do którego automatu.",
          "- Przypisanego przychodu per automat (kolumna „Przypisany przychód” na liście automatów).",
          "- Czy na stronie działa śledzenie (Web Connect) potrzebne do automatów przeglądania produktów.", "",
          f"_Zapytań do API: {D['zapytan_api']}._", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
