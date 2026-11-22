# Bezpieczeństwo

## Co robi i czego nie robi ten skill

- Wysyła wyłącznie zapytania odczytu (GET) do oficjalnego API GetResponse (`api.getresponse.com`, dla GetResponse MAX `api3.getresponse360.pl` / `.com`) albo MailerLite (`connect.mailerlite.com`).
- Odrzuca inne adresy i przekierowania, żeby klucz nie trafił pod obcy serwer.
- Nie pobiera adresów e-mail ani danych subskrybentów i kupujących. Z każdej odpowiedzi API od razu zostają tylko pola potrzebne audytowi, a adresy e-mail i telefony w nazwach list czy tematach są ukrywane. Nie ma telemetrii ani zależności spoza biblioteki standardowej Pythona.
- Przy błędzie API nie wypisuje treści odpowiedzi. PDF powstaje bez pobierania czegokolwiek z sieci.
- Nie zapisuje klucza nigdzie. Raport zostaje lokalnie w pliku `audyt-*.md`.
- Klucze GetResponse i MailerLite dają pełny dostęp do konta (panele nie mają kluczy tylko do odczytu) — używaj osobnego klucza do audytu i usuń go zaraz po nim.
- Przegląd wszystkich dróg wycieku: [docs/BEZPIECZENSTWO-przeglad.md](docs/BEZPIECZENSTWO-przeglad.md).

## Zgłaszanie problemu

Znalazłeś lukę? **Nie zakładaj publicznego zgłoszenia i nigdy nie wklejaj w nim swojego klucza API.**
Użyj prywatnego zgłoszenia na GitHubie: zakładka **Security → Report a vulnerability** w tym repozytorium.

Jeśli Twój klucz mógł wyciec, usuń go od razu w panelu (GetResponse: Menu → Integracje i API → API; MailerLite: Integracje → MailerLite API) i wygeneruj nowy.
