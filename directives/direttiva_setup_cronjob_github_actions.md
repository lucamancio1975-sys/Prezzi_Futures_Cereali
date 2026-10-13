# Direttiva — Trigger Deterministico di GitHub Actions tramite Cron-Job.org (Webhook API)

## 1. Obiettivo e Contesto
I cron nativi di GitHub Actions (`schedule: - cron: '...'`) presentano spesso ritardi casuali compresi tra 15 e 60 minuti o possono essere sospesi da GitHub se il repository non riceve commit frequenti.
Per garantire un'esecuzione **deterministica, puntuale e programmabile al secondo**, il trigger viene esternalizzato a un servizio web cron gratuito (come **cron-job.org**) che risveglia il workflow GitHub tramite l'API REST `workflow_dispatch`.

---

## 2. Architettura del Flusso

```
+-------------------+       POST API (con Bearer Token)       +-----------------------+
|   cron-job.org    | -------------------------------------> |  GitHub Actions API   |
| (Timer puntuale)  |                                        |  (workflow_dispatch)  |
+-------------------+                                        +-----------------------+
                                                                         |
                                                                         v
                                                             +-----------------------+
                                                             | Esecuzione Runner     |
                                                             | (Script, Scraping, DB)|
                                                             +-----------------------+
```

---

## 3. Requisiti Preliminari

1. **GitHub Personal Access Token (PAT):**
   - Un token di tipo *Classic* o *Fine-Grained*.
   - Permessi richiesti:
     - `repo` (accesso completo o scrittura repository)
     - `workflow` (permesso di gestire e avviare GitHub Workflows).
2. **Repository e Nome Workflow:**
   - Esempio: `UTENTE/REPO`
   - File workflow: `.github/workflows/<nome_file>.yml`

---

## 4. Configurazione del Workflow GitHub (`.github/workflows/<nome_file>.yml`)

Nel file YAML del workflow, **rimuovere o commentare** la sezione `schedule:` per evitare doppie esecuzioni o chiamate ridondanti. Mantenere abilitato `workflow_dispatch`:

```yaml
name: Nome Workflow

on:
  workflow_dispatch: # Abilita il trigger via API e via interfaccia web

permissions:
  contents: write

jobs:
  job_principale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ... step di esecuzione ...
```

---

## 5. Configurazione del Job su Cron-Job.org

### A. Parametri Generali
- **Title:** `Sync [Nome Progetto]`
- **URL:** 
  ```text
  https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW_FILE_O_ID}/dispatches
  ```
  *(Sostituire `{OWNER}`, `{REPO}` e `{WORKFLOW_FILE_O_ID}` es: `sync_prezzi.yml`)*
- **Attiva cronjob:** Spuntato / ON
- **Salva risposte nella cronologia:** Spuntato / ON (indispensabile per monitorare esito e codici HTTP)

### B. Richiesta HTTP (Sezione Avanzata / Request Settings)
- **Metodo HTTP:** `POST` (fondamentale: di default i cron usano GET, che GitHub rifiuta con 404!)
- **Headers HTTP:**
  | Chiave | Valore | Note |
  | :--- | :--- | :--- |
  | `Authorization` | `Bearer ghp_TUO_GITHUB_TOKEN` | Token PAT con permessi `repo` e `workflow` |
  | `Accept` | `application/vnd.github+json` | Header standard GitHub v3/REST |
  | `Content-Type` | `application/json` | Dichiara il payload JSON |
  | `User-Agent` | `cron-job.org` | GitHub richiede obbligatoriamente un User-Agent |

- **Request Body (JSON):**
  ```json
  {"ref": "main"}
  ```
  *(Sostituire `main` con il branch predefinito se diverso)*

### C. Metodo Rapido — Import via cURL
Nel pannello di modifica del cronjob su cron-job.org è possibile cliccare su **`</> IMPORT FROM CURL`** e incollare il seguente comando (popola tutti i campi automaticamente):

```bash
curl -X POST "https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW_FILE}.yml/dispatches" \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ghp_TUO_TOKEN" \
  -H "Content-Type: application/json" \
  -H "User-Agent: cron-job.org" \
  -d '{"ref":"main"}'
```

---

## 6. Schedulazione Oraria (Esempi Crontab)

Selezionare **Personalizzata** (fuso orario: `Europe/Rome`):

- **Ogni 30 minuti dalle 11:00 alle 15:30 tutti i giorni:**
  ```cron
  0,30 11-15 * * *
  ```
- **Ogni 15 minuti dal lunedì al venerdì tra le 09:00 e le 18:00:**
  ```cron
  */15 9-18 * * 1-5
  ```
- **Una volta al giorno alle 13:00:**
  ```cron
  0 13 * * *
  ```

---

## 7. Verifica e Collaudo

1. Cliccare su **"TEST DI ESECUZIONE"** all'interno di cron-job.org.
2. Codice di successo atteso: **`204 No Content`** (standard GitHub per i dispatch).
3. Verificare nel pannello GitHub: `https://github.com/{OWNER}/{REPO}/actions` che il workflow sia partito con stato `in_progress` o `queued` con evento `workflow_dispatch`.

---

## 8. Note sui Limiti (Rate Limits)
- Le chiamate autenticate con PAT godono di **5.000 richieste/ora**.
- Un cron ogni 30 minuti consuma 2 richieste/ora (lo 0,04% della quota).
- Nessun rischio di superamento soglie.
