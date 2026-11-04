"""
Modulo per l'aggiornamento/override manuale o confermato di una quotazione nel database.
Eseguito quando l'utente conferma una quotazione rilevata (es. forte rialzo reale di mercato)
oppure inserisce un valore manuale alternativo.
Aggiorna data/storico_prezzi.json e data/storico_prezzi.csv.
"""

import os
import sys
import argparse
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from execution import storage_manager

def apply_quote_override(
    data: str,
    prodotto: str,
    tipo: str,
    scadenza: str,
    prezzo: float,
    nota: str = "Confermato / Rettificato dall'utente"
) -> bool:
    """
    Applica una rettifica o conferma a una quotazione specifica.
    Trova la quotazione nel database per (data, prodotto, tipo, scadenza),
    ne aggiorna il prezzo, rimuove o aggiorna eventuali note di anomalia e salva.
    """
    quotes = storage_manager.load_quotes()
    if not quotes:
        print("[ERRORE] Impossibile caricare il database delle quotazioni.")
        return False

    p_norm = prodotto.strip().upper()
    t_norm = tipo.strip().upper()
    s_norm = scadenza.strip().lower()

    found = False
    for q in quotes:
        if (q.get("data") == data and
            str(q.get("prodotto", "")).strip().upper() == p_norm and
            str(q.get("tipo", "")).strip().upper() == t_norm and
            str(q.get("scadenza", "")).strip().lower() == s_norm):
            
            vecchio_prezzo = q.get("prezzo")
            q["prezzo"] = float(prezzo)
            q["confermato_da_utente"] = True
            q["note_override"] = nota
            if "note_anomalia" in q:
                del q["note_anomalia"]
            found = True
            print(f"[OK] Quotazione trovata e aggiornata: {data} {p_norm} {t_norm} {s_norm} da {vecchio_prezzo} a {prezzo} Eur/ton.")
            break

    if not found:
        # Se per qualche motivo non era presente nel DB, la crea
        new_q = {
            "data": data,
            "scadenza": s_norm,
            "prezzo": float(prezzo),
            "tipo": t_norm,
            "prodotto": p_norm,
            "fonte": "Manuale / Override utente",
            "confermato_da_utente": True,
            "note_override": nota
        }
        if "TENERO" in p_norm:
            new_q["premio_bologna_giorgione"] = 30.0
        quotes.append(new_q)
        print(f"[OK] Quotazione inserita come nuovo record: {data} {p_norm} {t_norm} {s_norm} = {prezzo} Eur/ton.")

    saved = storage_manager.save_quotes(quotes)
    if saved:
        print(f"[OK] Database JSON e CSV salvati con successo.")
    else:
        print(f"[ERRORE] Salvataggio database non riuscito.")
    return saved

def main():
    parser = argparse.ArgumentParser(description="Override o conferma manuale quotazione futures cereali.")
    parser.add_argument("--data", required=True, help="Data quotazione YYYY-MM-DD")
    parser.add_argument("--prodotto", required=True, help="Nome prodotto (es. GRANO DURO)")
    parser.add_argument("--tipo", required=True, help="Tipo contratto (PDT o PMG)")
    parser.add_argument("--scadenza", required=True, help="Scadenza (es. lug-27)")
    parser.add_argument("--prezzo", required=True, type=float, help="Nuovo prezzo da impostare (Eur/ton)")
    parser.add_argument("--nota", default="Confermato dall'utente", help="Nota opzionale")

    args = parser.parse_args()
    success = apply_quote_override(
        data=args.data,
        prodotto=args.prodotto,
        tipo=args.tipo,
        scadenza=args.scadenza,
        prezzo=args.prezzo,
        nota=args.nota
    )
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
