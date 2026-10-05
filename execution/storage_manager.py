"""
Modulo Deterministico per la gestione dello Storage e Statistiche delle quotazioni (Livello 3 - Execution).
Gestisce la persistenza in JSON/CSV, la deduplicazione per (data, prodotto, scadenza, tipo)
e il calcolo dei KPI finanziari per Grano Duro e Grano Tenero (PDT e PMG).
"""

import os
import json
import shutil
import base64
import time
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_JSON_PATH = os.path.join(DATA_DIR, "storico_prezzi.json")
DB_CSV_PATH = os.path.join(DATA_DIR, "storico_prezzi.csv")

DEFAULT_REPO = "lucamancio1975-sys/Prezzi_Futures_Cereali"
GITHUB_BRANCH = "main"
GH_JSON_PATH = "data/storico_prezzi.json"
GH_CSV_PATH = "data/storico_prezzi.csv"

# Esito dell'ultima operazione di sincronizzazione con GitHub (letto dalla UI per diagnostica)
LAST_GITHUB_STATUS: Dict[str, Any] = {"pull_ok": None, "push_ok": None, "error": ""}


def oggi_italia() -> date:
    """Data odierna nel fuso orario italiano (i server cloud girano in UTC)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).date()
    except Exception:
        return datetime.now().date()

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
        # newline="\n": stesso contenuto byte-per-byte su Windows e Linux (evita commit inutili)
        tmp_json = DB_JSON_PATH + ".tmp"
        with open(tmp_json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(quotes, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_json, DB_JSON_PATH)
            
        # 3. Scrittura atomica CSV
        if quotes:
            tmp_csv = DB_CSV_PATH + ".tmp"
            df = pd.DataFrame(quotes)
            df.to_csv(tmp_csv, index=False, sep=";", encoding="utf-8-sig", lineterminator="\n")
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

def get_missing_business_days(
    lookback_days: int = 10,
    max_gap_days: int = 180,
    today: Optional[date] = None
) -> List[str]:
    """
    Restituisce i giorni lavorativi (lun-ven) privi di quotazioni nel database, in ordine crescente.
    - Copre SEMPRE tutto il periodo dopo l'ultima data archiviata (anche settimane di inutilizzo
      dell'app), fino a un massimo di `max_gap_days` giorni.
    - Controlla anche eventuali "buchi" negli ultimi `lookback_days` giorni.
    I giorni festivi infrasettimanali risultano "mancanti" ma la loro verifica costa solo la
    lettura degli header delle email.
    """
    today = today or oggi_italia()
    dates = set(q.get("data") for q in load_quotes() if q.get("data"))

    start = today - timedelta(days=lookback_days)
    if dates:
        try:
            last = datetime.strptime(max(dates), "%Y-%m-%d").date()
            first = datetime.strptime(min(dates), "%Y-%m-%d").date()
            start = min(start, last + timedelta(days=1))
            start = max(start, first)
        except ValueError:
            pass
    start = max(start, today - timedelta(days=max_gap_days))

    missing = []
    d = start
    while d <= today:
        iso = d.isoformat()
        if d.weekday() < 5 and iso not in dates:
            missing.append(iso)
        d += timedelta(days=1)
    return missing

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

# =========================================================================
# SINCRONIZZAZIONE GITHUB
# =========================================================================
def get_github_config() -> Tuple[Optional[str], str]:
    """
    Legge GITHUB_TOKEN e GITHUB_REPO da variabili d'ambiente (.env in locale) o dai
    Secrets di Streamlit Cloud.
    NB: il vecchio token "di fallback" scritto nel codice è stato revocato da GitHub
    (risponde 401 Bad credentials) ed è stato rimosso: era la causa del mancato
    aggiornamento del database su GitHub.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    except Exception:
        pass
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")
    if not token or not repo:
        try:
            import streamlit as st
            token = token or st.secrets.get("GITHUB_TOKEN")
            repo = repo or st.secrets.get("GITHUB_REPO")
        except Exception:
            pass
    return (token or None), (repo or DEFAULT_REPO)

def _gh_http(url: str, token: Optional[str] = None, method: str = "GET",
             payload: Optional[dict] = None, accept: str = "application/vnd.github+json",
             timeout: float = 10.0) -> bytes:
    headers = {
        "User-Agent": "FuturesGrano-SyncBot",
        "Accept": accept,
        "Cache-Control": "no-cache",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def _gh_get_file(repo: str, path: str, token: str) -> Tuple[Optional[str], Optional[bytes]]:
    """Ritorna (sha, contenuto_bytes) del file su GitHub, oppure (None, None) se non esiste."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    try:
        info = json.loads(_gh_http(url, token).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    sha = info.get("sha")
    content = info.get("content") or ""
    if content and info.get("encoding") == "base64":
        return sha, base64.b64decode(content)
    # File > 1MB: la Contents API non include il contenuto, lo scarico in formato raw
    return sha, _gh_http(url, token, accept="application/vnd.github.raw")

def fetch_remote_quotes() -> Optional[List[Dict[str, Any]]]:
    """
    Scarica lo storico quotazioni da GitHub. Ritorna la lista oppure None se non raggiungibile.
    - Con token: Contents API (sempre aggiornata, nessuna cache CDN).
    - Senza token (o se l'API fallisce): URL raw pubblico SENZA header Authorization
      (un token non valido farebbe fallire anche il download pubblico).
    """
    token, repo = get_github_config()
    if token:
        try:
            url = f"https://api.github.com/repos/{repo}/contents/{GH_JSON_PATH}?ref={GITHUB_BRANCH}"
            data = json.loads(_gh_http(url, token, accept="application/vnd.github.raw", timeout=6).decode("utf-8"))
            if isinstance(data, list):
                LAST_GITHUB_STATUS["pull_ok"] = True
                return data
        except Exception as e:
            LAST_GITHUB_STATUS["error"] = f"Lettura GitHub via API fallita: {e}"
            print(f"[GITHUB SYNC] {LAST_GITHUB_STATUS['error']}")
    try:
        raw_url = f"https://raw.githubusercontent.com/{repo}/{GITHUB_BRANCH}/{GH_JSON_PATH}?_t={int(time.time())}"
        data = json.loads(_gh_http(raw_url, None, accept="*/*", timeout=6).decode("utf-8"))
        if isinstance(data, list):
            LAST_GITHUB_STATUS["pull_ok"] = True
            return data
    except Exception as e:
        print(f"[GITHUB SYNC] Lettura GitHub raw fallita: {e}")
    LAST_GITHUB_STATUS["pull_ok"] = False
    return None

def _quote_key(q: Dict[str, Any]) -> tuple:
    return (
        q.get("data"),
        str(q.get("prodotto", "GRANO DURO")).strip().upper(),
        str(q.get("scadenza", "lug-27")).strip().lower(),
        str(q.get("tipo", "PDT")).strip().upper(),
    )

def has_unpushed_changes(remote_quotes: Optional[List[Dict[str, Any]]]) -> bool:
    """True se il DB locale contiene quotazioni assenti (o diverse) rispetto a GitHub."""
    if remote_quotes is None:
        return False
    remote_map = {_quote_key(q): q.get("prezzo") for q in remote_quotes}
    for q in load_quotes():
        k = _quote_key(q)
        if k not in remote_map or remote_map[k] != q.get("prezzo"):
            return True
    return False

def sync_from_github() -> int:
    """
    Sincronizzazione in ingresso dal repository GitHub:
    Scarica la versione più recente di data/storico_prezzi.json da GitHub
    e fonde eventuali nuove quotazioni nel database locale.
    Restituisce il numero di quotazioni importate/aggiornate.
    """
    remote_quotes = fetch_remote_quotes()
    if not remote_quotes:
        return 0
    # Fonde le quotazioni remote nel DB locale senza rimandare indietro a GitHub
    return add_quotes(remote_quotes, push_github=False)

def sync_to_github(commit_message: str = "Auto-sync: nuove quotazioni futures cereali da Gmail [skip ci]") -> bool:
    """
    Pubblica data/storico_prezzi.json e data/storico_prezzi.csv su GitHub (Contents API).
    - Prima del push FONDE il contenuto remoto nel DB locale: un'istanza con DB incompleto
      non può mai sovrascrivere/cancellare dati già presenti su GitHub.
    - Salta il commit se il file remoto è già identico.
    - In caso di conflitto (409/422: un altro utente ha appena pubblicato) riprova.
    - Registra l'esito in LAST_GITHUB_STATUS (nessun errore silenzioso).
    """
    token, repo = get_github_config()
    if not token:
        LAST_GITHUB_STATUS.update(push_ok=False, error="GITHUB_TOKEN non configurato (Secrets di Streamlit o file .env)")
        print(f"[GITHUB SYNC ERROR] {LAST_GITHUB_STATUS['error']}")
        return False

    last_error = ""
    for attempt in range(3):
        try:
            # 1. Merge del contenuto remoto (protezione da sovrascritture)
            json_sha, remote_json = _gh_get_file(repo, GH_JSON_PATH, token)
            if remote_json:
                try:
                    remote_list = json.loads(remote_json.decode("utf-8"))
                    if isinstance(remote_list, list):
                        add_quotes(remote_list, push_github=False)
                except ValueError:
                    pass
            if not os.path.exists(DB_JSON_PATH):
                LAST_GITHUB_STATUS.update(push_ok=False, error="Database locale assente")
                return False
            # Rigenera JSON e CSV in formato normalizzato
            save_quotes(load_quotes())

            # 2. Push dei file che differiscono
            csv_sha, remote_csv = _gh_get_file(repo, GH_CSV_PATH, token)
            for gh_path, local_path, sha, remote_bytes in [
                (GH_JSON_PATH, DB_JSON_PATH, json_sha, remote_json),
                (GH_CSV_PATH, DB_CSV_PATH, csv_sha, remote_csv),
            ]:
                if not os.path.exists(local_path):
                    continue
                with open(local_path, "rb") as f:
                    local_bytes = f.read()
                if remote_bytes is not None and remote_bytes == local_bytes:
                    continue
                payload = {
                    "message": commit_message,
                    "content": base64.b64encode(local_bytes).decode("utf-8"),
                    "branch": GITHUB_BRANCH,
                }
                if sha:
                    payload["sha"] = sha
                _gh_http(f"https://api.github.com/repos/{repo}/contents/{gh_path}",
                         token, method="PUT", payload=payload, timeout=15)
                print(f"[GITHUB SYNC] Pubblicato {gh_path} su {repo}")

            LAST_GITHUB_STATUS.update(push_ok=True, error="")
            return True
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code} {e.reason}"
            if e.code in (409, 422) and attempt < 2:
                time.sleep(1.0 + attempt)  # conflitto di SHA: un altro utente ha appena pubblicato
                continue
            if e.code in (401, 403):
                last_error += " - token GitHub non valido, scaduto o senza permesso 'contents: write'"
            break
        except Exception as e:
            last_error = str(e)
            if attempt < 2:
                time.sleep(1.0)
                continue
            break

    LAST_GITHUB_STATUS.update(push_ok=False, error=f"Push GitHub fallito: {last_error}")
    print(f"[GITHUB SYNC ERROR] {LAST_GITHUB_STATUS['error']}")
    return False

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
