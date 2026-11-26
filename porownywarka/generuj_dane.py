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
import json
import os
import re
import statistics as st
import sys

WERSJA = 1
MIN_SKLEPOW_BRANZY = 3   # mniej sklepów = branża trafia do „inne”, bez karty porównania
MALO_MAILI = 20  # mniej zwykłych newsletterów w branży = dopisek „orientacyjnie”
MIN_DNI_CZESTOTLIWOSC = 7  # sklep wchodzi do „maili tygodniowo”, jeśli obserwujemy go co najmniej tydzień
TYPY_STARTOWE = {"potwierdzenie", "powitalny", "przypomnienie-kodu"}
SPRZEDAZ = {"sprzedazowy", "mieszany"}
DNI_PL = ["pn", "wt", "śr", "czw", "pt", "sob", "nd"]
DNI_W = ["w poniedziałek", "we wtorek", "w środę", "w czwartek", "w piątek", "w sobotę", "w niedzielę"]

RE_RABAT = re.compile(r"rabat", re.I)
RE_PROMOCJA = re.compile(r"promocj", re.I)
RE_PROCENT = re.compile(r"%")
RE_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
RE_BLACK = re.compile(r"black|czarn\w* (piątek|tydzień)|cyber", re.I)
RE_ZACHETA = re.compile(r"\d+\s?%|zł|rabat|kupon|zniżk", re.I)


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
                system = "platforma sklepu (IdoSell, Shoper i inne)"
            for sklep in kol[2].split(","):
                if sklep.strip():
                    wynik[norm(sklep)] = system
    return wynik, os.path.basename(pliki[-1])


def wczytaj(katalog):
    with open(os.path.join(katalog, "maile.jsonl"), encoding="utf-8") as f:
        maile = [json.loads(l) for l in f if l.strip()]
    with open(os.path.join(katalog, "klasyfikacja.jsonl"), encoding="utf-8") as f:
        klas = {k["klucz"]: k for k in (json.loads(l) for l in f if l.strip())}
    with open(os.path.join(katalog, "sklepy.json"), encoding="utf-8") as f:
        sklepy = json.load(f)
    return maile, klas, sklepy


def policz(maile, klas, sklepy, systemy, teraz=None):
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
        potw = [m for m in ms if m["_k"] and m["_k"].get("typ") == "potwierdzenie"]
        powitalne = [m for m in ms if m["_k"] and m["_k"].get("typ") == "powitalny"]
        info[nazwa] = {
            "branza": branza_wspolna(s["branza"]) if s else "Inne",
            "maile": ms, "regularne": regularne, "dni": dni,
            "tydzien": zaokr(len(regularne) / dni * 7) if dni >= MIN_DNI_CZESTOTLIWOSC else None,
            "potwierdzenie": bool(potw), "zacheta": any(RE_ZACHETA.search(m["temat"]) for m in potw),
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
    ciekawostki = []
    if potw:
        ciekawostki.append({"liczba": "%d%%" % procent(len(potw), len(wszystkie)),
                            "tekst": "sklepów prosi o potwierdzenie zapisu mailem (%d z %d). Tylko %d %s zachętę (rabat albo kwotę) już w temacie tego maila."
                            % (len(potw), len(wszystkie), len(zach), odmiana(len(zach), "daje", "dają", "daje"))})
    if tyg_all:
        ciekawostki.append({"liczba": tyg_all and liczba_pl(zaokr(st.median(tyg_all))),
                            "tekst": "zwykłego newslettera tygodniowo wysyła typowy (środkowy) sklep. Rozrzut jest duży: od %s do %s (%d %s obserwowanych co najmniej tydzień)."
                            % (liczba_pl(tyg_all[0]), liczba_pl(tyg_all[-1]), len(tyg_all), odmiana(len(tyg_all), "sklep", "sklepy", "sklepów"))})
    if reg_all:
        ciekawostki.append({"liczba": "%d%%" % procent(len(sprz_all), len(reg_all)),
                            "tekst": "zwykłych newsletterów w tym okresie to maile sprzedażowe. W %d%% tematów jest „Black” (Black Friday, Black Week, Black Days i podobne) albo „Cyber”."
                            % procent(sum(1 for t in tematy_all if RE_BLACK.search(t)), len(tematy_all))})
    if tematy_all:
        ciekawostki.append({"liczba": "%d wobec %d" % (n_rabat, n_promo),
                            "tekst": "tyle tematów ma słowo „rabat”, a tyle słowo „promocja”. Sam znak procentu jest w %d tematach."
                            % sum(1 for t in tematy_all if RE_PROCENT.search(t))})
        ciekawostki.append({"liczba": "%d%%" % procent(n_emoji, len(tematy_all)),
                            "tekst": "tematów ma emoji (%d z %d zwykłych newsletterów)." % (n_emoji, len(tematy_all))})
    if powit:
        ciekawostki.append({"liczba": "%d z %d" % (len(powit_r), len(powit)),
                            "tekst": "sklepów z mailem powitalnym daje w nim rabat albo kod."})
    if rabaty:
        ciekawostki.append({"liczba": "%d%%" % round(st.median(rabaty)),
                            "tekst": "tyle wynosi typowy najwyższy rabat w mailu sprzedażowym, np. „do 40%%” (wartość środkowa z %d %s z rabatem procentowym)."
                            % (len(rabaty), odmiana(len(rabaty), "mail", "maile", "maili"))})
    if cisza:
        ciekawostki.append({"liczba": str(len(cisza)),
                            "tekst": "%s po zapisie nie %s ani jednego maila przez co najmniej tydzień, choć trwał Black Week."
                            % (odmiana(len(cisza), "sklep", "sklepy", "sklepów"), odmiana(len(cisza), "wysłał", "wysłały", "wysłało"))})

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
        "inne_branze": inne,
        "ciekawostki": ciekawostki,
        "progi": {"min_sklepow_branzy": MIN_SKLEPOW_BRANZY, "min_dni_czestotliwosc": MIN_DNI_CZESTOTLIWOSC},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--zrodlo", default=os.path.expanduser("~/Obsidian/Zasoby/Newslettery-obserwacja"))
    p.add_argument("--wyjscie", default="dane-porownywarka.json")
    a = p.parse_args(argv)
    maile, klas, sklepy = wczytaj(a.zrodlo)
    systemy, raport = systemy_z_monitora(a.zrodlo)
    wynik = policz(maile, klas, sklepy, systemy)
    wynik["zrodlo_systemow"] = raport
    with open(a.wyjscie, "w", encoding="utf-8") as f:
        json.dump(wynik, f, ensure_ascii=False, indent=1)
    l = wynik["liczby"]
    print("Zapisano %s: okres %s–%s, %d maili, %d sklepów, %d branż z kartą, %d bez klasyfikacji"
          % (a.wyjscie, wynik["okres"]["od_pl"], wynik["okres"]["do_pl"], l["maile"], l["sklepy_wysylajace"],
             len(wynik["branze"]), l["bez_klasyfikacji"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
