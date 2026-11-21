"""Klasyfikacja maili serii powitalnej: SPRZEDAŻOWY / WARTOŚCIOWY / MIESZANY — HEURYSTYKA.

Działa wyłącznie na temacie i treści HTML maila (bez danych kontaktów). Reguły są jawne:

Sygnały sprzedażowe (każdy liczy się raz):
  - kod rabatowy: słowo „kod” / „kupon” / „voucher” obok rabatu albo jawny kod (np. WITAJ10),
  - procent rabatu („-10%”, „10% taniej”, „rabat 15%”),
  - kwota („50 zł”, „49,99 PLN”) — cena lub kwota rabatu,
  - wezwanie do zakupu: „kup”, „zamów”, „promocj”, „wyprzedaż”, „okazj”, „rabat”, „zniżk”, „taniej”, „gratis”, „darmowa dostawa”,
  - przycisk / link do produktu albo koszyka (href z /product, /produkt, /koszyk, /cart, /checkout, /sklep, ?add-to-cart).
Sygnały wartościowe:
  - poradnik / edukacja: „jak wybrać”, „jak dobrać”, „poradnik”, „porad”, „wskazówk”, „krok po kroku”, „dowiedz się”, „czy wiesz”, „przewodnik”, „sposob”,
  - historia marki: „nasza historia”, „kim jesteśmy”, „o nas”, „skąd”, „poznaj nas”, „nasz zespół”, „założy”,
  - opinie / społeczność: „opini”, „recenz”, „klienci mówią”, „co mówią”,
  - treść: tekst maila po odjęciu HTML i stopki ma co najmniej 120 słów — liczy się TYLKO, gdy sygnałów
    sprzedażowych jest mniej niż 2 (długi mail z listą produktów i cen to nadal oferta).
Stopka (od „wypisz się”, „nie chcesz już”, „unsubscribe”, „otrzymujesz tę wiadomość”) jest odcinana przed liczeniem,
bo linki typu „O nas” czy „Regulamin” w stopce nie mówią nic o treści maila.
Decyzja:
  - sprzedażowe ≥ 2 i wartościowe = 0          → SPRZEDAŻOWY
  - wartościowe ≥ 1 i sprzedażowe = 0          → WARTOŚCIOWY
  - wartościowe ≥ 1 i sprzedażowe ≥ 1          → MIESZANY
  - sprzedażowe = 1 i wartościowe = 0          → SPRZEDAŻOWY (słaby sygnał — zaznaczone w powodzie)
  - brak sygnałów                              → NIEOKREŚLONY (np. sam obrazek albo brak treści w API)
Treść maila to dane z konta użytkownika — tylko je liczymy, niczego z nich nie wykonujemy.
"""
import html as _html
import re
import unicodedata

# „kup”/„zamów” tylko jako polecenie: nie „kupowany”, „zakupy”, „zamówienie”
SPRZEDAZ_WZORCE = {"kup": r"(?<!\w)kup(uj\w*)?(?!\w)", "zamów": r"(?<!\w)zam(ó|o)w(\s*(teraz|już|juz))?(?!\w)"}
SPRZEDAZ_SLOWA = ["promocj", "wyprzedaż", "wyprzedaz", "okazj", "rabat", "zniżk", "znizk",
                  "taniej", "gratis", "darmowa dostawa", "darmową dostawę", "darmowa wysyłka", "darmową wysyłkę", "black friday",
                  "black week", "do koszyka", "sprawdź ofert", "sprawdz ofert", "tylko dziś", "tylko dzis", "ostatnia szansa"]
WARTOSC_SLOWA = {
    "poradnik": ["jak wybrać", "jak wybrac", "jak dobrać", "jak dobrac", "poradnik", "porad", "wskazówk", "wskazowk",
                 "krok po kroku", "dowiedz się", "dowiedz sie", "czy wiesz", "przewodnik", "sposob", "sposób"],
    "historia marki": ["nasza historia", "kim jesteśmy", "kim jestesmy", "o nas", "poznaj nas", "nasz zespół", "nasz zespol",
                       "założy", "zalozy", "skąd bierzemy", "skad bierzemy"],
    "opinie": ["opini", "recenz", "klienci mówią", "klienci mowia", "co mówią", "co mowia"],
}
MIN_SLOW_TRESCI = 120
RE_PROCENT = re.compile(r"(?:-|−|–)\s?\d{1,2}\s?%|\d{1,2}\s?%\s?(?:taniej|rabat|zniżk|znizk|off)|(?:rabat|zniżk\w*|znizk\w*)\s(?:\w+\s)?\d{1,2}\s?%", re.I)
RE_KWOTA = re.compile(r"\d+(?:[.,]\d{1,2})?\s?(?:zł|zl|pln)\b", re.I)
RE_KOD = re.compile(r"\b(?:kod\w*|kupon\w*|voucher\w*)\b", re.I)
RE_KOD_JAWNY = re.compile(r"\b[A-Z]{3,}[0-9]{1,3}\b")
RE_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)
LINK_SKLEPOWY = ("/product", "/produkt", "/koszyk", "/cart", "/checkout", "/zamowienie", "/sklep", "add-to-cart", "/p/")


STOPKA = re.compile(r"(?i)(nie chcesz już|nie chcesz juz|wypisz się|wypisz sie|zrezygnuj z|unsubscribe|otrzymujesz tę wiadomość|otrzymujesz te wiadomosc|otrzymujesz tego maila)")


def bez_stopki(t):
    m = STOPKA.search(t)
    return t[:m.start()] if m and m.start() > len(t) * 0.5 else t


def tekst_z_html(h):
    h = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", h or "")
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    t = unicodedata.normalize("NFKC", _html.unescape(h))
    return re.sub(r"\s+", " ", t).strip()


def klasyfikuj(temat, html_tresc):
    """Zwraca (klasa, powód). Heurystyka — patrz reguły w nagłówku modułu."""
    temat = unicodedata.normalize("NFKC", temat or "")
    tekst = bez_stopki(tekst_z_html(html_tresc))
    calosc = (temat + " " + tekst)
    maly = calosc.lower()
    hrefy = [x.lower() for x in RE_HREF.findall(html_tresc or "")]

    sprz = []
    if RE_KOD.search(calosc) and (RE_PROCENT.search(calosc) or RE_KWOTA.search(calosc) or RE_KOD_JAWNY.search(calosc)):
        sprz.append("kod rabatowy")
    if RE_PROCENT.search(calosc):
        sprz.append("procent rabatu")
    if RE_KWOTA.search(calosc):
        sprz.append("kwota/cena")
    slowa = [k for k, w in SPRZEDAZ_WZORCE.items() if re.search(w, maly)]
    slowa += [s for s in SPRZEDAZ_SLOWA if re.search(r"(?<!\w)" + re.escape(s), maly)]
    if slowa:
        sprz.append("wezwanie do zakupu („" + "”, „".join(slowa[:2]) + "”)")
    if any(any(k in h for k in LINK_SKLEPOWY) for h in hrefy):
        sprz.append("link do produktu/koszyka")

    wart = [k for k, sl in WARTOSC_SLOWA.items() if any(re.search(r"(?<!\w)" + re.escape(s), maly) for s in sl)]
    slow = len(tekst.split())
    if slow >= MIN_SLOW_TRESCI and len(sprz) < 2:
        wart.append(f"dłuższa treść ({slow} słów)")

    if sprz and wart:
        return "MIESZANY", "sprzedaż: " + ", ".join(sprz) + "; wartość: " + ", ".join(wart)
    if len(sprz) >= 2:
        return "SPRZEDAŻOWY", ", ".join(sprz)
    if sprz:
        return "SPRZEDAŻOWY", ", ".join(sprz) + " (słaby sygnał — tylko jeden)"
    if wart:
        return "WARTOŚCIOWY", ", ".join(wart)
    if not (html_tresc or "").strip():
        return "NIEOKREŚLONY", "API nie zwróciło treści maila"
    return "NIEOKREŚLONY", f"brak sygnałów w tekście ({slow} słów) — mail może być samym obrazkiem"


def wniosek_serii(maile):
    """maile: lista słowników z kluczami dzien (int|None), klasa, wyslane, wlaczony. Zwraca listę zdań."""
    akt = [m for m in maile if m.get("wlaczony")]
    W = []
    if not maile:
        return ["Nie znaleziono serii powitalnej."]
    if not akt:
        return ["Seria powitalna istnieje, ale żaden jej mail nie jest włączony — nowi zapisani nic nie dostają."]
    if not any(m.get("wyslane") for m in akt):
        W.append("Żaden włączony mail serii nie został jeszcze wysłany — sprawdź w panelu warunek startu.")
    dni = sorted({m["dzien"] for m in akt if m.get("dzien") is not None})
    if len(akt) == 1:
        m = akt[0]
        W.append("Seria ma 1 mail" + (" i to od razu oferta sprzedażowa" if m["klasa"] == "SPRZEDAŻOWY" else "") +
                 " — po pierwszym mailu nowa osoba nie dostaje już nic w ramach powitania.")
    elif dni and len(dni) == 1:
        W.append(f"Wszystkie {len(akt)} włączone maile serii mają ten sam dzień ({dni[0]}) — możliwe, że to warianty, nie kolejne kroki.")
    elif dni and max(dni) <= 2:
        W.append(f"Seria kończy się w dniu {max(dni)} — po tym nowy subskrybent nie dostaje nic do pierwszego newslettera.")
    # oceniamy maile, które realnie wychodzą; jeśli żaden jeszcze nie wyszedł — wszystkie włączone
    oceniane = [m for m in akt if m.get("wyslane")] or akt
    klasy = [m["klasa"] for m in sorted(oceniane, key=lambda m: (m.get("dzien") is None, m.get("dzien") or 0))]
    if klasy and all(k == "SPRZEDAŻOWY" for k in klasy):
        W.append("Wszystkie wysyłane maile serii są sprzedażowe — nie ma maila, który buduje zaufanie (poradnik, historia marki, opinie).")
    elif klasy and klasy[0] == "SPRZEDAŻOWY" and "WARTOŚCIOWY" not in klasy and "MIESZANY" not in klasy:
        W.append("Seria zaczyna od oferty i nie ma maila z treścią.")
    elif "WARTOŚCIOWY" in klasy or "MIESZANY" in klasy:
        W.append("Seria łączy ofertę z treścią (co najmniej jeden mail wartościowy albo mieszany).")
    return W
