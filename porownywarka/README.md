# Porównywarka newsletterów sklepów

Strona `/porownywarka-newsletterow/` na marketingkrokpokroku.pl: jak często, kiedy i o czym piszą newslettery polskich sklepów, z podziałem na branże, plus formularz „Dodaj swój sklep”. Dane pochodzą z obserwacji publicznych newsletterów na jednej skrzynce testowej (dane nie są w tym repozytorium).

## Pliki

| Plik | Gdzie na serwerze | Co robi |
|---|---|---|
| `generuj_dane.py` | — (uruchamiany lokalnie) | Z `maile.jsonl`, `klasyfikacja.jsonl`, `sklepy.json` i najnowszego `Raporty/Monitor-*.md` robi jeden plik JSON ze wszystkimi liczbami strony. Do pliku trafiają tylko liczby i nazwy sklepów — bez tematów, treści, adresów i nazwy skrzynki. |
| `wp/page-porownywarka-newsletterow.twig` | `wp-content/themes/_sdc/views/templates/` | Szablon strony (rozszerza `templates/usluga.twig`, style zawężone do `.usl .pn`). Wszystko renderuje serwer, JS tylko przełącza branże i wysyła formularz. |
| `wp/mkpk-porownywarka.php` | `wp-content/mu-plugins/` | `mkpk_porownywarka_dane()` czyta `wp-content/uploads/mkpk-porownywarka/dane.json`; obsługa formularza (`admin-ajax.php?action=mkpk_porownywarka`). |
| `odswiez.sh` | — | Bez interakcji: generuje JSON, wgrywa go na serwer, czyści cache, sprawdza żywą stronę (HTTP 200 + liczby), zapisuje historię pomiarów i dziennik odświeżeń (zmienne `MKPK_SSH`, `MKPK_WP` albo plik `~/.config/mkpk-porownywarka.env`). |

## Odświeżenie liczb

```bash
porownywarka/odswiez.sh   # zmienne z ~/.config/mkpk-porownywarka.env albo MKPK_SSH=… MKPK_WP=…
```

Do automatu raz dziennie. Kod wyjścia ≠ 0 = coś nie przeszło (2: strona nie zwraca 200, 3: na stronie nie ma nowych liczb, 4: nie udało się wyczyścić cache) — wtedy historia się nie zmienia. W katalogu danych: `porownywarka-pomiary.json` (historia podwójnego potwierdzenia) i `porownywarka-odswiezenia.log` (linijka na każde udane odświeżenie). Strona pokazuje datę ostatniej aktualizacji z pliku. Zmiana szablonu (`wp/*.twig`) nie idzie tym skryptem — wgrywa się ją osobno.

## Jak liczymy

- **Zwykłe newslettery** — wszystkie maile poza potwierdzeniem zapisu, powitaniem i przypomnieniem kodu powitalnego (`typ` z klasyfikacji). Z nich: częstotliwość, dni, godziny, udział sprzedaży, słowa w tematach.
- **Newsletterów tygodniowo** — zwykłe newslettery sklepu / dni obserwacji × 7; dni obserwacji od daty zapisu (najwcześniej od pierwszego maila w danych) do ostatniego maila w danych. Tylko sklepy obserwowane co najmniej 7 dni. Na stronie mediana branży („typowy sklep”).
- **Podwójne potwierdzenie zapisu** — liczy `podwojne_potwierdzenie()` z `monitor.py` w katalogu danych (jedna definicja dla monitora i strony; bez `monitor.py` generator się zatrzymuje): prośba o kliknięcie albo podziękowanie za potwierdzenie; zwykłe „Dziękujemy za zapisanie się” się nie liczy. „Z zachętą” = rabat, kwota albo kupon w temacie prośby. Blok `podwojne` w JSON-ie: x z y, %, branże z kartą, przykłady marek z rabatem w temacie (bez nazw sklepów bez potwierdzenia), `poprzedni` z historii (`--historia`, jeden wpis na dzień).
- **Rabat na powitanie** — sklep ma mail powitalny z `rabat_max` albo kodem.
- **Programy do wysyłki** — z tabeli w raporcie monitora (rozpoznanie po nagłówkach maili). Na stronie jedna linijka: trzy najczęstsze i „i inne”.
- **Tabela porównawcza** (`branze[].tabela`, `ogolem`) — maili w tygodniu, % ofert i rabatów, potwierdzenie zapisu (x z y), rabat na powitanie (x z y). Na stronie liczby pełne, poniżej 2 z jednym miejscem po przecinku. `wyroznienie` = najwyższa/najniższa wartość w kolumnie po zaokrągleniu, bez branż z małą liczbą maili i bez „x z y” przy y < 3.
- **Wnioski** (`branze[].wnioski`) — trzy zdania z porównaniem branży do wszystkich sklepów, bez nowych liczb.
- **Ciekawostki** — najwyżej 4, bez liczb z tabeli.
- Sekcja „Jak liczę” jest w szablonie, ale ukryta (`{% set pokaz_metode = false %}`); `true` ją przywraca.
- Pełna lista sklepów w kartach branż („Pokaż wszystkie sklepy”) jest w szablonie, ale ukryta (`{% set pokaz_sklepy = false %}`); `true` ją przywraca. Flaga siedzi w szablonie, więc `odswiez.sh` (wgrywa tylko JSON) jej nie cofa.
- Karta branży tylko przy co najmniej 3 sklepach, które coś przysłały; mniejsze branże są wymienione z nazwy.

## Formularz „Dodaj swój sklep”

Zgłoszenie (adres sklepu, branża, e-mail, zgoda) zapisuje się we Flamingo (kanał `mkpk-porownywarka`) i idzie jako powiadomienie na wnowak@autilo.eu. Zgłaszający nie dostaje żadnego automatycznego maila — wynik po około 14 dniach wysyła Wojtek ręcznie. Ochrona jak w formularzu kontaktu: pole-pułapka, 5 zgłoszeń na godzinę z IP, reCAPTCHA v3 (akcja `porownywarka`, próg 0,5).

Zdarzenia GA4 (bez danych osobowych): `porownywarka_branza` (branza), `porownywarka_zgloszenie` (branza, zrodlo).

## Testy

`python3 -m unittest tests.test_porownywarka -v` — na zmyślonych danych.
