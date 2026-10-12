"""
Micro Web Server Locale Resiliente con Endpoint API di Sincronizzazione Gmail.
Supporta:
  1. Servizio file statici (HTML, CSS, JS, immagini, manifest, service worker)
  2. Endpoint /api/sync per triggerare la sincronizzazione Gmail in tempo reale
     direttamente dal pulsante nell'interfaccia utente.
  3. Header no-cache sui file dati (JSON/CSV) per garantire aggiornamento immediato.
"""

import sys
import os
import json
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

class LocalAppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        # Disabilita cache su JSON e CSV per riflettere istantaneamente i nuovi dati
        path_lower = self.path.lower()
        if any(path_lower.endswith(ext) or ext in path_lower for ext in ['.json', '.csv', '/api/']):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        url_path = self.path.split('?')[0]

        if url_path == '/api/sync':
            self.handle_api_sync()
        elif url_path == '/api/status':
            self.handle_api_status()
        else:
            super().do_GET()

    def handle_api_sync(self):
        """Esegue la sincronizzazione Gmail su richiesta del pulsante nell'app."""
        try:
            from execution import storage_manager
            from execution.fetch_gmail_quotes import check_and_sync_today_quotes

            new_q, is_today, logs = check_and_sync_today_quotes(scan_depth=10)
            all_q = storage_manager.load_quotes()
            latest_d = storage_manager.get_latest_db_date()

            response_data = {
                "success": True,
                "new_quotes_count": len(new_q),
                "is_today_present": is_today,
                "latest_date": latest_d,
                "total_quotes": len(all_q),
                "logs": logs[-5:] if logs else [],
                "timestamp": time.time()
            }
            status_code = 200
        except Exception as e:
            response_data = {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
            status_code = 500

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

    def handle_api_status(self):
        """Restituisce lo stato corrente del database locale."""
        try:
            from execution import storage_manager
            all_q = storage_manager.load_quotes()
            latest_d = storage_manager.get_latest_db_date()
            oggi_str = storage_manager.oggi_italia().isoformat()
            missing = storage_manager.get_missing_business_days()

            response_data = {
                "success": True,
                "today": oggi_str,
                "latest_date": latest_d,
                "total_quotes": len(all_q),
                "missing_days": missing,
                "is_today_present": latest_d == oggi_str
            }
            status_code = 200
        except Exception as e:
            response_data = {"success": False, "error": str(e)}
            status_code = 500

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))

def run_server(port: int = 8088):
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, LocalAppHandler)
    print(f" [OK] Micro-server avviato con successo su http://localhost:{port}")
    print(f" [INFO] Servizio file statici + Endpoint API /api/sync attivi.")
    print(" [INFO] Premi Ctrl+C o chiudi questa finestra per arrestare il server.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto del server...")
        httpd.server_close()

if __name__ == "__main__":
    p = 8088
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except ValueError:
            pass
    run_server(p)
