import unittest
import os
import json
from datetime import date
from execution.storage_manager import (
    load_quotes, add_quotes, get_latest_db_date, sync_from_github,
    get_missing_business_days, has_unpushed_changes, get_github_config
)
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

    def test_missing_business_days_detection(self):
        # Data fittizia lunedì 2026-10-05
        test_today = date(2026, 10, 5)
        missing = get_missing_business_days(lookback_days=10, today=test_today)
        self.assertIsInstance(missing, list)
        # Deve essere lunedì-venerdì (nessun sabato o domenica)
        for d_str in missing:
            d = date.fromisoformat(d_str)
            self.assertLess(d.weekday(), 5, f"{d_str} è nel weekend!")

    def test_multiple_missing_days_calculation(self):
        # Simuliamo un periodo di inutilizzo di una settimana con weekend intermedio
        future_today = date(2026, 10, 12) # Lunedì successivo
        missing = get_missing_business_days(lookback_days=10, today=future_today)
        # Dovrà contenere 2026-10-06, 07, 08, 09, 12 (5 giorni lavorativi), saltando il weekend 10 e 11
        expected = ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12"]
        for exp in expected:
            self.assertIn(exp, missing)
        self.assertNotIn("2026-10-10", missing)
        self.assertNotIn("2026-10-11", missing)

    def test_has_unpushed_changes(self):
        quotes = load_quotes()
        # Se le quotazioni remote sono identiche a quelle locali, has_unpushed_changes è False
        self.assertFalse(has_unpushed_changes(quotes))
        # Se le quotazioni remote mancano dell'ultimo elemento, has_unpushed_changes è True
        if quotes:
            self.assertTrue(has_unpushed_changes(quotes[:-1]))

    def test_no_revoked_hardcoded_token(self):
        # Verifica che il token scaduto e hardcoded sia stato definitivamente rimosso
        path = os.path.join(os.path.dirname(__file__), "..", "execution", "storage_manager.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("Z2hwXzIzWkQxcUtBeWg3SnNMcW5vT2ltQmlGTUQ4SWxORjB6YWx1bw==", content)

if __name__ == "__main__":
    unittest.main()

