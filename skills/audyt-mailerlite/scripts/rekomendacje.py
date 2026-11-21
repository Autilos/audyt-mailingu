"""Rekomendacje do wykrytych problemów — zasady ogólne, bez danych żadnego klienta.

Każdy skrypt audytu zamienia swoje znaleziska na klucze z REKOMENDACJE (plus szczegół w nawiasie),
a ta funkcja układa je w kolejności: najpierw dane (bez nich reszta nie działa), potem dostarczalność,
potem automaty od najbardziej dochodowych. Rekomendacja pojawia się TYLKO dla wykrytego problemu.

Zasady (źródła: dobre praktyki e-mail marketingu w e-commerce, benchmarki dostawców; bez obietnic wzrostu):
- powitanie to seria, nie jeden mail; najpierw zaufanie, potem oferta; każdy mail zapowiada następny;
- koszyk: pierwszy mail bez rabatu, rabat najwyżej w ostatnim;
- każdy automat sprzedażowy ma wyjście po zakupie;
- czas do drugiego zakupu i reaktywacji liczy się z własnych zamówień (mediana), nie z założeń;
- limit kontaktu: około 2 maile na 7 dni łącznie z transakcyjnymi;
- wyniki ocenia się po kliknięciach i sprzedaży, nie po otwarciach.
"""

# (kolejność, tytuł, treść). Kolejność: mniejsza = pilniejsza.
REKOMENDACJE = {
    "sklep_bez_zamowien": (10, "Napraw przesyłanie zamówień ze sklepu",
        "Bez zamówień w systemie mailowym nie zadziałają porzucony koszyk, maile po zakupie, drugi zakup ani liczenie przychodu z maili. "
        "Sprawdź integrację sklepu (wtyczka albo połączenie API), zrób zamówienie testowe i potwierdź, że pojawia się przy kontakcie. To pierwszy krok — reszta rekomendacji od niego zależy."),
    "zamowienia_bez_kontaktu": (20, "Sprawdź, dlaczego część zamówień nie ma kontaktu",
        "Weź kilka ostatnich zamówień, przy których klient zaznaczył zgodę na maile, i sprawdź, czy kupujący jest kontaktem. Jeśli jest — w porządku, to klienci bez zgody. "
        "Jeśli nie ma — integracja gubi kontakty i to trzeba naprawić. Dobrą praktyką jest też widoczne, niezaznaczone domyślnie pole zgody w koszyku."),
    "skargi_spam": (30, "Obniż skargi na spam",
        "Mail z wysokimi skargami wyłącz albo przebuduj: wysyłaj tylko do osób z wyraźną zgodą, ustaw link do wypisu na górze i na dole, nie wysyłaj do kontaktów, które od miesięcy nic nie klikają. "
        "Google wymaga, żeby skargi były poniżej 0,3%, i zaleca poniżej 0,1%."),
    "duzo_wypisow": (35, "Zmniejsz wypisy",
        "Sprawdź, czy mail nie przychodzi zbyt szybko po innym (cel: około 2 maile na 7 dni łącznie z transakcyjnymi) i czy temat obiecuje to, co jest w treści. "
        "Wysokie wypisy w mailu powitalnym często znaczą, że osoba zapisała się tylko po kod — wtedy pomaga seria z treścią, a nie sam rabat."),
    "za_czesto": (37, "Ogranicz częstotliwość newsletterów",
        "Ustal limit: około 2 maile na 7 dni na osobę, licząc też automaty i maile transakcyjne. Najbardziej zaangażowanym możesz wysyłać częściej, reszcie rzadziej."),
    "brak_newsletterow": (40, "Wznów regularne wysyłki",
        "Baza, która nie dostaje maili, zapomina o sklepie i przy pierwszej wysyłce po przerwie częściej zgłasza spam. Zacznij od maila do osób aktywnych w ostatnich miesiącach, potem stały rytm, np. raz w tygodniu."),
    "powitanie_brak": (50, "Zbuduj serię powitalną",
        "Przykładowy układ: dzień 0 — powitanie, obiecany kod (jeśli formularz go obiecuje), jedno zdanie o marce i zapowiedź następnego maila; "
        "dzień 2 — historia marki albo dlaczego ten sklep; dzień 4 — opinie klientów i bestsellery; dzień 6 — poradnik (jak wybrać) z jednym polecanym produktem; "
        "dzień 8 — przypomnienie o wygasającym kodzie tylko dla tych, którzy nie kupili. Wyjście z serii po zakupie."),
    "koszyk_brak": (60, "Uruchom porzucony koszyk",
        "Trzy maile: po 1–4 godzinach przypomnienie ze zdjęciem produktu, bez rabatu; po 24 godzinach opinie i odpowiedź na typowe wątpliwości (dostawa, zwroty); "
        "po 48–72 godzinach ewentualnie jednorazowy kod. Wyjście po zakupie, automat może się powtarzać przy kolejnym porzuceniu."),
    "po_zakupie_brak": (70, "Dodaj maile po zakupie",
        "Kilka dni po dostawie: jak używać produktu i czego się spodziewać; około 14 dni po dostawie: prośba o opinię; potem propozycja kolejnego produktu dobranego do pierwszego zakupu."),
    "drugi_zakup_brak": (80, "Dodaj automat drugiego zakupu",
        "Policz w sklepie medianę dni między pierwszym a drugim zakupem i ustaw mail nieco przed nią. Sprawdź, czy klienci wracają po to samo, czy po inny produkt — "
        "jeśli po inny, proponuj nowość dopasowaną do pierwszego zakupu, a nie ponowienie tego samego."),
    "reaktywacja_brak": (90, "Dodaj reaktywację uśpionych klientów",
        "Start po czasie dłuższym niż typowy odstęp między zakupami w sklepie. Układ: mail bez oferty (co nowego), potem opinie lub bestseller, potem oferta ograniczona w czasie, "
        "na końcu pytanie „zostajesz z nami?” — kto nie zareaguje, przestaje dostawać kampanie."),
    "przegladanie_brak": (95, "Rozważ automat porzuconego przeglądania",
        "Wymaga śledzenia odwiedzin produktów na stronie. Jeden–dwa maile (po kilku godzinach i po 1–2 dniach), najwyżej jeden taki mail na dobę, bez wysyłki, gdy ktoś dostał już mail o koszyku lub kupił."),
    "automat_martwy": (100, "Sprawdź automaty, przez które nikt nie przechodzi",
        "Otwórz element startowy automatu: lista, tag albo zdarzenie, które go uruchamia. Jeśli automat jest celowo wstrzymany — wyłącz go, żeby stan na koncie był jednoznaczny."),
    "mail_nigdy_niewyslany": (105, "Sprawdź włączone maile, które nigdy nie wyszły",
        "Włączony mail bez żadnej wysyłki oznacza zwykle zły warunek startu albo brak osób spełniających warunek. Sprawdź warunek; jeśli mail jest zbędny — wyłącz."),
    "bez_sledzenia": (110, "Włącz śledzenie sprzedaży w każdym mailu",
        "W ustawieniach wiadomości włącz śledzenie e-commerce, a w linkach dodaj parametry UTM, żeby sklep i Google Analytics widziały sprzedaż z maili niezależnie od systemu mailowego."),
    "brak_wypisu": (25, "Dodaj link do wypisu w każdym mailu",
        "Mail bez linku do wypisu łamie wymogi prawne i jest sygnałem spamu dla Gmaila. Dodaj link w stopce każdego maila w automatach, zanim zmienisz cokolwiek innego w treści."),
    "automat_zepsuty": (45, "Napraw zepsute albo niedokończone automaty",
        "Otwórz automat w edytorze, uzupełnij brakujące kroki (mail bez treści, warunek bez gałęzi) i zapisz. Automat niedokończony nie wysyła nic, choć wygląda na skonfigurowany."),
    "brak_sklepu": (12, "Podłącz sklep do systemu mailowego",
        "Bez podłączonego sklepu nie zadziałają porzucony koszyk, drugi zakup ani liczenie sprzedaży z maili. Podłącz sklep przez oficjalną integrację i sprawdź na zamówieniu testowym."),
    "domena_nadawcy": (14, "Potwierdź domenę nadawcy",
        "Wysyłka z domeny niepotwierdzonej albo z darmowej skrzynki trafia częściej do spamu. Dodaj i potwierdź własną domenę w ustawieniach adresów nadawcy, ustaw rekordy DNS, które system podaje (DKIM, SPF), i wysyłaj z adresu w tej domenie."),
    "nadawca_darmowy": (17, "Nie wysyłaj z adresu w darmowej poczcie",
        "Adres nadawcy w darmowej domenie (np. gmail.com) nie może być uwierzytelniony przez system mailowy, więc skrzynki odbiorców częściej odrzucają takie maile albo kierują je do spamu. Wysyłaj wyłącznie z adresu we własnej domenie; jeśli ten adres nie jest używany jako nadawca — usuń go z listy adresów nadawcy."),
    "dkim_dmarc": (16, "Popraw uwierzytelnienie domeny (DKIM, DMARC)",
        "System zgłasza ostrzeżenie DKIM albo DMARC dla domeny nadawcy. Dodaj w DNS domeny rekordy, które podaje system mailowy, oraz rekord DMARC (na start z polityką „none” i adresem do raportów), a potem sprawdź ponownie status domeny."),
    "odplyw_bazy": (38, "Zatrzymaj kurczenie się bazy",
        "Ubywa więcej kontaktów, niż przybywa. Sprawdź najpierw powód usunięć: przy wypisach — częstotliwość i dopasowanie treści; przy odbiciach — jakość adresów ze źródeł zapisu. Równolegle wzmocnij zapisy: widoczny formularz, jasna korzyść z zapisu, zgoda w koszyku."),
    "formularz_bez_ruchu": (56, "Sprawdź formularze bez odwiedzin",
        "Włączony formularz bez odwiedzin zwykle nie jest osadzony na stronie albo został zastąpiony innym. Jeśli jest zbędny — wyłącz; jeśli ma działać — sprawdź, czy kod formularza jest na stronie."),
    "formularz_niska_konwersja": (57, "Popraw formularz z niską konwersją",
        "Formularz ma ruch, ale mało zapisów. Najczęściej pomaga: jedna konkretna korzyść w nagłówku (np. poradnik albo rabat na pierwsze zakupy), mniej pól (sam e-mail), wyraźny przycisk i sprawdzenie wyglądu na telefonie."),
    "przychod_rozjazd": (11, "Wyjaśnij różnicę między sprzedażą w sklepie a w systemie mailowym",
        "System mailowy widzi wyraźnie mniej zamówień niż sklep. Sprawdź, od kiedy zamówienia przestały dochodzić (porównaj dzień po dniu), czy integracja nie pomija części statusów płatności i czy nie wygasł klucz integracji."),
    "nazwa_robocza": (120, "Nazwij i opisz automaty",
        "Automat o nazwie roboczej (np. „Szkic”) działa, ale nikt nie wie, co robi. Nadaj nazwę mówiącą o celu i zapisz warunek wejścia i wyjścia."),
}


def rekomendacja_serii(maile):
    """maile: pozycje serii (klasa, dzien, wlaczony, wyslane). Zwraca (tytuł, treść) albo None, gdy seria jest dobra."""
    akt = [m for m in maile if m.get("wlaczony")]
    if not akt:
        return ("Włącz albo zbuduj serię powitalną", REKOMENDACJE["powitanie_brak"][2])
    klasy = [m["klasa"] for m in ([m for m in akt if m.get("wyslane")] or akt)]
    wart = sum(1 for k in klasy if k in ("WARTOŚCIOWY", "MIESZANY"))
    dni = [m["dzien"] for m in akt if m.get("dzien") is not None]
    rady = []
    if len(akt) == 1:
        rady.append("Rozbuduj powitanie z jednego maila do serii 4–5 maili. " + REKOMENDACJE["powitanie_brak"][2])
    else:
        nieokr = sum(1 for k in klasy if k == "NIEOKREŚLONY")
        if wart == 0 and nieokr == 0:
            rady.append("Między maile z ofertą wstaw co najmniej jeden mail bez oferty: historia marki, poradnik albo opinie klientów. "
                        "Zasada: najpierw zaufanie, potem sprzedaż — rabat w pierwszym mailu może zostać, kolejne maile niech dają powód, żeby kupić właśnie tu.")
        if dni and max(dni) <= 2:
            rady.append("Rozciągnij serię na około 8–10 dni (np. dzień 0, 2, 4, 6, 8), żeby nowa osoba miała kontakt ze sklepem do pierwszego newslettera.")
    if not rady:
        return None
    return ("Popraw serię powitalną", " ".join(rady))


def uloz(klucze, serie=None):
    """klucze: dict klucz → szczegół (str, może być pusty). serie: lista (tytuł, treść, szczegół) z rekomendacja_serii
    dla każdej serii z problemem. Zwraca listę (tytuł, treść, szczegół) w kolejności wykonania."""
    wynik = []
    for k, szczegol in klucze.items():
        if k not in REKOMENDACJE:
            continue
        kol, tyt, tresc = REKOMENDACJE[k]
        if k == "powitanie_brak" and serie:
            continue  # seria istnieje — rady dla serii zastępują ogólną
        wynik.append((kol, tyt, tresc, szczegol or ""))
    for i, (tyt, tresc, szcz) in enumerate(serie or []):
        wynik.append((50 + i / 100, tyt, tresc, szcz or ""))
    return [(t, r, s) for _, t, r, s in sorted(wynik, key=lambda x: x[0])]
