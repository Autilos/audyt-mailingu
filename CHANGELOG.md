# Zmiany

## 0.3.5 — 2026-11-23

MailerLite: wracają liczba zamówień i przychód — bez danych kupujących.

- Audyt MailerLite czyta raport zbiorczy sklepu (`/ecommerce/shops/{id}/reports/stats`) za okres audytu: ile zamówień i jaki przychód sklep przesłał do MailerLite, średnie zamówienie i ile z tego przypisano do maili, osobno kampanie i automaty. Raport sklepu obejmuje najwyżej 365 dni (limit API) — przy dłuższym okresie raport to zaznacza.
- Nowy problem w raporcie: „sklep podłączony, ale 0 zamówień w okresie” (tylko włączony sklep zewnętrzny, nie wewnętrzny sklep MailerLite) z rekomendacją „Napraw przesyłanie zamówień ze sklepu”.
- Prywatność: odpowiedź sprawdzona na żywym koncie — najpierw sama struktura (nazwy pól i typy, bez wartości), w niej żadnych pól o kupujących. Sito przepuszcza z tej odpowiedzi wyłącznie liczby. Pojedynczych zamówień (`/orders`) audyt nadal nie czyta.
- Tryb pokazowy: zmyślone liczby sklepu z herbatą.
- Dokumentacja: SKILL.md (nowy sygnał w tabeli), README („Co sprawdza”, „Bezpieczeństwo”), `docs/BEZPIECZENSTWO-przeglad.md`, `docs/CONCEPTS.md`. Testy: `tests/test_v035.py`.
- Strona (`landing/index.html`): akapit „Bez danych osobowych” i zdanie o kluczach zgodne z README i stroną w WordPressie.

## 0.3.4 — 2026-11-22

Prywatność „nawet przypadkiem”: zero danych osobowych kontaktów i kupujących, tylko statystyki.

- Sito odpowiedzi w obu skryptach: z każdej odpowiedzi API od razu zostają tylko pola potrzebne audytowi, a reszta jest odrzucana, zanim trafi do pamięci na dysku, raportu albo na ekran. Dotyczy to też pól, które GetResponse czy MailerLite dodadzą w przyszłości. Z adresu nadawcy w GetResponse zostaje sama domena.
- Adres e-mail i numer telefonu wpisany w nazwę listy, automatu, formularza albo temat maila jest w raporcie i pliku JSON ukryty („[e-mail ukryty]”, „[telefon ukryty]”).
- Błędy API: skrypt nie czyta i nie wypisuje treści odpowiedzi z błędem; zamiast surowych komunikatów Pythona (traceback) — jedno zdanie po polsku.
- MailerLite: klucz idzie tylko pod `https://connect.mailerlite.com` — dodatkowo sprawdzany protokół i host (także w linkach do kolejnej strony).
- Pamięć odpowiedzi: wyłącza się, gdy katalog tymczasowy należy do innego użytkownika; odpowiedzi zapisane przez starszą wersję też przechodzą przez sito.
- PDF: blokada pobierania czegokolwiek z sieci (Content-Security-Policy) i przeglądarka bez usług w tle.
- SKILL.md (oba audyty i pomoc): „Zasady dla Claude — prywatność i klucz” — żadnych wywołań API poza skryptem, żadnych kontaktów ani danych kupujących nawet na prośbę użytkownika (z wyjaśnieniem dlaczego), zakaz czytania klucza (`env`, `printenv`, pliki konfiguracyjne powłoki, `.env`, plik klucza).
- README: nowa sekcja „Bezpieczeństwo” — klucze dają pełny dostęp do konta, „tylko odczyt” dotyczy skryptu; osobny klucz do audytu i usunięcie go zaraz po nim. MailerLite: uczciwie, że API zwraca zamówienie w całości z danymi kupującego, więc audyt zamówień nie czyta.
- `.gitignore`: także PDF, HTML, pliki postępu i pliki kluczy.
- Nowy dokument `docs/BEZPIECZENSTWO-przeglad.md` i testy `tests/test_v034.py` (fikcyjne dane kupującego doklejone do każdej odpowiedzi nie wychodzą poza skrypt; tryb pokazowy nie dotyka sieci ani klucza).

## 0.3.3 — 2026-11-21

- Duże konta: skill uruchamia audyt od razu w tle i co chwilę czyta plik postępu (`<raport>.postep.txt`); domyślny okres 30 dni (90 na prośbę).
- Wznawianie: pamięć odpowiedzi API w katalogu tymczasowym (12 godzin, prawa tylko dla właściciela, bez danych osobowych) — przerwany audyt uruchomiony ponownie nie zaczyna od zera; `--bez-pamieci` wyłącza.
- Postęp: etapy i liczniki (automaty, maile x/y, newslettery, strony zamówień).
- Klucz bez zamykania Claude Code: zapis do `~/.config/audyt-mailingu/<system>.key` w drugim oknie terminala, z komunikatem „Klucz zapisany (N znaków)”; Claude nie pyta drugi raz o system. README: krok `/login` w świeżym Claude Code.
- Powitanie: ✅ tylko gdy działa na największej liście — jeśli tam jest wyłączone, raport mówi to wprost.
- Formularze bez uprawnień klucza: zwykły komunikat, że ta część jest pominięta i gdzie zobaczyć wyniki.
- MailerLite: dodane `--test-polaczenia` (SKILL.md się do niego odwoływał, a skrypt go nie miał).

## 0.3.2 — 2026-11-21

- Porzucony koszyk i maile po zakupie: zanim raport poleci ich budowę, każe zapytać, czy sklep nie wysyła ich już innym systemem (maile transakcyjne sklepu, wtyczka, osobny serwis) — bez dublowania maili. Uwaga pod listą kontrolną w raporcie GetResponse i MailerLite, zasada w SKILL.md i `docs/CONCEPTS.md`.

## 0.3.1 — 2026-11-21

- Raport pokazowy bez klucza i bez internetu: `--pokaz` w obu skryptach („zrób pokazowy audyt”), zmyślony sklep z herbatą, adnotacja „Raport pokazowy — dane zmyślone”.
- Plik `.md` zawsze obok PDF, na końcu sekcja „Dla asystenta AI” (problemy, zadania `- [ ]` z miejscem w panelu, czego audyt nie sprawdził, kontakt). W PDF ta sekcja jest pomijana.
- PDF: wszystkie adresy WWW i e-mail są klikalnymi linkami.
- Nowy skill `audyt-pomoc`: co zrobić samemu, co zlecić, kontakt bez cen, zgłoszenie błędu bez danych z konta; szablon `.github/ISSUE_TEMPLATE/blad.md`.
- Gwiazdka i opinie: odznaka w README, wątek opinii w Discussions, krótka linijka w stopce raportu.
- Poprawka: słowo „ponown” łapało „Witaj ponownie” i fałszywie oznaczało automat drugiego zakupu jako działający.

## 0.3.0 — 2026-11-21

**Zero danych osobowych**
- Lista dozwolonych ścieżek API w obu skryptach — każda inna ścieżka przerywa audyt (test w `tests/`).
- GetResponse: liczba kontaktów na listach ze statystyk list (`/campaigns/statistics/list-size`) zamiast `/contacts`. Zamówienia tylko z polami `orderId, totalPrice, processedAt, contactId, status` i filtrem daty po stronie API.
- MailerLite: zamówienia nie są już pobierane (API zwraca je z danymi kupującego i nie pozwala ograniczyć pól). Raport mówi, czego bez nich nie widać.

**Nowe w raporcie**
- Seria powitalna: maile, dni, wyniki i klasyfikacja sprzedażowy / wartościowy / mieszany (ocena po słowach i elementach maila (kod, procent, ceny, przyciski) — może się pomylić; reguły jawne w kodzie, powód przy każdym mailu).
- Rekomendacje w kolejności wykonania — tylko do wykrytych problemów; gdy seria jest dobra, raport to mówi.
- Formularze zapisu: wyświetlenia, zapisy, konwersja (GetResponse `/forms` — wymaga uprawnień klucza do formularzy; MailerLite `/forms/{typ}`).
- Zdrowie bazy: przyrost, odpływ, źródła zapisów, powody usunięć (GetResponse); stan grup (MailerLite).
- Dostarczalność (GetResponse): status domeny nadawcy, ostrzeżenia DKIM i DMARC.
- Przychód widziany przez GetResponse (`/statistics/ecommerce/revenue`) i opcjonalne porównanie z danymi sklepu (`--przychod-sklepu`, `--zamowienia-sklepu`).
- `--test-polaczenia` — sprawdza klucz jednym zapytaniem.
- `raport_pdf.py` — raport .md do PDF w kolorach strony audytu, bez dodatkowych pakietów.
- Stopka raportu: „To podstawowy audyt. Chcesz pełny audyt albo wdrożenie poprawek? Napisz do mnie” z linkiem do formularza kontaktu.
- Raport i strona bez żargonu (np. zamiast „heurystyka” — „ocena po słowach i elementach maila, może się pomylić”; „okres audytu” zamiast „okna”).

**Dokumentacja**
- `docs/CONCEPTS.md` — słownik pojęć projektu; `CLAUDE.md` i sekcja „Dla współtwórców” w README: przed zmianą przeczytaj słownik.

**Poprawki**
- MailerLite: dzień maila w automacie liczony po drzewie kroków (kolejność w API nie jest kolejnością w automacie).
- GetResponse: automaty o nazwie roboczej („Szkic…”) włączone i działające są oznaczane.
- Puste listy i sklep bez zamówień nie generują już mylących wierszy w raporcie.

## 0.2.1

- Klucz wysyłany tylko do oficjalnego API, przekierowania odrzucane, SECURITY.md.
