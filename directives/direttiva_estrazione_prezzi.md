# Direttiva — Estrazione e Monitoraggio Prezzi Futures Grano Duro

## 1. Obiettivo
Monitorare quotidianamente le quotazioni dei contratti Futures Grano Duro (PDT/PMG) inviate dal trading desk Consorzi Agrari d'Italia (CAI) via email con allegato PDF.
I dati estratti devono essere archiviati in modo deterministico e visualizzati in una dashboard analitica in stile Bloomberg / Wall Street.

## 2. Ingressi
- **Email:** Casella Gmail dedicata con messaggi provenienti da `carlo.citroni@consorziagrariditalia.it` (o recanti oggetto con "Quotazioni", "Futures", "PDT", "PMG").
- **Allegato PDF:** File denominato tipicamente `PDT  PMG.pdf` contenente le tabelle delle quotazioni per le varie colture (Mais, Soia, Colza, Grano Tenero, Grano Duro).

## 3. Strumenti di Esecuzione (Livello 3)
- `execution/parse_pdf_quotazioni.py`: Parser per estrarre data, scadenze e prezzi dal testo/PDF.
- `execution/parse_image_quotazioni.py`: Parser OCR per estrarre data, scadenze e prezzi dalle immagini della tabella (PNG/JPG inline o allegate).
- `execution/win_ocr.ps1`: Engine OCR Windows ad altissima affidabilità per la lettura delle tabelle copiate da Excel/Outlook.
- `execution/storage_manager.py`: Motore di persistenza per `data/storico_prezzi.json` e CSV.
- `execution/fetch_gmail_quotes.py`: Client IMAP SSL per scansione casella, elaborazione allegati PDF / immagini e popolamento DB.
- `app.py`: Applicazione Streamlit con interfaccia e grafici Plotly Wall Street Theme.

## 4. Casi Limite e Gestione Errori
- **Email con tabella incollata come immagine (senza PDF):** Il parser attiva automaticamente il modulo OCR deterministico per immagini, ritagliando ad alta risoluzione la sezione Grano Duro ed estraendo i prezzi per lug-27 e lug-28.
- **Email senza allegato PDF né immagine:** Il parser scansiona il corpo testuale dell'email (text/plain o text/html).
- **Quotazione già registrata:** Il sistema effettua la deduplicazione su chiave `(data, scadenza, tipo)` aggiornando il valore solo se variato.
- **Mancanza connessione o credenziali:** L'applicazione permette l'inserimento manuale rapido direttamente dall'interfaccia.
