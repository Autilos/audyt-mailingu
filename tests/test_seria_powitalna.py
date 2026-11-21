"""Testy klasyfikatora serii powitalnej na fikcyjnych mailach (bez danych z kont).

Uruchom:  python3 -m unittest discover -s tests -v
"""
import filecmp
import os
import sys
import unittest

KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GR = os.path.join(KORZEN, "skills", "audyt-getresponse", "scripts")
ML = os.path.join(KORZEN, "skills", "audyt-mailerlite", "scripts")
sys.path.insert(0, GR)

from seria_powitalna import klasyfikuj, wniosek_serii  # noqa: E402

DLUGI_PORADNIK = "<p>" + " ".join(["Herbatę na zimę dobieraj do pory dnia i do smaku."] * 20) + "</p>"


class Klasyfikacja(unittest.TestCase):
    def k(self, temat, html):
        return klasyfikuj(temat, html)[0]

    def test_kod_i_procent_to_sprzedaz(self):
        self.assertEqual(self.k("Witaj! Masz -10% na start", "<p>Twój kod: WITAJ10</p><a href='https://sklep.pl/koszyk'>Kup teraz</a>"), "SPRZEDAŻOWY")

    def test_kwota_rabatu_w_temacie(self):
        self.assertEqual(self.k("50 zł na pierwsze zakupy", "<p>Odbierz kupon i zamów herbatę.</p>"), "SPRZEDAŻOWY")

    def test_poradnik_bez_oferty(self):
        self.assertEqual(self.k("Jak wybrać pierwszą herbatę", "<p>Krótki poradnik krok po kroku.</p>"), "WARTOŚCIOWY")

    def test_historia_marki(self):
        self.assertEqual(self.k("Poznaj nas", "<p>Nasza historia zaczęła się w garażu.</p>"), "WARTOŚCIOWY")

    def test_dlugi_tekst_bez_slow_kluczy_to_wartosc(self):
        self.assertEqual(self.k("Zimowe herbaty", DLUGI_PORADNIK), "WARTOŚCIOWY")

    def test_poradnik_z_kodem_to_mieszany(self):
        self.assertEqual(self.k("Jak dobrać herbatę + kod -15%", "<p>Poradnik. Kod: ZIMA15</p>"), "MIESZANY")

    def test_opinie_z_przyciskiem_do_produktu_to_mieszany(self):
        k, powod = klasyfikuj("Co mówią klienci", "<p>Opinie naszych klientów</p><a href='https://sklep.pl/produkt/x'>Zobacz</a>")
        self.assertEqual(k, "MIESZANY")
        self.assertIn("link do produktu", powod)

    def test_jeden_slaby_sygnal_zaznaczony(self):
        k, powod = klasyfikuj("Nowości w sklepie", "<p>Zobacz promocje.</p>")
        self.assertEqual(k, "SPRZEDAŻOWY")
        self.assertIn("słaby sygnał", powod)

    def test_sam_obrazek_nieokreslony(self):
        self.assertEqual(self.k("Witaj", "<img src='baner.jpg'>"), "NIEOKREŚLONY")

    def test_brak_tresci(self):
        self.assertEqual(klasyfikuj("Witaj", "")[1], "API nie zwróciło treści maila")

    def test_o_nas_nie_lapie_sie_w_srodku_slowa(self):
        # „po naszej” zawiera „o nas” jako fragment — nie może dać sygnału „historia marki”
        self.assertEqual(self.k("Dzięki", "<p>Dziękujemy po naszej stronie.</p>"), "NIEOKREŚLONY")

    def test_styl_i_skrypt_nie_licza_sie_do_tresci(self):
        self.assertEqual(self.k("Witaj", "<style>.a{color:red} kup rabat 50 zł</style><p>Cześć</p>"), "NIEOKREŚLONY")

    def test_rok_i_godzina_nie_sa_kwota(self):
        self.assertEqual(self.k("Witaj w 2026", "<p>Odpisujemy do 16:00.</p>"), "NIEOKREŚLONY")


    def test_dlugi_mail_z_cenami_to_sprzedaz(self):
        produkty = " ".join(["Herbata czarna, aromatyczna, od 29 zł. Zobacz."] * 25)
        self.assertEqual(self.k("Witaj w klubie", f"<p>Kod WITAJ −10% na pierwsze zakupy. {produkty}</p>"), "SPRZEDAŻOWY")

    def test_stopka_z_o_nas_nie_daje_wartosci(self):
        tresc = "<p>Masz -10% z kodem START10. Kup teraz.</p>" + "<p>" + "Tekst oferty. " * 30 + "</p><p>Nie chcesz już takich wiadomości? Wypisz się. O nas · Poradnik · Opinie</p>"
        self.assertEqual(self.k("Witaj", tresc), "SPRZEDAŻOWY")


    def test_kupowany_i_zamowienie_to_nie_wezwanie(self):
        k, powod = klasyfikuj("Od czego zacząć", "<p>Nasza najczęściej kupowana herbata. Twoje zamówienie wyślemy szybko.</p>")
        self.assertNotIn("wezwanie", powod)
        self.assertEqual(klasyfikuj("Kup teraz", "<p>Zamów już dziś</p>")[0], "SPRZEDAŻOWY")

    def test_poradnik_z_linkami_do_produktow_to_mieszany(self):
        tekst = " ".join(["Ta herbata jest słodka i rozgrzewająca, najlepsza zimą, parzy się krótko."] * 15)
        html = f"<p>{tekst}</p><a href='https://sklep.pl/produkt/a'>Zobacz</a>"
        self.assertEqual(self.k("Od czego zacząć", html), "MIESZANY")


class Wniosek(unittest.TestCase):
    def test_jeden_mail_rabatowy(self):
        w = wniosek_serii([{"dzien": 0, "klasa": "SPRZEDAŻOWY", "wyslane": 100, "wlaczony": True}])
        self.assertTrue(any("1 mail i to od razu oferta" in x for x in w))

    def test_wszystko_wylaczone(self):
        w = wniosek_serii([{"dzien": 0, "klasa": "SPRZEDAŻOWY", "wyslane": 100, "wlaczony": False}])
        self.assertIn("żaden jej mail nie jest włączony", w[0])

    def test_krotka_seria_same_oferty(self):
        w = wniosek_serii([{"dzien": 0, "klasa": "SPRZEDAŻOWY", "wyslane": 10, "wlaczony": True},
                           {"dzien": 2, "klasa": "SPRZEDAŻOWY", "wyslane": 5, "wlaczony": True}])
        self.assertTrue(any("kończy się w dniu 2" in x for x in w))
        self.assertTrue(any("Wszystkie wysyłane maile serii są sprzedażowe" in x for x in w))

    def test_zdrowa_seria(self):
        w = wniosek_serii([{"dzien": 0, "klasa": "SPRZEDAŻOWY", "wyslane": 10, "wlaczony": True},
                           {"dzien": 3, "klasa": "WARTOŚCIOWY", "wyslane": 8, "wlaczony": True},
                           {"dzien": 7, "klasa": "MIESZANY", "wyslane": 6, "wlaczony": True}])
        self.assertTrue(any("łączy ofertę z treścią" in x for x in w))


class TaSamaKopia(unittest.TestCase):
    def test_kopia_w_mailerlite_identyczna(self):
        a, b = os.path.join(GR, "seria_powitalna.py"), os.path.join(ML, "seria_powitalna.py")
        if os.path.exists(b):
            self.assertTrue(filecmp.cmp(a, b, shallow=False), "seria_powitalna.py w obu skillach musi być identyczny")


if __name__ == "__main__":
    unittest.main()
