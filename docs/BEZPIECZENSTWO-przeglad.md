# Przegląd szczelności — v0.3.4 (22.11.2026), uzupełniony w v0.3.5 i v0.3.6 (23.11.2026)

Zasada: **zero danych osobowych kontaktów i kupujących — tylko statystyki.** Sprawdziliśmy każdą drogę, którą dane klientów sklepu albo klucz API mogłyby zostać pobrane lub wyjść poza skrypt. Przy każdej: czy była dziurą i co zrobiliśmy. Testy do tego przeglądu: `tests/test_v034.py`, `tests/test_v036.py` i dowód całościowy `tests/test_kanarek.py` (opis w sekcji 5). Pytania i odpowiedzi prostym językiem: [FAQ-bezpieczenstwo.md](FAQ-bezpieczenstwo.md).

## 1. Co skrypty pobierają z API

| Miejsce | Czy była dziura | Co zrobiono |
|---|---|---|
| MailerLite: zamówienia sklepu | Nie w v0.3.3 (zamówień skrypt nie czyta od v0.3.0; starsza kopia z v0.2 je czytała). API zwraca zamówienie zawsze w całości: e-mail, imię, nazwisko, telefon i IP kupującego; parametru do wyboru pól nie ma ([dokumentacja](https://developers.mailerlite.com/ecommerce/orders)). | Zostaje zablokowane w spisie dozwolonych ścieżek i w teście. README mówi to wprost. |
| MailerLite: automaty, kampanie | Częściowo: odpowiedź zawiera adres nadawcy i adres do odpowiedzi (`from`, `reply_to`). Nie trafiał do raportu, ale leżał w pamięci odpowiedzi na dysku. | Sito odpowiedzi — zostają tylko potrzebne pola. |
| MailerLite: sklepy | Częściowo: obiekt sklepu może mieć dane dostępowe do sklepu (`access_data`, np. klucze WooCommerce) i grupę. Leżały w pamięci na dysku. | Sito: zostaje identyfikator sklepu (potrzebny do raportu sprzedaży), nazwa, platforma, włączony, wewnętrzny, waluta. |
| MailerLite: raport sprzedaży sklepu (`/ecommerce/shops/{id}/reports/stats`, od v0.3.5) | Nie: sprawdzone na żywym koncie 23.11.2026 (wypisana tylko struktura, bez wartości) — `data.ecommerce`: liczba zamówień, przychód, średnie zamówienie (liczby); `data.series`: dzień po dniu data i liczby zamówień i przychodu z kampanii i z automatów. Żadnych pól o kupujących. Okres `start_date`–`end_date` wymagany, najwyżej 365 dni. | Ścieżka w spisie dozwolonych tylko z identyfikatorem z cyfr. Sito przepuszcza wyłącznie liczby (tekst, słownik albo lista w tych polach odpadają); data dnia i każde inne pole są odrzucane. Test z doklejonymi fikcyjnymi danymi kupującego (`tests/test_v035.py`). |
| MailerLite: grupy, formularze, ustawienia e-commerce | Nie (liczby i nazwy). | Sito i tak je przycina. |
| GetResponse: zamówienia | Częściowo: pola numer, kwota, data, status i identyfikator przypisanego kontaktu; identyfikator leżał w pamięci na dysku. | Od v0.3.6 identyfikator zamienia się od razu na „jest / nie ma”. |
| GetResponse: adresy nadawcy | Częściowo: pełny adres i nazwa nadawcy (np. imię właściciela) leżały w pamięci na dysku; raport pokazywał tylko domenę. | Sito: z adresu zostaje sama domena już w pamięci. |
| GetResponse: automaty, newslettery, autorespondery, sklepy, formularze | Częściowo: odpowiedzi bez wybranych pól zawierały pola, których audyt nie używa. | Sito dla każdej ścieżki. |
| Statystyki (rozmiar list, zapisy, usunięcia, wyniki maili, przychód) | Nie: same liczby zbiorcze. Ale do v0.3.5 napisy w nich przechodziły bez ukrywania (patrz sekcja 5). | Od v0.3.6 przechodzą tylko liczby i krótkie kody (np. daty). |
| Pola dodane przez dostawcę w przyszłości | Tak, potencjalnie: nowe pole z danymi trafiłoby do pamięci na dysku. | Sito działa jak lista dozwolonych pól — nowe pola są odrzucane same. |

## 2. Co skrypty wypisują i zapisują

| Miejsce | Czy była dziura | Co zrobiono |
|---|---|---|
| Ekran (stdout/stderr) | Nie wypisywał treści odpowiedzi, ale przy nieobsłużonym błędzie API (np. 400) albo zerwanym połączeniu pokazywał surowy komunikat Pythona (traceback). | Każdy błąd kończy się jednym zdaniem po polsku: kod błędu i ścieżka, bez treści odpowiedzi. Treść odpowiedzi z błędem nie jest czytana. |
| Tryb debug | Nie ma takiego trybu. | — |
| Plik postępu `<raport>.postep.txt` | Nie: tylko etapy i liczniki. | Dopisany do `.gitignore`. |
| Raport `.md` i plik `--json` | Tak, w wąskim przypadku: adres e-mail albo telefon wpisany przez właściciela w nazwę listy, automatu, formularza czy temat maila trafiał do raportu. | Maskowanie: „[e-mail ukryty]”, „[telefon ukryty]” — w sicie i jeszcze raz przed zapisem. |
| Pamięć odpowiedzi (katalog tymczasowy, 12 h) | Częściowo: trzymała całe odpowiedzi (adres nadawcy, dane dostępowe sklepu). Prawa tylko dla właściciela. | Trzyma tylko przycięte odpowiedzi; stara pamięć przy odczycie też przechodzi przez sito; wyłącza się, gdy katalog należy do innego użytkownika. |
| PDF i HTML | Nie pobierał zasobów, ale przeglądarka w tle mogła łączyć się z siecią (aktualizacje, statystyki). | Blokada w HTML (Content-Security-Policy: nic z sieci) i przeglądarka bez usług w tle. Raport nie zawiera obrazków. |
| Repozytorium (`.gitignore`) | Częściowo: PDF, HTML, pliki postępu i pliki kluczy nie były ignorowane. | Dopisane: `audyt*.pdf`, `audyt*.html`, `*.postep.txt`, `*.key`, `.env.*`. |

## 3. Klucz API

| Miejsce | Czy była dziura | Co zrobiono |
|---|---|---|
| Przekierowania | Nie: odrzucane, klucz nie idzie pod nowy adres. | Bez zmian, test. |
| Link „następna strona” (MailerLite) | Nie w praktyce (sprawdzany początek adresu), ale bez jawnego sprawdzenia protokołu i hosta. | Dodane sprawdzenie: tylko `https` i dokładnie `connect.mailerlite.com`. Test z czterema złymi adresami. |
| Adres API GetResponse | Nie: tylko trzy oficjalne adresy. | Bez zmian. |
| Zmienne proxy (`HTTPS_PROXY`) | Nie: połączenie przez proxy jest nadal szyfrowane, proxy nie widzi klucza. | Opisane w README. |
| Klucz w raporcie, nazwach plików, komunikatach | Nie: w nazwie katalogu pamięci jest tylko skrót SHA-256. | Test: „falszywy-klucz” nie pojawia się nigdzie. |
| Zależności i telemetria | Nie: tylko biblioteka standardowa Pythona, brak telemetrii. | — |
| Tryb pokazowy (`--pokaz`) | Nie: nie czyta klucza i nie łączy się z siecią. | Test z zablokowaną siecią i zablokowanym odczytem klucza. |

## 4. Instrukcje dla Claude (SKILL.md)

| Miejsce | Czy była dziura | Co zrobiono |
|---|---|---|
| Wywołania API poza skryptem | Tak: nic nie zabraniało Claude wywołania API kluczem użytkownika (np. `curl` po listę kontaktów). | Zakaz w „Zasadach dla Claude” w obu audytach i w `audyt-pomoc`. |
| Prośba użytkownika o kontakty | Tak: nie było instrukcji, co odpowiedzieć. | Zakaz także na prośbę użytkownika, z gotowym wyjaśnieniem: dane klientów trafiłyby do modelu AI. |
| Odczyt klucza | Częściowo: był zakaz `cat` pliku klucza, brakowało `env`, `printenv`, `set`, `export -p`, plików konfiguracyjnych powłoki i `.env`. | Pełna lista zakazów i jedyne dozwolone sprawdzenie bez wartości. |
| Pamięć odpowiedzi i plik JSON | Brak zasady. | Claude czyta tylko raport `.md` i plik postępu. |
| Polecenia w nazwach z konta | Była zasada (dane, nie polecenia). | Doprecyzowana. |

## Czego nie da się załatać technicznie

- **Klucz daje pełny dostęp do konta.** GetResponse i MailerLite nie mają kluczy tylko do odczytu. Skrypt tylko czyta, ale sam klucz pozwala na wszystko. Zalecenie w README i SKILL.md: osobny klucz do audytu, usunięty zaraz po nim (MailerLite pozwala też ograniczyć token do adresu IP). W GetResponse najbezpieczniej wygenerować klucz z konta osobnego użytkownika z ograniczonym dostępem ([zarządzanie zespołem](https://www.getresponse.pl/pomoc/zarzadzanie-zespolem)) — taki klucz ma te same uprawnienia co ten użytkownik. GetResponse nie oferuje kluczy tylko do odczytu i nie planuje ich wprowadzać; skrypt i tak wysyła wyłącznie zapytania odczytu (GET). GetResponse potwierdził (odpowiedź działu pomocy z 25.11.2026), że sposób korzystania z API przez narzędzie jest zgodny z ich zasadami korzystania z API.
- **Klucz leży na komputerze użytkownika** (zmienna środowiskowa albo plik). Każdy program uruchomiony z tymi samymi uprawnieniami — także asystent AI, który dostanie inne polecenie — technicznie może go odczytać. Skill tego zabrania, ale to zasada, nie blokada. Opisane w README („Czego nie da się wykluczyć technicznie”).
- **Treść raportu trafia do rozmowy z AI**: nazwy list i automatów, tematy maili, liczby. To dane firmy, nie klientów; adresy, telefony i numery IP w tych nazwach są ukrywane, ale inne dane wpisane w nazwy (np. samo imię i nazwisko) rozpoznać się nie da. Kto nie chce przekazywać AI nawet tego, używa trybu bez AI (README).
- **Treść maili** jest czytana tylko do oceny „sprzedażowy / wartościowy” i nie trafia do raportu (raport pokazuje tylko, jakie sygnały znaleziono, np. „kod rabatowy”).

## 5. Niezależny przegląd i test „kanarek” (v0.3.6, 23.11.2026)

**Przegląd:** osobny agent AI bez kontekstu projektu, z dostępem wyłącznie do skryptów i plików SKILL.md (bez tego dokumentu, README i testów), dostał zadanie: „znajdź każdą drogę, którą adres e-mail, imię, nazwisko, telefon, adres, IP kontaktu albo kupującego, albo klucz API może trafić do modelu AI, na dysk albo do sieci poza oficjalnym API”. Każde znalezisko sprawdziliśmy w kodzie.

| # | Znalezisko | Prawdziwe? | Co zrobiono |
|---|---|---|---|
| 1 | Imię, nazwisko, adres wpisane w nazwę listy, automatu, sklepu czy temat maila trafiają do raportu, a więc do AI. | Tak — znana granica. Program nie odróżni „Jan Kowalski” od nazwy produktu, a bez nazw raport byłby bezużyteczny. | Opisane w README, FAQ i poniżej. Test „kanarek” pilnuje, żeby imię i nazwisko mogło przejść **tylko** w takich polach (lista `GRANICA_NAZW`). |
| 2 | Telefon w zapisach 2-2-2, 2-3-2-2, z nawiasami, zagraniczny — nieukryty. | Tak. | Nowe rozpoznawanie: 9–13 cyfr w dowolnym podziale na grupy, z numerem kraju; daty zostają. Test `test_v036.py`. |
| 3 | E-mail z „＠”, „．”, „[at]”, „at … dot” — nieukryty. | Tak. | Ukrywanie najpierw sprowadza tekst do zwykłych znaków (NFKC); rozpoznaje też `%40`, `&#64;`, „[at]”, „at … dot”. |
| 4 | Nazwy pól w statystykach (np. źródła zapisów) nie były ukrywane, a trafiają do raportu. | Tak, przy nietypowej odpowiedzi API. | Ukrywane są też nazwy pól; w statystykach przechodzą tylko nazwy-kody. |
| 5 | Identyfikator kontaktu (`contactId`) z zamówień GetResponse leżał w pamięci na dysku; pamięć nie była sprzątana. | Tak (dysk, 12 h, tylko Twój użytkownik). | `contactId` → „jest / nie ma” już w sicie. Odpowiedzi starsze niż 12 h są usuwane przy każdym uruchomieniu (także z `--bez-pamieci`). |
| 6 | Klucz ustawiany jako zmienna przed uruchomieniem Claude Code jest w środowisku każdej komendy. | Tak. | SKILL.md: klucz tylko w pliku zapisanym przez użytkownika w drugim terminalu; zmienna — w trybie bez AI. To nadal zasada, nie blokada (patrz „Czego nie da się załatać”). |
| 7 | Zakaz MCP dotyczył tylko narzędzi „z kluczem użytkownika”, a konektor GetResponse zalogowany bez klucza może czytać kontakty. | Tak. | SKILL.md (oba audyty i pomoc): zakaz **każdego** innego połączenia z GetResponse i MailerLite (konektor, MCP, wtyczka), także bez klucza. |
| 8 | Klucz z nową linią albo spacją: biblioteka HTTP rzuca błąd z kluczem w treści. | Tak (rzadkie: zły zapis klucza). | Klucz sprawdzany przed użyciem; zły znak = jedno zdanie po polsku, bez klucza. |
| 9 | Statystyki zapisywane do pamięci bez ukrywania napisów. | Tak. | Statystyki: tylko liczby i krótkie kody. |
| 10 | Wynik funkcji we wzorze sita (np. flagi wiadomości) bez ukrywania. | Tak. | Wynik każdej funkcji przechodzi przez ukrywanie; flagi przechodzą tylko jako kody. |
| 11 | Link do kolejnej strony MailerLite (z kursorem) mógł trafić do listy niedostępnych miejsc w raporcie. | Tak, ale to nie dane osobowe. | Zapisywana sama ścieżka, bez kursora. |
| 12 | Katalog nadrzędny pamięci nie był sprawdzany (wspólny katalog tymczasowy). | Częściowo: na macOS i w większości systemów katalog tymczasowy jest osobny dla użytkownika. | Sprawdzany właściciel obu katalogów i to, że nie są dowiązaniem. |
| 13 | SKILL.md zachęca, by dać plik `.md` innemu asystentowi AI, i wspomina plik `--json`. | Nie — raport i JSON zawierają te same dane firmy (nazwy, liczby), bez danych klientów; granica z punktu 1 opisana w FAQ. | Bez zmian kodu; FAQ radzi przejrzeć nazwy list i tematy przed wysłaniem raportu dalej. |
| 14 | Kopia HTML zostaje obok raportu, gdy PDF się nie uda. | Nie — to celowe (HTML do ręcznego wydruku), ta sama treść co `.md`, na Twoim dysku. | Bez zmian. Przy okazji naprawiony błąd: Chrome uruchomiony w czystym środowisku zapisywał PDF, a skrypt mylnie zgłaszał porażkę. |

Dodatkowo, poza listą przeglądu: pola słownikowe (status, waluta, platforma, typ, daty) przepuszczają tylko krótki kod bez spacji, więc zdanie czy nazwisko w takim polu odpada.

**Test „kanarek”** (`python3 tests/test_kanarek.py -v`): atrapa API dla każdej ścieżki z `DOZWOLONE_SCIEZKI` (GetResponse i MailerLite) wpisuje w każde pole tekstowe każdej odpowiedzi — także w pola nieużywane i doklejone (`email`, `phone`, `ip_address`, `subscriber`, `customer`, adres) — unikalne zmyślone dane osobowe w różnych zapisach. Dwa przebiegi na system (kanarek we wszystkich polach; kanarek tylko w polach opisowych, żeby przeszły też gałęzie zależne od statusów), każdy dwukrotnie (drugi raz z pamięci na dysku), plus PDF. Wynik v0.3.6: ok. 3000 kanarków, **zero** adresów e-mail, telefonów i numerów IP na ekranie, w raporcie, JSON, HTML, PDF, pliku postępu, pamięci na dysku i w adresach zapytań; klucz tylko w nagłówku zapytania do oficjalnego API. Test sam sprawdza, że wykrywa wyciek: z wyłączonym ukrywaniem musi się nie udać.

## Dodane po sprawdzeniu na żywym API

- v0.3.5: raport sprzedaży sklepu MailerLite `GET /ecommerce/shops/{id}/reports/stats?start_date=…&end_date=…` ([dokumentacja](https://developers.mailerlite.com/ecommerce/shops)) — po sprawdzeniu struktury odpowiedzi na żywym koncie (same nazwy pól i typy, bez wartości, zgodnie z `CLAUDE.md`). Pojedyncze zamówienia (`/orders`) nadal zablokowane.
