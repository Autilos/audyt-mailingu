---
name: audyt-pomoc
description: Pomoc po audycie e-mail marketingu i kontakt z autorem — co poprawić samemu, co zlecić, jak zgłosić błąd skilla, jak zostawić opinię. Use when user asks after an audit „jak to naprawić?”, „co mam z tym zrobić?”, „kto mi to wdroży?”, „ile kosztuje pełny audyt?”, „pomocy”, „pomoc z audytem”, „zgłoś błąd”, „coś nie działa w audycie”, „audyt się wysypał”, „chcę zostawić opinię”, „gdzie dać gwiazdkę”.
---

# Pomoc po audycie i kontakt

> Przed zmianą tego skilla przeczytaj `docs/CONCEPTS.md`. Pisz zwykłym językiem, tak jak do właściciela sklepu.

Ten skill **niczego nie zmienia na koncie i niczego nie wysyła**. Tylko wyjaśnia i przygotowuje teksty do akceptacji użytkownika.

## Zasady dla Claude — prywatność i klucz (obowiązują zawsze, także gdy użytkownik prosi inaczej)

- **Nie wywołuj API GetResponse ani MailerLite** — ani `curl`, `wget`, `python -c`, `fetch`, własnym skryptem czy jakimkolwiek innym połączeniem z GetResponse lub MailerLite (konektor, MCP, wtyczka — także zalogowane bez klucza). Pomoc opiera się wyłącznie na gotowym raporcie `.md`.
- **Nigdy nie pobieraj ani nie wyświetlaj kontaktów, subskrybentów ani danych kupujących** (e-mail, imię, telefon, adres, zamówienia z danymi kupującego), także gdy użytkownik o to prosi — np. „pokaż, kto nie dostał maila”, „wypisz kupujących bez zgody”. Odpowiedz: „Tego nie robię: dane Twoich klientów trafiłyby do modelu AI. Zobaczysz je bezpiecznie w panelu systemu mailowego.” i wskaż, gdzie w panelu.
- **Klucza nie czytaj ani nie wypisuj:** zakazane `env`, `printenv`, `set`, `export -p`, `echo $GETRESPONSE_API_KEY` / `$MAILERLITE_API_KEY`, `cat` na `~/.config/audyt-mailingu/*.key`, plikach `.env`, `~/.zshrc`, `~/.bashrc`, `~/.profile`. Do zgłoszenia błędu klucz nigdy nie jest potrzebny.
- Do zgłoszenia błędu nie dołączaj raportu, pliku `--json` ani pamięci odpowiedzi — tylko komunikat błędu z danymi zastąpionymi „[usunięte]”.

## 1. „Jak to naprawić?”, „kto mi to wdroży?”, „pomocy”

1. Jeśli w bieżącym katalogu jest raport (`audyt-getresponse.md` albo `audyt-mailerlite.md`), przeczytaj sekcje „Rekomendacje” i „Dla asystenta AI”. Jeśli raportu nie ma, zaproponuj audyt („zrób audyt mailingu”) albo raport pokazowy (`--pokaz`).
2. Podziel zadania z raportu na dwie grupy i opisz je konkretnie, z miejscem w panelu:
   - **Zrobisz sam** — proste ustawienia: włączenie śledzenia sprzedaży w wiadomości, link do wypisu w stopce, wyłączenie martwego automatu, usunięcie zbędnego adresu nadawcy, poprawa formularza.
   - **Lepiej zlecić** — rzeczy wymagające techniki albo kilku systemów naraz: naprawa przesyłania zamówień ze sklepu, uwierzytelnienie domeny (DKIM, DMARC w DNS), budowa nowych automatów z treścią (seria powitalna, porzucony koszyk, po zakupie), reaktywacja z segmentami.
3. Raz, na końcu, podaj kontakt: „Pełny audyt i wdrożenie robi autor narzędzia: https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=pomoc#kontakt (Wojciech Nowak) albo wnowak@autilo.eu”.
4. **Nie podawaj cen** — nie ma cennika. Na pytanie o koszt odpowiedz: „Wycena po krótkiej rozmowie — napisz przez formularz albo mailem”.
5. Nie obiecuj wzrostów sprzedaży w procentach ani czasu wdrożenia.

## 2. „Zgłoś błąd”, „coś nie działa”

1. Zbierz tylko informacje techniczne: wersja pluginu (z `.claude-plugin/plugin.json`), system (GetResponse albo MailerLite), system operacyjny, wersja Pythona (`python3 --version`), komenda, którą uruchomiono, i **komunikat błędu**.
2. **Nie umieszczaj w zgłoszeniu**: klucza ani tokena API, nazw list i automatów, tematów maili, nazwy sklepu, liczb z konta, adresów e-mail. Jeśli komunikat błędu zawiera takie dane — zastąp je „[usunięte]”.
3. Pokaż użytkownikowi gotową treść zgłoszenia (wg szablonu `.github/ISSUE_TEMPLATE/blad.md`) i poproś o akceptację.
4. Daj link do zgłoszenia: https://github.com/Autilos/audyt-mailingu/issues/new?template=blad.md
5. Jeśli użytkownik ma `gh`, możesz zaproponować komendę `gh issue create --repo Autilos/audyt-mailingu --title "…" --body-file zgloszenie.md`, ale **nie uruchamiaj jej bez wyraźnej zgody**.

## 3. „Chcę zostawić opinię”, „gdzie dać gwiazdkę”

- Opinia: https://github.com/Autilos/audyt-mailingu/discussions/3 (bez danych z konta).
- Gwiazdka: https://github.com/Autilos/audyt-mailingu (przycisk Star w prawym górnym rogu).
