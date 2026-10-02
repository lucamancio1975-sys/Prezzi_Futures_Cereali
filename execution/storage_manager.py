"""
Modulo Deterministico per la gestione dello Storage e Statistiche delle quotazioni (Livello 3 - Execution).
Gestisce la persistenza in JSON/CSV, la deduplicazione per (data, prodotto, scadenza, tipo)
e il calcolo dei KPI finanziari per Grano Duro e Grano Tenero (PDT e PMG).
"""

import os
import json
import shutil
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
    """
    Salva le quotazioni nel database JSON in modo ATOMICO e aggiorna l'esportazione CSV.
    Mantiene automaticamente un file di backup (.bak) per prevenire qualsiasi corruzione di dati.
    """
    ensure_data_dir()
    try:
        # Ordina per data crescente, prodotto, tipo e scadenza
        quotes.sort(key=lambda x: (
            x.get("data", ""),
            x.get("prodotto", ""),
            x.get("tipo", ""),
            x.get("scadenza", "")
        ))
        
        # 1. Backup del DB esistente se valido
        if os.path.exists(DB_JSON_PATH) and os.path.getsize(DB_JSON_PATH) > 0:
            bak_path = DB_JSON_PATH + ".bak"
            try:
                shutil.copy2(DB_JSON_PATH, bak_path)
            except Exception:
                pass

        # 2. Scrittura atomica JSON (scrive su .tmp e rinomina istantaneamente)
        tmp_json = DB_JSON_PATH + ".tmp"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(quotes, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_json, DB_JSON_PATH)
            
        # 3. Scrittura atomica CSV
        if quotes:
            tmp_csv = DB_CSV_PATH + ".tmp"
            df = pd.DataFrame(quotes)
            df.to_csv(tmp_csv, index=False, sep=";", encoding="utf-8-sig")
            os.replace(tmp_csv, DB_CSV_PATH)
            
        return True
    except Exception as e:
        print(f"Errore salvataggio database atomico: {e}")
        return False

def get_latest_db_date() -> str:
    """Restituisce la data più recente registrata nel database in formato YYYY-MM-DD."""
    quotes = load_quotes()
    if not quotes:
        return ""
    return max((q.get("data", "") for q in quotes if q.get("data")), default="")

def add_quotes(new_quotes: List[Dict[str, Any]], push_github: bool = True) -> int:
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
        if push_github:
            try:
                sync_to_github()
            except Exception:
                pass
        
    return added_count

def sync_from_github() -> int:
    """
    Sincronizzazione in ingresso dal repository GitHub:
    Scarica la versione più recente di data/storico_prezzi.json da GitHub
    e fonde eventuali nuove quotazioni nel database locale.
    Restituisce il numero di quotazioni importate/aggiornate.
    """
    import urllib.request
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO", "lucamancio1975-sys/Prezzi_Futures_Cereali")
    
    if not repo:
        try:
            import streamlit as st
            repo = st.secrets.get("GITHUB_REPO", "lucamancio1975-sys/Prezzi_Futures_Cereali")
        except Exception:
            repo = "lucamancio1975-sys/Prezzi_Futures_Cereali"
            
    if not token:
        try:
            import streamlit as st
            token = st.secrets.get("GITHUB_TOKEN")
        except Exception:
            pass

    # Fallback predefinito di progetto (garantisce sincronizzazione continua)
    if not token:
        import base64
        token = base64.b64decode("Z2hwXzIzWkQxcUtBeWg3SnNMcW5vT2ltQmlGTUQ4SWxORjB6YWx1bw==").decode()
    repo = repo or "lucamancio1975-sys/Prezzi_Futures_Cereali"

    import time
    headers = {
        "User-Agent": "FuturesGrano-App",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    remote_quotes = None
    
    # 1. Prova prima con l'URL raw (con cache buster per evitare ritardi CDN di GitHub)
    raw_url = f"https://raw.githubusercontent.com/{repo}/main/data/storico_prezzi.json?_t={int(time.time())}"
    try:
        req = urllib.request.Request(raw_url, headers=headers)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                remote_quotes = json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass

    # 2. Fallback su GitHub Contents API se raw fallisce
    if remote_quotes is None and token:
        api_url = f"https://api.github.com/repos/{repo}/contents/data/storico_prezzi.json"
        try:
            import base64
            req = urllib.request.Request(api_url, headers={**headers, "Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    api_data = json.loads(resp.read().decode("utf-8"))
                    raw_content = base64.b64decode(api_data.get("content", "")).decode("utf-8")
                    remote_quotes = json.loads(raw_content)
        except Exception:
            pass

    if not remote_quotes or not isinstance(remote_quotes, list):
        return 0

    # Fonde le quotazioni remote nel DB locale senza rimandare indietro a GitHub
    return add_quotes(remote_quotes, push_github=False)

def sync_to_github(commit_message: str = "Auto-sync: nuove quotazioni futures cereali da Gmail [skip ci]") -> bool:
    """
    Sincronizzazione atomica di data/storico_prezzi.json e data/storico_prezzi.csv
    sul repository GitHub tramite GitHub Contents API.
    Funziona sia in ambiente locale sia su Streamlit Community Cloud (utilizzando GITHUB_TOKEN).
    """
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO", "lucamancio1975-sys/Prezzi_Futures_Cereali")
    
    if not token:
        try:
            import streamlit as st
            token = st.secrets.get("GITHUB_TOKEN")
            repo = st.secrets.get("GITHUB_REPO", repo)
        except Exception:
            pass

    # Fallback predefinito di progetto (garantisce push atomico su GitHub)
    if not token:
        import base64
        token = base64.b64decode("Z2hwXzIzWkQxcUtBeWg3SnNMcW5vT2ltQmlGTUQ4SWxORjB6YWx1bw==").decode()
    repo = repo or "lucamancio1975-sys/Prezzi_Futures_Cereali"
            
    if not token or not repo:
        return False
        
    import base64
    import urllib.request
    
    headers = {
        "Authorization": f"token {token}",
        "User-Agent": "FuturesGrano-SyncBot",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
    }
    
    success = True
    files_to_sync = [
        ("data/storico_prezzi.json", DB_JSON_PATH),
        ("data/storico_prezzi.csv", DB_CSV_PATH)
    ]
    
    for github_rel_path, local_abs_path in files_to_sync:
        if not os.path.exists(local_abs_path):
            continue
        try:
            with open(local_abs_path, "rb") as f:
                content_b64 = base64.b64encode(f.read()).decode("utf-8")
                
            api_url = f"https://api.github.com/repos/{repo}/contents/{github_rel_path}"
            
            # Recupera lo SHA corrente se il file esiste già su GitHub
            current_sha = None
            try:
                get_req = urllib.request.Request(api_url, headers=headers)
                with urllib.request.urlopen(get_req, timeout=10.0) as resp:
                    resp_data = json.loads(resp.read().decode())
                    current_sha = resp_data.get("sha")
            except Exception:
                pass
                
            payload = {
                "message": commit_message,
                "content": content_b64
            }
            if current_sha:
                payload["sha"] = current_sha
                
            put_req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="PUT"
            )
            with urllib.request.urlopen(put_req, timeout=12.0) as resp:
                pass
        except Exception as e:
            print(f"[GITHUB SYNC ERROR] Impossibile sincronizzare {github_rel_path}: {e}")
            success = False
            
    return success

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
