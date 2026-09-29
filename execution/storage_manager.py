"""
Modulo Deterministico per la gestione dello Storage e Statistiche delle quotazioni (Livello 3 - Execution).
Gestisce la persistenza in JSON/CSV, la deduplicazione per (data, prodotto, scadenza, tipo)
e il calcolo dei KPI finanziari per Grano Duro e Grano Tenero (PDT e PMG).
"""

import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_JSON_PATH = os.path.join(DATA_DIR, "storico_prezzi.json")
DB_CSV_PATH = os.path.join(DATA_DIR, "storico_prezzi.csv")

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def get_db_path() -> str:
    """Trova il file storico_prezzi.json controllando i percorsi possibili."""
    candidates = [
        DB_JSON_PATH,
        os.path.join(os.getcwd(), "data", "storico_prezzi.json"),
        os.path.join(os.path.dirname(__file__), "..", "storico_prezzi.json"),
        os.path.join(os.getcwd(), "storico_prezzi.json"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return DB_JSON_PATH

def load_quotes() -> List[Dict[str, Any]]:
    """Carica tutte le quotazioni salvate nel database JSON."""
    ensure_data_dir()
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return []
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Errore caricamento database JSON: {e}")
        return []

def save_quotes(quotes: List[Dict[str, Any]]) -> bool:
    """Salva le quotazioni nel database JSON e aggiorna l'esportazione CSV."""
    ensure_data_dir()
    try:
        # Ordina per data crescente, prodotto, tipo e scadenza
        quotes.sort(key=lambda x: (
            x.get("data", ""),
            x.get("prodotto", ""),
            x.get("tipo", ""),
            x.get("scadenza", "")
        ))
        
        # Scrittura JSON
        with open(DB_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(quotes, f, indent=2, ensure_ascii=False)
            
        # Scrittura CSV
        if quotes:
            df = pd.DataFrame(quotes)
            df.to_csv(DB_CSV_PATH, index=False, sep=";", encoding="utf-8-sig")
            
        return True
    except Exception as e:
        print(f"Errore salvataggio database: {e}")
        return False

def add_quotes(new_quotes: List[Dict[str, Any]]) -> int:
    """
    Aggiunge nuove quotazioni deduplicando su chiave: (data, prodotto, scadenza, tipo).
    Ritorna il numero di nuovi record aggiunti o aggiornati.
    """
    current_quotes = load_quotes()
    
    # Costruisci mappa esistente
    existing_map = {}
    for q in current_quotes:
        key = (
            q.get("data"),
            q.get("prodotto", "GRANO DURO").strip().upper(),
            q.get("scadenza", "lug-27").strip().lower(),
            q.get("tipo", "PDT").strip().upper()
        )
        existing_map[key] = q
    
    added_count = 0
    for nq in new_quotes:
        d = nq.get("data")
        if not d:
            continue
        p = nq.get("prodotto", "GRANO DURO").strip().upper()
        s = nq.get("scadenza", "lug-27").strip().lower()
        t = nq.get("tipo", "PDT").strip().upper()
        
        key = (d, p, s, t)
        if key not in existing_map:
            existing_map[key] = nq
            added_count += 1
        else:
            # Aggiorna se il prezzo o altri attributi differiscono
            if existing_map[key].get("prezzo") != nq.get("prezzo"):
                existing_map[key] = nq
                added_count += 1
                
    if added_count > 0:
        save_quotes(list(existing_map.values()))
        
    return added_count

def get_quotes_for_selection(
    prodotto: str,
    tipo: str = "PDT",
    scadenza: str = "lug-27"
) -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco filtrato delle quotazioni per il prodotto e tipo specificati.
    Normalizza i nomi di prodotto (es. 'DURO' -> 'GRANO DURO', 'TENERO' -> 'GRANO TENERO FINO ROSSO').
    """
    all_quotes = load_quotes()
    prod_norm = prodotto.strip().upper()
    tipo_norm = tipo.strip().upper()
    scad_norm = scadenza.strip().lower()
    
    filtered = []
    for q in all_quotes:
        q_prod = q.get("prodotto", "").strip().upper()
        q_tipo = q.get("tipo", "").strip().upper()
        q_scad = q.get("scadenza", "").strip().lower()
        
        # Match prodotto
        prod_match = False
        if "DURO" in prod_norm and "DURO" in q_prod:
            prod_match = True
        elif "TENERO" in prod_norm and "TENERO" in q_prod:
            prod_match = True
            
        if prod_match and q_tipo == tipo_norm and q_scad == scad_norm:
            filtered.append(q)
            
    filtered.sort(key=lambda x: x.get("data", ""))
    return filtered

def get_delta_for_selection(
    prodotto: str,
    tipo: str = "PDT",
    scadenza: str = "lug-27"
) -> Dict[str, Any]:
    """
    Calcola rapidamente solo i valori essenziali per la hero card (ultimo prezzo e delta).
    Zero calcoli su serie storiche complesse per massima velocità.
    """
    quotes = get_quotes_for_selection(prodotto, tipo, scadenza)
    if not quotes:
        return {}
        
    last_item = quotes[-1]
    prev_item = quotes[-2] if len(quotes) > 1 else last_item
    
    last_price = last_item.get("prezzo", 0.0)
    prev_price = prev_item.get("prezzo", 0.0)
    delta = last_price - prev_price
    pct_change = (delta / prev_price * 100) if prev_price else 0.0
    
    # Rilevamento rapido dell'ultimo cambio se delta == 0
    last_move_delta = 0.0
    last_move_date = ""
    if delta == 0 and len(quotes) > 1:
        for q in reversed(quotes[:-1]):
            if q.get("prezzo") != last_price:
                last_move_delta = last_price - q.get("prezzo", 0.0)
                d_str = q.get("data", "")
                if len(d_str) >= 10:
                    last_move_date = f"{d_str[8:10]}/{d_str[5:7]}"
                break

    return {
        "last_price": last_price,
        "last_date": last_item.get("data", ""),
        "prev_price": prev_price,
        "prev_date": prev_item.get("data", ""),
        "delta": delta,
        "pct_change": pct_change,
        "last_move_delta": last_move_delta,
        "last_move_date": last_move_date,
    }
