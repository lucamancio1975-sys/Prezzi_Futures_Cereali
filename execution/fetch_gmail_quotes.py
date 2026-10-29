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

# Indirizzi email autorizzati dai quali pervengono le quotazioni ufficiali CAI
OFFICIAL_SENDERS = [
    "carlo.citroni@consorziagrariditalia.it",
    "giacomo.stocco@consorziagrariditalia.it",
]

def is_relevant_email(subject: str, sender: str) -> bool:
    """
    Verifica se un'email è pertinente per l'estrazione delle quotazioni.
    Riconosce:
      1. I due mittenti ufficiali CAI:
         - Carlo Citroni (carlo.citroni@consorziagrariditalia.it)
         - Giacomo Stocco (giacomo.stocco@consorziagrariditalia.it)
         oltre a parole chiave mittente ('citroni', 'stocco', 'consorziagrariditalia', 'consorziagrari').
      2. Parole chiave nell'oggetto della mail relative alle quotazioni futures cereali.
    """
    subj_lower = (subject or "").lower()
    sender_lower = (sender or "").lower()

    sender_matches = any(s in sender_lower for s in [
        "carlo.citroni@consorziagrariditalia.it",
        "giacomo.stocco@consorziagrariditalia.it",
        "citroni",
        "stocco",
        "consorziagrariditalia",
        "consorziagrari"
    ])

    subject_matches = any(k in subj_lower for k in [
        "quotazion", "futures", "pdt", "pmg", "grano", "prezzi", "tenero", "duro"
    ])

    return sender_matches or subject_matches

def safe_print(msg: str):
    """Stampa messaggi in console in modo resiliente anche con emoji su Windows (cp1252)."""
    try:
        print(msg)
    except (UnicodeEncodeError, Exception):
        try:
            enc = sys.stdout.encoding or "utf-8"
            print(msg.encode(enc, errors="replace").decode(enc))
        except Exception:
            pass

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

def send_alert_email(
    anomalies: List[Dict[str, Any]],
    user: Optional[str] = None,
    password: Optional[str] = None,
    recipient: str = "agriprecisione@gmail.com"
) -> bool:
    """
    Invia un'email di alert alla casella specificata quando una o più quotazioni
    estratte presentano uno scostamento anomalo (> 5.01 €/t) rispetto all'ultimo prezzo valido.
    """
    import smtplib
    from email.mime.text import MIMEText

    user = user or os.getenv("GMAIL_USER") or "agriprecisione@gmail.com"
    password = password or os.getenv("GMAIL_APP_PASSWORD") or "rjcxbatitqsuzjyg"

    corpo_righe = [
        "ATTENZIONE: Rilevata anomalia nell'estrazione delle quotazioni Cereali / Futures.",
        "Una o piu' quotazioni presentano uno scostamento superiore a 5.01 Eur/ton rispetto all'ultima quotazione valida registrata.",
        "Nel database il valore anomalo e' stato impostato cautelativamente a 0.0 (Dato non disponibile / Fuori standard).",
        "",
        "--- DETTAGLIO ANOMALIE RILEVATE ---"
    ]

    for an in anomalies:
        d = an.get("data", "N.D.")
        prod = an.get("prodotto", "")
        tipo = an.get("tipo", "")
        scad = an.get("scadenza", "")
        p_estratto = an.get("prezzo_estratto", 0.0)
        p_prec = an.get("prezzo_precedente", 0.0)
        scost = an.get("scostamento", 0.0)
        fonte = an.get("fonte", "Email")
        corpo_righe.append(
            f"- Data: {d} | Prodotto: {prod} ({tipo}) Scadenza: {scad}\n"
            f"  Prezzo estratto rilevato: {p_estratto:.2f} Eur/ton\n"
            f"  Ultimo prezzo valido precedente: {p_prec:.2f} Eur/ton\n"
            f"  Scostamento rilevato: {scost:+.2f} Eur/ton (Soglia max tollerata: 5.00 Eur/ton)\n"
            f"  Fonte: {fonte}\n"
        )

    corpo_righe.extend([
        "Azione consigliata: verificare il layout dell'email ricevuta da CAI o eventuali variazioni straordinarie di mercato,",
        "e correggere manualmente la quotazione nel database se il prezzo era effettivo o correggere il parser.",
        "",
        "Messaggio generato automaticamente dal Monitor Futures Cereali."
    ])

    corpo_msg = "\n".join(corpo_righe)

    msg = MIMEText(corpo_msg, 'plain', 'utf-8')
    msg['Subject'] = f"ALLERTA: Quotazione fuori standard ({len(anomalies)} serie con scostamento > 5 Eur/ton)"
    msg['From'] = user
    msg['To'] = recipient

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as srv:
            srv.login(user, password)
            srv.send_message(msg)
        safe_print(f"[ALERT EMAIL] Inviata email di allerta a {recipient} con successo.")
        return True
    except Exception as e:
        safe_print(f"[ALERT EMAIL] Errore invio email di allerta a {recipient}: {e}")
        return False

def validate_quote_deviations(
    quotes_list: List[Dict[str, Any]],
    max_allowed_delta: float = 5.01,
    send_email: bool = True
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Confronta ogni quotazione estratta con l'ultima quotazione valida precedente (prezzo > 0)
    per la medesima serie (prodotto, tipo, scadenza):
      - Se lo scostamento è <= 5.00 €/t (o < 5.01 €/t), la quotazione è accettata.
      - Se lo scostamento è > 5.01 €/t (o >= 5.01 €/t), imposta cautelativamente il prezzo a 0.0 (000),
        registra l'anomalia e invia una email di allerta ad agriprecisione@gmail.com.
    Ritorna: (quotes_sanificate, lista_anomalie, log_messaggi)
    """
    get_last_price = getattr(storage_manager, "get_last_valid_price", None)
    sanitized_quotes = []
    anomalies = []
    logs = []

    # Ordina cronologicamente per verificare con coerenza
    quotes_sorted = sorted(quotes_list, key=lambda x: x.get("data", ""))

    for q in quotes_sorted:
        d = q.get("data")
        prod = q.get("prodotto", "GRANO DURO")
        tipo = q.get("tipo", "PDT")
        scad = q.get("scadenza", "lug-27")
        try:
            prz = float(q.get("prezzo", 0) or 0)
        except Exception:
            prz = 0.0

        # Se già 0, non valutare scostamento
        if prz <= 0:
            sanitized_quotes.append(q)
            continue

        prev_price = None
        if get_last_price:
            prev_price = get_last_price(prod, tipo, scad, before_date=d)

        # Se non esiste storico precedente valido, accetta il dato come primo riferimento
        if prev_price is None or prev_price <= 0:
            sanitized_quotes.append(q)
            continue

        delta = abs(prz - prev_price)
        if delta >= max_allowed_delta:
            anomalia = {
                "data": d,
                "prodotto": prod,
                "tipo": tipo,
                "scadenza": scad,
                "prezzo_estratto": prz,
                "prezzo_precedente": prev_price,
                "scostamento": prz - prev_price,
                "fonte": q.get("fonte", "Email")
            }
            anomalies.append(anomalia)
            logs.append(
                f"[SCARTATO PER ANOMALIA] {d} {prod} {tipo} {scad}: letto {prz:.2f} €/t "
                f"ma ultimo precedente era {prev_price:.2f} €/t (delta={delta:.2f} > {max_allowed_delta:.2f} €/t). "
                f"Impostato cautelativamente a 0.0 nel database."
            )
            # Clona dizionario e imposta prezzo a 0.0 (000)
            q_anomalo = dict(q)
            q_anomalo["prezzo"] = 0.0
            q_anomalo["note_anomalia"] = f"Prezzo rilevato fuori standard ({prz:.2f} vs prec {prev_price:.2f})"
            sanitized_quotes.append(q_anomalo)
        else:
            sanitized_quotes.append(q)

    if anomalies and send_email:
        send_alert_email(anomalies)

    return sanitized_quotes, anomalies, logs

def fetch_quotes_from_gmail(
    user: str = None,
    password: str = None,
    server: str = "imap.gmail.com",
    folder: str = "INBOX",
    search_criteria: str = 'ALL',
    max_emails: int = 35,
    target_date: Optional[str] = None,
    stop_after_first_match: bool = False,
    since_date: Optional[str] = None
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
    global LAST_FETCH_OK
    LAST_FETCH_OK = False
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

        # Ricerca per data: tutte le email arrivate dal primo giorno mancante (since_date)
        # oppure, in assenza, dal giorno precedente l'ultima data in archivio.
        if search_criteria == 'ALL':
            from datetime import datetime as _dt, timedelta as _td
            since_dt = None
            if since_date:
                try:
                    since_dt = _dt.strptime(since_date, "%Y-%m-%d") - _td(days=1)
                except Exception:
                    since_dt = None
            if since_dt is None:
                last_d = getattr(storage_manager, "get_latest_db_date", lambda: "")()
                try:
                    since_dt = _dt.strptime(last_d, "%Y-%m-%d") - _td(days=1)
                except Exception:
                    since_dt = _dt.now() - _td(days=30)
            _mesi = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            search_criteria = f'(SINCE "{since_dt.day:02d}-{_mesi[since_dt.month-1]}-{since_dt.year}")'
            # Con ricerca per data non serve limitare il numero di email
            max_emails = max(max_emails, 500)

        status, data = mail.search(None, search_criteria)
        if status != 'OK' or not data[0]:
            logs.append("Nessuna email nuova trovata nella casella.")
            LAST_FETCH_OK = (status == 'OK')
            mail.logout()
            return [], logs

        mail_ids = data[0].split()
        n_scan = min(len(mail_ids), max_emails)
        logs.append(f"Trovate {len(mail_ids)} email ({search_criteria}). Esame delle ultime {n_scan}...")

        # Esamina le email dalla più recente a ritroso
        recent_ids = mail_ids[-n_scan:]
        recent_ids.reverse()

        # Carica le date già archiviate (e COMPLETE: duro + tenero PDT/PMG) nel database per
        # evitare download e OCR ridondanti. Le date con dati parziali vengono rilette.
        existing_quotes = load_quotes()
        _complete = getattr(storage_manager, "get_complete_dates", None)
        existing_dates = _complete(existing_quotes) if _complete else set(q.get("data") for q in existing_quotes if q.get("data"))

        # Lettura degli header IN BLOCCO (una sola richiesta IMAP ogni 100 email invece di una
        # per email): permette di coprire anche settimane di email in pochi istanti.
        headers_map: Dict[bytes, bytes] = {}
        for i in range(0, len(recent_ids), 100):
            chunk = recent_ids[i:i + 100]
            try:
                r, hd = mail.fetch(b",".join(chunk), '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
                if r == 'OK':
                    for item in hd:
                        if isinstance(item, tuple) and len(item) >= 2:
                            headers_map[item[0].split()[0]] = item[1]
            except Exception:
                pass

        for mid in recent_ids:
            # 1. Ispezione preliminare dell'header (già scaricato in blocco)
            hdr_bytes = headers_map.get(mid)
            if hdr_bytes is None:
                hdr_res, hdr_data = mail.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])')
                if hdr_res == 'OK' and hdr_data and isinstance(hdr_data[0], tuple):
                    hdr_bytes = hdr_data[0][1]
            subject = ""
            sender = ""
            date_hdr = ""
            email_date = None

            if hdr_bytes:
                hdr_msg = email.message_from_bytes(hdr_bytes)
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

            # Filtro di pertinenza su oggetto o mittente autorizzato (Citroni, Stocco, CAI)
            sender_lower = sender.lower()
            is_relevant = is_relevant_email(subject, sender)

            if not is_relevant:
                continue

            # Se questa data è già archiviata nel DB salta download e OCR pesanti.
            # NB: niente più arresto della scansione qui, altrimenti i giorni mancanti
            # più vecchi (periodi di inutilizzo dell'app) non verrebbero mai recuperati.
            if email_date and email_date in existing_dates:
                continue

            # Filtro mittente consentito (opzionale tramite GMAIL_ALLOWED_SENDERS)
            allowed_senders_cfg = os.getenv("GMAIL_ALLOWED_SENDERS", "").strip()
            if allowed_senders_cfg:
                allowed_list = [s.strip().lower() for s in allowed_senders_cfg.split(",") if s.strip()]
                if not any(a in sender_lower for a in allowed_list):
                    continue

            # 2. Scarica il messaggio completo solo per email pertinente e con data nuova
            res, msg_data = mail.fetch(mid, '(BODY.PEEK[])')
            if res != 'OK' or not msg_data or not isinstance(msg_data[0], tuple):
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

                # Helper per verificare se sono presenti tutte le serie principali
                def _has_all_series(quotes_list):
                    keys = set((q.get("prodotto", "").upper(), q.get("tipo", "").upper()) for q in quotes_list)
                    has_duro = any("DURO" in p for p, _ in keys)
                    has_tenero_pmg = ("GRANO TENERO FINO ROSSO", "PMG") in keys
                    has_tenero_pdt = ("GRANO TENERO FINO ROSSO", "PDT") in keys
                    return has_duro and has_tenero_pmg and has_tenero_pdt

                def _merge_quotes(primary, secondary):
                    """Unisce secondary in primary senza sovrascrivere le chiavi già estratte."""
                    existing_keys = set((q.get("data"), q.get("prodotto"), q.get("tipo"), q.get("scadenza")) for q in primary)
                    for q in secondary:
                        k = (q.get("data"), q.get("prodotto"), q.get("tipo"), q.get("scadenza"))
                        if k not in existing_keys:
                            primary.append(q)
                            existing_keys.add(k)
                    return primary

                # -------------------------------------------------------------
                # PASSAGGIO 1 (Priorità 1): Allegato PDF (massima accuratezza vettoriale)
                # -------------------------------------------------------------
                if pdf_parts:
                    for part, fname in pdf_parts:
                        filepath = os.path.join(tmp_dir, fname)
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        logs.append(f"Ispezione allegato PDF: '{fname}' (Email: '{subject}')")
                        try:
                            quotes = extract_quotes_from_pdf(filepath)
                            for q in quotes:
                                if email_date and (not q.get("data") or q.get("data") == email_date):
                                    q["data"] = email_date
                            if quotes:
                                _merge_quotes(extracted_from_this_email, quotes)
                                logs.append(f" -> Integrate {len(quotes)} quotazioni dal PDF '{fname}'.")
                                if _has_all_series(extracted_from_this_email):
                                    break
                        except Exception as err:
                            logs.append(f" -> Avviso parsing PDF '{fname}': {err}")

                # -------------------------------------------------------------
                # PASSAGGIO 2 (Priorità 2): OCR su immagini e tabelle (fallback se assente PDF o serie incomplete)
                # -------------------------------------------------------------
                if image_parts and not _has_all_series(extracted_from_this_email):
                    image_parts_loaded = []
                    for part, fname in image_parts:
                        p_data = part.get_payload(decode=True)
                        if p_data:
                            image_parts_loaded.append((fname, p_data))
                    # Analizza prima le immagini con payload maggiore (tabelle quotazioni > firme/loghi)
                    image_parts_loaded.sort(key=lambda item: len(item[1]), reverse=True)

                    for fname, p_data in image_parts_loaded:
                        filepath = os.path.join(tmp_dir, fname)
                        with open(filepath, "wb") as f:
                            f.write(p_data)
                        try:
                            quotes = extract_quotes_from_image(filepath, fallback_date=email_date)
                            if quotes:
                                _merge_quotes(extracted_from_this_email, quotes)
                                logs.append(f" -> Estratte {len(quotes)} quotazioni da immagine/tabella OCR '{fname}' (Email: '{subject}').")
                                if _has_all_series(extracted_from_this_email):
                                    break
                        except Exception as err:
                            logs.append(f" -> Avviso parsing immagine '{fname}': {err}")

                # -------------------------------------------------------------
                # PASSAGGIO 3 (Priorità 3): Interpretazione testo / tabelle HTML nel corpo email
                # -------------------------------------------------------------
                if not _has_all_series(extracted_from_this_email) and is_relevant:
                    for part, ctype in text_parts:
                        try:
                            payload = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            if any(k in payload.lower() for k in ["grano duro", "grano tenero", "eur/ton", "€/t"]):
                                quotes = extract_quotes_from_text(payload, source_name=f"Email ({subject[:30]})")
                                for q in quotes:
                                    if email_date and (not q.get("data") or q.get("data") == email_date):
                                        q["data"] = email_date
                                if quotes:
                                    _merge_quotes(extracted_from_this_email, quotes)
                                    logs.append(f" -> Integrate {len(quotes)} quotazioni dal corpo/tabella email: '{subject}'.")
                                    if _has_all_series(extracted_from_this_email):
                                        break
                        except Exception:
                            pass

            if extracted_from_this_email:
                all_extracted_quotes.extend(extracted_from_this_email)
                if target_date or stop_after_first_match:
                    logs.append(f"Trovata quotazione per la data richiesta ({email_date}): arresto rapido scansione.")
                    break

        LAST_FETCH_OK = True
    except Exception as e:
        logs.append(f"[ERRORE] Errore durante il collegamento o sincronizzazione Gmail: {str(e)}")
    finally:
        if mail is not None:
            try:
                mail.logout()
            except Exception:
                pass

    # Validazione scostamento giornaliero prima di salvare nel database
    # Se il discostamento > 5.01 €/t scrive 0.0 (000) e manda alert email ad agriprecisione@gmail.com
    if all_extracted_quotes:
        validated_quotes, anomalies, val_logs = validate_quote_deviations(all_extracted_quotes, max_allowed_delta=5.01, send_email=True)
        logs.extend(val_logs)
        added = add_quotes(validated_quotes, push_github=False)
        logs.append(f"[OK] Sincronizzazione completata: {added} nuove quotazioni archiviate nel database.")
        all_extracted_quotes = validated_quotes
    else:
        logs.append("[INFO] Nessuna nuova quotazione rilevata nelle email scansionate.")

    return all_extracted_quotes, logs

def check_and_sync_today_quotes(target_date: Optional[str] = None, scan_depth: int = 5) -> Tuple[List[Dict[str, Any]], bool, List[str]]:
    """
    Workflow eseguito ad ogni apertura dell'app (click su icona o link):
      1. Scarica il database da GitHub e lo fonde nel DB locale (se un altro utente ha già
         aggiornato oggi, i dati arrivano da qui e Gmail non viene interrogato).
      2. Calcola TUTTI i giorni lavorativi mancanti (anche settimane senza utilizzo dell'app).
      3. Se ne mancano, scansiona Gmail dal primo giorno mancante e archivia le quotazioni.
      4. Se il DB locale contiene dati che GitHub non ha (nuove quotazioni o push precedenti
         falliti), pubblica JSON e CSV su GitHub in modo SINCRONO e ne verifica l'esito.
    """
    logs = []
    oggi_str = target_date or storage_manager.oggi_italia().isoformat()

    # FASE 1: Allineamento in ingresso da GitHub
    remote_quotes = None
    try:
        remote_quotes = storage_manager.fetch_remote_quotes()
        if remote_quotes is not None:
            n_github = add_quotes(remote_quotes, push_github=False)
            if n_github > 0:
                logs.append(f"☁️ Sincronizzate {n_github} quotazioni dal repository cloud GitHub.")
        else:
            logs.append("⚠️ Repository GitHub non raggiungibile: uso il database locale.")
    except Exception as e:
        logs.append(f"Nota sync cloud: {e}")

    # FASE 2: Giorni lavorativi mancanti (dopo l'ultima data + buchi recenti)
    missing_days = storage_manager.get_missing_business_days()
    extracted_quotes: List[Dict[str, Any]] = []
    if missing_days:
        logs.append(f"🔎 Giorni lavorativi mancanti: {len(missing_days)} (dal {missing_days[0]} al {missing_days[-1]}).")
        actual_scan_depth = max(scan_depth, len(missing_days) * 20, 50)
        extracted_quotes, gmail_logs = fetch_quotes_from_gmail(
            max_emails=actual_scan_depth,
            target_date=None,
            stop_after_first_match=False,
            since_date=missing_days[0]
        )
        logs.extend(gmail_logs)
        for line in gmail_logs:
            safe_print(f"[GMAIL SYNC] {line}")
        still_missing = storage_manager.get_missing_business_days()
        recovered = [d for d in missing_days if d not in still_missing]
        if recovered:
            logs.append(f"✅ Recuperati {len(recovered)} giorni: {', '.join(recovered)}.")
    else:
        logs.append(f"🟢 Nessun giorno lavorativo mancante nel database ({oggi_str}).")

    # FASE 3: Pubblicazione su GitHub se GitHub è indietro rispetto al DB locale
    need_push = bool(extracted_quotes) or storage_manager.has_unpushed_changes(remote_quotes)
    if need_push:
        if storage_manager.sync_to_github():
            logs.append("☁️ Database CSV/JSON pubblicato su GitHub.")
        else:
            err = storage_manager.LAST_GITHUB_STATUS.get("error", "")
            logs.append(f"[ERRORE] Aggiornamento GitHub non riuscito: {err}")
        for line in logs[-1:]:
            safe_print(f"[GITHUB SYNC] {line}")

    updated_quotes = load_quotes()
    is_today_present = any(q.get("data") == oggi_str for q in updated_quotes)
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
