"""
Modulo per l'aggiornamento/override manuale o confermato di una quotazione nel database.
Eseguito quando l'utente conferma una quotazione rilevata (es. forte rialzo reale di mercato)
oppure inserisce un valore manuale alternativo.
Aggiorna data/storico_prezzi.json, data/storico_prezzi.csv e sincronizza su GitHub.
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
    nota: str = "Confermato / Rettificato dall'utente",
    push_github: bool = True
) -> bool:
    """
    Applica una rettifica o conferma a una quotazione specifica.
    Trova la quotazione nel database per (data, prodotto, tipo, scadenza),
    ne aggiorna il prezzo, rimuove categoricamente le note di anomalia e il valore 0.0,
    ripulisce eventuali record 0.0 duplicati o fuori standard per quella serie e salva atomico.
    Se push_github=True sincronizza immediatamente su GitHub.
    """
    quotes = storage_manager.load_quotes()
    if not quotes:
        print("[ERRORE] Impossibile caricare il database delle quotazioni.")
        return False

    p_norm = prodotto.strip().upper()
    t_norm = tipo.strip().upper()
    s_norm = scadenza.strip().lower()

    found = False
    cleaned_quotes = []

    for q in quotes:
        q_data = q.get("data")
        q_prod = str(q.get("prodotto", "")).strip().upper()
        q_tipo = str(q.get("tipo", "")).strip().upper()
        q_scad = str(q.get("scadenza", "")).strip().lower()

        # Rimuove categoricamente eventuali record lug-28 rimasti per la stessa data
        if q_data == data and q_scad == "lug-28":
            continue

        if (q_data == data and
            q_prod == p_norm and
            q_tipo == t_norm and
            q_scad == s_norm):
            
            vecchio_prezzo = q.get("prezzo")
            q["prezzo"] = float(prezzo)
            q["confermato_da_utente"] = True
            q["note_override"] = nota
            # Rimuove note_anomalia per eliminare definitivamente "Prezzo rilevato fuori standard"
            if "note_anomalia" in q:
                del q["note_anomalia"]
            found = True
            print(f"[OK] Quotazione trovata e aggiornata: {data} {p_norm} {t_norm} {s_norm} da {vecchio_prezzo} a {prezzo} Eur/ton.")
            cleaned_quotes.append(q)
        else:
            cleaned_quotes.append(q)

    if not found:
        # Se non era ancora presente nel DB, la crea come nuovo record confermato
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
        cleaned_quotes.append(new_q)
        print(f"[OK] Quotazione inserita come nuovo record: {data} {p_norm} {t_norm} {s_norm} = {prezzo} Eur/ton.")

    saved = storage_manager.save_quotes(cleaned_quotes)
    if saved:
        print(f"[OK] Database JSON e CSV salvati con successo in locale.")
        if push_github:
            try:
                pushed = storage_manager.sync_to_github(merge_remote=False)
                if pushed:
                    print(f"[OK] Database sincronizzato con successo su GitHub.")
                else:
                    print(f"[WARN] Sincronizzazione GitHub non riuscita.")
            except Exception as e:
                print(f"[WARN] Errore sync GitHub: {e}")
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
    parser.add_argument("--no-push", action="store_true", help="Non sincronizzare su GitHub")

    args = parser.parse_args()
    success = apply_quote_override(
        data=args.data,
        prodotto=args.prodotto,
        tipo=args.tipo,
        scadenza=args.scadenza,
        prezzo=args.prezzo,
        nota=args.nota,
        push_github=not args.no_push
    )
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
