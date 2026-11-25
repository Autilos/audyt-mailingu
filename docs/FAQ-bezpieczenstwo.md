# Bezpieczeństwo — najczęstsze pytania

English: [FAQ-security.en.md](FAQ-security.en.md)

Krótko i bez technicznego żargonu: co audyt robi z Twoim kontem GetResponse albo MailerLite, co widzi asystent AI (Claude) i jak to sprawdzić samemu.

## Czy moje kontakty trafiają do AI albo do Anthropic?

Nie. Audyt nie pobiera listy kontaktów ani danych kupujących — nie ma ich więc czego przekazać. Do Claude (modelu AI firmy Anthropic) trafia tylko treść raportu: nazwy Twoich list, automatów i formularzy, tematy maili i liczby (ile wysłanych, ile kliknięć, ile zamówień). To dane Twojej firmy, nie Twoich klientów.

Jeśli nie chcesz, żeby do AI trafiło cokolwiek z konta — także te nazwy i liczby — użyj [trybu bez AI](../README.md#tryb-bez-ai).

## Czy skrypt widzi adresy e-mail moich klientów?

Nie. Skrypt może odczytać tylko wybrane miejsca w API: statystyki, ustawienia i treść Twoich maili. Spis tych miejsc jest w kodzie (`DOZWOLONE_SCIEZKI`), a próba odczytu czegokolwiek innego — na przykład listy kontaktów — przerywa audyt. Z każdej odpowiedzi od razu zostają tylko potrzebne pola, a reszta jest odrzucana, zanim cokolwiek trafi na dysk.

Dwa szczegóły:

- **Zamówienia w GetResponse** audyt czyta tylko z polami: numer, kwota, data, status i informacja „czy zamówienie ma przypisany kontakt” (tak / nie). Bez imienia, adresu ani e-maila kupującego.
- **Zamówień w MailerLite** audyt nie czyta wcale, bo API MailerLite zwraca je zawsze razem z danymi kupującego. Liczbę zamówień i przychód bierze z raportu zbiorczego sklepu, w którym są same liczby.

Jeśli sam wpisałeś adres e-mail, telefon albo numer IP w nazwę listy czy temat maila, skrypt go ukrywa („[e-mail ukryty]”), zanim zapisze cokolwiek na dysk.

## Dlaczego klucz API ma pełny dostęp do konta?

Bo GetResponse i MailerLite nie pozwalają utworzyć klucza „tylko do odczytu” — każdy klucz z panelu pozwala na wszystko, co Ty. „Tylko odczyt” dotyczy naszego skryptu: wysyła wyłącznie zapytania odczytu i niczego nie zmienia.

Dlatego zalecamy:

- utwórz **osobny klucz tylko do audytu** (np. o nazwie „audyt”),
- **usuń go zaraz po audycie** w tym samym miejscu panelu,
- nigdy nie wklejaj klucza do czatu.

W GetResponse najbezpieczniej jest utworzyć w panelu osobnego użytkownika z ograniczonym dostępem ([zarządzanie zespołem](https://www.getresponse.pl/pomoc/zarzadzanie-zespolem)) i wygenerować klucz z jego konta. Taki klucz ma te same uprawnienia co ten użytkownik — nie więcej. Daj mu dostęp do tego, co audyt ma sprawdzić (listy, newslettery, automatyzacje): czego ten użytkownik nie widzi, tego audyt też nie zobaczy. Po audycie usuń klucz.

GetResponse nie oferuje kluczy tylko do odczytu i nie planuje ich wprowadzać. Skrypt audytu i tak wysyła wyłącznie zapytania odczytu (GET). GetResponse potwierdził też (odpowiedź działu pomocy z 25.11.2026), że sposób, w jaki narzędzie korzysta z API, jest zgodny z ich zasadami korzystania z API.

W MailerLite możesz dodatkowo ograniczyć token do swojego adresu IP.

## Co jeśli AI zrobi coś innego niż skrypt?

Claude Code uruchamia komendy na Twoim komputerze, więc technicznie mógłby wywołać API inaczej niż przez skrypt. Skill wprost mu tego zabrania: nie może wywoływać API GetResponse ani MailerLite poza skryptem, łączyć się z nimi przez inne narzędzia ani czytać klucza — nawet jeśli go o to poprosisz. To jednak zasada, a nie blokada.

Co Cię chroni naprawdę:

- w ustawieniach domyślnych Claude Code pyta o zgodę, zanim uruchomi komendę — widzisz, co zatwierdzasz,
- osobny klucz usunięty zaraz po audycie: po usunięciu nikt już nic nim nie zrobi,
- [tryb bez AI](../README.md#tryb-bez-ai): skrypt uruchamiasz sam, AI w ogóle nie bierze udziału.

## Czy mogę użyć audytu bez AI?

Tak. Pobierz repozytorium i uruchom skrypt sam w terminalu — instrukcja w [README, sekcja „Tryb bez AI”](../README.md#tryb-bez-ai). Raport `.md` i PDF powstają na Twoim komputerze, a nic nie trafia do żadnego modelu AI. Potrzebny jest tylko Python 3.8 lub nowszy. Bez klucza możesz najpierw zobaczyć przykładowy raport: dodaj `--pokaz`.

## Co AI widzi z mojego konta?

Tylko to, co jest w raporcie:

- nazwy list (grup) i liczbę kontaktów na każdej — bez samych kontaktów,
- przyrost i odpływ kontaktów w okresie audytu, źródła zapisów i powody usunięć (same liczby),
- nazwy automatów, czy są włączone i ile osób przez nie przeszło,
- tematy maili i ich wyniki: wysłane, otwarcia, kliknięcia, wypisy, skargi na spam, odbicia,
- dla serii powitalnej: czy mail jest sprzedażowy, wartościowy czy mieszany, z krótkim powodem (np. „kod rabatowy, procent”) — sama treść maila nie trafia do raportu,
- nazwy formularzy zapisu, ich wyświetlenia, zapisy i skuteczność,
- nazwę sklepu, walutę, liczbę zamówień i przychód w okresie audytu oraz to, ile zamówień nie ma przypisanego kontaktu,
- w GetResponse: domenę adresu nadawcy (np. „@twojsklep.pl”, bez części przed „@”) i ostrzeżenia o jej ustawieniach,
- czy maile mają włączone liczenie sprzedaży.

Imię i nazwisko mogłoby się tam znaleźć tylko wtedy, gdy sam wpisałeś je w nazwę listy, automatu, formularza, sklepu albo w temat maila. Program nie odróżni „Jan Kowalski” od nazwy produktu, więc takich nazw nie ukrywa.

## Czy raport zawiera dane moich klientów?

Nie: żadnych adresów e-mail, imion, telefonów, adresów ani numerów IP klientów i kupujących. Raport zawiera nazwy i liczby z Twojego konta (patrz pytanie wyżej). Zanim wyślesz go dalej, przejrzyj tylko nazwy list i tematy maili — jeśli wpisałeś w nie czyjeś imię i nazwisko, będzie widoczne także w raporcie.

## Czy dane są gdzieś wysyłane albo zapisywane?

- **Wysyłane:** skrypt łączy się wyłącznie z oficjalnym API GetResponse albo MailerLite, szyfrowanym połączeniem. Nie ma statystyk użycia ani wysyłania czegokolwiek do nas. Inne adresy i przekierowania skrypt odrzuca.
- **Zapisywane na Twoim komputerze:** raport `.md` i `.pdf` w bieżącym katalogu, plik postępu (same etapy i liczniki) i — jeśli o to poprosisz — plik `.json` z tymi samymi danymi co raport.
- **Pamięć podręczna:** żeby przerwany audyt nie zaczynał od zera, skrypt na 12 godzin zachowuje przycięte odpowiedzi API (bez danych osobowych) w katalogu tymczasowym systemu, dostępnym tylko dla Twojego użytkownika. Starsze niż 12 godzin usuwa przy kolejnym uruchomieniu.
- **Z Claude Code:** treść raportu trafia do rozmowy z Claude, jak każdy plik, który Claude czyta. Zasady przechowywania rozmów określa Twoje konto Claude i umowa z Anthropic.

## RODO: czy potrzebuję umowy powierzenia?

Nie udzielamy porad prawnych — tę decyzję podejmujesz Ty albo Twój doradca. Pomogą Ci w niej te fakty:

- **W trybie bez AI** dane Twoich klientów nie opuszczają Twojego komputera: skrypt łączy się tylko z Twoim kontem GetResponse albo MailerLite, a danych osobowych kontaktów i kupujących w ogóle nie pobiera.
- **Z AI (Claude Code)** do modelu trafiają tylko dane Twojej firmy — nazwy list, automatów, tematy maili i liczby — bez danych osobowych klientów. Wyjątek: imię czy nazwisko, które sam wpisałeś w nazwę listy albo temat maila (patrz wyżej).
- Autor narzędzia nie otrzymuje żadnych danych z Twojego konta.

## Jak to sprawdzić samemu?

Uruchom test „kanarek” — bez klucza, bez internetu, w kilkanaście sekund:

```bash
python3 tests/test_kanarek.py -v
```

Test udaje API GetResponse i MailerLite dla każdego miejsca, które skrypt może odczytać, i w każde pole odpowiedzi wpisuje zmyślone dane osobowe (np. `kanarek-17@example.com`, `+48 600 000 017`, `203.0.113.17`, „Jan Kanarek17”), także w pola, których audyt nie używa. Potem uruchamia pełny audyt i PDF i sprawdza, że żaden z tych adresów, telefonów i numerów IP nie pojawił się na ekranie, w raporcie, w pliku JSON, w PDF, w pliku postępu ani w pamięci na dysku. Na końcu wypisuje, w których polach może przejść imię i nazwisko (tylko nazwy i tematy wpisane przez właściciela konta).

Kod do przejrzenia:

- test: [tests/test_kanarek.py](../tests/test_kanarek.py),
- skrypty: [GetResponse](../skills/audyt-getresponse/scripts/audyt_getresponse.py), [MailerLite](../skills/audyt-mailerlite/scripts/audyt_mailerlite.py), [wspólne sito i ukrywanie](../skills/audyt-getresponse/scripts/wspolne.py),
- pełny przegląd: [docs/BEZPIECZENSTWO-przeglad.md](BEZPIECZENSTWO-przeglad.md),
- zgłoszenie problemu: [SECURITY.md](../SECURITY.md).
