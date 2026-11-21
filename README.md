# Audyt e-mail marketingu dla sklepów internetowych

[![Gwiazdki na GitHubie](https://img.shields.io/github/stars/Autilos/audyt-mailingu?style=social)](https://github.com/Autilos/audyt-mailingu/stargazers)

Skill do Claude Code, który w kilka minut sprawdza e-mail marketing Twojego sklepu i mówi wprost, co nie działa.

Obsługuje **GetResponse** i **MailerLite**.

## Co sprawdza

- Czy masz automaty, które powinien mieć każdy sklep: powitanie, porzucony koszyk, po zakupie, drugi zakup, reaktywacja nieaktywnych klientów.
- Czy automaty naprawdę działają — czy ktoś przez nie przechodzi (częsty problem: automat „włączony”, a od miesięcy nikt do niego nie wszedł).
- Wyniki każdego maila: kliknięcia, otwarcia, wypisy, skargi na spam, odbicia. W GetResponse otwarcia i kliknięcia są liczone bez botów (pola „ludzkie” z API). W MailerLite otwarcia są surowe (z automatycznymi otwarciami, np. Apple Mail), dlatego tam liczą się kliknięcia.
- Jak często wysyłasz newslettery i czy nie męczysz bazy.
- Czy sklep w ogóle przesyła zamówienia do systemu mailingowego i ilu kupujących nie trafia do bazy.
- Czy maile mają włączone śledzenie e-commerce (przypisywanie sprzedaży do maila).
- **Serię powitalną**: ile maili, w jakie dni, czy działa, i czy każdy mail jest sprzedażowy, wartościowy czy mieszany (ocena po słowach i elementach maila (kod, procent, ceny, przyciski) — może się pomylić; przy każdym mailu podany powód).
- **Formularze zapisu**: wyświetlenia, zapisy i konwersja każdego formularza.
- **Zdrowie bazy**: przyrost i odpływ kontaktów w okresie audytu, źródła zapisów i powody usunięć (GetResponse); stan grup — aktywni, wypisani, odbicia, spam (MailerLite).
- **Dostarczalność** (GetResponse): czy domena nadawcy jest potwierdzona i czy są ostrzeżenia DKIM albo DMARC.
- **Przychód widziany przez GetResponse** i — jeśli podasz dane sklepu — porównanie z nimi.

Wynik: raport po polsku — najpierw najważniejsze problemy, potem **rekomendacje w kolejności wykonania** (tylko do tego, co wykryto), potem szczegóły. Raport można zamienić na PDF: `python3 skills/audyt-getresponse/scripts/raport_pdf.py audyt-getresponse.md` (potrzebny Chrome, Chromium albo Edge; bez nich powstaje HTML do wydrukowania).

## Wypróbuj bez klucza

Chcesz zobaczyć raport, zanim podasz klucz API? Napisz w Claude Code **„zrób pokazowy audyt”** albo uruchom skrypt z `--pokaz` — działa bez klucza i bez internetu, na zmyślonych danych sklepu z herbatą:

```bash
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --pokaz --raport audyt-pokaz.md
python3 skills/audyt-getresponse/scripts/raport_pdf.py audyt-pokaz.md
```

Raport ma na górze adnotację „Raport pokazowy — dane zmyślone”. To samo dla MailerLite: `skills/audyt-mailerlite/scripts/audyt_mailerlite.py --pokaz`.

## Raport: PDF i plik dla asystenta AI

Po audycie dostajesz dwa pliki: **PDF** do czytania i wysłania dalej oraz **Markdown** (`.md`) z tą samą treścią i dodatkową sekcją „Dla asystenta AI” — listą problemów, zadań do odhaczenia z miejscem w panelu i tego, czego audyt nie sprawdził. Plik `.md` możesz dać swojemu asystentowi AI (Claude, ChatGPT) albo agentowi, żeby pomógł we wdrożeniu. Linki i adresy w PDF są klikalne.

## Pomoc po audycie

Zapytaj w Claude Code „jak to naprawić?”, „kto mi to wdroży?” albo „zgłoś błąd” — skill `audyt-pomoc` podzieli zadania na to, co zrobisz sam, i to, co lepiej zlecić, a przy błędzie przygotuje zgłoszenie bez danych z konta (szablon: [Issues](https://github.com/Autilos/audyt-mailingu/issues/new?template=blad.md)).

## Bezpieczeństwo

- **Tylko odczyt.** Skrypt wysyła wyłącznie zapytania GET — niczego nie zmienia, nie wysyła maili, nie kasuje kontaktów. Kod jest krótki i jawny: [GetResponse](skills/audyt-getresponse/scripts/audyt_getresponse.py), [MailerLite](skills/audyt-mailerlite/scripts/audyt_mailerlite.py).
- **Bez danych osobowych.** Skill nie pobiera danych osobowych kontaktów ani kupujących — wyłącznie statystyki, ustawienia i treść maili. W kodzie jest lista dozwolonych ścieżek API; każda inna przerywa audyt. W GetResponse zamówienia są czytane tylko z polami: numer, kwota, data, status i informacja, czy zamówienie ma przypisany kontakt (bez danych kupującego). W MailerLite zamówień audyt nie czyta wcale, bo API zwraca je z danymi kupującego.
- **Klucz zostaje u Ciebie, bez pośrednika.** Skrypt czyta klucz ze zmiennej środowiskowej na Twoim komputerze i wysyła go wyłącznie do oficjalnego API GetResponse albo MailerLite. Inne adresy i przekierowania są odrzucane, a klucz nie trafia do raportu ani do komunikatów o błędach. Jeśli masz ustawione proxy w zmiennych środowiskowych (`HTTPS_PROXY`), połączenie idzie przez nie, nadal szyfrowane.
- **Wyniki zostają na Twoim dysku.** Raport to plik `audyt-*.md` w bieżącym katalogu. W Claude Code jego treść (nazwy automatów, list, tematy maili, liczby) trafia do rozmowy, tak jak każdy plik, który Claude czyta.
- **Klucz traktuj jak hasło.** Nie udało się potwierdzić, że GetResponse lub MailerLite oferują klucze tylko do odczytu, więc zakładaj, że klucz daje pełny dostęp do konta. Ten skill go nie wykorzystuje do zmian, ale po audycie klucz usuń:
  - GetResponse: Menu → Integracje i API → API → usuń klucz,
  - MailerLite: Integracje → MailerLite API → usuń token.
- Zgłaszanie problemów z bezpieczeństwem: [SECURITY.md](SECURITY.md).

## Instalacja w Claude Code

```
/plugin marketplace add Autilos/audyt-mailingu
/plugin install audyt-mailingu@audyt-mailingu
```

Potem napisz: **„zainstaluj audyt”** albo **„zrób audyt mailingu”** — skill poprowadzi krok po kroku: który system, skąd wziąć klucz, jak go ustawić bez wklejania do czatu (Mac/Linux i Windows), test połączenia, pierwszy przebieg i przypomnienie o usunięciu klucza.

## Bez Claude Code

```bash
# GetResponse
read -rs GETRESPONSE_API_KEY && export GETRESPONSE_API_KEY   # wklej klucz, Enter (GetResponse → Menu → Integracje i API → API)
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --dni 90 --raport audyt-getresponse.md

# MailerLite
read -rs MAILERLITE_API_KEY && export MAILERLITE_API_KEY     # wklej token, Enter (MailerLite → Integracje → MailerLite API)
python3 skills/audyt-mailerlite/scripts/audyt_mailerlite.py --dni 90 --raport audyt-mailerlite.md
```

Wymaga Pythona 3.8+, bez dodatkowych pakietów. Test połączenia (jedno zapytanie): `--test-polaczenia`. Porównanie z danymi sklepu (GetResponse): `--przychod-sklepu 12345 --zamowienia-sklepu 67`.

Windows (PowerShell 7):

```powershell
$env:GETRESPONSE_API_KEY = Read-Host -MaskInput "Klucz API"
python skills/audyt-getresponse/scripts/audyt_getresponse.py --dni 90 --raport audyt-getresponse.md
```

Testy: `python3 -m unittest discover -s tests -v`.

## Dla współtwórców

Przed zmianą kodu, raportu albo SKILL.md przeczytaj [docs/CONCEPTS.md](docs/CONCEPTS.md) — słownik pojęć (co znaczy „automat działa”, „zamówienie bez kontaktu”, „otwarcia bez botów”, lista dozwolonych ścieżek API). Testy: `python3 -m unittest discover -s tests -v`.

## Autor

Wojciech Nowak — [marketingkrokpokroku.pl](https://marketingkrokpokroku.pl). Zmiany: [CHANGELOG.md](CHANGELOG.md).

## Przydało się?

Zostaw [gwiazdkę na GitHubie](https://github.com/Autilos/audyt-mailingu) (przycisk Star) albo krótką [opinię](https://github.com/Autilos/audyt-mailingu/discussions/3) — bez danych z konta.

## Chcesz pełny audyt albo wdrożenie poprawek?

To podstawowy audyt. Chcesz pełny audyt (z ręcznym przejściem automatów, ścieżki zakupu i sprzedaży z maili) albo wdrożenie poprawek? Napisz do mnie przez [formularz](https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=github#kontakt) albo na wnowak@autilo.eu (Wojciech Nowak). Więcej o narzędziu: [marketingkrokpokroku.pl/audyt-mailingu](https://marketingkrokpokroku.pl/audyt-mailingu/).
