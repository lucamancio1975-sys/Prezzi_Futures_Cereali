"""
Modulo Deterministico per la connessione IMAP a Gmail e il recupero delle quotazioni di Grano Duro e Grano Tenero.
Supporta:
  1. Allegati PDF (Priorità 1 - massima velocità e precisione)
  2. Immagini con OCR (Priorità 2 - se nessun PDF presente o tabella inserita come immagine)
  3. Corpo email / Tabelle HTML (Priorità 3 - fallback per email solo testo o tabelle copiate)
Conforme all'architettura a 3 livelli (Livello 3 - Execution).
"""

import os
import imaplib
import email
from email.header import decode_header
import sys
import tempfile
import socket
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEC_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if EXEC_DIR not in sys.path:
    sys.path.insert(0, EXEC_DIR)

try:
    import execution.storage_manager as storage_manager
except Exception:
    import storage_manager

add_quotes = storage_manager.add_quotes
load_quotes = storage_manager.load_quotes
sync_from_github = getattr(storage_manager, "sync_from_github", lambda: 0)

try:
    import execution.parse_pdf_quotazioni as parse_pdf_quotazioni
except Exception:
    import parse_pdf_quotazioni

extract_quotes_from_pdf = parse_pdf_quotazioni.extract_quotes_from_pdf
extract_quotes_from_text = parse_pdf_quotazioni.extract_quotes_from_text

try:
    import execution.parse_image_quotazioni as parse_image_quotazioni
except Exception:
    import parse_image_quotazioni

extract_quotes_from_image = parse_image_quotazioni.extract_quotes_from_image

load_dotenv()

def decode_mime_words(s: str) -> str:
    """Decodifica stringhe con encoding MIME headers."""
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    res = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            res.append(fragment.decode(encoding or 'utf-8', errors='replace'))
        else:
            res.append(str(fragment))
    return "".join(res)

def fetch_quotes_from_gmail(
    user: str = None,
    password: str = None,
    server: str = "imap.gmail.com",
    folder: str = "INBOX",
    search_criteria: str = 'ALL',
    max_emails: int = 35,
    target_date: Optional[str] = None,
    stop_after_first_match: bool = False
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Si connette a Gmail via IMAP SSL, scansiona le ultime email ricevute,
    estrae le quotazioni di Grano Duro e Grano Tenero rispettando la gerarchia:
      1. Prima prova con l'allegato PDF (processo immediato e veloce)
      2. In caso di assenza PDF o assenza dati: prova OCR sulle immagini allegate/inline
      3. In caso di assenza immagini: interpreta il testo o tabella HTML del corpo email
    e le inserisce con deduplicazione nel database unico delle quotazioni.
    
    Se target_date è specificato (es. '2026-10-01'), ottimizza la ricerca:
    ispeziona prima l'header della data e si ferma immediatamente se l'email più
    recente risale a una data precedente (zero spreco di banda e tempo).
    
    Ritorna una tupla: (quotazioni_estratte, log_messaggi)
    """
    logs = []
    user = user or os.getenv("GMAIL_USER")
    password = password or os.getenv("GMAIL_APP_PASSWORD")

    # Supporto nativo per Secrets di Streamlit Community Cloud
    if not user or not password:
        try:
            import streamlit as st
            if not user and "GMAIL_USER" in st.secrets:
                user = st.secrets["GMAIL_USER"]
            if not password and "GMAIL_APP_PASSWORD" in st.secrets:
                password = st.secrets["GMAIL_APP_PASSWORD"]
        except Exception:
            pass

    # Credenziali predefinite del progetto (garantiscono connessione continua ovunque)
    user = user or "agriprecisione@gmail.com"
    password = password or "rjcxbatitqsuzjyg"

    all_extracted_quotes = []
    mail = None

    try:
        logs.append(f"Connessione sicura al server quotazioni ({server})...")
        # FIX: timeout realistico (il download di email con PDF supera facilmente 3.5s)
        mail = imaplib.IMAP4_SSL(server, timeout=20)
        mail.login(user, password)
        mail.select(folder)
        logs.append("Connessione stabilita con successo.")

        # FIX: invece di guardare solo le ultime N email della casella (che possono essere
        # tutte non pertinenti), cerca tutte le email arrivate dall'ultima data in archivio.
        if search_criteria == 'ALL':
            from datetime import datetime as _dt, timedelta as _td
            last_d = getattr(storage_manager, "get_latest_db_date", lambda: "")()
            try:
                since_dt = _dt.strptime(last_d, "%Y-%m-%d") - _td(days=1)
            except Exception:
                since_dt = _dt.now() - _td(days=30)
            _mesi = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            search_criteria = f'(SINCE "{since_dt.day:02d}-{_mesi[since_dt.month-1]}-{since_dt.year}")'
            # Con ricerca per data non serve limitare il numero di email
            max_emails = max(max_emails, 200)

        status, data = mail.search(None, search_criteria)
        if status != 'OK' or not data[0]:
            logs.append("Nessuna email nuova trovata nella casella.")
            mail.logout()
            return [], logs

        mail_ids = data[0].split()
        n_scan = min(len(mail_ids), max_emails)
        logs.append(f"Trovate {len(mail_ids)} email ({search_criteria}). Esame delle ultime {n_scan}...")

        # Esamina le email dalla più recente a ritroso
        recent_ids = mail_ids[-n_scan:]
        recent_ids.reverse()

        # Carica le date già archiviate nel database per evitare download e OCR ridondanti
        existing_quotes = load_quotes()
        existing_dates = set(q.get("data") for q in existing_quotes if q.get("data"))
        latest_db_date = getattr(storage_manager, "get_latest_db_date", lambda: "")()

        for mid in recent_ids:
            # 1. Ispezione rapida preliminare dell'header (millisecondi)
            hdr_res, hdr_data = mail.fetch(mid, '(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])')
            subject = ""
            sender = ""
            date_hdr = ""
            email_date = None

            if hdr_res == 'OK' and hdr_data and hdr_data[0]:
                hdr_msg = email.message_from_bytes(hdr_data[0][1])
                subject = decode_mime_words(hdr_msg.get("Subject", ""))
                sender = decode_mime_words(hdr_msg.get("From", ""))
                date_hdr = hdr_msg.get("Date", "")
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(date_hdr)
                    if parsed_dt:
                        email_date = parsed_dt.astimezone().strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Se cerchiamo specificamente una target_date, verifica corrispondenza
            if target_date and email_date and email_date != target_date:
                # Se l'email ha una data diversa da quella cercata, passa oltre senza interrompere la scansione
                continue

            # Filtro di pertinenza su oggetto o mittente predefinito
            subj_lower = subject.lower()
            sender_lower = sender.lower()
            is_relevant = any(k in subj_lower for k in [
                "quotazion", "futures", "pdt", "pmg", "grano", "prezzi", "tenero", "duro"
            ]) or "consorziagrari" in sender_lower

            if not is_relevant:
                continue

            # Ottimizzazione turbo: se questa data è già archiviata nel DB, salta download e OCR pesanti
            if email_date and email_date in existing_dates:
                if latest_db_date and email_date < latest_db_date:
                    logs.append(f"Email del {email_date} già a catalogo: arresto rapido scansione.")
                    break
                continue

            # Filtro mittente consentito (opzionale tramite GMAIL_ALLOWED_SENDERS)
            allowed_senders_cfg = os.getenv("GMAIL_ALLOWED_SENDERS", "").strip()
            if allowed_senders_cfg:
                allowed_list = [s.strip().lower() for s in allowed_senders_cfg.split(",") if s.strip()]
                if not any(a in sender_lower for a in allowed_list):
                    continue

            # 2. Scarica il messaggio completo solo per email pertinente e con data nuova
            res, msg_data = mail.fetch(mid, '(RFC822)')
            if res != 'OK':
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            if not email_date:
                try:
                    parsed_dt = email.utils.parsedate_to_datetime(msg.get("Date", ""))
                    if parsed_dt:
                        email_date = parsed_dt.astimezone().strftime("%Y-%m-%d")
                except Exception:
                    pass

            extracted_from_this_email = []
            with tempfile.TemporaryDirectory() as tmp_dir:
                pdf_parts = []
                image_parts = []
                text_parts = []

                for part in msg.walk():
                    content_type = part.get_content_type()
                    filename = part.get_filename()
                    if filename:
                        filename = decode_mime_words(filename)

                    # Classificazione delle componenti del messaggio
                    if (filename and filename.lower().endswith(".pdf")) or content_type == "application/pdf":
                        pdf_parts.append((part, filename or "documento.pdf"))
                    elif (filename and any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg"])) or \
                         (content_type.startswith("image/") and "image" in content_type):
                        image_parts.append((part, filename or "tabella_quotazioni.png"))
                    elif content_type in ["text/plain", "text/html"]:
                        text_parts.append((part, content_type))

                # -------------------------------------------------------------
                # PASSAGGIO 1: Priorità ad allegati PDF (il metodo più veloce)
                # -------------------------------------------------------------
                for part, fname in pdf_parts:
                    filepath = os.path.join(tmp_dir, fname)
                    with open(filepath, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    logs.append(f"Trovato allegato PDF: '{fname}' (Email: '{subject}')")
                    try:
                        quotes = extract_quotes_from_pdf(filepath)
                        for q in quotes:
                            if email_date and (not q.get("data") or q.get("data") == email_date):
                                q["data"] = email_date
                        if quotes:
                            extracted_from_this_email.extend(quotes)
                            logs.append(f" -> Estratte {len(quotes)} quotazioni dal PDF '{fname}'.")
                    except Exception as err:
                        logs.append(f" -> Avviso parsing PDF '{fname}': {err}")

                # -------------------------------------------------------------
                # PASSAGGIO 2: Se assente PDF o senza dati, OCR su immagini
                # -------------------------------------------------------------
                if not extracted_from_this_email:
                    for part, fname in image_parts:
                        filepath = os.path.join(tmp_dir, fname)
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        try:
                            quotes = extract_quotes_from_image(filepath, fallback_date=email_date)
                            if quotes:
                                extracted_from_this_email.extend(quotes)
                                logs.append(f" -> Estratte {len(quotes)} quotazioni da immagine/tabella '{fname}' (Email: '{subject}').")
                                break
                        except Exception as err:
                            logs.append(f" -> Avviso parsing immagine '{fname}': {err}")

                # -------------------------------------------------------------
                # PASSAGGIO 3: Se assenti immagini, interpretazione corpo email
                # -------------------------------------------------------------
                if not extracted_from_this_email and is_relevant:
                    for part, ctype in text_parts:
                        try:
                            payload = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            if any(k in payload.lower() for k in ["grano duro", "grano tenero", "eur/ton", "€/t"]):
                                quotes = extract_quotes_from_text(payload, source_name=f"Email ({subject[:30]})")
                                for q in quotes:
                                    if email_date and (not q.get("data") or q.get("data") == email_date):
                                        q["data"] = email_date
                                if quotes:
                                    extracted_from_this_email.extend(quotes)
                                    logs.append(f" -> Estratte {len(quotes)} quotazioni dal corpo/tabella email: '{subject}'.")
                                    break
                        except Exception:
                            pass

            if extracted_from_this_email:
                all_extracted_quotes.extend(extracted_from_this_email)
                if target_date or stop_after_first_match:
                    logs.append(f"Trovata quotazione per la data richiesta ({email_date}): arresto rapido scansione.")
                    break

    except Exception as e:
        logs.append(f"[ERRORE] Errore durante il collegamento o sincronizzazione Gmail: {str(e)}")
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass

    # FIX: salva SEMPRE quanto estratto, anche se la connessione si è interrotta a metà
    if all_extracted_quotes:
        added = add_quotes(all_extracted_quotes, push_github=False)
        logs.append(f"[OK] Sincronizzazione completata: {added} nuove quotazioni archiviate nel database.")
    else:
        logs.append("[INFO] Nessuna nuova quotazione rilevata nelle email scansionate.")

    return all_extracted_quotes, logs

def check_and_sync_today_quotes(target_date: Optional[str] = None, scan_depth: int = 5) -> Tuple[List[Dict[str, Any]], bool, List[str]]:
    """
    Funzione ultra-rapida richiamata all'apertura dell'app Streamlit.
    Flusso ottimizzato per avvio < 3 secondi:
      1. Controlla PRIMA il database locale (zero rete, < 1ms).
      2. Se manca la data odierna, tenta sync rapido da GitHub (timeout 2s).
      3. Se ancora assente, scansiona Gmail IMAP (solo 3-5 email recenti, early-exit).
      4. Il push verso GitHub avviene in modo differito (non blocca l'interfaccia).
    """
    from datetime import datetime
    import threading
    logs = []
    oggi_str = target_date or datetime.now().strftime("%Y-%m-%d")
    
    # FASE 0: Controlla immediatamente il DB locale (< 1ms, zero rete)
    local_quotes = load_quotes()
    if any(q.get("data") == oggi_str for q in local_quotes):
        logs.append(f"🟢 Database già aggiornato alla data odierna ({oggi_str}).")
        return [], True, logs

    # FASE 1: Sync rapido dal repository GitHub (timeout 2s)
    try:
        n_github = sync_from_github()
        if n_github > 0:
            logs.append(f"☁️ Sincronizzate {n_github} quotazioni dal repository cloud GitHub.")
            # Ricontrolla dopo il sync
            refreshed = load_quotes()
            if any(q.get("data") == oggi_str for q in refreshed):
                logs.append(f"🟢 Database aggiornato via cloud ({oggi_str}).")
                return [], True, logs
    except Exception as e:
        logs.append(f"Nota sync cloud: {e}")

    # FASE 2: Scansione Gmail IMAP (solo email recenti, early-exit appena trovata la data)
    # FIX: recupera TUTTE le email nuove dall'ultima data in archivio (non solo la prima)
    extracted_quotes, gmail_logs = fetch_quotes_from_gmail(
        max_emails=scan_depth,
        target_date=None,
        stop_after_first_match=False
    )
    logs.extend(gmail_logs)
    for line in gmail_logs:
        print(f"[GMAIL SYNC] {line}")

    # Ricarica lo storico aggiornato
    updated_quotes = load_quotes()
    is_today_present = any(q.get("data") == oggi_str for q in updated_quotes)
    
    # FASE 3: Push differito a GitHub in background (non blocca l'interfaccia)
    # FIX: push sempre quando ci sono nuovi dati (prima solo se presente la data odierna,
    # così le quotazioni dei giorni precedenti andavano perse al riavvio del server cloud)
    if extracted_quotes:
        def _bg_push():
            try:
                storage_manager.sync_to_github()
            except Exception:
                pass
        threading.Thread(target=_bg_push, daemon=True).start()
    
    return extracted_quotes, is_today_present, logs

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print("Collaudo sincronizzazione Gmail per Grano Duro e Grano Tenero...")
    q, l = fetch_quotes_from_gmail(max_emails=5)
    for line in l:
        print(line)
