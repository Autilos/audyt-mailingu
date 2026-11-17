---
name: audyt-mailerlite
description: Audyt e-mail marketingu sklepu internetowego w MailerLite — tylko odczyt. Sprawdza automaty po wyzwalaczu (powitanie, porzucony koszyk, po zakupie, ponowny zakup), czy są zepsute albo martwe, wyniki każdego maila w automacie, brak linku do wypisu, kampanie z ostatnich dni, podłączenie sklepu i liczenie sprzedaży z maili. Kończy raportem po polsku z listą najważniejszych problemów. Use when user says „audyt mailerlite", „sprawdź mój mailerlite", „czy moje automaty mailerlite działają", „audyt mailingu mailerlite", „mailerlite audit".
---

# Audyt MailerLite (tylko odczyt)

Skill czyta konto MailerLite przez oficjalne API (nowy MailerLite, konta od 22.03.2022) i pisze raport. **Niczego nie zmienia** — skrypt wywołuje wyłącznie zapytania GET. Nie pobiera adresów e-mail ani danych subskrybentów.

## Krok 1 — token API

1. Token: MailerLite → **Integracje → MailerLite API → Wygeneruj nowy token**.
2. Uprzedź wprost: **token MailerLite daje pełny dostęp do konta** (nie znalazłem w dokumentacji API, stan na listopad 2026, tokenów ograniczonych do odczytu). Skill tylko czyta; po audycie token można usunąć w tym samym miejscu. Przy tworzeniu tokenu można ograniczyć go do adresu IP.
3. Ustaw jako zmienną środowiskową — **nie wklejaj tokenu do czatu**:
   ```bash
   export MAILERLITE_API_KEY='…'
   ```

## Krok 2 — uruchom

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-.}/skills/audyt-mailerlite/scripts/audyt_mailerlite.py" --dni 90 --raport audyt-mailerlite.md
```

Python 3.8+, bez dodatkowych pakietów. Limit API MailerLite to 120 zapytań na minutę — skrypt robi przerwy; mały sklep to kilkanaście sekund.

## Krok 3 — omów raport

Najpierw sekcja „Najważniejsze”, szczegóły na prośbę. Dla każdego problemu powiedz, co zrobić w panelu MailerLite.

| Sygnał | Co znaczy | Co doradzić |
|---|---|---|
| BRAK LINKU DO WYPISU | Mail w automacie nie ma linku do wypisu | Pilne: wymóg prawny i sygnał spamu dla Gmaila |
| Automat zepsuty / niedokończony | MailerLite sam oznacza go jako broken lub incomplete | Otwórz automat w panelu i popraw zaznaczony krok |
| Włączony, nikt nie wszedł | Wyzwalacz nie łapie nikogo | Sprawdź formularz, grupę albo sklep w wyzwalaczu |
| Brak (wymaga podłączonego sklepu) | Koszyk i ponowny zakup potrzebują zamówień ze sklepu | Podłącz sklep: Integracje → e-commerce |
| Bez liczenia sprzedaży | Kampania/automat nie przypisuje zamówień do maili | Ustawienia kampanii/automatu → śledzenie e-commerce |
| Skargi na spam ≥ 0,3% (powyżej 0,1% — ostrzeżenie) | Google wymaga poniżej 0,3% i zaleca poniżej 0,1% | Segmentacja, łatwy wypis, czyszczenie bazy |

Zasady:
- Oceniaj maile po kliknięciach i sprzedaży — otwarcia w MailerLite obejmują automatyczne otwarcia programów pocztowych.
- Progi wypisów i kliknięć to orientacyjne progi praktyczne, nie normy.
- „Wewnętrzny sklep MailerLite” zakłada się sam — zero zamówień w nim nie jest problemem, jeśli sprzedajesz gdzie indziej.
- Nie podawaj liczb spoza raportu. Nie proponuj zmian przez API — skill jest tylko do odczytu.

## Co API MailerLite pokazuje (a GetResponse nie)

Wyzwalacz każdego automatu, jego kroki, flagi „zepsuty/niedokończony”, wyniki każdego maila w automacie, link do wypisu i przyciski bez linków, przypisanie zamówień do konkretnego maila. Automatu „porzucone przeglądanie” MailerLite nie oferuje — skill go nie wymaga.
