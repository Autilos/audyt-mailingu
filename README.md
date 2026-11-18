# Audyt e-mail marketingu dla sklepów internetowych

Skill do Claude Code, który w kilka minut sprawdza e-mail marketing Twojego sklepu i mówi wprost, co nie działa.

Obsługuje **GetResponse** i **MailerLite**.

## Co sprawdza

- Czy masz automaty, które powinien mieć każdy sklep: powitanie, porzucony koszyk, po zakupie, drugi zakup, reaktywacja nieaktywnych klientów.
- Czy automaty naprawdę działają — czy ktoś przez nie przechodzi (częsty problem: automat „włączony”, a od miesięcy nikt do niego nie wszedł).
- Wyniki każdego maila: otwarcia i kliknięcia bez botów, wypisy, skargi na spam, odbicia.
- Jak często wysyłasz newslettery i czy nie męczysz bazy.
- Czy sklep w ogóle przesyła zamówienia do systemu mailingowego i ilu kupujących nie trafia do bazy.
- Czy maile mają włączone śledzenie e-commerce (przypisywanie sprzedaży do maila).

Wynik: raport po polsku z listą najważniejszych problemów na górze.

## Bezpieczeństwo

- **Tylko odczyt.** Skrypt wysyła wyłącznie zapytania GET — niczego nie zmienia, nie wysyła maili, nie kasuje kontaktów. Kod jest krótki i jawny: [GetResponse](skills/audyt-getresponse/scripts/audyt_getresponse.py), [MailerLite](skills/audyt-mailerlite/scripts/audyt_mailerlite.py).
- **Bez danych kontaktów.** Skrypt nie pobiera adresów e-mail ani danych subskrybentów — raport ma liczby zbiorcze oraz nazwy automatów, list i tematy maili z Twojego konta.
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

Potem napisz: **„zrób audyt mojego GetResponse”** albo **„zrób audyt mojego MailerLite”**.

## Bez Claude Code

```bash
# GetResponse
read -rs GETRESPONSE_API_KEY && export GETRESPONSE_API_KEY   # wklej klucz, Enter (GetResponse → Menu → Integracje i API → API)
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --dni 90 --raport audyt-getresponse.md

# MailerLite
read -rs MAILERLITE_API_KEY && export MAILERLITE_API_KEY     # wklej token, Enter (MailerLite → Integracje → MailerLite API)
python3 skills/audyt-mailerlite/scripts/audyt_mailerlite.py --dni 90 --raport audyt-mailerlite.md
```

Wymaga Pythona 3.8+, bez dodatkowych pakietów.

## Autor

Wojciech Nowak — [marketingkrokpokroku.pl](https://marketingkrokpokroku.pl)
