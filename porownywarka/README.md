# Porównywarka newsletterów sklepów

Strona `/porownywarka-newsletterow/` na marketingkrokpokroku.pl: jak często, kiedy i o czym piszą newslettery polskich sklepów, z podziałem na branże, plus formularz „Dodaj swój sklep”. Dane pochodzą z obserwacji publicznych newsletterów na jednej skrzynce testowej (dane nie są w tym repozytorium).

## Pliki

| Plik | Gdzie na serwerze | Co robi |
|---|---|---|
| `generuj_dane.py` | — (uruchamiany lokalnie) | Z `maile.jsonl`, `klasyfikacja.jsonl`, `sklepy.json` i najnowszego `Raporty/Monitor-*.md` robi jeden plik JSON ze wszystkimi liczbami strony. Do pliku trafiają tylko liczby i nazwy sklepów — bez tematów, treści, adresów i nazwy skrzynki. |
| `wp/page-porownywarka-newsletterow.twig` | `wp-content/themes/_sdc/views/templates/` | Szablon strony (rozszerza `templates/usluga.twig`, style zawężone do `.usl .pn`). Wszystko renderuje serwer, JS tylko przełącza branże i wysyła formularz. |
| `wp/mkpk-porownywarka.php` | `wp-content/mu-plugins/` | `mkpk_porownywarka_dane()` czyta `wp-content/uploads/mkpk-porownywarka/dane.json`; obsługa formularza (`admin-ajax.php?action=mkpk_porownywarka`). |
| `odswiez.sh` | — | Generuje JSON i wgrywa go na serwer (zmienne `MKPK_SSH`, `MKPK_WP`). |

## Odświeżenie liczb

```bash
MKPK_SSH=<alias> MKPK_WP=<katalog WP> porownywarka/odswiez.sh
```

Potem zrzut strony (telefon + komputer). Strona pokazuje datę ostatniej aktualizacji z pliku.

## Jak liczymy

- **Zwykłe newslettery** — wszystkie maile poza potwierdzeniem zapisu, powitaniem i przypomnieniem kodu powitalnego (`typ` z klasyfikacji). Z nich: częstotliwość, dni, godziny, udział sprzedaży, słowa w tematach.
- **Newsletterów tygodniowo** — zwykłe newslettery sklepu / dni obserwacji × 7; dni obserwacji od daty zapisu (najwcześniej od pierwszego maila w danych) do ostatniego maila w danych. Tylko sklepy obserwowane co najmniej 7 dni. Na stronie mediana branży („typowy sklep”).
- **Potwierdzenie zapisu** — sklep przysłał prośbę o potwierdzenie albo podziękowanie za potwierdzenie (wzorce w temacie). „Z zachętą” = rabat, kwota albo kupon w temacie prośby.
- **Rabat na powitanie** — sklep ma mail powitalny z `rabat_max` albo kodem.
- **Programy do wysyłki** — z tabeli w raporcie monitora (rozpoznanie po nagłówkach maili). Na stronie jedna linijka: trzy najczęstsze i „i inne”.
- **Tabela porównawcza** (`branze[].tabela`, `ogolem`) — maili w tygodniu, % ofert i rabatów, potwierdzenie zapisu (x z y), rabat na powitanie (x z y). Na stronie liczby pełne, poniżej 2 z jednym miejscem po przecinku. `wyroznienie` = najwyższa/najniższa wartość w kolumnie po zaokrągleniu, bez branż z małą liczbą maili i bez „x z y” przy y < 3.
- **Wnioski** (`branze[].wnioski`) — trzy zdania z porównaniem branży do wszystkich sklepów, bez nowych liczb.
- **Ciekawostki** — najwyżej 4, bez liczb z tabeli.
- Sekcja „Jak liczę” jest w szablonie, ale ukryta (`{% set pokaz_metode = false %}`); `true` ją przywraca.
- Karta branży tylko przy co najmniej 3 sklepach, które coś przysłały; mniejsze branże są wymienione z nazwy.

## Formularz „Dodaj swój sklep”

Zgłoszenie (adres sklepu, branża, e-mail, zgoda) zapisuje się we Flamingo (kanał `mkpk-porownywarka`) i idzie jako powiadomienie na wnowak@autilo.eu. Zgłaszający nie dostaje żadnego automatycznego maila — wynik po około 14 dniach wysyła Wojtek ręcznie. Ochrona jak w formularzu kontaktu: pole-pułapka, 5 zgłoszeń na godzinę z IP, reCAPTCHA v3 (akcja `porownywarka`, próg 0,5).

Zdarzenia GA4 (bez danych osobowych): `porownywarka_branza` (branza), `porownywarka_zgloszenie` (branza, zrodlo).

## Testy

`python3 -m unittest tests.test_porownywarka -v` — na zmyślonych danych.
