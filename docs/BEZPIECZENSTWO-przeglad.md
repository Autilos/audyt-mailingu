# Przegląd szczelności — v0.3.4 (22.11.2026), uzupełniony w v0.3.5 (23.11.2026)

Zasada: **zero danych osobowych kontaktów i kupujących — tylko statystyki.** Sprawdziliśmy każdą drogę, którą dane klientów sklepu albo klucz API mogłyby zostać pobrane lub wyjść poza skrypt. Przy każdej: czy była dziurą i co zrobiliśmy. Testy do tego przeglądu: `tests/test_v034.py`.

## 1. Co skrypty pobierają z API

| Miejsce | Czy była dziura | Co zrobiono |
|---|---|---|
| MailerLite: zamówienia sklepu | Nie w v0.3.3 (zamówień skrypt nie czyta od v0.3.0; starsza kopia z v0.2 je czytała). API zwraca zamówienie zawsze w całości: e-mail, imię, nazwisko, telefon i IP kupującego; parametru do wyboru pól nie ma ([dokumentacja](https://developers.mailerlite.com/ecommerce/orders)). | Zostaje zablokowane w spisie dozwolonych ścieżek i w teście. README mówi to wprost. |
| MailerLite: automaty, kampanie | Częściowo: odpowiedź zawiera adres nadawcy i adres do odpowiedzi (`from`, `reply_to`). Nie trafiał do raportu, ale leżał w pamięci odpowiedzi na dysku. | Sito odpowiedzi — zostają tylko potrzebne pola. |
| MailerLite: sklepy | Częściowo: obiekt sklepu może mieć dane dostępowe do sklepu (`access_data`, np. klucze WooCommerce) i grupę. Leżały w pamięci na dysku. | Sito: zostaje identyfikator sklepu (potrzebny do raportu sprzedaży), nazwa, platforma, włączony, wewnętrzny, waluta. |
| MailerLite: raport sprzedaży sklepu (`/ecommerce/shops/{id}/reports/stats`, od v0.3.5) | Nie: sprawdzone na żywym koncie 23.11.2026 (wypisana tylko struktura, bez wartości) — `data.ecommerce`: liczba zamówień, przychód, średnie zamówienie (liczby); `data.series`: dzień po dniu data i liczby zamówień i przychodu z kampanii i z automatów. Żadnych pól o kupujących. Okres `start_date`–`end_date` wymagany, najwyżej 365 dni. | Ścieżka w spisie dozwolonych tylko z identyfikatorem z cyfr. Sito przepuszcza wyłącznie liczby (tekst, słownik albo lista w tych polach odpadają); data dnia i każde inne pole są odrzucane. Test z doklejonymi fikcyjnymi danymi kupującego (`tests/test_v035.py`). |
| MailerLite: grupy, formularze, ustawienia e-commerce | Nie (liczby i nazwy). | Sito i tak je przycina. |
| GetResponse: zamówienia | Nie: tylko pola numer, kwota, data, status, przypisany kontakt (sam identyfikator, liczymy tylko, czy jest). | Bez zmian, plus sito. |
| GetResponse: adresy nadawcy | Częściowo: pełny adres i nazwa nadawcy (np. imię właściciela) leżały w pamięci na dysku; raport pokazywał tylko domenę. | Sito: z adresu zostaje sama domena już w pamięci. |
| GetResponse: automaty, newslettery, autorespondery, sklepy, formularze | Częściowo: odpowiedzi bez wybranych pól zawierały pola, których audyt nie używa. | Sito dla każdej ścieżki. |
| Statystyki (rozmiar list, zapisy, usunięcia, wyniki maili, przychód) | Nie: same liczby zbiorcze. | Przechodzą w całości (jedyny wyjątek od sita). |
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

- **Klucz daje pełny dostęp do konta.** GetResponse i MailerLite nie mają kluczy tylko do odczytu. Skrypt tylko czyta, ale sam klucz pozwala na wszystko. Zalecenie w README i SKILL.md: osobny klucz do audytu, usunięty zaraz po nim (MailerLite pozwala też ograniczyć token do adresu IP).
- **Klucz leży na komputerze użytkownika** (zmienna środowiskowa albo plik). Każdy program uruchomiony z tymi samymi uprawnieniami — także asystent AI, który dostanie inne polecenie — technicznie może go odczytać. Skill tego zabrania, ale to zasada, nie blokada. Opisane w README („Czego nie da się wykluczyć technicznie”).
- **Treść raportu trafia do rozmowy z AI**: nazwy list i automatów, tematy maili, liczby. To dane firmy, nie klientów; adresy i telefony w tych nazwach są ukrywane, ale inne dane wpisane w nazwy (np. samo imię i nazwisko) rozpoznać się nie da.
- **Treść maili** jest czytana tylko do oceny „sprzedażowy / wartościowy” i nie trafia do raportu (raport pokazuje tylko, jakie sygnały znaleziono, np. „kod rabatowy”).

## Dodane po sprawdzeniu na żywym API

- v0.3.5: raport sprzedaży sklepu MailerLite `GET /ecommerce/shops/{id}/reports/stats?start_date=…&end_date=…` ([dokumentacja](https://developers.mailerlite.com/ecommerce/shops)) — po sprawdzeniu struktury odpowiedzi na żywym koncie (same nazwy pól i typy, bez wartości, zgodnie z `CLAUDE.md`). Pojedyncze zamówienia (`/orders`) nadal zablokowane.
