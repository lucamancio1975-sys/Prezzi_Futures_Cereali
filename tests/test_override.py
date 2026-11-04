"""
Test unitario per la procedura di override / conferma manuale delle quotazioni.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from execution.storage_manager import load_quotes, save_quotes
from execution.override_quote import apply_quote_override

class TestQuoteOverride(unittest.TestCase):

    def test_apply_quote_override(self):
        # Inserisci una quotazione di prova fittizia
        test_data = "2099-01-01"
        apply_quote_override(
            data=test_data,
            prodotto="GRANO DURO",
            tipo="PDT",
            scadenza="lug-27",
            prezzo=310.5,
            nota="Test Unitario Override"
        )

        quotes = load_quotes()
        match = [q for q in quotes if q.get("data") == test_data and q.get("scadenza") == "lug-27"]
        self.assertTrue(len(match) > 0)
        self.assertEqual(match[0]["prezzo"], 310.5)
        self.assertTrue(match[0].get("confermato_da_utente"))

        # Pulizia record di test
        quotes_cleaned = [q for q in quotes if q.get("data") != test_data]
        save_quotes(quotes_cleaned)

if __name__ == "__main__":
    unittest.main()
