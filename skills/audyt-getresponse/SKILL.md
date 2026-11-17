---
name: audyt-getresponse
description: Audyt e-mail marketingu sklepu internetowego w GetResponse — tylko odczyt. Sprawdza, czy działają podstawowe automaty (powitanie, porzucony koszyk, po zakupie, drugi zakup, reaktywacja), czy ktoś przez nie przechodzi, wyniki każdego maila (otwarcia i kliknięcia bez botów, wypisy, skargi), częstotliwość newsletterów, czy sklep przesyła zamówienia i czy maile mają włączone liczenie przychodu. Kończy raportem po polsku z listą najważniejszych problemów. Use when user says „audyt getresponse", „sprawdź mój getresponse", „czy moje automaty działają", „audyt mailingu", „audyt e-mail marketingu", „getresponse audit".
---

# Audyt GetResponse (tylko odczyt)

Skill czyta konto GetResponse przez oficjalne API v3 i pisze raport. **Niczego nie zmienia** — skrypt wywołuje wyłącznie zapytania GET. Nie pobiera adresów e-mail ani danych kontaktów — tylko liczby zbiorcze oraz nazwy automatów, list i tematy maili z konta.

## Krok 1 — klucz API

1. Zapytaj użytkownika, czy ma klucz API. Jeśli nie: GetResponse → **Menu → Integracje i API → API → Wygeneruj klucz API**.
2. Uprzedź wprost: **klucz API GetResponse daje pełny dostęp do konta** (w dokumentacji API, stan na listopad 2026, nie ma kluczy ograniczonych do odczytu). Ten skill tylko czyta, ale klucz trzymaj jak hasło, a po audycie możesz go usunąć w tym samym miejscu.
3. Klucz ustaw jako zmienną środowiskową w terminalu użytkownika — **nie wklejaj go do czatu i nie zapisuj w plikach projektu**:
   ```bash
   export GETRESPONSE_API_KEY='…'
   ```
   Jeśli użytkownik wkleił klucz do czatu, poproś, żeby po audycie wygenerował nowy.
4. GetResponse MAX (własna domena konta): potrzebne `--max-domena twojadomena.pl` i `--api https://api3.getresponse360.pl/v3` (albo `.com` — zależnie od środowiska konta).

## Krok 2 — uruchom

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-.}/skills/audyt-getresponse/scripts/audyt_getresponse.py" --dni 90 --raport audyt-getresponse.md
```

- Wymaga tylko Pythona 3.8+ (bez dodatkowych pakietów).
- Czas: od kilkudziesięciu sekund (mały sklep) do kilku minut (tysiące zamówień miesięcznie — GetResponse wolno oddaje listę zamówień). Przy ogromnym sklepie skróć okno (`--dni 30`) albo pomiń zamówienia (`--bez-zamowien`).
- `--json dane.json` zapisuje dane zbiorcze, jeśli chcesz liczyć dalej.

## Krok 3 — omów raport

Przeczytaj `audyt-getresponse.md` i przedstaw użytkownikowi **najpierw sekcję „Najważniejsze”**, potem szczegóły tylko na prośbę. Dla każdego problemu powiedz, co zrobić w panelu GetResponse.

Jak czytać wyniki:

| Sygnał | Co znaczy | Co doradzić |
|---|---|---|
| Automat włączony, 0 zakończyło i 0 w trakcie | Wygląda na działający, a nikt do niego nie wchodzi — zwykle zły warunek startu, pusta lista albo brak zdarzeń ze sklepu | Sprawdź w panelu element startowy automatu |
| ❓ na liście kontrolnej | Nie znaleziono automatu po nazwie — API nie pokazuje warunków | Zapytaj użytkownika, czy taki automat ma pod inną nazwą; jeśli nie — to luka do zbudowania |
| Sklep bez zamówień w oknie | API nie zwróciło zamówień — jeśli sklep sprzedawał, integracja najpewniej ich nie przesyła | Zapytaj, czy sklep sprzedawał; sprawdź integrację sklepu w panelu |
| Dużo zamówień bez kontaktu | Kupujący nie są łączeni z kontaktami | Normalne dla klientów bez zgody; problem, gdy dotyczy kupujących ze zgodą na maile |
| „bez śledzenia e-commerce” | Mail nie ma flagi śledzenia e-commerce, więc sprzedaż z niego najpewniej nie jest przypisywana | Ustawienia wiadomości → Śledzenie; przypisywanie przychodu działa od planu Marketer (wg bloga GetResponse) |
| Wypisy > 0,5% na wysyłkę | Treść lub częstotliwość męczy odbiorców | Rzadziej, lepiej dobrany segment |
| Skargi na spam ≥ 0,3% (powyżej 0,1% — ostrzeżenie) | Google wymaga od nadawców masowych poniżej 0,3% i zaleca poniżej 0,1% | Pilne: segmentacja, łatwiejszy wypis, czyszczenie bazy |
| Kliknięcia < 0,5% | Mail praktycznie nic nie robi | Zmień ofertę/temat albo wyłącz |

Zasady:
- Progi wypisów i kliknięć to orientacyjne progi praktyczne, nie normy — mów o nich jako o sygnale do sprawdzenia.
- Oceniaj maile po kliknięciach i sprzedaży, nie po otwarciach (otwarcia zawyżają programy pocztowe, nawet po odsianiu botów).
- Nie podawaj liczb, których nie ma w raporcie. Czego API nie widzi — powiedz, że trzeba sprawdzić w panelu.
- Nie proponuj zmian na koncie przez API — ten skill jest tylko do odczytu.

## Ograniczenia API GetResponse (sprawdzone)

- API nie pokazuje warunków, opóźnień ani rozgałęzień automatów i nie łączy maila z automatem.
- Przypisany przychód per automat jest tylko w panelu (kolumna „Przypisany przychód” na liście automatów).
- Oficjalny MCP GetResponse (`mcp.getresponse.com`) nie widzi automatów ani zamówień — dlatego ten skill używa API.
- Limity API: 30 000 zapytań na 10 minut, 80 na sekundę; skrypt robi przerwy i sam czeka po błędzie 429.
