import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarkers.cli import detect_invalid_source

# Condensed from the real error pages that poisoned the June 2026 scraping
# results (gemeinderat-zuerich.ch/protokolle and lausanne.ch seances-et-pv).
ZURICH_404 = (
    "# Dokument nicht auffindbar (Error 404)\n\nHinweis\n\n"
    "Ihr gewünschtes Dokument bzw. die gewünschte Seite ist nicht auffindbar. "
    "Vielleicht hat sich die Platzierung des Dokuments geändert.\n"
    "© 2026 Stadt Zürich\n"
)

LAUSANNE_404 = (
    "[liens d'évitement](https://www.lausanne.ch/officiel/autorites/conseil-communal/"
    "seances-et-pv.html)\n\n# Erreur 404\n\n"
    "#### Désolé, la page recherchée est introuvable!\n"
    "Soit votre URL est incorrecte ou le fichier a été déplacé ou renommé.\n"
)

REAL_PAGE = (
    "# Termine\n\nIn den einzelnen Sitzungen sind die Traktanden, Sitzungsunterlagen "
    "und Protokolle aufgeführt. Eine Übersicht über alle Sitzungstermine eines "
    "Amtsjahres bietet der Sitzungskalender.\n" * 20
)

# A large legitimate page that merely mentions a 404 in passing must not trip.
BIG_PAGE_MENTIONING_404 = (
    "Ratsprotokolle des Grossen Rates\n"
    + ("Sitzung vom 24.06.2026 Wortprotokoll Tagesordnung Geschäftsverzeichnis\n" * 800)
    + "Hinweis: alte Links liefern teilweise einen Error 404 zurück.\n"
)


def test_zurich_404_detected():
    assert detect_invalid_source(ZURICH_404) is not None


def test_lausanne_404_detected():
    assert detect_invalid_source(LAUSANNE_404) is not None


def test_english_not_found_detected():
    assert detect_invalid_source("<h1>404 Not Found</h1>\nnginx") is not None


def test_real_page_passes():
    assert detect_invalid_source(REAL_PAGE) is None


def test_big_page_mentioning_404_passes():
    assert detect_invalid_source(BIG_PAGE_MENTIONING_404) is None


def test_empty_output_is_not_flagged():
    # Empty output is a tool failure, not a source-liveness verdict.
    assert detect_invalid_source("") is None
