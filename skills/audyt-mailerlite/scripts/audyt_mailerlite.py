#!/usr/bin/env python3
"""Audyt e-mail marketingu w MailerLite — TYLKO ODCZYT.

Sprawdza: automatyzacje (wyzwalacz, czy działają, czy są zepsute, każdy mail z wynikami,
link do wypisu), kampanie z ostatnich N dni, sklep (zamówienia i przypisanie do maili),
ustawienia liczenia sprzedaży i listę kontrolną automatów sklepu internetowego.

Nie zmienia niczego na koncie. Wywołuje wyłącznie zapytania GET.
Nie pobiera adresów e-mail ani danych subskrybentów — tylko liczby zbiorcze.

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

API = "https://connect.mailerlite.com/api"
PRZERWA = 0.55  # limit MailerLite: 120 zapytań na minutę


class _BezPrzekierowan(urllib.request.HTTPRedirectHandler):
    """Przekierowanie = błąd. urllib przy przekierowaniu wysyła nagłówki (z kluczem) pod nowy adres."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OTWIERACZ = urllib.request.build_opener(_BezPrzekierowan)

# Lista kontrolna wg WYZWALACZA automatu (API MailerLite go pokazuje). Wyzwalacze ogólne
# (formularz, grupa, segment, pole) rozstrzyga nazwa automatu.
KOSZYK = {"abandoned_cart", "abandoned_checkout"}
ZAKUP = {"purchased_any_product", "purchased_from_category", "purchased_specific_product"}
PONOWNY = {"purchase_frequency"}
SLOWA = {
    "Po zakupie": ["po zakup", "post-purchase", "dziękujemy za zakup", "dziękujemy za zamówienie", "opini", "recenz", "kupił", "kupil"],
    "Porzucony koszyk": ["koszyk", "cart", "porzuc"],
    "Drugi zakup / reaktywacja": ["ponown", "drugi zakup", "kolejne zamów", "replenish", "uzupełn", "reaktyw", "win-back", "winback", "tęsknimy", "dawno cię", "dawno nie"],
    "Powitanie": ["powital", "powitan", "welcome", "witaj", "po zapisie", "za zapis", "onboard"],
}
LISTA = ["Powitanie", "Porzucony koszyk", "Po zakupie", "Drugi zakup / reaktywacja"]


class ML:
    def __init__(self, klucz):
        self.h = {"Authorization": "Bearer " + klucz, "Accept": "application/json"}
        self.zapytan = 0
        self.niedostepne = []
        self.ostrzezenia = []

    def get(self, sciezka, params=None):
        url = sciezka if sciezka.startswith("https://") else API + sciezka
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="[]")
        if not url.startswith(API + "/"):
            sys.exit(f"Nieoczekiwany adres spoza API MailerLite — przerwano, token nie zostanie wysłany ({url.split('?')[0]}).")
        for proba in range(5):
            time.sleep(PRZERWA)
            self.zapytan += 1
            try:
                r = _OTWIERACZ.open(urllib.request.Request(url, headers=self.h), timeout=120)
                surowe = r.read() or b"null"
                try:
                    return json.loads(surowe)
                except ValueError:
                    sys.exit(f"API zwróciło odpowiedź, która nie jest JSON-em ({sciezka}).")
            except (socket.timeout, TimeoutError, http.client.IncompleteRead, ConnectionError):
                if proba < 4:
                    time.sleep(5 * (proba + 1))
                    continue
                raise
            except urllib.error.HTTPError as e:
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
                raise
        sys.exit(f"API MailerLite nie odpowiedziało po 5 próbach ({sciezka}) — przerwano, żeby raport nie był oparty na brakujących danych.")

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


def main():
    ap = argparse.ArgumentParser(description="Audyt MailerLite (tylko odczyt)")
    ap.add_argument("--dni", type=int, default=90)
    ap.add_argument("--raport", default="audyt-mailerlite.md")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if a.dni < 1:
        sys.exit("--dni musi być co najmniej 1.")
    klucz = os.environ.get("MAILERLITE_API_KEY")
    if not klucz:
        sys.exit("Brak zmiennej MAILERLITE_API_KEY. Token: MailerLite → Integracje → MailerLite API → Wygeneruj nowy token.")
    ml = ML(klucz)
    dzis = dt.date.today()
    od = (dzis - dt.timedelta(days=a.dni)).isoformat()
    D = {"data_audytu": dzis.isoformat(), "okno_dni": a.dni, "od": od}

    print("1/5 grupy…", file=sys.stderr)
    D["grupy"] = sorted(({"nazwa": g.get("name"), "aktywni": int(liczba(g.get("active_count")))}
                         for g in ml.wszystkie("/groups")), key=lambda x: -x["aktywni"])

    print("2/5 ustawienia sprzedaży i sklepy…", file=sys.stderr)
    ust = (ml.get("/ecommerce/settings") or {}).get("data") or {}
    D["ustawienia"] = {"sledzenie_kampanie": ust.get("ecommerce_tracking_in_campaigns"),
                       "sledzenie_automaty": ust.get("ecommerce_tracking_in_automations"),
                       "okno_przypisania_dni": ust.get("ecommerce_attribution_window")}
    D["sklepy"] = []
    for s in ml.wszystkie("/ecommerce/shops"):
        n = suma = przyp = 0
        statusy = {}
        for o in ml.wszystkie(f"/ecommerce/shops/{s['id']}/orders"):
            kiedy = str(o.get("completed_at") or o.get("created_at") or "")[:10]
            if kiedy and kiedy < od:
                continue
            st = o.get("status") or "brak"
            statusy[st] = statusy.get(st, 0) + 1
            if st not in ("brak", "complete", "completed"):
                continue
            n += 1
            suma += liczba(o.get("total_price"))
            at = o.get("attribution")
            if isinstance(at, dict) and isinstance(at.get("attribution"), dict):
                at = at["attribution"]
            przyp += 1 if isinstance(at, dict) and at.get("email_id") else 0
        D["sklepy"].append({"nazwa": czysc(s.get("name")) or "—", "platforma": s.get("platform"), "wlaczony": s.get("enabled"),
                            "wewnetrzny": bool(s.get("internal")),  # sklep MailerLite zakładany automatycznie
                            "waluta": s.get("currency"), "zamowienia": n, "suma": round(suma, 2),
                            "przypisane_do_maili": przyp, "statusy": statusy})

    print("3/5 automatyzacje…", file=sys.stderr)
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
        for k in x.get("steps") or []:
            if k.get("type") != "email":
                continue
            e = k.get("email") or {}
            m = wyniki_maila(e.get("stats"))
            m["temat"] = czysc(k.get("subject") or e.get("subject"))
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

    print(f"4/5 kampanie z {a.dni} dni…", file=sys.stderr)
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

    print("5/5 lista kontrolna…", file=sys.stderr)
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

    with open(a.raport, "w", encoding="utf-8") as plik:
        plik.write(raport(D))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as plik:
            json.dump(D, plik, ensure_ascii=False, indent=1)
    print(f"Gotowe: {a.raport} ({ml.zapytan} zapytań do API)", file=sys.stderr)


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


def raport(D):
    L = [f"# Audyt e-mail marketingu — MailerLite ({D['data_audytu']})", "",
         f"Okno kampanii i zamówień: ostatnie {D['okno_dni']} dni (od {D['od']}). Tylko odczyt, dane zbiorcze, bez danych subskrybentów.", ""]
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
        if s["zamowienia"] == 0:
            naj.append(f"Sklep „{s['nazwa']}” jest podłączony, ale API nie zwróciło zamówień z tego okresu. Jeśli sklep sprzedawał, zamówienia nie trafiają do MailerLite — sprawdź integrację.")
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

    L += ["## Lista kontrolna automatów sklepu", "", "| Automat | Stan | Znalezione |", "|---|---|---|"]
    for x in D["lista_kontrolna"]:
        ik = "✅" if x["stan"] == "działa" else ("⚠️" if x["stan"].startswith("jest") or "wymaga" in x["stan"] else "❌")
        L.append(f"| {x['automat']} | {ik} {x['stan']} | {'; '.join(x['trafienia']) or '—'} |")
    L += ["", "Rozpoznanie po wyzwalaczu automatu (koszyk, zakup, częstotliwość zakupów); przy wyzwalaczach ogólnych (formularz, grupa) — po nazwie. "
          "Automatu „porzucone przeglądanie” MailerLite nie oferuje, więc go nie sprawdzamy.", ""]

    L += ["## Automatyzacje", "", "| Automat | Wyzwalacz | Włączony | Zakończyli | W kolejce | Wysłane | Kliknięcia | Uwagi |", "|---|---|---|---|---|---|---|---|"]
    for x in sorted(D["automaty"], key=lambda x: (not x["wlaczony"], -x["wyslane"])):
        L.append(f"| {x['nazwa']} | {', '.join(x['wyzwalacze']) or '—'} | {'tak' if x['wlaczony'] else 'nie'} | {zl(x['zakonczyli'])} | {zl(x['w_kolejce'])} | {zl(x['wyslane'])} | {f(x['klikniecia_proc'])} | {'; '.join(x['uwagi'])} |")
    L += ["", "### Maile w automatach", "", "Otwarcia w MailerLite obejmują też automatyczne otwarcia programów pocztowych — oceniaj po kliknięciach.", "",
          "| Automat | Temat | Wysłane | Otwarcia | Kliknięcia | Wypisy | Problemy |", "|---|---|---|---|---|---|---|"]
    for x in D["automaty"]:
        for m in x["maile"]:
            L.append(f"| {x['nazwa']} | {m['temat'] or '—'} | {zl(m['wyslane'])} | {f(m['otwarcia_proc'])} | {f(m['klikniecia_proc'])} | {f(m['wypisy_proc'])} | {', '.join(m['problemy'])} |")
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

    L += ["## Sklep i liczenie sprzedaży", "",
          f"- Liczenie sprzedaży w nowych kampaniach: **{tn(u.get('sledzenie_kampanie'))}**, w nowych automatach: **{tn(u.get('sledzenie_automaty'))}**, okno przypisania: {u.get('okno_przypisania_dni') or '—'} dni po kliknięciu."]
    for s in D["sklepy"]:
        L.append(f"- Sklep „{s['nazwa']}” ({'wewnętrzny sklep MailerLite' if s['wewnetrzny'] else s['platforma']}, {'włączony' if s['wlaczony'] else 'wyłączony'}): {zl(s['zamowienia'])} {odm(s['zamowienia'], 'zamówienie', 'zamówienia', 'zamówień')} na {zl(s['suma'])} {s['waluta'] or ''} w oknie, z tego przypisanych do maili: {zl(s['przypisane_do_maili'])}."
                 + (f" Statusy zamówień w oknie: {', '.join(f'{k} {v}' for k, v in s['statusy'].items())} (do sprzedaży liczone tylko zakończone)." if s.get("statusy") else ""))
    if not D["sklepy"]:
        L.append("- Brak podłączonego sklepu.")
    L += ["", "## Czego ten audyt nie widzi", "",
          "- Treści maili i tego, czy oferta ma sens — tylko liczby.",
          "- Sprzedaży poza MailerLite (jeśli sklep nie przesyła zamówień, sprzedaż z maili jest niewidoczna).",
          "- Progi w kolumnie „Problemy” (wypisy > 0,5%, kliknięcia < 0,5%, odbicia > 2%, ocena od 200 wysłanych) to orientacyjne progi praktyczne. Skargi: Google wymaga poniżej 0,3% i zaleca poniżej 0,1%.", ""]
    if D.get("niedostepne"):
        L += ["**Niedostępne na tym koncie (403/404 — funkcja może nie wchodzić w plan):** " + ", ".join(f"`{x}`" for x in D["niedostepne"][:8]), ""]
    if D.get("ostrzezenia"):
        L += ["**Ostrzeżenia:**", ""] + [f"- {x}" for x in D["ostrzezenia"]] + [""]
    L += [f"_Zapytań do API: {D['zapytan_api']}._", ""]
    return "\n".join(L)


if __name__ == "__main__":
    main()
