# Zmiany

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
