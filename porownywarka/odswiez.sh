#!/bin/bash
# Odświeżenie liczb porównywarki newsletterów: generuje JSON z danych obserwacji i wgrywa go na serwer WP.
# Strona czyta plik przy każdym wyświetleniu — po wgraniu wystarczy wyczyścić cache strony.
# Wymaga zmiennych (nie trzymamy ich w publicznym repo):
#   MKPK_SSH      alias hosta SSH z WordPressem MKpK
#   MKPK_WP       katalog instalacji WordPressa na serwerze
#   NEWSLETTERY   katalog danych obserwacji (domyślnie ~/Obsidian/Zasoby/Newslettery-obserwacja)
set -euo pipefail
: "${MKPK_SSH:?ustaw MKPK_SSH}"; : "${MKPK_WP:?ustaw MKPK_WP}"
ZRODLO="${NEWSLETTERY:-$HOME/Obsidian/Zasoby/Newslettery-obserwacja}"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
python3 -I "$(dirname "$0")/generuj_dane.py" --zrodlo "$ZRODLO" --wyjscie "$TMP/dane.json"
CEL="$MKPK_WP/wp-content/uploads/mkpk-porownywarka"
ssh "$MKPK_SSH" "mkdir -p '$CEL'"
scp -q "$TMP/dane.json" "$MKPK_SSH:$CEL/dane.json.nowy"
# Podmiana dopiero po sprawdzeniu, że plik na serwerze jest poprawnym JSON-em z branżami.
ssh "$MKPK_SSH" "php -r '\$d=json_decode(file_get_contents(\"$CEL/dane.json.nowy\"),true); exit(is_array(\$d)&&!empty(\$d[\"branze\"])?0:1);' && mv '$CEL/dane.json.nowy' '$CEL/dane.json' && chown --reference='$MKPK_WP/wp-content/uploads' '$CEL/dane.json' && cd '$MKPK_WP' && (wp --allow-root rocket clean --confirm >/dev/null 2>&1 || true)"
echo "Wgrano. Sprawdź stronę /porownywarka-newsletterow/ (zrzut telefon + komputer)."
