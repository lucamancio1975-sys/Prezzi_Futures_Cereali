"""
Modulo di Pre-avvio Deterministico (Boot Sync).
Eseguito all'avvio dell'applicazione su PC (tramite avvia_app.bat / avvia_locale.bat).
Verifica se le quotazioni per la data odierna (e giorni lavorativi precedenti) sono già
presenti nel database locale o su GitHub.
- Se già presenti: termina in <0.2 secondi senza ritardi.
- Se mancanti: contatta Gmail, estrae le quotazioni (PDF/OCR) e le sincronizza su GitHub.
- Non blocca mai l'avvio dell'app in caso di mancata connessione a Internet.
"""

import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def run_boot_sync():
    print("---------------------------------------------------------------")
    print(" [BOOT] Controllo allineamento quotazioni odierne...")
    print("---------------------------------------------------------------")
    
    try:
        from execution import storage_manager
        from execution.fetch_gmail_quotes import check_and_sync_today_quotes
        
        # 1. Verifica se mancano giorni lavorativi
        missing = storage_manager.get_missing_business_days()
        oggi = storage_manager.oggi_italia().isoformat()
        
        if not missing:
            print(f" [OK] Database gia' allineato ({oggi}). Avvio immediato.")
            return True
            
        print(f" [INFO] Mancano {len(missing)} sedute lavorative ({', '.join(missing)}).")
        print(" [INFO] Connessione a Gmail ed estrazione ultime quotazioni...")
        
        start_t = time.time()
        new_q, is_today, logs = check_and_sync_today_quotes(scan_depth=10)
        dur = round(time.time() - start_t, 1)
        
        for l in logs:
            try:
                print(f"   -> {l}")
            except Exception:
                pass
                
        if new_q:
            print(f" [OK] Acquisite con successo {len(new_q)} nuove quotazioni in {dur}s.")
        else:
            print(f" [INFO] Nessuna nuova quotazione disponibile nella casella Gmail ({dur}s).")
            
        return True
    except Exception as e:
        print(f" [AVVISO] Controllo quotazioni saltato ({e}). Procedo con l'avvio offline...")
        return False

if __name__ == "__main__":
    run_boot_sync()
