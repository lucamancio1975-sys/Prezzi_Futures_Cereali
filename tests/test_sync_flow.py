import unittest
import os
import json
from execution.storage_manager import load_quotes, add_quotes, get_latest_db_date, sync_from_github
from execution.fetch_gmail_quotes import check_and_sync_today_quotes

class TestSyncFlow(unittest.TestCase):
    def test_get_latest_db_date(self):
        latest = get_latest_db_date()
        self.assertTrue(len(latest) == 10)
        self.assertTrue(latest.startswith("202"))

    def test_sync_from_github_structure(self):
        # Verifica che la funzione di sync da GitHub non sollevi eccezioni
        try:
            res = sync_from_github()
            self.assertIsInstance(res, int)
            self.assertGreaterEqual(res, 0)
        except Exception as e:
            self.fail(f"sync_from_github ha sollevato un'eccezione imprevista: {e}")

    def test_add_quotes_deduplication(self):
        current_len = len(load_quotes())
        # Tenta di aggiungere una quotazione già identica
        duplicate_quote = [{
            "data": "2026-10-01",
            "prodotto": "GRANO DURO",
            "scadenza": "lug-27",
            "prezzo": 258.0,
            "tipo": "PDT"
        }]
        added = add_quotes(duplicate_quote, push_github=False)
        self.assertEqual(added, 0)
        self.assertEqual(len(load_quotes()), current_len)

if __name__ == "__main__":
    unittest.main()
