"""
Modulo Deterministico per l'elaborazione dei comandi di conferma/aggiornamento
inviati dall'utente tramite GitHub (Issue o Commenti su Issue).
Supporta:
  - Formato compatto: /conferma 2026-11-04 300.0 (o /aggiorna 2026-11-04 300.0)
  - Formato esteso: /conferma DATA="2026-11-04" PROD="GRANO DURO" TIPO="PDT" SCAD="lug-27" PREZZO=300.00
Conforme all'architettura a 3 livelli (Livello 3 - Execution).
"""

import os
import re
import sys
import json
import ssl
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from execution import storage_manager
from execution.override_quote import apply_quote_override

def get_github_token() -> Optional[str]:
    """Recupera il token GitHub da env GITHUB_TOKEN, file locale o configurazione."""
    t = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if t:
        return t.strip()
    tok_file = os.path.join(BASE_DIR, "token git hub.txt")
    if os.path.exists(tok_file):
        try:
            with open(tok_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass
    return None

def parse_command_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Riconosce ed estrae i parametri da un comando nel testo (/conferma o /aggiorna).
    Riconosce:
      1. Sintassi estesa:
         /conferma DATA="2026-11-04" PROD="GRANO DURO" TIPO="PDT" SCAD="lug-27" PREZZO=300.00
      2. Sintassi compatta:
         /conferma 2026-11-04 300.0
         /conferma 300.0 (data odierna default, GRANO DURO PDT lug-27 default)
         /aggiorna 2026-11-04 295.0
    """
    if not text:
        return None
    
    clean_txt = text.strip()
    m_cmd = re.search(r'/(?:conferma|aggiorna)\b(.*)', clean_txt, re.IGNORECASE)
    if not m_cmd:
        return None
    
    args_str = m_cmd.group(1).strip()
    
    # 1. Prova parsing parametri nominati
    m_data = re.search(r'DATA=["\']?([0-9]{4}-[0-9]{2}-[0-9]{2})["\']?', args_str, re.IGNORECASE)
    m_prod = re.search(r'PROD=["\']?([^"\'\s]+(?:\s+[^"\'\s]+)*)["\']?', args_str, re.IGNORECASE)
    m_tipo = re.search(r'TIPO=["\']?([A-Z]{3})["\']?', args_str, re.IGNORECASE)
    m_scad = re.search(r'SCAD=["\']?([a-z]{3}-[0-9]{2})["\']?', args_str, re.IGNORECASE)
    m_prz = re.search(r'PREZZO=([0-9]+(?:\.[0-9]+)?)', args_str, re.IGNORECASE)
    
    if m_prz:
        prz = float(m_prz.group(1))
        d = m_data.group(1) if m_data else storage_manager.oggi_italia().isoformat()
        prod = m_prod.group(1).upper() if m_prod else "GRANO DURO"
        tipo = m_tipo.group(1).upper() if m_tipo else "PDT"
        scad = m_scad.group(1).lower() if m_scad else "lug-27"
        return {
            "data": d,
            "prodotto": prod,
            "tipo": tipo,
            "scadenza": scad,
            "prezzo": prz,
            "raw": clean_txt
        }
    
    # 2. Prova parsing sintassi posizionale:
    # es: 2026-11-04 300.0 oppure 300.0
    tokens = args_str.split()
    if not tokens:
        return None
    
    target_data = None
    target_prz = None
    
    for tok in tokens:
        # Check data YYYY-MM-DD
        if re.match(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$', tok):
            target_data = tok
        else:
            try:
                # Sostituisce virgola se usata all'italiana (es. 300,5)
                val = float(tok.replace(',', '.'))
                if val > 0:
                    target_prz = val
            except ValueError:
                pass
                
    if target_prz is not None:
        d = target_data or storage_manager.oggi_italia().isoformat()
        return {
            "data": d,
            "prodotto": "GRANO DURO",
            "tipo": "PDT",
            "scadenza": "lug-27",
            "prezzo": target_prz,
            "raw": clean_txt
        }
        
    return None

def process_github_pending_commands(repo: str = "lucamancio1975-sys/Prezzi_Futures_Cereali") -> List[str]:
    """
    Interroga le Issue aperte e i commenti della Issue #1 per trovare comandi di conferma.
    Se ne trova, applica l'override del prezzo nel database, elimina le righe spurie (0.0 e lug-28)
    e sincronizza con GitHub.
    """
    token = get_github_token()
    if not token:
        return ["[WARN] Nessun GITHUB_TOKEN disponibile per verificare i comandi GitHub."]
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FuturesBot"
    }
    
    logs = []
    processed_count = 0
    
    # 1. Controlla commenti nell'Issue #1
    try:
        url_comments = f"https://api.github.com/repos/{repo}/issues/1/comments"
        req = urllib.request.Request(url_comments, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as resp:
            comments = json.loads(resp.read().decode())
            
        # Identifica gli ID dei commenti o comandi già processati in risposte precedenti
        processed_cids = set()
        for c in comments:
            b = c.get("body", "")
            for m in re.finditer(r'commento\s+([0-9]+)', b):
                processed_cids.add(int(m.group(1)))

        for c in comments:
            body = c.get("body", "")
            cid = c.get("id")
            if "[BOT_PROCESSED]" in body or "✅" in body:
                continue
            if cid in processed_cids:
                continue
                
            cmd = parse_command_text(body)
            if cmd:
                logs.append(f"[CMD TROVATO IN ISSUE #1] {cmd['raw']}")
                success = apply_quote_override(
                    data=cmd["data"],
                    prodotto=cmd["prodotto"],
                    tipo=cmd["tipo"],
                    scadenza=cmd["scadenza"],
                    prezzo=cmd["prezzo"],
                    nota=f"Confermato da utente via GitHub Issue #1 (commento {cid})"
                )
                if success:
                    # Preserva intatti i record storici di archivio (es. lug-28)
                    
                    # Push delle modifiche
                    storage_manager.sync_to_github(merge_remote=False)
                    
                    # Rispondi al commento confermando l'avvenuto aggiornamento
                    try:
                        reply_url = f"https://api.github.com/repos/{repo}/issues/1/comments"
                        reply_data = json.dumps({
                            "body": f"✅ [BOT_PROCESSED] Quotazione **{cmd['data']}** per **{cmd['prodotto']} ({cmd['tipo']} {cmd['scadenza']})** aggiornata con successo a **{cmd['prezzo']:.2f} €/t** nel database e riallineata all'app."
                        }).encode()
                        reply_req = urllib.request.Request(reply_url, data=reply_data, headers=headers)
                        with urllib.request.urlopen(reply_req, context=ctx):
                            pass
                    except Exception:
                        pass
                    
                    processed_count += 1
                    logs.append(f"[OK] Quotazione {cmd['data']} aggiornata a {cmd['prezzo']:.2f} Eur/ton.")
    except Exception as e:
        logs.append(f"[NOTA] Errore verifica commenti Issue #1: {e}")
        
    # 2. Controlla Nuove Issue aperte con label o comando
    try:
        url_issues = f"https://api.github.com/repos/{repo}/issues?state=open"
        req = urllib.request.Request(url_issues, headers=headers)
        with urllib.request.urlopen(req, context=ctx) as resp:
            issues = json.loads(resp.read().decode())
            
        for iss in issues:
            inum = iss.get("number")
            if inum == 1:
                continue  # Issue #1 è quella fissa dei commenti
                
            title = iss.get("title", "")
            body = iss.get("body", "")
            
            # Cerca nel titolo o nel body
            cmd = parse_command_text(body) or parse_command_text(title)
            if cmd:
                logs.append(f"[CMD TROVATO IN ISSUE #{inum}] {cmd['raw']}")
                success = apply_quote_override(
                    data=cmd["data"],
                    prodotto=cmd["prodotto"],
                    tipo=cmd["tipo"],
                    scadenza=cmd["scadenza"],
                    prezzo=cmd["prezzo"],
                    nota=f"Confermato da utente via GitHub Issue #{inum}"
                )
                if success:
                    # Preserva intatti i record storici di archivio (es. lug-28)
                        
                    storage_manager.sync_to_github(merge_remote=False)
                    
                    # Rispondi e chiudi l'issue
                    try:
                        reply_url = f"https://api.github.com/repos/{repo}/issues/{inum}/comments"
                        reply_data = json.dumps({
                            "body": f"✅ [BOT_PROCESSED] Quotazione **{cmd['data']}** per **{cmd['prodotto']} ({cmd['tipo']} {cmd['scadenza']})** aggiornata con successo a **{cmd['prezzo']:.2f} €/t** nel database."
                        }).encode()
                        reply_req = urllib.request.Request(reply_url, data=reply_data, headers=headers)
                        with urllib.request.urlopen(reply_req, context=ctx):
                            pass
                            
                        close_url = f"https://api.github.com/repos/{repo}/issues/{inum}"
                        close_data = json.dumps({"state": "closed"}).encode()
                        close_req = urllib.request.Request(close_url, data=close_data, headers=headers, method="PATCH")
                        with urllib.request.urlopen(close_req, context=ctx):
                            pass
                    except Exception:
                        pass
                        
                    processed_count += 1
                    logs.append(f"[OK] Issue #{inum} processata e chiusa.")
    except Exception as e:
        logs.append(f"[NOTA] Errore verifica issues aperte: {e}")
        
    logs.append(f"Elaborazione comandi completata: {processed_count} comandi eseguiti.")
    return logs

if __name__ == "__main__":
    for l in process_github_pending_commands():
        print(l)
