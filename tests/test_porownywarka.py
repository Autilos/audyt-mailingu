"""Testy generatora liczb porównywarki newsletterów — na zmyślonych danych (prawdziwe dane nie trafiają do repo)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KORZEN, "porownywarka"))

import generuj_dane as g  # noqa: E402

TAJNE = "Tajnaskrzynka"  # udaje nazwę skrzynki testowej w temacie — nie może trafić do pliku


def mail(sklep, data, temat, typ, kat, rabat=None, kody=None):
    klucz = "%s|%s|%s" % (sklep, data, temat)
    return ({"klucz": klucz, "sklep": sklep, "data": data, "temat": temat, "tresc": "treść " + TAJNE,
             "email": "news@" + sklep.lower() + ".pl", "kody": kody or []},
            {"klucz": klucz, "sklep": sklep, "kategoria": kat, "typ": typ, "rabat_max": rabat})


def zestaw():
    m = []
    for s in ("Alfa", "Beta", "Gamma"):
        m.append(mail(s, "Mon, Nov 2, 2026, 9:00 AM", "Potwierdź zapis", "potwierdzenie", "niesprzedazowy"))
        m.append(mail(s, "Mon, Nov 2, 2026, 9:05 AM", "Witaj! -10% na start", "powitalny", "sprzedazowy", "10%",
                      ["KOD"] if s != "Gamma" else []))
    # Alfa: 4 zwykłe w 14 dni = 2/tydz.; Beta: 2 = 1/tydz.; Gamma: 0
    for d in (3, 5, 10, 12):
        m.append(mail("Alfa", "Thu, Nov %d, 2026, 12:00 PM" % d, TAJNE + ", rabat -20% 🔥", "promocja", "sprzedazowy", "20%"))
    m.append(mail("Beta", "Fri, Nov 6, 2026, 5:00 PM", "Black Friday już jest", "black-friday", "sprzedazowy", "30%"))
    m.append(mail("Beta", "Sun, Nov 15, 2026, 5:00 PM", "Poradnik zimowy", "tresc/poradnik", "niesprzedazowy"))
    m.append(mail("Delta", "Sun, Nov 15, 2026, 5:00 PM", "Nowości", "promocja", "sprzedazowy"))
    sklepy = [
        {"nazwa": "Alfa", "branza": "Odzież/obuwie", "status": "zapisany", "zapis": "2026-11-02"},
        {"nazwa": "Beta", "branza": "Moda", "status": "zapisany", "zapis": "2026-11-02"},
        {"nazwa": "Gamma", "branza": "Moda", "status": "zapisany", "zapis": "2026-11-02"},
        {"nazwa": "Delta", "branza": "Kawa", "status": "zapisany", "zapis": "2026-11-14"},
        {"nazwa": "Cisza", "branza": "Moda", "status": "zapisany", "zapis": "2026-11-02"},
        {"nazwa": "Kandydat", "branza": "Moda", "status": "brak_formularza"},
    ]
    return [x for x, _ in m], {k["klucz"]: k for _, k in m}, sklepy


class Generator(unittest.TestCase):
    def setUp(self):
        maile, klas, sklepy = zestaw()
        self.d = g.policz(maile, klas, sklepy, {"alfa": "EmailLabs", "beta": "nierozpoznane"})

    def test_okres_i_liczby(self):
        self.assertEqual(self.d["okres"]["od"], "2026-11-02")
        self.assertEqual(self.d["okres"]["do"], "2026-11-15")
        self.assertEqual(self.d["okres"]["dni"], 14)
        self.assertEqual(self.d["liczby"]["maile"], 13)
        self.assertEqual(self.d["liczby"]["sklepy_wysylajace"], 4)
        self.assertEqual(self.d["liczby"]["sklepy_zapisane"], 5)

    def test_karta_mody(self):
        self.assertEqual([b["nazwa"] for b in self.d["branze"]], ["Moda"])
        b = self.d["branze"][0]
        self.assertEqual(b["sklepy"], 3)
        self.assertEqual(b["regularne"], 6)  # bez potwierdzeń i powitań
        self.assertEqual(b["tydzien"], {"mediana": "1,0", "od": "0,0", "do": "2,0", "sklepy": 3})
        self.assertEqual(b["sprzedazowe_proc"], 83)  # 5 z 6
        self.assertEqual(b["dni_top"], ["we wtorek", "w czwartek"])  # 3, 10.11 = wt; 5, 12.11 = czw
        self.assertEqual(b["tematy"]["rabat"], 67)
        self.assertEqual(b["tematy"]["emoji"], 67)
        self.assertEqual(b["tematy"]["black"], 17)
        self.assertEqual(b["potwierdzenie"], {"prosi": 3, "z_zacheta": 0, "sklepy": 3})
        self.assertEqual(b["powitanie"], {"z_rabatem": 3, "sklepy": 3})  # rabat_max wystarcza, nawet bez kodu
        self.assertEqual(b["systemy"], [{"nazwa": "EmailLabs", "sklepy": 1}])
        self.assertEqual(b["najczesciej"][0]["nazwa"], "Alfa")
        self.assertEqual(b["cisza"], 1)

    def test_mala_branza_bez_karty(self):
        self.assertEqual(self.d["inne_branze"], [{"nazwa": "Kawa", "sklepy": 1, "maile": 1}])

    def test_krotko_obserwowany_bez_czestotliwosci(self):
        # Delta zapisana 14.11 → 2 dni obserwacji, nie wchodzi do „tygodniowo”.
        self.assertEqual(self.d["liczby"]["tydzien_mediana"], "1,0")

    def test_bez_tematow_i_skrzynki(self):
        tekst = json.dumps(self.d, ensure_ascii=False)
        for zakazane in (TAJNE, "Potwierdź zapis", "Poradnik", "@", "treść"):
            self.assertNotIn(zakazane, tekst)

    def test_ciekawostki_maja_liczby(self):
        self.assertTrue(self.d["ciekawostki"])
        for c in self.d["ciekawostki"]:
            self.assertRegex(c["liczba"], r"\d")


class Pomocnicze(unittest.TestCase):
    def test_branze(self):
        self.assertEqual(g.branza_wspolna("Beauty/perfumy"), "Uroda")
        self.assertEqual(g.branza_wspolna("Podróże/hotele"), "Podróże")
        self.assertEqual(g.branza_wspolna("Odzież/obuwie sportowe"), "Sport")
        self.assertEqual(g.branza_wspolna("Apteka/suplementy"), "Apteka i drogeria")

    def test_zaokraglenie_polowki_w_gore(self):
        self.assertEqual(g.zaokr(3.15), 3.2)
        self.assertEqual(g.zaokr(2.25), 2.3)

    def test_remisy(self):
        import collections
        c = collections.Counter({0: 2, 1: 2, 3: 2, 5: 1})
        self.assertEqual(g.najczestsze(c, 2, str), ["0", "1", "3"])  # remis — wszystkie trzy, nie arbitralnie dwa
        self.assertEqual(g.najczestsze(collections.Counter({i: 1 for i in range(6)}), 2, str), [])

    def test_odmiana(self):
        self.assertEqual([g.odmiana(n, "sklep", "sklepy", "sklepów") for n in (1, 3, 5, 12, 22)],
                         ["sklep", "sklepy", "sklepów", "sklepów", "sklepy"])

    def test_systemy_z_monitora(self):
        with tempfile.TemporaryDirectory() as k:
            os.makedirs(os.path.join(k, "Raporty"))
            with open(os.path.join(k, "Raporty", "Monitor-2026-11-01.md"), "w", encoding="utf-8") as f:
                f.write("x\n| System | Sklepów | Sklepy |\n|---|---|---|\n| EmailLabs (Vercom) | 2 | Alfa, Beta |\n"
                        "| Platforma sklepu (IdoSell, Shoper) | 1 | Gamma |\n\npo tabeli | A | 1 | Zeta |\n")
            s, plik = g.systemy_z_monitora(k)
        self.assertEqual(plik, "Monitor-2026-11-01.md")
        self.assertEqual(s, {"alfa": "EmailLabs", "beta": "EmailLabs", "gamma": "platforma sklepu (IdoSell, Shoper i inne)"})

    def test_cli(self):
        maile, klas, sklepy = zestaw()
        with tempfile.TemporaryDirectory() as k:
            with open(os.path.join(k, "maile.jsonl"), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(m, ensure_ascii=False) + "\n" for m in maile)
            with open(os.path.join(k, "klasyfikacja.jsonl"), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in klas.values())
            with open(os.path.join(k, "sklepy.json"), "w", encoding="utf-8") as f:
                json.dump(sklepy, f)
            wy = os.path.join(k, "dane.json")
            r = subprocess.run([sys.executable, os.path.join(KORZEN, "porownywarka", "generuj_dane.py"),
                                "--zrodlo", k, "--wyjscie", wy], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(wy, encoding="utf-8") as f:
                d = json.load(f)
        self.assertEqual(d["liczby"]["maile"], 13)
        self.assertIsNone(d["zrodlo_systemow"])


if __name__ == "__main__":
    unittest.main()
