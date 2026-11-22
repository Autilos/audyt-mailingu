# Słownik pojęć audytu e-mail marketingu

Każde hasło znaczy w kodzie, raportach i rozmowie dokładnie to, co tu napisano. Przed zmianą skryptu, raportu albo SKILL.md przeczytaj ten plik. Raport i strona po polsku bez żargonu — pisz tak, jak do właściciela sklepu; jeśli zmieniasz znaczenie pojęcia, zmień je najpierw tutaj.

## Dane i bezpieczeństwo

**Tylko odczyt** — skrypty wysyłają wyłącznie zapytania GET do oficjalnego API. Niczego nie zmieniają, nie wysyłają maili i nie kasują kontaktów.

**Dane osobowe** — skill nigdy nie pobiera danych kontaktów ani kupujących (e-mail, imię, adres, telefon), tylko statystyki, ustawienia i treść maili. Claude ma zakaz wywoływania API poza skryptem i pokazywania takich danych, także na prośbę użytkownika (sekcja „Zasady dla Claude” w SKILL.md). Przegląd wszystkich dróg wycieku: `docs/BEZPIECZENSTWO-przeglad.md`. Pilnuje tego lista dozwolonych ścieżek (`DOZWOLONE_SCIEZKI` w obu skryptach): każda inna ścieżka przerywa audyt, a test w `tests/` sprawdza, że w kodzie nie ma zapytań do `/contacts`, `/subscribers`, `/account` ani do zamówień MailerLite.

**Lista dozwolonych ścieżek** — jawny spis endpointów, które skrypt może wywołać. W GetResponse zamówienia (`/shops/{id}/orders`) są dozwolone tylko z polami `orderId, totalPrice, processedAt, contactId, status`. Nową ścieżkę dodaje się dopiero po sprawdzeniu na żywym API, że odpowiedź nie zawiera danych osobowych.

**Klucz API** — klucz albo token użytkownika, czytany wyłącznie ze zmiennej środowiskowej albo pliku `~/.config/audyt-mailingu/<system>.key` i wysyłany tylko do oficjalnego adresu API (https, właściwy host; przekierowania i linki do innych hostów są odrzucane). Klucze GetResponse i MailerLite dają pełny dostęp do konta (panele nie mają kluczy tylko do odczytu) — „tylko odczyt” dotyczy skryptu. Zalecamy osobny klucz do audytu, usunięty zaraz po nim.

**Sito odpowiedzi** — `WZORY_ODPOWIEDZI` w obu skryptach i `wspolne.przytnij`: z każdej odpowiedzi API od razu po odebraniu zostają wyłącznie pola potrzebne audytowi; reszta (np. adres nadawcy, dane dostępowe sklepu, pola dodane przez dostawcę w przyszłości) jest odrzucana, zanim cokolwiek trafi do pamięci na dysku, raportu albo na ekran. Ścieżka bez wzoru = pusta odpowiedź. Całe odpowiedzi przechodzą tylko przy statystykach (same liczby zbiorcze).

**Maskowanie** — `wspolne.maskuj`: adres e-mail albo numer telefonu wpisany w nazwę listy, automatu, formularza czy temat maila jest zamieniany na „[e-mail ukryty]” / „[telefon ukryty]” już w sicie i jeszcze raz przed zapisem raportu i JSON.

**Treść odpowiedzi z błędem** — przy błędzie API skrypt nie czyta i nie wypisuje treści odpowiedzi (mogłaby zawierać dane), tylko kod błędu i ścieżkę; nie ma też surowych tracebacków z połączeniem.

## Okno i liczby

**Okres audytu** — liczba dni wstecz od dnia uruchomienia (`--dni`, domyślnie 90), w którym liczone są newslettery, zamówienia i zdrowie bazy. Wyniki maili z automatów i formularzy obejmują całe ich życie, nie tylko ten okres.

**Otwarcia bez botów** — tylko w GetResponse: pole `uniqueHumanOpened` (i `uniqueHumanClicked`), z którego GetResponse odsiewa automatyczne otwarcia, np. Apple Mail. MailerLite podaje otwarcia surowe, dlatego tam oceniamy maile po kliknięciach.

**Próg praktyczny** — orientacyjna granica, od której raport oznacza problem: wypisy powyżej 0,5%, kliknięcia poniżej 0,5%, odbicia powyżej 2%, ocena dopiero od 200 wysyłek. To sygnał do sprawdzenia, nie norma branżowa.

**Skarga na spam — próg 0,3%** — Google wymaga od nadawców masowych, żeby odsetek skarg był poniżej 0,3%, i zaleca poniżej 0,1% (wytyczne dla nadawców Gmaila, „Email sender guidelines”, Google, 2024). Raport oznacza 0,3% i więcej jako przekroczenie, a powyżej 0,1% jako ostrzeżenie.

## Automaty

**Automat działa** — automat jest włączony **i** ktoś przez niego przechodzi (zakończyli albo są w trakcie, w MailerLite także wysłane maile). Włączony automat, przez który nikt nie przeszedł, to „włączony, ale nikt nie przechodzi” — zwykle zły warunek startu.

**Lista kontrolna automatów** — pięć–sześć automatów, które powinien mieć sklep: powitanie, porzucony koszyk, po zakupie, porzucone przeglądanie (tylko GetResponse), drugi zakup, reaktywacja. W GetResponse rozpoznawane po nazwie (API nie pokazuje wyzwalaczy), więc „nie znaleziono” znaczy „sprawdź w panelu”, a nie „na pewno brak”.

**Automat wysyłany przez sklep** — porzucony koszyk i maile po zakupie może wysyłać sam sklep albo osobny serwis (maile transakcyjne, wtyczka). Wtedy brak takiego automatu w systemie mailowym nie jest problemem, a jego budowa dublowałaby maile — rekomendacja najpierw o to pyta.

**Seria powitalna** — maile wysyłane nowej osobie po zapisie: w GetResponse klasyczne autorespondery (grupowane po liście, z dniem cyklu) oraz maile z automatów o nazwie lub temacie powitalnym; w MailerLite automat rozpoznany jako powitanie, z dniem liczonym po drzewie kroków. Oceniane są maile, które realnie wychodzą; mail włączony, ale nigdy niewysłany, nie poprawia oceny serii.

**Mail sprzedażowy / wartościowy / mieszany** — ocena po słowach i elementach maila, z tematu i treści (`seria_powitalna.py`); może się pomylić: sprzedażowy ma sygnały oferty (kod, procent, kwota, „kup”, „zamów”, link do produktu lub koszyka), wartościowy ma treść bez oferty (poradnik, historia marki, opinie, dłuższy tekst), mieszany ma jedno i drugie. Stopka jest odcinana; mail z samych obrazków wychodzi jako „nieokreślony”. W raporcie zawsze piszemy, że to ocena po słowach i elementach maila, która może się pomylić — bez słowa „heurystyka”.

## Sklep i sprzedaż

**Zamówienie bez kontaktu** — zamówienie w GetResponse bez przypisanego kontaktu (`contactId`). Nie musi być błędem: zwykle to klient bez zgody na maile. W raporcie to „do sprawdzenia” na kilku zamówieniach z zaznaczoną zgodą, a nie wniosek.

**Sklep bez zamówień** — sklep jest podłączony, ale API nie zwraca zamówień z okresu audytu. Jeśli sklep w tym czasie sprzedawał, integracja najpewniej nie przesyła zamówień; potwierdza to dopiero porównanie z danymi sklepu.

**Przychód z `/statistics/ecommerce/revenue`** — przychód przypisany do maili (zakup po kliknięciu w mail), a nie cały przychód sklepu. Do porównania ze sklepem służy suma zamówień z `/shops/{id}/orders` i opcjonalne `--przychod-sklepu` / `--zamowienia-sklepu`.

**Śledzenie e-commerce** — ustawienie w wiadomości (GetResponse) albo ustawienie liczenia sprzedaży (MailerLite). Bez niej sprzedaż z danego maila najpewniej nie jest przypisywana.

## Baza i dostarczalność

**Zdrowie bazy** — w GetResponse przyrost i odpływ kontaktów w okresie audytu (`/campaigns/statistics/list-size`), źródła zapisów (`/subscriptions`) i powody usunięć (`/removals`); w MailerLite tylko stan grup na dziś (aktywni, wypisani, odbicia, spam), bo API nie daje historii.

**Adres nadawcy** — dane firmy, nie klientów. W GetResponse raport pokazuje tylko domenę, status domeny oraz ostrzeżenia DKIM i DMARC (`/from-fields`); adres w darmowej poczcie (np. gmail.com) dostaje osobną radę, bo nie da się go uwierzytelnić.

## Raport

**Rekomendacja** — konkretna rada tylko do wykrytego problemu, ułożona w kolejności: dane, dostarczalność, automaty (`rekomendacje.py`). Bez obietnic wzrostu w procentach i bez czasu wdrożenia; gdy seria powitalna jest dobra, raport mówi, że jest dobra.

**Pewne / do sprawdzenia** — pewne jest to, co API podaje wprost albo co potwierdza niezależne źródło (np. dane sklepu). „Do sprawdzenia” to interpretacja, której API nie rozstrzyga (przyczyna braku kontaktu, klasyfikacja maili, brak automatu „nie znaleziono po nazwie”).
