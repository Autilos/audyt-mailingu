#!/bin/bash
# Odświeżenie liczb porównywarki newsletterów — bez interakcji (do automatu raz dziennie).
# 1) generuje JSON z aktualnych danych obserwacji (podwójne potwierdzenie liczy monitor.py z katalogu danych),
# 2) wgrywa go na serwer WP i czyści cache strony,
# 3) sprawdza żywą stronę bez logowania (HTTP 200 + liczba z pliku na stronie),
# 4) dopiero wtedy zapisuje pomiar do historii i linijkę do dziennika odświeżeń.
# Wymaga zmiennych (nie trzymamy ich w publicznym repo; mogą być w ~/.config/mkpk-porownywarka.env):
#   MKPK_SSH      alias hosta SSH z WordPressem MKpK
#   MKPK_WP       katalog instalacji WordPressa na serwerze
#   NEWSLETTERY   katalog danych obserwacji (domyślnie ~/Obsidian/Zasoby/Newslettery-obserwacja)
#   MKPK_URL      adres strony (domyślnie https://marketingkrokpokroku.pl/porownywarka-newsletterow/)
set -euo pipefail
KONFIG="${MKPK_KONFIG:-$HOME/.config/mkpk-porownywarka.env}"
# shellcheck disable=SC1090
[ -f "$KONFIG" ] && . "$KONFIG"
: "${MKPK_SSH:?ustaw MKPK_SSH}"; : "${MKPK_WP:?ustaw MKPK_WP}"
ZRODLO="${NEWSLETTERY:-$HOME/Obsidian/Zasoby/Newslettery-obserwacja}"
URL="${MKPK_URL:-https://marketingkrokpokroku.pl/porownywarka-newsletterow/}"
HISTORIA="$ZRODLO/porownywarka-pomiary.json"
DZIENNIK="$ZRODLO/porownywarka-odswiezenia.log"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 "$MKPK_SSH")
START=$(date +%s)
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Historia na kopii — oryginał podmieniamy dopiero, gdy strona na żywo pokazuje nowe liczby.
[ -f "$HISTORIA" ] && cp "$HISTORIA" "$TMP/pomiary.json"
python3 -I "$(dirname "$0")/generuj_dane.py" --zrodlo "$ZRODLO" --wyjscie "$TMP/dane.json" --historia "$TMP/pomiary.json"

CEL="$MKPK_WP/wp-content/uploads/mkpk-porownywarka"
"${SSH[@]}" "mkdir -p '$CEL'"
scp -q -o BatchMode=yes -o ConnectTimeout=20 "$TMP/dane.json" "$MKPK_SSH:$CEL/dane.json.nowy"
# Podmiana dopiero po sprawdzeniu, że plik na serwerze jest poprawnym JSON-em z branżami.
"${SSH[@]}" "php -r '\$d=json_decode(file_get_contents(\"$CEL/dane.json.nowy\"),true); exit(is_array(\$d)&&!empty(\$d[\"branze\"])?0:1);' && mv '$CEL/dane.json.nowy' '$CEL/dane.json' && chown --reference='$MKPK_WP/wp-content/uploads' '$CEL/dane.json' "
# Cache WP Rocket tej strony (wp-cli nie ma komendy „rocket” — czyścimy funkcją wtyczki). Brak funkcji = błąd.
WYCZYSZCZONO=$("${SSH[@]}" "cd '$MKPK_WP' && wp --allow-root eval 'if (!function_exists(\"rocket_clean_post\")) { echo \"brak\"; return; } \$id = url_to_postid(\"$URL\"); if (!\$id) { echo \"brak-strony\"; return; } rocket_clean_post(\$id); echo \"ok\";' 2>/dev/null" || true)
case "$WYCZYSZCZONO" in *ok) ;; *) echo "BŁĄD: nie wyczyściłem cache strony ($WYCZYSZCZONO)" >&2; exit 4 ;; esac

# Sprawdzenie żywej strony bez logowania: 200 i „x z y” podwójnego potwierdzenia z właśnie wgranego pliku.
OCZEKIWANE=$(python3 -I -c 'import json,sys; p=json.load(open(sys.argv[1]))["podwojne"]; print("%d%%|%d z %d" % (p["proc"], p["z_potwierdzeniem"], p["sklepy"]))' "$TMP/dane.json")
PROC="${OCZEKIWANE%%|*}"; XZY="${OCZEKIWANE#*|}"
# Bez parametrów w adresie — tak jak wchodzi czytelnik (parametr omija cache i zakryłby starą wersję).
KOD=$(curl -s -o "$TMP/strona.html" -w '%{http_code}' "$URL")
if [ "$KOD" != "200" ]; then echo "BŁĄD: strona zwróciła HTTP $KOD" >&2; exit 2; fi
if ! grep -q "<b>$PROC</b>" "$TMP/strona.html" || ! grep -q "sklepów (${XZY})" "$TMP/strona.html"; then
  echo "BŁĄD: na stronie nie ma liczb z pliku ($PROC, $XZY) — sprawdź cache i szablon." >&2; exit 3
fi

cp "$TMP/pomiary.json" "$HISTORIA"
CZAS=$(( $(date +%s) - START ))
LINIA="$(date '+%Y-%m-%d %H:%M') ok: podwójne potwierdzenie $XZY ($PROC), HTTP $KOD, ${CZAS} s"
echo "$LINIA" >> "$DZIENNIK"
echo "$LINIA"
