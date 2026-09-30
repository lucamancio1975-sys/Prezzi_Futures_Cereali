"""
Script per la generazione e compilazione ad alta fedeltà delle Guide PDF:
1. 'Guida agli Impegni e Conferimento Grano Duro.pdf'
2. 'Guida agli Impegni e Conferimento Grano Tenero.pdf'

Utilizza Google Chrome headless per produrre un layout tipografico perfetto (A4 esatto a 2 pagine).
Include la riformattazione degli spazi, il layout compatto e l'aggiunta del disclaimer richiesto.
"""

import os
import subprocess
import pypdf

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WORKSPACE_DIR = os.path.abspath(os.path.dirname(__file__))

COMMON_CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  @page {
    size: A4 portrait;
    margin: 8mm 12mm 7mm 12mm;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }

  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background-color: #ffffff;
    font-size: 8.05pt;
    line-height: 1.27;
  }

  .page {
    width: 100%;
    min-height: 279mm;
    max-height: 282mm;
    position: relative;
    page-break-after: always;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
  }

  .page:last-child {
    page-break-after: avoid;
  }

  /* Header */
  .header-container {
    text-align: center;
    margin-bottom: 5px;
  }

  .main-title {
    font-size: 12.8pt;
    font-weight: 700;
    color: #1d4d2b;
    letter-spacing: 0.3px;
    margin-bottom: 2px;
    text-transform: uppercase;
  }

  .sub-title {
    font-size: 8.8pt;
    font-weight: 500;
    color: #475569;
    margin-bottom: 5px;
  }

  .divider-gold {
    height: 2.2px;
    background: linear-gradient(90deg, #f59e0b, #fbbf24, #f59e0b);
    border-radius: 2px;
    margin-bottom: 5px;
  }

  /* Section Card */
  .section-block {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 5px;
    margin-bottom: 5px;
    overflow: hidden;
  }

  .section-header {
    background-color: #f1f6f2;
    padding: 3px 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-left: 4px solid #f59e0b;
    border-bottom: 1px solid #e5ebe6;
  }

  .section-title {
    font-size: 8.5pt;
    font-weight: 700;
    color: #1d4d2b;
    letter-spacing: 0.2px;
  }

  .section-badge {
    font-size: 6.5pt;
    font-weight: 600;
    color: #64748b;
    background: #ffffff;
    padding: 1px 5px;
    border-radius: 3px;
    border: 1px solid #cbd5e1;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }

  .section-body {
    padding: 4.5px 8px;
  }

  /* Typography & Layouts */
  p {
    margin-bottom: 2.5px;
  }
  p:last-child {
    margin-bottom: 0;
  }

  .bullet-title {
    font-weight: 700;
    color: #0f172a;
  }

  .two-cols {
    display: flex;
    gap: 10px;
  }

  .col {
    flex: 1;
  }

  /* Highlight boxes (Yellow) */
  .highlight-box {
    background-color: #fffef2;
    border: 1px solid #fde047;
    border-left: 3.5px solid #eab308;
    border-radius: 4px;
    padding: 3.5px 7px;
    margin-top: 3.5px;
  }

  .highlight-box .bullet-title {
    color: #854d0e;
  }

  /* Numbered items list */
  .numbered-item {
    display: flex;
    align-items: flex-start;
    gap: 6px;
    margin-bottom: 3.5px;
  }

  .numbered-item:last-child {
    margin-bottom: 0;
  }

  .number-badge {
    background-color: #f59e0b;
    color: #ffffff;
    font-size: 7.2pt;
    font-weight: 700;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
  }

  .numbered-content {
    flex: 1;
  }

  /* 6-Grid Cards (Agronomia) */
  .grid-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
  }

  .grid-card {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 7.55pt;
    line-height: 1.24;
  }

  .grid-card .bullet-title {
    display: block;
    color: #1d4d2b;
    font-size: 7.65pt;
    margin-bottom: 1px;
  }

  /* Compact Table */
  .compact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.2pt;
    line-height: 1.2;
    margin-top: 2px;
  }

  .compact-table th {
    background-color: #f1f6f2;
    color: #1d4d2b;
    font-weight: 700;
    padding: 2.5px 4px;
    border: 1px solid #cbd5e1;
    text-align: left;
  }

  .compact-table td {
    padding: 2px 4px;
    border: 1px solid #e2e8f0;
    vertical-align: middle;
  }

  .compact-table tr:nth-child(even) {
    background-color: #fafbfc;
  }

  /* Bottom Banner Unificato con Disclaimer */
  .bottom-banner-container {
    margin-top: auto;
    margin-bottom: 2px;
  }

  .bottom-banner {
    background-color: #1d4d2b;
    color: #ffffff;
    text-align: center;
    padding: 4.5px 10px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 7.9pt;
    letter-spacing: 0.25px;
  }

  .bottom-disclaimer {
    margin-top: 3px;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #f59e0b;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 6.95pt;
    line-height: 1.22;
    color: #334155;
    text-align: center;
  }

  .bottom-disclaimer em {
    font-weight: 700;
    font-style: italic;
    color: #b45309;
  }

  .bottom-disclaimer span.desc {
    font-style: italic;
  }

  /* Page Footer */
  .page-footer {
    display: flex;
    justify-content: flex-end;
    font-size: 6.8pt;
    color: #94a3b8;
    padding-top: 2px;
  }
"""

HTML_TENERO = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>Guida al Tuo Contratto Grano Tenero - CAI</title>
<style>
{COMMON_CSS}
</style>
</head>
<body>

<!-- ==================== PAGINA 1 ==================== -->
<div class="page">
  <div class="header-container">
    <div class="main-title">Analisi degli Obblighi, Penali e Responsabilità del Conferente</div>
    <div class="sub-title">Contratto di Protezione Grano Tenero Nazionale Convenzionale — Raccolto 2027</div>
    <div class="divider-gold"></div>
  </div>

  <!-- SEZIONE 1 -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">1. QUADRO NORMATIVO E QUALIFICA DELLE PARTI</span>
      <span class="section-badge">D.LGS. N. 198/2021</span>
    </div>
    <div class="section-body">
      <p><span class="bullet-title">• Disciplina di Settore:</span> Piena conformità all'art. 3 del D.Lgs. n. 198/2021 sulle pratiche commerciali sleali nella filiera agroalimentare.</p>
      <p style="margin-top: 2px;"><span class="bullet-title">• Struttura Contrattuale:</span> Proposta contrattuale di compravendita a "Prezzo Determinato a Termine" (Mod. TIPCON-GT Rev. 01 – 22/09/26), integrata dalle Condizioni Generali Unificate CAI (Mod. C15) e regolata per le difformità merceologiche dal Contratto Nazionale A.G.E.R. n. 101 per Frumento Tenero.</p>
    </div>
  </div>

  <!-- SEZIONE 2 -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">2. OBBLIGHI PRIMARI DI CONSEGNA E QUANTITÀ DETERMINATA</span>
      <span class="section-badge">PARAMETRI & IMPEGNI</span>
    </div>
    <div class="section-body">
      <div class="two-cols">
        <div class="col">
          <p><span class="bullet-title">• Quantità Rigorosamente Fissa:</span><br>
          La quantità contrattuale pattuita è tassativa ed inderogabile. Il Venditore è tenuto al suo integrale rispetto, costituendo obbligazione primaria non derogabile.</p>
        </div>
        <div class="col">
          <p><span class="bullet-title">• Termine e Modalità di Resa:</span><br>
          La merce deve essere consegnata presso il Centro di Raccolta indicato in contratto a cura e spese integrali del conferente, entro e non oltre la data di chiusura della campagna di raccolta 2027. Anche in caso di ritiro concordato in azienda agricola ("sotto trebbia"), le spese e i rischi del trasferimento al centro di stoccaggio gravano sull'agricoltore.</p>
        </div>
      </div>

      <div style="margin-top: 4px; padding-top: 3px; border-top: 1px dashed #e2e8f0;">
        <p><span class="bullet-title">• Qualità della Partita:</span> merce che non raggiunga le qualità minime ma resti commerciabile, il conferente non è liberato dall'obbligo di consegna; il prezzo verrà declassato secondo i parametri e bollettini riportati in contratto.</p>
        <p style="margin-top: 2px;">Il prezzo pattuito a termine (PDT) pieno si applica esclusivamente alla merce conforme alla qualifica <strong>"FINO"</strong> (Fino - Misto Rosso o Fino - Bianco, con Peso Specifico ≥ 78,00 kg/hl, Falling Number ≥ 220 sec, Impurità totali ≤ 1%).</p>
        <p style="margin-top: 2px;">Resta comunque ferma per CAI la facoltà di pretendere la penale per inadempimento qualitativo in caso di comportamenti difformi o scorretti.</p>
      </div>

      <!-- Box Giallo 1 -->
      <div class="highlight-box">
        <span class="bullet-title">• Obbligo Espresso di Riacquisto sul Mercato:</span><br>
        Qualora la produzione effettivamente raccolta sui terreni aziendali risulti insufficiente a raggiungere il quantitativo pattuito, il conferente ha l'obbligo inderogabile di procurarsi a proprie spese sul mercato prodotto sostitutivo della medesima qualità e consegnarlo a CAI.
      </div>

      <!-- Box Giallo 2 -->
      <div class="highlight-box">
        <span class="bullet-title">• Assunzione del Rischio Climatico:</span><br>
        Il Venditore si assume espressamente il <strong>RISCHIO INTEGRALE</strong> per impossibilità sopravvenuta della consegna della quantità e qualità pattuita, anche laddove la mancata o minore produzione dipenda da cause totalmente indipendenti dalla propria responsabilità, quali fenomeni atmosferici avversi, siccità prolungata, alluvioni, grandine, calamità naturali o cause di forza maggiore.
      </div>
    </div>
  </div>

  <div class="page-footer">
    Pagina 1 di 2
  </div>
</div>

<!-- ==================== PAGINA 2 ==================== -->
<div class="page">
  <!-- SEZIONE 3 -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">3. PENALI PER MANCATA CONSEGNA</span>
      <span class="section-badge">SU EVENTUALE RICHIESTA DI CAI</span>
    </div>
    <div class="section-body">
      <p style="font-weight: 600; margin-bottom: 3.5px; color: #334155;">Il Venditore, su eventuale richiesta di CAI, deve versare:</p>
      
      <div class="numbered-item">
        <div class="number-badge">1</div>
        <div class="numbered-content">
          <span class="bullet-title">Penale Contrattuale Fissa ex Art. 1382 C.C.:</span> Pagamento della penale specifica pari a <strong>€/Ton 30,00</strong> per ogni tonnellata pattuita e non consegnata (espressamente pattuita al punto 4 del contratto).
        </div>
      </div>

      <div class="numbered-item">
        <div class="number-badge">2</div>
        <div class="numbered-content">
          <span class="bullet-title">Quota Differenziale di Mercato:</span> Somma pari alla differenza (se positiva) tra il prezzo pattuito a contratto (PDT) e il maggior prezzo medio calcolato sui valori massimi della categoria di appartenenza rilevati dai bollettini della CCIAA territorialmente competente nel periodo di consegna, moltiplicata per le tonnellate non consegnate (Art. XII Condizioni Generali).
        </div>
      </div>

      <div class="numbered-item">
        <div class="number-badge">3</div>
        <div class="numbered-content">
          <span class="bullet-title">Risarcimento Danni Ulteriori:</span> CAI si riserva espressamente il diritto di addebitare i costi logistici straordinari, i maggiori oneri per acquisti sostitutivi d'urgenza sul mercato, le perdite economiche subite dalla risoluzione o chiusura forzata dei contratti derivati di copertura finanziaria (futures) stipulati sui mercati a termine (es. MATIF) e la perdita delle premialità di filiera.
        </div>
      </div>

      <div class="numbered-item">
        <div class="number-badge">4</div>
        <div class="numbered-content">
          <span class="bullet-title">Rinuncia alla Riduzione Giudiziale della Penale:</span> L'agricoltore, mediante espressa doppia sottoscrizione delle clausole vessatorie (artt. 1341 e 1342 C.C.), rinuncia formalmente ad adire il Giudice per ottenere la riduzione equitativa dell'ammontare della penale ex art. 1384 C.C.
        </div>
      </div>
    </div>
  </div>

  <!-- SEZIONE 4: TABELLA C COMPATTA -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">4. SPECIFICHE QUALITATIVE, ABBUONI E DECLASSAMENTI (TABELLA C)</span>
      <span class="section-badge">AGER N. 101</span>
    </div>
    <div class="section-body" style="padding: 3px 6px;">
      <table class="compact-table">
        <thead>
          <tr>
            <th style="width: 25%;">Parametro / Categoria</th>
            <th style="width: 25%;">Qualità Tipo (Base PDT)</th>
            <th style="width: 25%;">Fuori Limiti</th>
            <th style="width: 25%;">Conseguenza Economica / Azione CAI</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Fino (Misto Rosso / Bianco)</strong></td>
            <td>Peso Spec. ≥ 78,00 kg/hl</td>
            <td>—</td>
            <td><strong style="color: #166534;">Prezzo Pieno PDT di contratto</strong></td>
          </tr>
          <tr>
            <td><strong>Buono Mercantile</strong></td>
            <td>Peso Spec. ≥ 76,00 kg/hl</td>
            <td>P.S. tra 76,00 e 77,99 kg/hl</td>
            <td>Detrazione fissa pari a <strong>€/Ton 8,00</strong></td>
          </tr>
          <tr>
            <td><strong>Mercantile</strong></td>
            <td>Peso Spec. ≥ 72,00 kg/hl</td>
            <td>P.S. tra 72,00 e 75,99 kg/hl</td>
            <td>Detrazione fissa pari a <strong>€/Ton 18,00</strong></td>
          </tr>
          <tr>
            <td><strong>Sotto 72,00 kg/hl</strong></td>
            <td>—</td>
            <td>&lt; 72 kg/hl (Foraggero/Pregerm.)</td>
            <td>Declassamento a cat. inferiore o Facoltà di Rifiuto Merce</td>
          </tr>
          <tr>
            <td><strong>Falling Number (Hagberg)</strong></td>
            <td>Minimo 220 secondi</td>
            <td>Inferiore a 220 sec.</td>
            <td>Abbuono da concordare sul prezzo o Rifiuto Merce</td>
          </tr>
          <tr>
            <td><strong>Impurità Totali (AGER 101)</strong></td>
            <td>Max 1,00%</td>
            <td>Da 1,01% a 3,00%<br>Superiore al 3,00%</td>
            <td>Abbuono 1% sul peso per ogni punto<br>Abbuono 3% sul peso per ogni punto o Rifiuto</td>
          </tr>
          <tr>
            <td><strong>Cimice / Germinati</strong></td>
            <td>Tolleranza ZERO (0%)</td>
            <td>Presenza accertata</td>
            <td><strong style="color: #991b1b;">Rifiuto Merce</strong> — Facoltà di ritiro a solo "uso foraggero"</td>
          </tr>
          <tr>
            <td><strong>Fusariati / Umidità</strong></td>
            <td>Fus. max 1% | Umid. max 14%</td>
            <td>Fusariati &gt; 1% | Umidità &gt; 14%</td>
            <td>Umidità: riconduzione peso a secco. Fusariati: Rifiuto o uso foraggero</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- SEZIONE 5: AGRO (6 CARD GRID) -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">5. IMPEGNI AGRONOMICI, SANITARI E DI COLTIVAZIONE</span>
      <span class="section-badge">DISCIPLINARE DI CAMPO</span>
    </div>
    <div class="section-body" style="padding: 3.5px 6px;">
      <div class="grid-container">
        <div class="grid-card">
          <span class="bullet-title">• Semente Certificata e No OGM</span>
          Utilizzo esclusivo di sementi controllate e certificate dall'Ente C.R.E.A. rigorosamente Non OGM.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Delimitazione Terreni della Coltivazione</span>
          Individuazione certa delle superfici e particelle catastali condotte sotto contratto (Tabella A).
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Lotta Obbligatoria alla Cimice</span>
          Obbligo piano di difesa mirato. Le cariossidi danneggiate da cimice hanno tolleranza zero (0%).
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Divieto Fanghi e Trattamenti Post-Raccolta</span>
          Divieto assoluto di fanghi non ammessi e divieto di trattamenti chimici di conservazione post-raccolta.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Prevenzione Contaminazioni da Macchine</span>
          Pulizia accurata di mietitrebbiatrici e mezzi per evitare inquinamenti accidentali da altri cereali o inerti.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Diritto di Ispezione in Campo</span>
          Accesso garantito in campo per verifiche da parte del Personale Tecnico CAI durante il ciclo vegetativo.
        </div>
      </div>
    </div>
  </div>

  <!-- SEZIONE 6 & 7: ADEMPIMENTI E CLAUSOLE LEGALI -->
  <div class="two-cols" style="gap: 6px; margin-bottom: 4px;">
    <!-- ADEMPIMENTI -->
    <div class="col section-block" style="margin-bottom: 0;">
      <div class="section-header">
        <span class="section-title">6. ADEMPIMENTI E FISCO</span>
        <span class="section-badge">TRACCIABILITÀ</span>
      </div>
      <div class="section-body" style="font-size: 7.3pt;">
        <p><span class="bullet-title">• DDT:</span> Documento di Trasporto regolare con causale e filiera ad ogni conferimento.</p>
        <p><span class="bullet-title">• Produttore Primario:</span> Registrazione Reg. UE 183/2005 e 852/2004; quaderno di campagna aggiornato.</p>
        <p><span class="bullet-title">• Mandato Fatturazione:</span> Mandato a CAI per emissione fattura SDI conto terzi (Art. 34 DPR 633/72).</p>
      </div>
    </div>

    <!-- CLAUSOLE GIURIDICHE -->
    <div class="col section-block" style="margin-bottom: 0;">
      <div class="section-header">
        <span class="section-title">7. CLAUSOLE GIURIDICHE</span>
        <span class="section-badge">CONDIZIONI LEGALI</span>
      </div>
      <div class="section-body" style="font-size: 7.3pt;">
        <p><span class="bullet-title">• Divieto Cessione Credito:</span> Vietata cessione credito/contratto senza ok scritto CAI.</p>
        <p><span class="bullet-title">• Compensazione Debiti:</span> Saldo automatico con crediti/debiti CAI (Art. 1252 C.C.).</p>
        <p><span class="bullet-title">• Vizi Occulti e Foro:</span> Denuncia vizi entro 15 gg (deroga 1495 C.C.). Foro di Bologna.</p>
      </div>
    </div>
  </div>

  <!-- Banner finale con Disclaimer Integrato -->
  <div class="bottom-banner-container">
    <div class="bottom-banner">
      Puoi visionare il contratto completo presso la tua Agenzia CAI di fiducia.
    </div>
    <div class="bottom-disclaimer">
      <em>Disclaimer:</em> <span class="desc">le quotazioni giornaliere sono aggiornate ma indicative; saranno confermate o eventualmente corrette al momento della stipula dell'accordo presso l'agenzia Cai di riferimento</span>
    </div>
  </div>

  <div class="page-footer">
    Pagina 2 di 2
  </div>
</div>

</body>
</html>
"""

HTML_DURO = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>Guida al Tuo Contratto Grano Duro - CAI</title>
<style>
{COMMON_CSS}
</style>
</head>
<body>

<!-- ==================== PAGINA 1 ==================== -->
<div class="page">
  <div class="header-container">
    <div class="main-title">Analisi degli Obblighi, Penali e Responsabilità del Conferente</div>
    <div class="sub-title">Contratto di Protezione Grano Duro Nazionale Convenzionale — Raccolto 2027</div>
    <div class="divider-gold"></div>
  </div>

  <!-- SEZIONE 1 -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">1. QUADRO NORMATIVO E QUALIFICA DELLE PARTI</span>
      <span class="section-badge">D.LGS. N. 198/2021</span>
    </div>
    <div class="section-body">
      <p><span class="bullet-title">• Disciplina di Settore:</span> Piena conformità all'art. 3 del D.Lgs. n. 198/2021 sulle pratiche commerciali sleali nella filiera agroalimentare.</p>
    </div>
  </div>

  <!-- SEZIONE 2 -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">2. OBBLIGHI PRIMARI DI CONSEGNA E QUANTITÀ DETERMINATA</span>
      <span class="section-badge">PARAMETRI & IMPEGNI</span>
    </div>
    <div class="section-body">
      <div class="two-cols">
        <div class="col">
          <p><span class="bullet-title">• Quantità Rigorosamente Fissa:</span><br>
          La quantità contrattuale pattuita è tassativa ed inderogabile. Il Venditore è tenuto al suo integrale rispetto.</p>
        </div>
        <div class="col">
          <p><span class="bullet-title">• Termine e Modalità di Resa:</span><br>
          La merce deve essere consegnata presso il Centro di Raccolta indicato in contratto a cura e spese integrali del conferente, entro e non oltre la data di chiusura della campagna di raccolta 2027. Anche in caso di ritiro concordato in azienda agricola ("sotto trebbia"), le spese e i rischi del trasferimento al centro di stoccaggio gravano sull'agricoltore.</p>
        </div>
      </div>

      <div style="margin-top: 5px; padding-top: 4px; border-top: 1px dashed #e2e8f0;">
        <p><span class="bullet-title">• Qualità della Partita:</span> merce che non raggiunga le qualità minime ma resti commerciabile, il conferente non è liberato dall'obbligo di consegna; il prezzo verrà declassato secondo i parametri riportati in contratto.</p>
        <p style="margin-top: 2px;">Il prezzo pattuito a termine (PDT) pieno si applica esclusivamente alla merce conforme alla qualifica <strong>"FINO"</strong> (Peso Specifico ≥ 78 kg/hl e Proteine ≥ 13,50%).</p>
        <p style="margin-top: 2px;">Resta comunque ferma per CAI la facoltà di pretendere la penale per inadempimento qualitativo in caso di comportamenti scorretti.</p>
      </div>

      <!-- Box Giallo 1 -->
      <div class="highlight-box">
        <span class="bullet-title">• Obbligo Espresso di Riacquisto sul Mercato:</span><br>
        Qualora la produzione effettivamente raccolta sui terreni aziendali risulti insufficiente a raggiungere il quantitativo pattuito, il conferente ha l'obbligo inderogabile di procurarsi a proprie spese sul mercato prodotto sostitutivo della medesima qualità e consegnarlo a CAI.
      </div>

      <!-- Box Giallo 2 -->
      <div class="highlight-box">
        <span class="bullet-title">• Assunzione del Rischio Climatico:</span><br>
        Il Venditore si assume espressamente il <strong>RISCHIO INTEGRALE</strong> per impossibilità sopravvenuta della consegna della quantità e qualità pattuita, anche laddove la mancata o minore produzione dipenda da cause totalmente indipendenti dalla propria responsabilità, quali fenomeni atmosferici avversi, siccità prolungata, alluvioni, grandine, calamità naturali o cause di forza maggiore.
      </div>
    </div>
  </div>

  <div class="page-footer">
    Pagina 1 di 2
  </div>
</div>

<!-- ==================== PAGINA 2 ==================== -->
<div class="page">
  <!-- SEZIONE 3 -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">3. PENALI PER MANCATA CONSEGNA</span>
      <span class="section-badge">SU EVENTUALE RICHIESTA DI CAI</span>
    </div>
    <div class="section-body">
      <p style="font-weight: 600; margin-bottom: 3.5px; color: #334155;">Il Venditore, su eventuale richiesta di CAI, deve versare:</p>
      
      <div class="numbered-item">
        <div class="number-badge">1</div>
        <div class="numbered-content">
          <span class="bullet-title">Quota Fissa di Gestione:</span> Pagamento integrale dell'"Onere di Amministrazione" fissato per la scelta contrattuale dedotta in inadempienza.
        </div>
      </div>

      <div class="numbered-item">
        <div class="number-badge">2</div>
        <div class="numbered-content">
          <span class="bullet-title">Quota Differenziale di Mercato:</span> Somma pari alla differenza (se positiva) tra il prezzo pattuito a contratto (PDT) e il maggior prezzo medio calcolato sui valori massimi della categoria di appartenenza rilevati dai bollettini della CCIAA territorialmente competente nel mese di LUGLIO 2027, moltiplicata per le tonnellate non consegnate.
        </div>
      </div>

      <div class="numbered-item">
        <div class="number-badge">3</div>
        <div class="numbered-content">
          <span class="bullet-title">Risarcimento Danni Ulteriori:</span> CAI si riserva espressamente il diritto di addebitare i costi logistici straordinari, i maggiori oneri per acquisti sostitutivi d'urgenza, le perdite economiche subite dalla risoluzione o chiusura forzata dei contratti derivati di copertura finanziaria (futures) stipulati sui mercati a termine e la perdita delle premialità di filiera.
        </div>
      </div>

      <div class="numbered-item">
        <div class="number-badge">4</div>
        <div class="numbered-content">
          <span class="bullet-title">Rinuncia alla Riduzione Giudiziale della Penale:</span> L'agricoltore, mediante espressa doppia sottoscrizione delle clausole vessatorie, rinuncia formalmente ad adire il Giudice per ottenere la riduzione equitativa dell'ammontare della penale ex art. 1384 C.C.
        </div>
      </div>
    </div>
  </div>

  <!-- SEZIONE 5: AGRO (6 CARD GRID) -->
  <div class="section-block">
    <div class="section-header">
      <span class="section-title">5. IMPEGNI AGRONOMICI, SANITARI E DI COLTIVAZIONE</span>
      <span class="section-badge">DISCIPLINARE DI CAMPO</span>
    </div>
    <div class="section-body" style="padding: 4px 6px;">
      <div class="grid-container">
        <div class="grid-card">
          <span class="bullet-title">• Semente Certificata e No OGM</span>
          Utilizzo esclusivo di sementi controllate e certificate di provenienza certificata.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Delimitazione Terreni della Coltivazione</span>
          Individuazione certa delle superfici condotte sotto contratto.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Lotta Obbligatoria alla Cimice</span>
          Le cariossidi danneggiate da cimice hanno tolleranza zero (0%).
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Divieto Fanghi e Trattamenti Post-Raccolta</span>
          Divieto assoluto di fanghi e trattamenti di conservazione post-raccolta.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Prevenzione Contaminazioni da Macchine</span>
          Scongiurare qualsiasi inquinamento accidentale da grani teneri, semi estranei o corpi inerti.
        </div>
        <div class="grid-card">
          <span class="bullet-title">• Diritto di Ispezione in Campo</span>
          Accesso garantito in campo per verifiche da parte del Personale Tecnico CAI.
        </div>
      </div>
    </div>
  </div>

  <!-- SEZIONE 7 & 8: ADEMPIMENTI E CLAUSOLE LEGALI -->
  <div class="two-cols" style="gap: 6px; margin-bottom: 5px;">
    <!-- ADEMPIMENTI -->
    <div class="col section-block" style="margin-bottom: 0;">
      <div class="section-header">
        <span class="section-title">7. ADEMPIMENTI AMMINISTRATIVI</span>
        <span class="section-badge">TRACCIABILITÀ</span>
      </div>
      <div class="section-body" style="font-size: 7.35pt;">
        <p><span class="bullet-title">• DDT:</span> Documento di Trasporto regolare ad ogni conferimento.</p>
        <p><span class="bullet-title">• Quaderno e Fascicolo:</span> Disponibili e aggiornati a richiesta CAI.</p>
        <p><span class="bullet-title">• Dichiarazione Doganale (Pag. 6):</span> Origine preferenziale UE (Italia).</p>
      </div>
    </div>

    <!-- CLAUSOLE GIURIDICHE -->
    <div class="col section-block" style="margin-bottom: 0;">
      <div class="section-header">
        <span class="section-title">8. CLAUSOLE GIURIDICHE</span>
        <span class="section-badge">CONDIZIONI LEGALI</span>
      </div>
      <div class="section-body" style="font-size: 7.35pt;">
        <p><span class="bullet-title">• Divieto Cessione Credito:</span> Salva autorizzazione scritta di CAI.</p>
        <p><span class="bullet-title">• Compensazione Debiti:</span> Diretta con il credito post-conferimento.</p>
        <p><span class="bullet-title">• Vizi Occulti e Foro:</span> Denuncia entro 15 gg. Foro di Bologna.</p>
      </div>
    </div>
  </div>

  <!-- Banner finale con Disclaimer Integrato -->
  <div class="bottom-banner-container">
    <div class="bottom-banner">
      Puoi visionare il contratto completo presso la tua Agenzia CAI di fiducia.
    </div>
    <div class="bottom-disclaimer">
      <em>Disclaimer:</em> <span class="desc">le quotazioni giornaliere sono aggiornate ma indicative; saranno confermate o eventualmente corrette al momento della stipula dell'accordo presso l'agenzia Cai di riferimento</span>
    </div>
  </div>

  <div class="page-footer">
    Pagina 2 di 2
  </div>
</div>

</body>
</html>
"""

def compile_pdf(html_content: str, output_pdf_path: str):
    temp_html = output_pdf_path + ".temp.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    file_url = "file:///" + os.path.abspath(temp_html).replace("\\", "/")
    
    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={output_pdf_path}",
        file_url
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(temp_html):
        os.remove(temp_html)
        
    if res.returncode != 0:
        raise RuntimeError(f"Errore generazione PDF con Chrome: {res.stderr}")
        
    reader = pypdf.PdfReader(output_pdf_path)
    page_count = len(reader.pages)
    return page_count

if __name__ == "__main__":
    targets = [
        ("Guida agli Impegni e Conferimento Grano Tenero.pdf", HTML_TENERO),
        ("Guida agli Impegni e Conferimento Grano Duro.pdf", HTML_DURO)
    ]
    
    for filename, html in targets:
        # Genera in root
        root_path = os.path.join(WORKSPACE_DIR, filename)
        pages_root = compile_pdf(html, root_path)
        print(f"File generato in root: {filename} -> Pagine: {pages_root}")
        
        # Copia/genera anche in static/ se presente
        static_dir = os.path.join(WORKSPACE_DIR, "static")
        if os.path.exists(static_dir):
            static_path = os.path.join(static_dir, filename)
            pages_static = compile_pdf(html, static_path)
            print(f"File aggiornato in static/: {filename} -> Pagine: {pages_static}")
