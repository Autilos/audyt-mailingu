# Audyt e-mail marketingu dla sklepów internetowych

English: [README.en.md](README.en.md)

[![Gwiazdki na GitHubie](https://img.shields.io/github/stars/Autilos/audyt-mailingu?style=social)](https://github.com/Autilos/audyt-mailingu/stargazers)

Skill do Claude Code, który w kilka minut sprawdza e-mail marketing Twojego sklepu i mówi wprost, co nie działa.

Obsługuje **GetResponse** i **MailerLite**.

## Co sprawdza

- Czy masz automaty, które powinien mieć każdy sklep: powitanie, porzucony koszyk, po zakupie, drugi zakup, reaktywacja nieaktywnych klientów.
- Czy automaty naprawdę działają — czy ktoś przez nie przechodzi (częsty problem: automat „włączony”, a od miesięcy nikt do niego nie wszedł).
- Wyniki każdego maila: kliknięcia, otwarcia, wypisy, skargi na spam, odbicia. W GetResponse otwarcia i kliknięcia są liczone bez botów (pola „ludzkie” z API). W MailerLite otwarcia są surowe (z automatycznymi otwarciami, np. Apple Mail), dlatego tam liczą się kliknięcia.
- Jak często wysyłasz newslettery i czy nie męczysz bazy.
- Czy sklep w ogóle przesyła zamówienia do systemu mailingowego i ilu kupujących nie trafia do bazy (GetResponse). W MailerLite: ile zamówień i jaki przychód sklep przesłał w okresie audytu i ile z tego przypisano do maili — osobno kampanie i automaty — z raportu zbiorczego sklepu, bez pojedynczych zamówień.
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

Nie chcesz, żeby cokolwiek z Twojego konta trafiło do AI? Uruchom skrypt sam w terminalu — [tryb bez AI](#tryb-bez-ai). Najczęstsze pytania: [FAQ o bezpieczeństwie](docs/FAQ-bezpieczenstwo.md).

**Adresy i dane Twoich subskrybentów oraz kupujących nie trafiają do AI.** Audyt czyta tylko statystyki, ustawienia i treść Twoich maili — nigdy listy kontaktów.

- **Tylko odczyt.** Skrypt wysyła wyłącznie zapytania odczytu — niczego nie zmienia, nie wysyła maili, nie kasuje kontaktów. Kod jest krótki i jawny: [GetResponse](skills/audyt-getresponse/scripts/audyt_getresponse.py), [MailerLite](skills/audyt-mailerlite/scripts/audyt_mailerlite.py).
- **Bez danych osobowych.** W kodzie jest spis miejsc w API, które skrypt może odczytać; każde inne przerywa audyt. Z każdej odpowiedzi od razu zostają tylko potrzebne liczby i nazwy, a reszta jest odrzucana, zanim cokolwiek trafi na dysk czy do rozmowy. Jeśli w nazwie listy albo temacie maila jest adres e-mail, numer telefonu albo numer IP, skrypt go ukrywa, zanim zapisze cokolwiek na dysk.
- **Zamówienia.** W GetResponse audyt czyta zamówienia tylko z polami: numer, kwota, data, status i informacja, czy zamówienie ma przypisany kontakt — bez danych kupującego. W MailerLite pojedynczych zamówień audyt **nie czyta wcale**: API MailerLite zwraca zamówienie zawsze w całości, razem z danymi kupującego (e-mail, imię, nazwisko, telefon), i nie pozwala wybrać samych pól ([dokumentacja](https://developers.mailerlite.com/ecommerce/orders)). Liczbę zamówień i przychód audyt bierze z raportu zbiorczego sklepu, w którym są same liczby ([dokumentacja](https://developers.mailerlite.com/ecommerce/shops)).
- **Claude ma zakazy wpisane w skill.** Nie wywołuje API GetResponse ani MailerLite poza skryptem audytu, nie czyta klucza (np. komendami pokazującymi zmienne środowiskowe czy pliki konfiguracyjne) i nie pobiera kontaktów ani danych kupujących — nawet jeśli go o to poprosisz. Wtedy wyjaśni, że ten audyt tego nie robi, bo dane klientów trafiłyby do modelu AI.
- **Klucz daje pełny dostęp do konta.** GetResponse i MailerLite nie mają w panelu kluczy „tylko do odczytu” — każdy klucz pozwala na wszystko, co Ty. „Tylko odczyt” dotyczy skryptu audytu, nie klucza. Dlatego:
  - utwórz **osobny klucz tylko do audytu** (np. nazwij go „audyt”) — GetResponse: Menu → Integracje i API → API; MailerLite: Integracje → MailerLite API → Wygeneruj nowy token (tu możesz też ograniczyć token do swojego adresu IP),
  - w GetResponse najbezpieczniej: utwórz w panelu **osobnego użytkownika z ograniczonym dostępem** ([zarządzanie zespołem](https://www.getresponse.pl/pomoc/zarzadzanie-zespolem)) i wygeneruj klucz z jego konta — taki klucz może tylko to, co ten użytkownik. GetResponse nie oferuje kluczy tylko do odczytu, a skrypt audytu i tak wysyła wyłącznie zapytania odczytu (GET),
  - **usuń go zaraz po audycie** w tym samym miejscu, a z komputera usuń plik: `rm ~/.config/audyt-mailingu/*.key`,
  - nigdy nie wklejaj klucza do czatu.
- **Klucz idzie tylko do GetResponse albo MailerLite.** Skrypt wysyła go wyłącznie do oficjalnego adresu API, szyfrowanym połączeniem. Inne adresy i przekierowania są odrzucane, a klucz nie trafia do raportu ani do komunikatów o błędach. Jeśli masz ustawione proxy w zmiennych środowiskowych (`HTTPS_PROXY`), połączenie idzie przez nie, nadal szyfrowane.
- **Wyniki zostają na Twoim dysku.** Raport to plik `audyt-*.md` (i PDF) w bieżącym katalogu. W Claude Code jego treść (nazwy automatów, list, tematy maili, liczby) trafia do rozmowy, tak jak każdy plik, który Claude czyta — dlatego raport nie zawiera danych klientów. PDF powstaje bez pobierania czegokolwiek z internetu.
- **Czego nie da się wykluczyć technicznie:** klucz z pełnym dostępem leży w zmiennej środowiskowej albo pliku na Twoim komputerze, więc każdy program, który tam uruchomisz (także asystent AI z innymi poleceniami), technicznie mógłby go odczytać. Skill zabrania tego Claude, ale najpewniejszą ochroną jest osobny klucz usunięty zaraz po audycie.
- Pełny przegląd, co sprawdziliśmy: [docs/BEZPIECZENSTWO-przeglad.md](docs/BEZPIECZENSTWO-przeglad.md). Zgłaszanie problemów: [SECURITY.md](SECURITY.md).

### Jak samemu sprawdzić

Nie musisz nam wierzyć na słowo. W repozytorium jest test „kanarek”: udaje API GetResponse i MailerLite dla każdego miejsca, które skrypt może odczytać, i w każde pole odpowiedzi wpisuje zmyślone dane osobowe (np. `kanarek-17@example.com`, `+48 600 000 017`, `203.0.113.17`, „Jan Kanarek17”). Potem uruchamia pełny audyt i PDF i sprawdza, że żaden z tych adresów, telefonów i numerów IP nie pojawił się na ekranie, w raporcie, w pliku JSON, w PDF, w pliku postępu ani w pamięci na dysku. Działa bez klucza i bez internetu, w kilkanaście sekund:

```bash
python3 tests/test_kanarek.py -v
```

Na końcu test wypisuje, w których polach może przejść imię i nazwisko: tylko w nazwach i tematach, które sam wpisałeś w panelu (nazwa listy, automatu, formularza, sklepu, temat maila) — tego, że „Jan Kowalski” to osoba, a nie nazwa produktu, program nie rozpozna. Kod testu: [tests/test_kanarek.py](tests/test_kanarek.py).

## Instalacja w Claude Code

0. Zainstaluj [Claude Code](https://claude.com/claude-code) i przy pierwszym uruchomieniu zaloguj się kontem Claude: w terminalu wpisz `claude`, a potem `/login`.
1. W Claude Code wpisz:

```
/plugin marketplace add Autilos/audyt-mailingu
/plugin install audyt-mailingu@audyt-mailingu
```

2. Napisz: **„zrób audyt mailingu”** — skill poprowadzi krok po kroku: który system, skąd wziąć klucz, jak go zapisać bez wklejania do czatu i **bez zamykania Claude Code**, test połączenia, przebieg i przypomnienie o usunięciu klucza.

**Klucz bez zamykania Claude Code:** otwórz drugie okno albo kartę terminala i wklej (Mac / Linux):

```bash
mkdir -p ~/.config/audyt-mailingu && (umask 077; read -rs K && printf %s "$K" > ~/.config/audyt-mailingu/getresponse.key && echo "Klucz zapisany (${#K} znaków)"; unset K)
```

Wklej klucz (nic się nie wyświetli) i naciśnij Enter — zobaczysz „Klucz zapisany (N znaków)”. Wróć do Claude Code i napisz „gotowe”. Dla MailerLite plik nazywa się `mailerlite.key`. Po audycie usuń plik: `rm ~/.config/audyt-mailingu/getresponse.key`.

**Duże konto?** Audyt domyślnie obejmuje 30 dni (90 na prośbę), działa w tle i pokazuje postęp (plik `audyt-getresponse.postep.txt`). Jeśli zostanie przerwany, uruchomiony ponownie nie zaczyna od zera — pamięta pobrane odpowiedzi API przez 12 godzin (w katalogu tymczasowym, bez danych osobowych).

## Tryb bez AI

**Uruchom skrypt sam w terminalu. Raport PDF i MD powstaje na Twoim komputerze, a nic z konta nie trafia do żadnego modelu AI.** Claude Code nie jest wtedy potrzebny — wystarczy Python 3.8+ (bez dodatkowych pakietów) i pobrane repozytorium (przycisk **Code → Download ZIP** na GitHubie albo `git clone https://github.com/Autilos/audyt-mailingu`).

Mac / Linux, w katalogu repozytorium:

```bash
# GetResponse: klucz wklejasz po Enterze (nic się nie wyświetla, nie zostaje w historii terminala)
read -rs GETRESPONSE_API_KEY && export GETRESPONSE_API_KEY
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --raport audyt-getresponse.md
python3 skills/audyt-getresponse/scripts/raport_pdf.py audyt-getresponse.md

# MailerLite
read -rs MAILERLITE_API_KEY && export MAILERLITE_API_KEY
python3 skills/audyt-mailerlite/scripts/audyt_mailerlite.py --raport audyt-mailerlite.md
python3 skills/audyt-mailerlite/scripts/raport_pdf.py audyt-mailerlite.md
```

Windows (PowerShell 7):

```powershell
$env:GETRESPONSE_API_KEY = Read-Host -MaskInput "Klucz API"
python skills/audyt-getresponse/scripts/audyt_getresponse.py --raport audyt-getresponse.md
python skills/audyt-getresponse/scripts/raport_pdf.py audyt-getresponse.md
```

Skrypt łączy się tylko z oficjalnym API GetResponse albo MailerLite. Raport (`.md` i `.pdf`) czytasz sam. PDF wymaga Chrome, Chromium albo Edge (bez nich powstaje plik HTML do wydrukowania); przeglądarka działa niewidocznie w tle i bez internetu. Najpierw bez klucza: dodaj `--pokaz`.

Przydatne: domyślnie 30 dni, `--dni 90` dla dłuższego okresu; postęp w pliku `<raport>.postep.txt`; `--test-polaczenia` sprawdza klucz jednym zapytaniem; porównanie z danymi sklepu (GetResponse): `--przychod-sklepu 12345 --zamowienia-sklepu 67`. Po audycie usuń klucz w panelu.

Testy: `python3 -m unittest discover -s tests -v`.

## Dla współtwórców

Przed zmianą kodu, raportu albo SKILL.md przeczytaj [docs/CONCEPTS.md](docs/CONCEPTS.md) — słownik pojęć (co znaczy „automat działa”, „zamówienie bez kontaktu”, „otwarcia bez botów”, lista dozwolonych ścieżek API). Testy: `python3 -m unittest discover -s tests -v`.

## Autor

Wojciech Nowak — [marketingkrokpokroku.pl](https://marketingkrokpokroku.pl). Zmiany: [CHANGELOG.md](CHANGELOG.md).

## Przydało się?

Zostaw [gwiazdkę na GitHubie](https://github.com/Autilos/audyt-mailingu) (przycisk Star) albo krótką [opinię](https://github.com/Autilos/audyt-mailingu/discussions/3) — bez danych z konta.

## Chcesz pełny audyt albo wdrożenie poprawek?

To podstawowy audyt. Chcesz pełny audyt (z ręcznym przejściem automatów, ścieżki zakupu i sprzedaży z maili) albo wdrożenie poprawek? Napisz do mnie przez [formularz](https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=github#kontakt) albo na wnowak@autilo.eu (Wojciech Nowak). Więcej o narzędziu: [marketingkrokpokroku.pl/audyt-mailingu](https://marketingkrokpokroku.pl/audyt-mailingu/).
