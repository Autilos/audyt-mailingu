#!/usr/bin/env python3
"""Raport audytu .md → PDF (kolory bordo jak na stronie audytu).

Bez dodatkowych pakietów: zamienia Markdown na HTML własnym, prostym konwerterem i drukuje go do PDF
przeglądarką Chrome / Chromium / Edge w trybie bez okna (osobny, tymczasowy profil — nie dotyka Twojego).
Jeśli przeglądarki nie ma, zostawia plik HTML: otwórz go i wybierz Drukuj → Zapisz jako PDF.

Użycie:
  python3 raport_pdf.py audyt-getresponse.md            # → audyt-getresponse.pdf
  python3 raport_pdf.py raport.md --pdf raport.pdf --html raport.html
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

STOPKA_HTML = 'Audyt e-mail marketingu · więcej o narzędziu: <a href="https://marketingkrokpokroku.pl/audyt-mailingu/">marketingkrokpokroku.pl/audyt-mailingu</a>'

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: #24140f; font-size: 10.5pt; line-height: 1.45; margin: 0; }
.naglowek { background: #2e070b; color: #f3ead8; padding: 14px 18px; border-bottom: 3px solid #c8102e; margin-bottom: 18px; }
.naglowek .marka { color: #d7bb79; font-size: 9pt; letter-spacing: .08em; text-transform: uppercase; }
.naglowek h1 { margin: 4px 0 0; font-size: 17pt; color: #f3ead8; }
h1 { color: #4a0a12; font-size: 16pt; }
h2 { color: #4a0a12; font-size: 13pt; border-bottom: 2px solid #d7bb79; padding-bottom: 3px; margin-top: 22px; page-break-after: avoid; }
h3, h4 { color: #4a0a12; font-size: 11pt; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #ece2cc; color: #4a0a12; text-align: left; }
th, td { border-bottom: 1px solid #dccfb3; padding: 4px 6px; vertical-align: top; }
code { background: #f3ead8; padding: 0 3px; border-radius: 3px; font-size: 9pt; }
strong { color: #1c0003; }
ol li, ul li { margin: 3px 0; }
a { color: #8a1020; }
.stopka { margin-top: 26px; text-align: center; font-size: 8.5pt; color: #6e2028; border-top: 2px solid #d7bb79; padding-top: 6px; page-break-inside: avoid; }
"""


RE_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
RE_URL = re.compile(r"https?://[^\s<>()\[\]„”\"']+[^\s<>()\[\]„”\"'.,;:!?)]")
RE_MAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")


def inline(t):
    """Markdown w linii → HTML. Wszystkie adresy WWW i e-mail stają się klikalnymi linkami (także w PDF)."""
    schowek = []

    def odloz(fragment):
        schowek.append(fragment)
        return f"\x00{len(schowek) - 1}\x00"

    t = RE_MD_LINK.sub(lambda m: odloz(f'<a href="{html.escape(m.group(2))}">{html.escape(m.group(1), quote=False)}</a>'), t)
    t = RE_URL.sub(lambda m: odloz(f'<a href="{html.escape(m.group(0))}">{html.escape(m.group(0), quote=False)}</a>'), t)
    t = RE_MAIL.sub(lambda m: odloz(f'<a href="mailto:{m.group(0)}">{m.group(0)}</a>'), t)
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])_(.+?)_(?![\w*])", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: schowek[int(m.group(1))], t)


def bez_sekcji_dla_ai(md):
    """Sekcja „Dla asystenta AI” jest dla pliku .md (do wklejenia asystentowi) — w PDF ją pomijamy."""
    return re.sub(r"(?ms)^## Dla asystenta AI\n.*?(?=^## |^---\s*$|\Z)", "", md)


def md_na_html(md):
    """Prosty konwerter: nagłówki, akapity, listy (- i 1.), tabele, pogrubienia, kod w linii."""
    wyj, lista, akapit = [], None, []
    linie = md.splitlines()

    def zamknij():
        nonlocal lista, akapit
        if akapit:
            wyj.append("<p>" + " ".join(inline(x) for x in akapit) + "</p>")
            akapit = []
        if lista:
            wyj.append(f"</{lista}>")
            lista = None

    i = 0
    while i < len(linie):
        l = linie[i].rstrip()
        if not l.strip():
            zamknij(); i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)$", l)
        if m:
            zamknij()
            n = len(m.group(1))
            wyj.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); i += 1; continue
        if l.lstrip().startswith("|") and i + 1 < len(linie) and re.match(r"^\s*\|[\s:|-]+\|\s*$", linie[i + 1]):
            zamknij()
            komorki = lambda x: [c.strip() for c in x.strip().strip("|").split("|")]
            wyj.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in komorki(l)) + "</tr></thead><tbody>")
            i += 2
            while i < len(linie) and linie[i].lstrip().startswith("|"):
                wyj.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in komorki(linie[i])) + "</tr>")
                i += 1
            wyj.append("</tbody></table>"); continue
        m = re.match(r"^\s*(-|\d+\.)\s+(.*)$", l)
        if m:
            if akapit:
                wyj.append("<p>" + " ".join(inline(x) for x in akapit) + "</p>"); akapit = []
            typ = "ul" if m.group(1) == "-" else "ol"
            if lista != typ:
                if lista:
                    wyj.append(f"</{lista}>")
                start = "" if typ == "ul" or m.group(1) == "1." else f' start="{m.group(1)[:-1]}"'
                wyj.append(f"<{typ}{start}>"); lista = typ
            wyj.append(f"<li>{inline(m.group(2))}</li>"); i += 1; continue
        if lista and linie[i].startswith("   "):
            wyj[-1] = wyj[-1][:-5] + " " + inline(l.strip()) + "</li>"; i += 1; continue
        if lista:
            wyj.append(f"</{lista}>"); lista = None
        akapit.append(l.strip()); i += 1
    zamknij()
    return "\n".join(wyj)


def dokument(md):
    md = bez_sekcji_dla_ai(md)
    tytul = next((re.sub(r"^#\s+", "", x) for x in md.splitlines() if x.startswith("# ")), "Audyt e-mail marketingu")
    tresc = md_na_html("\n".join(x for x in md.splitlines() if x.strip() != f"# {tytul}"))
    return (f"<!doctype html><html lang=\"pl\"><head><meta charset=\"utf-8\"><title>{html.escape(tytul)}</title>"
            f"<style>{CSS}</style></head><body>"
            f"<div class=\"naglowek\"><div class=\"marka\">Audyt e-mail marketingu</div><h1>{inline(tytul)}</h1></div>"
            f"{tresc}<div class=\"stopka\">{STOPKA_HTML}</div></body></html>")


def przegladarka():
    kandydaci = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    kandydaci += [shutil.which(x) for x in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")]
    return next((k for k in kandydaci if k and os.path.exists(k)), None)


def main():
    ap = argparse.ArgumentParser(description="Raport audytu .md → PDF")
    ap.add_argument("md")
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--html", default=None, help="opcjonalnie: zapisz też HTML")
    a = ap.parse_args()
    with open(a.md, encoding="utf-8") as plik:
        h = dokument(plik.read())
    baza = os.path.splitext(a.md)[0]
    pdf = os.path.abspath(a.pdf or baza + ".pdf")
    sciezka_html = os.path.abspath(a.html or baza + ".html")
    with open(sciezka_html, "w", encoding="utf-8") as plik:
        plik.write(h)
    przeg = przegladarka()
    if not przeg:
        print(f"Nie znalazłem Chrome, Chromium ani Edge. Zapisałem HTML: {sciezka_html} — otwórz go i wybierz Drukuj → Zapisz jako PDF.")
        return
    with tempfile.TemporaryDirectory() as profil:
        cmd = [przeg, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profil}",
               "--no-pdf-header-footer", f"--print-to-pdf={pdf}", "file://" + sciezka_html]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not os.path.exists(pdf):
        print(f"Przeglądarka nie zapisała PDF (kod {r.returncode}). HTML jest tutaj: {sciezka_html} — otwórz i wydrukuj do PDF.")
        sys.exit(1)
    if not a.html:
        os.remove(sciezka_html)
    print(f"PDF: {pdf}")


if __name__ == "__main__":
    main()
