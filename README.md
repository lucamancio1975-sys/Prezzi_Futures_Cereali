# 🌾 Quotazioni Futures Cereali — Grano Duro e Grano Tenero (Luglio 2027)

Dashboard analitica finanziaria in stile **Wall Street / Bloomberg Terminal**, ottimizzata specificamente per **smartphone (mobile-first)** e pronta per il deployment pubblico su **Streamlit Community Cloud** e **GitHub**.

---

## 🎯 Panoramica e Funzionalità

L'applicazione consente la consultazione quotidiana immediata delle quotazioni dei contratti di protezione Futures per il raccolto **Luglio 2027 (lug-27)**:

1. **🌾 Grano Duro PDT** (Prezzo Determinato a Termine)
2. **🌱 Grano Tenero PDT** (Prezzo Determinato a Termine)
3. **🌱 Grano Tenero PMG** (Prezzo Minimo Garantito)

### Caratteristiche Principali:
- **Schermata Principale di Selezione**: visualizzazione pulita con banner di protezione e tre pulsanti dedicati ad alto contrasto.
- **Ispezione Intelligente ad Alta Velocità**:
  1. *Priorità 1*: ricerca e parsing istantaneo degli **allegati PDF** inviati via email.
  2. *Priorità 2*: in assenza di PDF, scansione e **OCR ad alta affidabilità su immagini/tabelle**.
  3. *Priorità 3*: in assenza di immagini, interpretazione del **testo o tabelle HTML** nel corpo dell'email.
- **Interfaccia Pulita di Sola Consultazione**:
  - Nessuna icona GitHub, pulsante di modifica ("Fork this app"), menu hamburger o footer Streamlit visibili all'utente finale.
- **Mobile-First Responsivo**:
  - Prezzo in risalto e grafico Plotly visibili nella prima schermata dello smartphone senza necessità di scorrere verticalmente.
  - Grafico touch con scrolling verticale abilitato (`touch-action: pan-y`).
- **Guide Ufficiali PDF Integrate**:
  - Download o apertura immediata con un tocco della **Guida agli Impegni e Conferimento** dedicata (Duro o Tenero).
- **Archiviazione e Storico**:
  - Database unificato in `data/storico_prezzi.json` e `data/storico_prezzi.csv` con deduplicazione automatica.

---

## 🚀 Avvio Rapido Locale (Windows)

1. Fare doppio clic sul file:
   ```cmd
   avvia_app.bat
   ```
2. Oppure da terminale:
   ```bash
   streamlit run app.py
   ```
3. L'applicazione si aprirà automaticamente nel browser all'indirizzo `http://localhost:8501`.

---

## ☁️ Pubblicazione su GitHub e Streamlit Cloud

### 1. Repository Pubblica GitHub
Il file `.gitignore` incluso esclude già automaticamente il file `.env` contenente le password private, garantendo la sicurezza.
Per creare la repository su GitHub ed eseguire il push:
```bash
git init
git add .
git commit -m "Creazione App Generale Quotazioni Grano Duro e Tenero"
git branch -M main
git remote add origin https://github.com/TUO-USERNAME/NOME-REPO.git
git push -u origin main
```

### 2. Deployment su Streamlit Community Cloud
1. Collegati a [share.streamlit.io](https://share.streamlit.io) e seleziona la repository GitHub appena creata.
2. Imposta `app.py` come file principale.
3. Nella sezione **Advanced Settings** -> **Secrets**, inserisci:
   ```toml
   GMAIL_USER = "tuacasella@gmail.com"
   GMAIL_APP_PASSWORD = "tua_password_per_le_app_google"
   ```
4. Clicca su **Deploy**. L'applicazione sarà accessibile pubblicamente con la grafica personalizzata scura, senza elementi di modifica o icone della repository visibili ai clienti.
