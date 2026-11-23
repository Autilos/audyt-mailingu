# Bezpieczeństwo

Najczęstsze pytania prostym językiem: [docs/FAQ-bezpieczenstwo.md](docs/FAQ-bezpieczenstwo.md). Chcesz, żeby nic z konta nie trafiło do AI? [Tryb bez AI](README.md#tryb-bez-ai).

## Co robi i czego nie robi ten skill

- Wysyła wyłącznie zapytania odczytu (GET) do oficjalnego API GetResponse (`api.getresponse.com`, dla GetResponse MAX `api3.getresponse360.pl` / `.com`) albo MailerLite (`connect.mailerlite.com`).
- Odrzuca inne adresy i przekierowania, żeby klucz nie trafił pod obcy serwer.
- Nie pobiera adresów e-mail ani danych subskrybentów i kupujących. Z każdej odpowiedzi API od razu zostają tylko pola potrzebne audytowi, a adresy e-mail, telefony i numery IP w nazwach list czy tematach są ukrywane. Nie ma telemetrii ani zależności spoza biblioteki standardowej Pythona.
- Przy błędzie API nie wypisuje treści odpowiedzi. PDF powstaje bez pobierania czegokolwiek z sieci.
- Nie zapisuje klucza nigdzie. Raport zostaje lokalnie w pliku `audyt-*.md`.
- Klucze GetResponse i MailerLite dają pełny dostęp do konta (panele nie mają kluczy tylko do odczytu) — używaj osobnego klucza do audytu i usuń go zaraz po nim.
- Dowód, który możesz uruchomić sam: `python3 tests/test_kanarek.py -v` (opis w [README](README.md#jak-samemu-sprawdzić)).
- Przegląd wszystkich dróg wycieku: [docs/BEZPIECZENSTWO-przeglad.md](docs/BEZPIECZENSTWO-przeglad.md).

## Jak zgłosić problem z bezpieczeństwem

**Nie zakładaj publicznego zgłoszenia (Issue) i nigdy nie wklejaj w nim swojego klucza API ani danych z konta.**

1. **Prywatne zgłoszenie na GitHubie (zalecane):** w tym repozytorium zakładka **Security → Report a vulnerability** ([bezpośredni link](https://github.com/Autilos/audyt-mailingu/security/advisories/new)). Zgłoszenie widzi tylko autor.
2. **Bez konta na GitHubie:** formularz kontaktowy na stronie narzędzia — [marketingkrokpokroku.pl/audyt-mailingu/#kontakt](https://marketingkrokpokroku.pl/audyt-mailingu/#kontakt). Napisz w temacie „Bezpieczeństwo”, a w treści tylko opis problemu; szczegóły prześlemy sobie bezpieczną drogą.

Co warto podać: wersję (plik `CHANGELOG.md` albo `.claude-plugin/plugin.json`), co zrobiłeś krok po kroku, co się stało i czego się spodziewałeś. Zamiast prawdziwych danych użyj zmyślonych (np. `kanarek@example.com`).

**Czas odpowiedzi:** to projekt jednej osoby, utrzymywany po godzinach. Każde zgłoszenie przeczytamy i odpowiemy, gdy tylko będzie to możliwe — nie obiecujemy konkretnego terminu. Poprawkę opiszemy w `CHANGELOG.md`, a zgłaszającego — jeśli zechce — wymienimy z nazwy.

## Jeśli Twój klucz mógł wyciec

Usuń go od razu w panelu (GetResponse: Menu → Integracje i API → API; MailerLite: Integracje → MailerLite API) i wygeneruj nowy. Usuń też plik z kluczem z komputera: `rm ~/.config/audyt-mailingu/*.key`.
