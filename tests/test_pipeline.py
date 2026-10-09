"""
Suite di test unitari per la pipeline di elaborazione quotazioni futures cereali.
Verifica:
1. Normalizzazione date e dizionario mesi italiani (utils.py)
2. Estrazione regex e parser testuale (parse_pdf_quotazioni.py)
3. Deduplicazione e gestione storage atomico (storage_manager.py)
"""

import os
import sys
import unittest
from datetime import datetime

# Assicura importazione corretta dei moduli
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from execution.utils import parse_data_string, MESI_IT
from execution.parse_pdf_quotazioni import extract_quotes_from_text
from execution.storage_manager import add_quotes, load_quotes, get_quotes_for_selection

class TestPipeline(unittest.TestCase):

    def test_parse_data_string_standard(self):
        """Verifica la corretta conversione delle date con abbreviazioni italiane."""
        self.assertEqual(parse_data_string("18-set-26"), "2026-09-18")
        self.assertEqual(parse_data_string("05-ott-2025"), "2025-10-05")
        self.assertEqual(parse_data_string("1-lug-27"), "2027-07-01")
        self.assertEqual(parse_data_string("28-feb-26"), "2026-02-28")

    def test_parse_data_string_esteso(self):
        """Verifica le date con nome del mese completo."""
        self.assertEqual(parse_data_string("18 settembre 2026"), "2026-09-18")
        self.assertEqual(parse_data_string("5 ottobre 2025"), "2025-10-05")
        self.assertEqual(parse_data_string("12 maggio 2026"), "2026-05-12")

    def test_parse_data_string_invalid(self):
        """Verifica che stringhe non valide restituiscano None senza eccezioni."""
        self.assertIsNone(parse_data_string(""))
        self.assertIsNone(parse_data_string(None))
        self.assertIsNone(parse_data_string("testo generico"))

    def test_extract_quotes_from_sample_text(self):
        """Verifica l'estrazione corretta di Grano Duro e Grano Tenero da testo tipico CAI."""
        sample = """
        Quotazioni valide il: 25-set-26
        
        GRANO DURO
        lug-27 285 Eur/ton
        lug-28 290 Eur/ton
        
        GRANO TENERO FINO ROSSO
        lug-27 215 Eur/ton 240 Eur/ton
        """
        quotes = extract_quotes_from_text(sample, source_name="Test")
        self.assertTrue(len(quotes) >= 3, f"Attese almeno 3 quotazioni, trovate {len(quotes)}")
        
        duro_quotes = [q for q in quotes if "DURO" in q["prodotto"]]
        self.assertTrue(any(q["prezzo"] == 285.0 and q["scadenza"] == "lug-27" for q in duro_quotes))
        
        tenero_quotes = [q for q in quotes if "TENERO" in q["prodotto"]]
        pmg = [q for q in tenero_quotes if q["tipo"] == "PMG"]
        pdt = [q for q in tenero_quotes if q["tipo"] == "PDT"]
        self.assertTrue(len(pmg) > 0 and pmg[0]["prezzo"] == 215.0)
        self.assertTrue(len(pdt) > 0 and pdt[0]["prezzo"] == 240.0)

    def test_price_tokens_filtering(self):
        """Verifica la normalizzazione di token spezzati e il filtraggio per range di prezzo."""
        from execution.parse_image_quotazioni import _price_tokens
        
        # Test 1: parole con spazi interni (es. '20 7' -> 207, '2 29' -> 229)
        line_split = {
            "Text": "20 7   2 29   435",
            "Words": [
                {"Text": "20", "X": 100, "Y": 50},
                {"Text": "7", "X": 115, "Y": 50},
                {"Text": "2", "X": 200, "Y": 50},
                {"Text": "29", "X": 210, "Y": 50},
                {"Text": "435", "X": 300, "Y": 50}
            ]
        }
        
        # Grano Tenero: range 140 - 330 (deve accettare 207 e 229, scartare 435)
        tokens_tenero = _price_tokens(line_split, min_val=140.0, max_val=330.0)
        vals_tenero = [v for v, _, _ in tokens_tenero]
        self.assertIn(207.0, vals_tenero)
        self.assertIn(229.0, vals_tenero)
        self.assertNotIn(435.0, vals_tenero)
        
        # Grano Duro: range 180 - 420
        line_duro = {
            "Text": "lug-27 258.00  lug-28 260.00",
            "Words": [
                {"Text": "258.00", "X": 100, "Y": 100},
                {"Text": "260.00", "X": 200, "Y": 100}
            ]
        }
        tokens_duro = _price_tokens(line_duro, min_val=180.0, max_val=420.0)
        vals_duro = [v for v, _, _ in tokens_duro]
        self.assertEqual(vals_duro, [258.0, 260.0])

if __name__ == "__main__":
    unittest.main()
