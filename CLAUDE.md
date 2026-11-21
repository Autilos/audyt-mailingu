# audyt-mailingu — zasady dla współtwórców

- Przed zmianą przeczytaj `docs/CONCEPTS.md` — słownik pojęć; zmieniasz znaczenie pojęcia → najpierw tam.
- Zero danych osobowych: nowy endpoint tylko po sprawdzeniu na żywym API i dopisaniu do `DOZWOLONE_SCIEZKI`.
- Raport i strona po polsku bez żargonu — pisz tak, jak do właściciela sklepu (nie „heurystyka”, „hipoteza”, „okno”, „flaga”, „holdout”, „sunset”; w kodzie i komentarzach mogą zostać).
- Tylko zapytania GET. Raporty po polsku, pełne zdania, bez obietnic wzrostu i czasu wdrożenia.
- `seria_powitalna.py`, `rekomendacje.py`, `raport_pdf.py` są identyczne w obu skillach — zmieniaj w obu (test sprawdza `seria_powitalna.py` i `rekomendacje.py`).
- Testy: `python3 -m unittest discover -s tests -v`.
