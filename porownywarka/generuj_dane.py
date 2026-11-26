#!/usr/bin/env python3
"""Porównywarka newsletterów sklepów — generator jednego pliku z liczbami dla strony.

Czyta dane obserwacji (tylko odczyt) i zapisuje JSON, z którego strona
/porownywarka-newsletterow/ bierze wszystkie liczby. Po odświeżeniu danych wystarczy
uruchomić skrypt ponownie i wgrać plik (patrz odswiez.sh).

Wejście (katalog --zrodlo):
  maile.jsonl          jeden mail na wiersz (sklep, data, temat, kody…)
  klasyfikacja.jsonl   klasyfikacja maila po kluczu (kategoria, typ, rabat_max…)
  sklepy.json          lista sklepów (nazwa, branża, status zapisu, data zapisu)
  Raporty/Monitor-*.md najnowszy raport monitora — tabela „System | Sklepów | Sklepy”
  monitor.py           funkcja podwojne_potwierdzenie() — JEDYNA definicja podwójnego potwierdzenia zapisu
                       (ta sama liczba w monitorze i na stronie; bez monitor.py generator się zatrzymuje)
  porownywarka-pomiary.json  (z --historia) historia pomiarów podwójnego potwierdzenia, dopisywana przy odświeżeniu

Do pliku trafiają wyłącznie liczby i nazwy sklepów. Bez tematów maili, treści,
adresów nadawców i nazwy skrzynki testowej.

Użycie:
  python3 porownywarka/generuj_dane.py --zrodlo ~/Obsidian/Zasoby/Newslettery-obserwacja --wyjscie dane-porownywarka.json
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP
import collections
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import statistics as st
import sys

WERSJA = 3
MIN_SKLEPOW_BRANZY = 3   # mniej sklepów = branża trafia do „inne”, bez karty porównania
MALO_MAILI = 20  # mniej zwykłych newsletterów w branży = dopisek „orientacyjnie”
MIN_DNI_CZESTOTLIWOSC = 7  # sklep wchodzi do „maili tygodniowo”, jeśli obserwujemy go co najmniej tydzień
MIN_PROBA_WYROZNIENIA = 3  # „x z y” wyróżniamy w tabeli tylko przy y co najmniej tyle (1 z 1 to nie wynik)
TYPY_STARTOWE = {"potwierdzenie", "powitalny", "przypomnienie-kodu"}
SPRZEDAZ = {"sprzedazowy", "mieszany"}
DNI_PL = ["pn", "wt", "śr", "czw", "pt", "sob", "nd"]
DNI_W = ["w poniedziałek", "we wtorek", "w środę", "w czwartek", "w piątek", "w sobotę", "w niedzielę"]

RE_RABAT = re.compile(r"rabat", re.I)
RE_PROMOCJA = re.compile(r"promocj", re.I)
RE_PROCENT = re.compile(r"%")
RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
RE_BLACK = re.compile(r"black|czarn\w* (piątek|tydzień)|cyber", re.I)
PRZYKLADY_ZACHETY = 4  # ile marek z rabatem w temacie prośby o potwierdzenie pokazujemy z nazwy


def najczestsze(licznik, ile, nazwa, limit=4):
    """Najczęstsze wartości razem z remisami na ostatnim miejscu. Za dużo remisów = pusta lista (brak wyraźnego wzoru)."""
    if not licznik:
        return []
    po = sorted(licznik.items(), key=lambda x: (-x[1], x[0]))
    prog = po[min(ile, len(po)) - 1][1]
    wynik = [k for k, v in po if v >= prog]
    return [nazwa(k) for k in sorted(wynik, key=lambda k: (-licznik[k], k))] if len(wynik) <= limit else []


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def branza_wspolna(b):
    """Sprowadza opisy branż z listy sklepów do kilkunastu nazw widocznych na stronie."""
    b = (b or "").strip()
    m = b.lower()
    if any(x in m for x in ("beauty", "uroda", "kosmety", "perfum")):
        return "Uroda"
    if "drogeri" in m or "aptek" in m:
        return "Apteka i drogeria"
    if m.startswith("podróże"):
        return "Podróże"
    if m in ("dom i ogród", "meble"):
        return "Dom"
    if "sport" in m or m == "outdoor":
        return "Sport"
    if m in ("odzież/obuwie",):
        return "Moda"
    if m.startswith("elektronika"):
        return "Elektronika"
    if m.startswith("dzieci"):
        return "Dzieci"
    if "biżuteria" in m:
        return "Biżuteria"
    return b or "Inne"


def slug(s):
    tr = str.maketrans("ąćęłńóśźż", "acelnoszz")
    return re.sub(r"[^a-z0-9]+", "-", s.lower().translate(tr)).strip("-")


def data_maila(s):
    s = (s or "").replace(" ", " ").replace("\xa0", " ").strip()
    for f in ("%a, %b %d, %Y, %I:%M %p", "%b %d, %Y, %I:%M %p"):
        try:
            return dt.datetime.strptime(s, f)
        except ValueError:
            pass
    raise ValueError("nieznany format daty: %r" % s)


def zaokr(x, miejsca=1):
    """Zaokrąglenie „szkolne” (połówki w górę), np. 3,15 → 3,2."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-miejsca), rounding=ROUND_HALF_UP))


def procent(a, b):
    return round(100 * a / b) if b else None


def odmiana(n, jeden, kilka, wiele):
    if n == 1:
        return jeden
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return kilka
    return wiele


def liczba_pl(x):
    """1.5 -> „1,5”."""
    return ("%.1f" % x).replace(".", ",") if isinstance(x, float) else str(x)


def liczba_strony(x):
    """Liczba do tabeli na stronie: pełne liczby, poniżej 2 jedno miejsce po przecinku (0 bez przecinka)."""
    if x is None:
        return None
    if x == 0:
        return "0"
    if x < 2:
        return liczba_pl(zaokr(x))
    return str(int(zaokr(x, 0)))


def z_ilu(n):
    """„z 1 sklepu” / „z 5 sklepów”."""
    return "z %d %s" % (n, "sklepu" if n == 1 else "sklepów")


def wnioski(b, og):
    """Trzy zdania „co to znaczy dla Twojego sklepu” — porównanie branży z wszystkimi sklepami, bez nowych liczb."""
    zd = []
    t, t_og = b["tabela"]["tydzien_wartosc"], og["tydzien_wartosc"]
    if t == 0:
        zd.append("Co najmniej połowa sklepów w tej branży nie wysłała w tym czasie żadnego newslettera, a ogół sklepów wysyła %s tygodniowo." % og["tydzien"])
    elif t is None:
        zd.append("Za krótko obserwuję te sklepy, żeby policzyć, ile newsletterów wysyłają w tygodniu.")
    else:
        ile = "%s %s tygodniowo" % (b["tabela"]["tydzien"], "newslettera" if "," in b["tabela"]["tydzien"]
                                     else odmiana(int(b["tabela"]["tydzien"]), "newsletter", "newslettery", "newsletterów"))
        if t_og and t < 0.75 * t_og:
            jak = "rzadziej niż ogół sklepów"
        elif t_og and t > 1.33 * t_og:
            jak = "częściej niż ogół sklepów"
        else:
            jak = "mniej więcej tyle co ogół sklepów"
        zd.append("Typowy sklep w tej branży wysyła %s, czyli %s (%s)." % (ile, jak, og["tydzien"]))
    p, p_og = b["tabela"]["oferty_proc"], og["oferty_proc"]
    if p is not None:
        if p == 100:
            zd.append("Każdy newsletter to oferta albo rabat (we wszystkich branżach %d%%)." % p_og)
        elif p >= 90:
            zd.append("Prawie każdy newsletter to oferta albo rabat: %d%% (we wszystkich branżach %d%%)." % (p, p_og))
        elif p > p_og + 5:
            zd.append("Oferty i rabaty to %d%% newsletterów, więcej niż we wszystkich branżach (%d%%)." % (p, p_og))
        elif p < p_og - 5:
            zd.append("Oferty i rabaty to %d%% newsletterów, mniej niż we wszystkich branżach (%d%%)." % (p, p_og))
        else:
            zd.append("Oferty i rabaty to %d%% newsletterów, podobnie jak we wszystkich branżach (%d%%)." % (p, p_og))
    po, pw = b["tabela"]["potwierdzenie"], b["tabela"]["powitanie"]
    if po["prosi"]:
        a = "Kliknięcia w link potwierdzający zapis wymaga %d %s" % (po["prosi"], z_ilu(po["sklepy"]))
    else:
        a = "Żaden sklep nie wymaga kliknięcia w link potwierdzający zapis"
    if pw["sklepy"]:
        c = "rabat na powitanie daje %d %s z mailem powitalnym" % (pw["z_rabatem"], z_ilu(pw["sklepy"]))
    else:
        c = "żaden nie przysłał maila powitalnego"
    zd.append("%s, a %s." % (a, c))
    return zd


def wyroznij(branze):
    """Najwyższa i najniższa wartość w każdej kolumnie tabeli (po zaokrągleniu, remisy razem).
    Pomijamy branże z małą liczbą maili i „x z y” przy y < MIN_PROBA_WYROZNIENIA."""
    def wart(b, kol):
        t = b["tabela"]
        if kol == "tydzien":
            return None if t["tydzien"] is None else float(t["tydzien"].replace(",", "."))
        if kol == "oferty":
            return t["oferty_proc"]
        x = t[kol]
        n = x["sklepy"]
        return procent(x["prosi"] if kol == "potwierdzenie" else x["z_rabatem"], n) if n >= MIN_PROBA_WYROZNIENIA else None
    for b in branze:
        b["wyroznienie"] = {}
    for kol in ("tydzien", "oferty", "potwierdzenie", "powitanie"):
        w = {b["slug"]: wart(b, kol) for b in branze if not b["malo_danych"]}
        w = {k: v for k, v in w.items() if v is not None}
        if len(set(w.values())) < 2:
            continue
        hi, lo = max(w.values()), min(w.values())
        for b in branze:
            if b["slug"] in w:
                b["wyroznienie"][kol] = "max" if w[b["slug"]] == hi else "min" if w[b["slug"]] == lo else None


def systemy_linia(systemy):
    """Jedna linijka: trzy najczęstsze programy i „i inne”."""
    nazwy = [s["nazwa"] for s in systemy]
    return ", ".join(nazwy[:3]) + (" i inne" if len(nazwy) > 3 else "") if nazwy else None


def rabat_proc(v):
    m = re.search(r"(\d{1,2})\s?%", str(v or ""))
    return int(m.group(1)) if m else None


def systemy_z_monitora(katalog):
    """Najnowszy Raporty/Monitor-*.md → {nazwa sklepu (norm): system}. Bez raportu = pusty słownik."""
    pliki = sorted(glob.glob(os.path.join(katalog, "Raporty", "Monitor-*.md")))
    if not pliki:
        return {}, None
    wynik = {}
    w_tabeli = False
    with open(pliki[-1], encoding="utf-8") as f:
        linie = f.read().splitlines()
    for linia in linie:
        if re.match(r"\|\s*System\s*\|\s*Sklepów\s*\|", linia):
            w_tabeli = True
            continue
        if w_tabeli:
            if not linia.startswith("|"):
                break
            kol = [k.strip() for k in linia.strip().strip("|").split("|")]
            if len(kol) < 3 or set(kol[0]) <= {"-", " "}:
                continue
            system = re.sub(r"\s*\(.*?\)", "", kol[0]).strip()
            if system.lower() == "platforma sklepu":
                system = "platforma sklepu (np. IdoSell, Shoper)"
            for sklep in kol[2].split(","):
                if sklep.strip():
                    wynik[norm(sklep)] = system
    return wynik, os.path.basename(pliki[-1])


def potwierdzenia_z_monitora(katalog, maile, klas):
    """Wywołuje podwojne_potwierdzenie() z monitor.py w katalogu danych — ta sama logika co w monitorze,
    bez liczenia drugi raz po swojemu. Brak monitor.py albo funkcji = błąd (nie zgadujemy)."""
    sciezka = os.path.join(katalog, "monitor.py")
    if not os.path.exists(sciezka):
        raise SystemExit("Brak %s — nie liczę podwójnego potwierdzenia bez monitora." % sciezka)
    spec = importlib.util.spec_from_file_location("monitor_newsletterow", sciezka)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "podwojne_potwierdzenie"):
        raise SystemExit("monitor.py nie ma funkcji podwojne_potwierdzenie().")
    return mod.podwojne_potwierdzenie([
        {"sklep": m["sklep"], "temat": m.get("temat"), "tresc": m.get("tresc"), "przyciski": m.get("przyciski"),
         "typ": (klas.get(m["klucz"]) or {}).get("typ")} for m in maile])


def historia(plik, wynik, dzis):
    """Dopisuje dzisiejszy pomiar podwójnego potwierdzenia (jeden na dzień, ten sam dzień = nadpisanie)
    i zwraca poprzedni pomiar z innego dnia albo None. Plik nie istnieje = zaczynamy historię."""
    p = wynik["podwojne"]
    pomiary = []
    if os.path.exists(plik):
        with open(plik, encoding="utf-8") as f:
            pomiary = json.load(f)
    pomiary = [x for x in pomiary if x.get("data") != dzis]
    wczesniej = sorted((x for x in pomiary if x.get("data", "") < dzis), key=lambda x: x["data"])
    pomiary.append({"data": dzis, "dane_do": wynik["okres"]["do"], "sklepy": p["sklepy"],
                    "z_potwierdzeniem": p["z_potwierdzeniem"], "proc": p["proc"]})
    pomiary.sort(key=lambda x: x["data"])
    tmp = plik + ".nowy"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pomiary, f, ensure_ascii=False, indent=1)
    os.replace(tmp, plik)
    if not wczesniej:
        return None
    x = dict(wczesniej[-1])
    x["data_pl"] = dt.date.fromisoformat(x["data"]).strftime("%d.%m.%Y")
    return x


def wczytaj(katalog):
    with open(os.path.join(katalog, "maile.jsonl"), encoding="utf-8") as f:
        maile = [json.loads(l) for l in f if l.strip()]
    with open(os.path.join(katalog, "klasyfikacja.jsonl"), encoding="utf-8") as f:
        klas = {k["klucz"]: k for k in (json.loads(l) for l in f if l.strip())}
    with open(os.path.join(katalog, "sklepy.json"), encoding="utf-8") as f:
        sklepy = json.load(f)
    return maile, klas, sklepy


def policz(maile, klas, sklepy, systemy, potwierdzenia, teraz=None):
    """potwierdzenia = wynik monitor.podwojne_potwierdzenie() ({sklep: {"jak", "zacheta", ...}})."""
    po_nazwie = {norm(s["nazwa"]): s for s in sklepy}

    def sklep_z_listy(n):
        k = norm(n)
        if k in po_nazwie:
            return po_nazwie[k]
        for kk, s in po_nazwie.items():
            if kk and (kk in k or k in kk):
                return s
        return None

    for m in maile:
        m["_dt"] = data_maila(m["data"])
        m["_k"] = klas.get(m["klucz"])
    od = min(m["_dt"] for m in maile).date()
    do = max(m["_dt"] for m in maile).date()
    dni_okresu = (do - od).days + 1

    per_sklep = collections.defaultdict(list)
    for m in maile:
        per_sklep[m["sklep"]].append(m)

    info = {}
    for nazwa, ms in per_sklep.items():
        s = sklep_z_listy(nazwa)
        zapis = None
        if s and s.get("zapis"):
            try:
                zapis = dt.date.fromisoformat(s["zapis"])
            except ValueError:
                zapis = None
        start = max(od, zapis) if zapis else min(m["_dt"] for m in ms).date()
        dni = (do - start).days + 1
        regularne = [m for m in ms if m["_k"] and m["_k"].get("typ") not in TYPY_STARTOWE]
        powitalne = [m for m in ms if m["_k"] and m["_k"].get("typ") == "powitalny"]
        info[nazwa] = {
            "branza": branza_wspolna(s["branza"]) if s else "Inne",
            "maile": ms, "regularne": regularne, "dni": dni,
            "tydzien": zaokr(len(regularne) / dni * 7) if dni >= MIN_DNI_CZESTOTLIWOSC else None,
            "potwierdzenie": nazwa in potwierdzenia,
            "potwierdzenie_jak": (potwierdzenia.get(nazwa) or {}).get("jak"),
            "zacheta": bool((potwierdzenia.get(nazwa) or {}).get("zacheta")),
            "powitanie": bool(powitalne),
            "powitanie_rabat": any(m["_k"].get("rabat_max") or m.get("kody") for m in powitalne),
            "system": systemy.get(norm(nazwa)),
        }

    wysylajace = {norm(n) for n in per_sklep}

    def milczy(s):
        if s.get("status") != "zapisany" or not s.get("zapis"):
            return False
        try:
            z = dt.date.fromisoformat(s["zapis"])
        except ValueError:
            return False
        k = norm(s["nazwa"])
        wyslal = k in wysylajace or any(k and (k in w or w in k) for w in wysylajace)
        return not wyslal and (do - z).days >= MIN_DNI_CZESTOTLIWOSC

    cisza = [s for s in sklepy if milczy(s)]

    def tabela(tyg, n_sprz, n_reg, prosi, sklepy_n, z_rabatem, z_powitaniem):
        """Cztery liczby z tabeli porównawczej (te same definicje co w karcie)."""
        med = zaokr(st.median(tyg)) if tyg else None
        return {"tydzien": liczba_strony(med), "tydzien_wartosc": med,
                "oferty_proc": procent(n_sprz, n_reg),
                "potwierdzenie": {"prosi": prosi, "sklepy": sklepy_n},
                "powitanie": {"z_rabatem": z_rabatem, "sklepy": z_powitaniem}}

    def karta(nazwa_br, sklepy_br):
        ms = [m for n in sklepy_br for m in info[n]["maile"]]
        reg = [m for n in sklepy_br for m in info[n]["regularne"]]
        sprz = [m for m in reg if m["_k"].get("kategoria") in SPRZEDAZ]
        tyg = sorted(info[n]["tydzien"] for n in sklepy_br if info[n]["tydzien"] is not None)
        dni = collections.Counter(m["_dt"].weekday() for m in reg)
        godz = collections.Counter(m["_dt"].hour for m in reg)
        tematy = [m["temat"] for m in reg]
        sys_c = collections.Counter(info[n]["system"] for n in sklepy_br if info[n]["system"] and info[n]["system"] != "nierozpoznane")
        z_powitaniem = [n for n in sklepy_br if info[n]["powitanie"]]
        kolejnosc = sorted(sklepy_br, key=lambda n: (-len(info[n]["maile"]), n.lower()))
        return {
            "nazwa": nazwa_br, "slug": slug(nazwa_br),
            "sklepy": len(sklepy_br), "maile": len(ms), "regularne": len(reg),
            "tydzien": {
                "mediana": liczba_pl(zaokr(st.median(tyg))) if tyg else None,
                "od": liczba_pl(tyg[0]) if tyg else None, "do": liczba_pl(tyg[-1]) if tyg else None,
                "sklepy": len(tyg),
            },
            "sprzedazowe_proc": procent(len(sprz), len(reg)),
            "dni": [{"dzien": DNI_PL[i], "maile": dni.get(i, 0),
                     "proc": procent(dni.get(i, 0), len(reg)) or 0,
                     "wys": round(100 * dni.get(i, 0) / max(dni.values())) if dni else 0} for i in range(7)],
            "dni_top": najczestsze(dni, 2, DNI_W.__getitem__),
            "godziny_top": najczestsze(godz, 3, lambda h: "%d:00" % h),
            "malo_danych": len(reg) < MALO_MAILI,
            "tematy": {
                "rabat": procent(sum(1 for t in tematy if RE_RABAT.search(t)), len(tematy)),
                "procent": procent(sum(1 for t in tematy if RE_PROCENT.search(t)), len(tematy)),
                "emoji": procent(sum(1 for t in tematy if RE_EMOJI.search(t)), len(tematy)),
                "black": procent(sum(1 for t in tematy if RE_BLACK.search(t)), len(tematy)),
            },
            "potwierdzenie": {"prosi": sum(1 for n in sklepy_br if info[n]["potwierdzenie"]),
                              "z_zacheta": sum(1 for n in sklepy_br if info[n]["zacheta"]),
                              "sklepy": len(sklepy_br)},
            "potwierdzenie_proc": procent(sum(1 for n in sklepy_br if info[n]["potwierdzenie"]), len(sklepy_br)),
            "powitanie": {"z_rabatem": sum(1 for n in z_powitaniem if info[n]["powitanie_rabat"]),
                          "sklepy": len(z_powitaniem)},
            "systemy": [{"nazwa": k, "sklepy": v} for k, v in sorted(sys_c.items(), key=lambda x: (-x[1], x[0].lower()))],
            "systemy_rozpoznane": sum(sys_c.values()),
            "systemy_linia": systemy_linia([{"nazwa": k} for k, v in sorted(sys_c.items(), key=lambda x: (-x[1], x[0].lower()))]),
            "tabela": tabela(tyg, len(sprz), len(reg),
                             sum(1 for n in sklepy_br if info[n]["potwierdzenie"]), len(sklepy_br),
                             sum(1 for n in z_powitaniem if info[n]["powitanie_rabat"]), len(z_powitaniem)),
            "przyklady": [n for n in kolejnosc],
            "najczesciej": [{"nazwa": n, "maile": len(info[n]["maile"]),
                             "tydzien": liczba_pl(info[n]["tydzien"]) if info[n]["tydzien"] is not None else None}
                            for n in kolejnosc[:3]],
            "cisza": sum(1 for s in cisza if branza_wspolna(s["branza"]) == nazwa_br),
        }

    grupy = collections.defaultdict(list)
    for n, i in info.items():
        grupy[i["branza"]].append(n)
    branze, inne = [], []
    for b, ss in sorted(grupy.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(ss) >= MIN_SKLEPOW_BRANZY and b != "Inne":
            branze.append(karta(b, ss))
        else:
            inne.append({"nazwa": b, "sklepy": len(ss), "maile": sum(len(info[n]["maile"]) for n in ss)})

    # Ciekawostki — każda z liczbą, liczona z tych samych danych co karty.
    wszystkie = list(info)
    reg_all = [m for n in wszystkie for m in info[n]["regularne"]]
    sprz_all = [m for m in reg_all if m["_k"].get("kategoria") in SPRZEDAZ]
    tematy_all = [m["temat"] for m in reg_all]
    potw = [n for n in wszystkie if info[n]["potwierdzenie"]]
    zach = [n for n in wszystkie if info[n]["zacheta"]]
    powit = [n for n in wszystkie if info[n]["powitanie"]]
    powit_r = [n for n in powit if info[n]["powitanie_rabat"]]
    rabaty = [r for r in (rabat_proc(m["_k"].get("rabat_max")) for m in sprz_all) if r]
    tyg_all = sorted(info[n]["tydzien"] for n in wszystkie if info[n]["tydzien"] is not None)
    n_rabat = sum(1 for t in tematy_all if RE_RABAT.search(t))
    n_promo = sum(1 for t in tematy_all if RE_PROMOCJA.search(t))
    n_emoji = sum(1 for t in tematy_all if RE_EMOJI.search(t))
    ogolem = tabela(tyg_all, len(sprz_all), len(reg_all), len(potw), len(wszystkie), len(powit_r), len(powit))
    ogolem["sklepy"] = len(wszystkie)
    for b in branze:
        b["wnioski"] = wnioski(b, ogolem)
    wyroznij(branze)

    # Ciekawostki — najwyżej 4, każda jednym zdaniem z liczbą; bez liczb, które są już w tabeli.
    ciekawostki = []
    if tematy_all:
        ciekawostki.append({"liczba": "%d%%" % procent(n_emoji, len(tematy_all)),
                            "tekst": "tematów newsletterów ma emoji (%d z %d)." % (n_emoji, len(tematy_all))})
    if rabaty:
        ciekawostki.append({"liczba": "%d%%" % round(st.median(rabaty)),
                            "tekst": "to typowy najwyższy rabat w mailu z ofertą, np. „do %d%%”." % round(st.median(rabaty))})
    if n_rabat or n_promo:
        ciekawostki.append({"liczba": "%d wobec %d" % (n_rabat, n_promo),
                            "tekst": "tyle tematów ma słowo „rabat”, a tyle słowo „promocja”."})
    if cisza:
        ciekawostki.append({"liczba": str(len(cisza)),
                            "tekst": "%s nie %s ani jednego maila w tygodniu po zapisie, choć trwał Black Week."
                            % (odmiana(len(cisza), "zapisany sklep", "zapisane sklepy", "zapisanych sklepów"),
                               odmiana(len(cisza), "wysłał", "wysłały", "wysłało"))})

    # Podwójne potwierdzenie zapisu — liczby z monitora; branże te same co w tabeli (co najmniej 3 sklepy).
    zach_nazwy = sorted(zach, key=lambda n: (-len(info[n]["maile"]), n.lower()))
    podwojne = {
        "sklepy": len(wszystkie), "z_potwierdzeniem": len(potw), "proc": procent(len(potw), len(wszystkie)),
        "bez": len(wszystkie) - len(potw), "bez_proc": procent(len(wszystkie) - len(potw), len(wszystkie)),
        "prosba": sum(1 for n in potw if info[n]["potwierdzenie_jak"] == "prosba"),
        "tylko_podziekowanie": sum(1 for n in potw if info[n]["potwierdzenie_jak"] == "podziekowanie"),
        "z_zacheta": len(zach),
        "przyklady_zachety": zach_nazwy[:PRZYKLADY_ZACHETY],
        "po_angielsku": sum(1 for n in potw if (potwierdzenia.get(n) or {}).get("jezyk") == "EN"),
        "branze": sorted(({"nazwa": b["nazwa"], "slug": b["slug"], "sklepy": b["potwierdzenie"]["sklepy"],
                           "z_potwierdzeniem": b["potwierdzenie"]["prosi"], "proc": b["potwierdzenie_proc"]}
                          for b in branze), key=lambda x: (-x["proc"], -x["sklepy"], x["nazwa"])),
        "poprzedni": None,
    }

    return {
        "wersja": WERSJA,
        "wygenerowano": (teraz or dt.datetime.now()).strftime("%Y-%m-%d %H:%M"),
        "okres": {"od": od.isoformat(), "do": do.isoformat(), "dni": dni_okresu,
                  "od_pl": od.strftime("%d.%m.%Y"), "do_pl": do.strftime("%d.%m.%Y")},
        "liczby": {
            "maile": len(maile), "sklepy_wysylajace": len(info),
            "sklepy_zapisane": sum(1 for s in sklepy if s.get("status") == "zapisany"),
            "regularne": len(reg_all), "bez_klasyfikacji": sum(1 for m in maile if not m["_k"]),
            "tydzien_mediana": liczba_pl(zaokr(st.median(tyg_all))) if tyg_all else None,
            "sprzedazowe_proc": procent(len(sprz_all), len(reg_all)),
        },
        "branze": branze,
        "ogolem": ogolem,
        "inne_branze": inne,
        "podwojne": podwojne,
        "ciekawostki": ciekawostki,
        "progi": {"min_sklepow_branzy": MIN_SKLEPOW_BRANZY, "min_dni_czestotliwosc": MIN_DNI_CZESTOTLIWOSC},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--zrodlo", default=os.path.expanduser("~/Obsidian/Zasoby/Newslettery-obserwacja"))
    p.add_argument("--wyjscie", default="dane-porownywarka.json")
    p.add_argument("--historia", help="plik historii pomiarów (JSON); podany = dopisz dzisiejszy pomiar i pokaż zmianę")
    a = p.parse_args(argv)
    maile, klas, sklepy = wczytaj(a.zrodlo)
    systemy, raport = systemy_z_monitora(a.zrodlo)
    potwierdzenia = potwierdzenia_z_monitora(a.zrodlo, maile, klas)
    wynik = policz(maile, klas, sklepy, systemy, potwierdzenia)
    wynik["zrodlo_systemow"] = raport
    if a.historia:
        wynik["podwojne"]["poprzedni"] = historia(a.historia, wynik, wynik["wygenerowano"][:10])
    with open(a.wyjscie, "w", encoding="utf-8") as f:
        json.dump(wynik, f, ensure_ascii=False, indent=1)
    l = wynik["liczby"]
    pp = wynik["podwojne"]
    print("Zapisano %s: okres %s–%s, %d maili, %d sklepów, %d branż z kartą, %d bez klasyfikacji; "
          "podwójne potwierdzenie %d z %d (%s%%), z rabatem w temacie %d"
          % (a.wyjscie, wynik["okres"]["od_pl"], wynik["okres"]["do_pl"], l["maile"], l["sklepy_wysylajace"],
             len(wynik["branze"]), l["bez_klasyfikacji"], pp["z_potwierdzeniem"], pp["sklepy"], pp["proc"], pp["z_zacheta"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
