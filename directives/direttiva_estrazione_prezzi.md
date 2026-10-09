# Direttiva — Estrazione e Monitoraggio Prezzi Futures Grano Duro e Grano Tenero
 
## 1. Obiettivo
Monitorare quotidianamente le quotazioni dei contratti Futures Grano Duro (PDT/PMG) e Grano Tenero Fino Rosso (PDT/PMG) inviate dal trading desk Consorzi Agrari d'Italia (CAI) via email.
I dati estratti devono essere archiviati in modo deterministico e visualizzati nella dashboard analitica in stile Bloomberg / Wall Street.

## 2. Ingressi e Gerarchia di Estrazione
- **Priorità 1 (Immagini/Tabelle OCR):** Scansione e OCR deterministico su immagini PNG/JPG inserite nel corpo dell'email o allegate (metodo primario ad altissima frequenza).
- **Priorità 2 (Allegato PDF):** File denominato tipicamente `PDT  PMG.pdf` o con codice identificativo (es. `PDT  PMG-PCE001376-2.pdf`), utilizzato come completamento o fallback.
- **Priorità 3 (Corpo Testo / Tabelle HTML):** Scansione testuale dell'email per messaggi senza immagini o allegati.

## 3. Strumenti di Esecuzione (Livello 3)
- `execution/parse_image_quotazioni.py`: Parser OCR per estrarre data, scadenze e prezzi dalle immagini della tabella (PNG/JPG inline o allegate), con ritagli geometrici per coltura, normalizzazione caratteri spezzati e mappatura ordinata delle scadenze.
- `execution/win_ocr.ps1`: Engine OCR Windows ad altissima affidabilità per la lettura delle tabelle copiate da Excel/Outlook.
- `execution/parse_pdf_quotazioni.py`: Parser per estrarre data, scadenze e prezzi dal testo/PDF.
- `execution/storage_manager.py`: Motore di persistenza atomica per `data/storico_prezzi.json` e CSV con sincronizzazione bidirezionale GitHub.
- `execution/fetch_gmail_quotes.py`: Client IMAP SSL per scansione casella, elaborazione gerarchica delle email e popolamento DB.

## 4. Casi Limite e Gestione Errori
- **Isolamento Geometrico delle Sezioni:** Ritaglio mirato per evitare interferenze di colture sovrastanti/sottostanti.
- **Deduplicazione e Integrazione Serie:** Deduplicazione su chiave `(data, prodotto, tipo, scadenza)`. Se una fonte parziale manca di una serie, le fonti successive completano i dati mancanti.

