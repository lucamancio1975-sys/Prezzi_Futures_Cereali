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

    def test_price_tokens(self):
        """Verifica la normalizzazione di token spezzati dall'OCR (es. '20 7' -> 207, '2 29' -> 229)."""
        from execution.parse_image_quotazioni import _price_tokens
        
        line_split = {
            "Text": "20 7   2 29",
            "Words": [
                {"Text": "20", "X": 100, "Y": 50},
                {"Text": "7", "X": 115, "Y": 50},
                {"Text": "2", "X": 200, "Y": 50},
                {"Text": "29", "X": 210, "Y": 50}
            ]
        }
        
        tokens = _price_tokens(line_split)
        vals = [v for v, _, _ in tokens]
        self.assertIn(207.0, vals)
        self.assertIn(229.0, vals)
        
        line_duro = {
            "Text": "lug-27 258.00  lug-28 260.00",
            "Words": [
                {"Text": "258.00", "X": 100, "Y": 100},
                {"Text": "260.00", "X": 200, "Y": 100}
            ]
        }
        tokens_duro = _price_tokens(line_duro)
        vals_duro = [v for v, _, _ in tokens_duro]
        self.assertEqual(vals_duro, [258.0, 260.0])

    def test_pdf_quotes_parsing(self):
        """Verifica che l'estrazione da PDF assegni correttamente PDT 229 e PMG 207 per lug-27."""
        pdf_path = os.path.join(os.path.dirname(__file__), "..", "scratch", "email_210", "PDT  PMG.pdf")
        if os.path.exists(pdf_path):
            from execution.parse_pdf_quotazioni import extract_quotes_from_pdf
            quotes = extract_quotes_from_pdf(pdf_path)
            tenero_pdt = next((q for q in quotes if "TENERO" in q["prodotto"] and q["tipo"] == "PDT" and q["scadenza"] == "lug-27"), None)
            tenero_pmg = next((q for q in quotes if "TENERO" in q["prodotto"] and q["tipo"] == "PMG" and q["scadenza"] == "lug-27"), None)
            self.assertIsNotNone(tenero_pdt)
            self.assertEqual(tenero_pdt["prezzo"], 229.0)
            self.assertIsNotNone(tenero_pmg)
            self.assertEqual(tenero_pmg["prezzo"], 207.0)

    def test_deviation_validation(self):
        """Verifica che scostamenti <= 5 siano accettati e che scostamenti > 5.01 vengano impostati a 0.0."""
        from execution.fetch_gmail_quotes import validate_quote_deviations
        
        # Test 1: scostamento normale di 1 €/t (258 -> 259)
        sample_ok = [{
            "data": "2026-10-15",
            "prodotto": "GRANO DURO",
            "tipo": "PDT",
            "scadenza": "lug-27",
            "prezzo": 259.0
        }]
        res_ok, anom_ok, _ = validate_quote_deviations(sample_ok, max_allowed_delta=5.01, send_email=False)
        self.assertEqual(len(anom_ok), 0)
        self.assertEqual(res_ok[0]["prezzo"], 259.0)

        # Test 2: scostamento anomalo di 200 €/t (207 -> 425) come avvenuto per il Grano Tenero PMG
        sample_bad = [{
            "data": "2026-10-15",
            "prodotto": "GRANO TENERO FINO ROSSO",
            "tipo": "PMG",
            "scadenza": "lug-27",
            "prezzo": 425.0
        }]
        res_bad, anom_bad, _ = validate_quote_deviations(sample_bad, max_allowed_delta=5.01, send_email=False)
        self.assertEqual(len(anom_bad), 1)
        self.assertEqual(res_bad[0]["prezzo"], 0.0)

if __name__ == "__main__":
    unittest.main()
