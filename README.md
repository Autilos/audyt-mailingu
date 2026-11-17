# Audyt e-mail marketingu dla sklepów internetowych

Skill do Claude Code, który w kilka minut sprawdza e-mail marketing Twojego sklepu i mówi wprost, co nie działa.

**Teraz:** GetResponse. **W planie:** MailerLite i Klaviyo.

## Co sprawdza

- Czy masz automaty, które powinien mieć każdy sklep: powitanie, porzucony koszyk, po zakupie, drugi zakup, reaktywacja nieaktywnych klientów.
- Czy automaty naprawdę działają — czy ktoś przez nie przechodzi (częsty problem: automat „włączony”, a od miesięcy nikt do niego nie wszedł).
- Wyniki każdego maila: otwarcia i kliknięcia bez botów, wypisy, skargi na spam, odbicia.
- Jak często wysyłasz newslettery i czy nie męczysz bazy.
- Czy sklep w ogóle przesyła zamówienia do systemu mailingowego i ilu kupujących nie trafia do bazy.
- Czy maile mają włączone śledzenie e-commerce (przypisywanie sprzedaży do maila).

Wynik: raport po polsku z listą najważniejszych problemów na górze.

## Bezpieczeństwo

- **Tylko odczyt.** Skrypt wysyła wyłącznie zapytania GET — niczego nie zmienia, nie wysyła maili, nie kasuje kontaktów. Kod jest krótki i jawny: [`skills/audyt-getresponse/scripts/audyt_getresponse.py`](skills/audyt-getresponse/scripts/audyt_getresponse.py).
- **Bez danych kontaktów.** Skrypt nie pobiera adresów e-mail ani danych subskrybentów — raport ma liczby zbiorcze oraz nazwy automatów, list i tematy maili z Twojego konta.
- **Klucz zostaje u Ciebie.** Skrypt czyta klucz ze zmiennej środowiskowej na Twoim komputerze i łączy się bezpośrednio z API GetResponse.
- Klucz API GetResponse daje pełny dostęp do konta (dokumentacja nie przewiduje kluczy tylko do odczytu). Po audycie możesz go usunąć.

## Instalacja w Claude Code

```
/plugin marketplace add Autilos/audyt-mailingu
/plugin install audyt-mailingu@audyt-mailingu
```

Potem napisz: **„zrób audyt mojego GetResponse”**.

## Bez Claude Code

```bash
export GETRESPONSE_API_KEY='twój-klucz'      # GetResponse → Menu → Integracje i API → API
python3 skills/audyt-getresponse/scripts/audyt_getresponse.py --dni 90 --raport audyt.md
```

Wymaga Pythona 3.8+, bez dodatkowych pakietów.

## Autor

Wojciech Nowak — [marketingkrokpokroku.pl](https://marketingkrokpokroku.pl)
