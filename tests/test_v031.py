"""Testy v0.3.1: klikalne linki w PDF, sekcja „Dla asystenta AI”, tryb pokazowy, skill pomocy, poprawka „ponown”."""
import filecmp
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR = os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts")
ML = os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts")
sys.path.insert(0, GR)
import raport_pdf  # noqa: E402
import audyt_getresponse as A  # noqa: E402

LINK = "https://marketingkrokpokroku.pl/audyt-mailingu/?zrodlo=raport#kontakt"


def uruchom(skrypt, *arg):
    with tempfile.TemporaryDirectory() as d:
        md = os.path.join(d, "r.md")
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}  # bez klucza
        wynik = subprocess.run([sys.executable, skrypt, "--pokaz", "--raport", md, *arg], capture_output=True, text=True, env=env, cwd=d, timeout=60)
        assert wynik.returncode == 0, wynik.stderr
        return open(md, encoding="utf-8").read()


class LinkiPDF(unittest.TestCase):
    def test_adresy_i_maile_sa_linkami(self):
        h = raport_pdf.inline(f"Napisz: {LINK} (Wojciech Nowak) albo wnowak@autilo.eu.")
        self.assertIn(f'<a href="{LINK}">', h)
        self.assertIn('<a href="mailto:wnowak@autilo.eu">', h)
        self.assertTrue(h.endswith("</a>."), "kropka po adresie nie wchodzi do linku")

    def test_link_markdown_i_escapowanie(self):
        h = raport_pdf.inline("[GitHub](https://github.com/x/y) <b>")
        self.assertIn('<a href="https://github.com/x/y">GitHub</a>', h)
        self.assertIn("&lt;b&gt;", h)

    def test_pdf_ma_klikalny_uri(self):
        if not raport_pdf.przegladarka():
            self.skipTest("brak Chrome/Chromium/Edge")
        try:
            import pypdf
        except ImportError:
            self.skipTest("brak pypdf")
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "r.md")
            open(md, "w", encoding="utf-8").write(f"# Test\n\nKontakt: {LINK}\n")
            sys.argv = ["x", md]
            raport_pdf.main()
            uri = [a.get_object().get("/A", {}).get("/URI") for s in pypdf.PdfReader(os.path.join(d, "r.pdf")).pages
                   for a in (s.get("/Annots") or [])]
            self.assertIn(LINK, uri)

    def test_sekcja_ai_pominieta_w_pdf(self):
        h = raport_pdf.dokument("# T\n\n## Najważniejsze\n\n1. A\n\n## Dla asystenta AI\n\n- [ ] zadanie\n\n---\n\nStopka\n")
        self.assertNotIn("Dla asystenta AI", h)
        self.assertIn("Stopka", h)


class TrybPokazowy(unittest.TestCase):
    def test_gr_bez_klucza(self):
        r = uruchom(os.path.join(GR, "audyt_getresponse.py"))
        self.assertIn("Raport pokazowy — dane zmyślone", r)
        for sekcja in ("## Rekomendacje", "## Seria powitalna", "## Baza kontaktów", "## Formularze zapisu",
                       "## Dostarczalność", "## Dla asystenta AI", "- [ ] ", LINK, "discussions/3"):
            self.assertIn(sekcja, r)

    def test_ml_bez_tokena(self):
        r = uruchom(os.path.join(ML, "audyt_mailerlite.py"))
        self.assertIn("Raport pokazowy — dane zmyślone", r)
        for sekcja in ("## Rekomendacje", "## Seria powitalna", "## Formularze zapisu", "## Dla asystenta AI", LINK):
            self.assertIn(sekcja, r)

    def test_pokaz_bez_sladow_klientow(self):
        for plik in (os.path.join(GR, "pokaz_gr.py"), os.path.join(ML, "pokaz_ml.py")):
            tekst = open(plik, encoding="utf-8").read().lower()
            self.assertIn("herbat", tekst)
            # tylko zmyślone domeny (.example) i jedna darmowa poczta do pokazania ostrzeżenia
            domeny = set(re.findall(r"@([a-z0-9.-]+\.[a-z]+)|https?://([a-z0-9.-]+)", tekst))
            for d in {x or y for x, y in domeny}:
                self.assertTrue(d.endswith(".example") or d == "gmail.com", f"{plik}: {d}")

    def test_kontakt_md(self):
        r = uruchom(os.path.join(GR, "audyt_getresponse.py"))
        self.assertIn("?zrodlo=raport-md#kontakt", r)


class Poprawki(unittest.TestCase):
    def test_witaj_ponownie_to_nie_drugi_zakup(self):
        slowa = A.LISTA_KONTROLNA[4][1]
        self.assertFalse(A.dopasuj("Witaj ponownie — ostatni dzień kodu", slowa))
        self.assertTrue(A.dopasuj("Ponowny zakup — przypomnienie", slowa))

    def test_wspolne_pliki_identyczne(self):
        for plik in ("raport_pdf.py", "rekomendacje.py", "seria_powitalna.py"):
            self.assertTrue(filecmp.cmp(os.path.join(GR, plik), os.path.join(ML, plik), shallow=False), plik)


class SkillPomocy(unittest.TestCase):
    def test_skill_i_szablon(self):
        s = open(os.path.join(KORZEN, "skills", "audyt-pomoc", "SKILL.md"), encoding="utf-8").read()
        self.assertTrue(s.startswith("---\nname: audyt-pomoc\ndescription: "))
        self.assertIn("?zrodlo=pomoc#kontakt", s)
        self.assertIn("Nie podawaj cen", s)
        self.assertIn("issues/new", s)
        self.assertTrue(os.path.exists(os.path.join(KORZEN, ".github", "ISSUE_TEMPLATE", "blad.md")))

    def test_wersja_pluginu(self):
        # wersja pluginu = najnowsza wersja w CHANGELOG.md
        with open(os.path.join(KORZEN, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            wersja = json.load(f)["version"]
        with open(os.path.join(KORZEN, "CHANGELOG.md"), encoding="utf-8") as f:
            najnowsza = re.search(r"^## (\d+\.\d+\.\d+)", f.read(), re.M).group(1)
        self.assertEqual(wersja, najnowsza)


if __name__ == "__main__":
    unittest.main()
