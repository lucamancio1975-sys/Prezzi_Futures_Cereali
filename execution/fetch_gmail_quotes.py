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
import tempfile
import socket
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

try:
    from execution.parse_pdf_quotazioni import extract_quotes_from_pdf, extract_quotes_from_text
    from execution.parse_image_quotazioni import extract_quotes_from_image
    from execution.storage_manager import add_quotes
except ImportError:
    from parse_pdf_quotazioni import extract_quotes_from_pdf, extract_quotes_from_text
    from parse_image_quotazioni import extract_quotes_from_image
    from storage_manager import add_quotes

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
    max_emails: int = 35
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Si connette a Gmail via IMAP SSL, scansiona le ultime email ricevute,
    estrae le quotazioni di Grano Duro e Grano Tenero rispettando la gerarchia:
      1. Prima prova con l'allegato PDF (processo immediato e veloce)
      2. In caso di assenza PDF o assenza dati: prova OCR sulle immagini allegate/inline
      3. In caso di assenza immagini: interpreta il testo o tabella HTML del corpo email
    e le inserisce con deduplicazione nel database unico delle quotazioni.
    
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

    if not user or not password:
        logs.append("⚠️ Credenziali Gmail non configurate (impostare GMAIL_USER e GMAIL_APP_PASSWORD nel file .env o nei Secrets di Streamlit).")
        return [], logs

    all_extracted_quotes = []
    socket.setdefaulttimeout(14.0)

    try:
        logs.append(f"Connessione sicura al server quotazioni ({server})...")
        mail = imaplib.IMAP4_SSL(server, timeout=14.0)
        mail.login(user, password)
        mail.select(folder)
        logs.append("Connessione stabilita con successo.")

        status, data = mail.search(None, search_criteria)
        if status != 'OK' or not data[0]:
            logs.append("Nessuna email trovata nella casella.")
            mail.logout()
            return [], logs

        mail_ids = data[0].split()
        logs.append(f"Trovate {len(mail_ids)} email totali. Esame delle ultime {min(len(mail_ids), max_emails)}...")

        # Esamina le email dalla più recente a ritroso
        recent_ids = mail_ids[-max_emails:]
        recent_ids.reverse()

        for mid in recent_ids:
            res, msg_data = mail.fetch(mid, '(RFC822)')
            if res != 'OK':
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = decode_mime_words(msg.get("Subject", ""))
            sender = decode_mime_words(msg.get("From", ""))
            date_hdr = msg.get("Date", "")

            # Filtro di pertinenza
            subj_lower = subject.lower()
            sender_lower = sender.lower()
            is_relevant = any(k in subj_lower for k in [
                "quotazion", "futures", "pdt", "pmg", "grano", "prezzi", "tenero", "duro"
            ]) or "consorziagrari" in sender_lower

            email_date = None
            try:
                parsed_tuple = email.utils.parsedate_to_datetime(date_hdr)
                if parsed_tuple:
                    email_date = parsed_tuple.strftime("%Y-%m-%d")
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

        mail.logout()

        # Deduplica e memorizzazione nel database
        if all_extracted_quotes:
            added = add_quotes(all_extracted_quotes)
            logs.append(f"[OK] Sincronizzazione completata: {added} nuove quotazioni archiviate nel database.")
        else:
            logs.append("[INFO] Nessuna nuova quotazione rilevata nelle email scansionate.")

    except Exception as e:
        logs.append(f"[ERRORE] Errore durante il collegamento o sincronizzazione Gmail: {str(e)}")

    return all_extracted_quotes, logs

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
