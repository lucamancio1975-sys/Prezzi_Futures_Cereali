/**
 * FUTURES GRANO & CEREALI - ENGINE REATTIVO WEB APP (PWA)
 * Architettura Client-Side ad alte prestazioni senza dipendenze server.
 */

const CONFIG = {
  DATA_LOCAL_URL: './data/storico_prezzi.json',
  DATA_REMOTE_URL: 'https://raw.githubusercontent.com/lucamancio1975-sys/Prezzi_Futures_Cereali/main/data/storico_prezzi.json',
  GITHUB_REPO: 'lucamancio1975-sys/Prezzi_Futures_Cereali',
  DEFAULT_TIMEFRAME: 'june', // '1m', '3m', 'june', 'all'
};

const MESI_IT = ['', 'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre'];
const GIORNI_IT = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'];

const STATE = {
  allQuotes: [],
  currentProduct: null, // 'DURO_PDT' | 'TENERO_PDT' | 'TENERO_PMG'
  timeframe: CONFIG.DEFAULT_TIMEFRAME,
  chartInstance: null,
  deferredPrompt: null,
  lastSyncTime: null,
  applyPremioBologna: false
};

// =========================================================================
// UTILITY & FORMATTER
// =========================================================================
function formatDateItalian(dateStr) {
  if (!dateStr) return 'N.D.';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
  const dayName = GIORNI_IT[(d.getDay() + 6) % 7];
  const monthName = MESI_IT[parseInt(parts[1])];
  return `${dayName} ${parseInt(parts[2])} ${monthName} ${parts[0]}`;
}

function formatDateShort(dateStr) {
  if (!dateStr) return '';
  const parts = dateStr.split('-');
  if (parts.length !== 3) return dateStr;
  const monthShort = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'][parseInt(parts[1]) - 1];
  return `${parts[2]} ${monthShort}`;
}

function getTodayItalianStr() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, '0');
  const d = String(now.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

// =========================================================================
// DATA FETCHING CON STRATEGIA RESILIENTE
// =========================================================================
async function fetchQuotesData() {
  const syncBtn = document.getElementById('btn-sync');
  if (syncBtn) syncBtn.classList.add('spinning');

  let data = null;
  const timestamp = Date.now();

  try {
    // 1. Prova prima il file locale (stesso host / server statico)
    const resp = await fetch(`${CONFIG.DATA_LOCAL_URL}?_t=${timestamp}`, { cache: 'no-store' });
    if (resp.ok) {
      data = await resp.json();
    }
  } catch (err) {
    console.warn('Fallback a GitHub Raw per caricamento dati...');
  }

  if (!data || !Array.isArray(data) || data.length === 0) {
    try {
      // 2. Fallback diretto a GitHub Raw (sempre aggiornato via Actions)
      const remoteResp = await fetch(`${CONFIG.DATA_REMOTE_URL}?_t=${timestamp}`, { cache: 'no-store' });
      if (remoteResp.ok) {
        data = await remoteResp.json();
      }
    } catch (err) {
      console.error('Errore download da GitHub:', err);
    }
  }

  if (syncBtn) syncBtn.classList.remove('spinning');

  if (data && Array.isArray(data) && data.length > 0) {
    STATE.allQuotes = data;
    STATE.lastSyncTime = new Date();
    try {
      localStorage.setItem('futures_quotes_cache', JSON.stringify(data));
    } catch (e) {}
    renderApp();
    return true;
  } else {
    // Recupero da cache locale se offline
    const cached = localStorage.getItem('futures_quotes_cache');
    if (cached) {
      STATE.allQuotes = JSON.parse(cached);
      renderApp();
      return true;
    }
  }
  return false;
}

// =========================================================================
// ELABORAZIONE QUOTAZIONI PER PRODOTTO
// =========================================================================
function getQuotesForProduct(productKey) {
  let prodName = 'GRANO DURO';
  let contractType = 'PDT';

  if (productKey === 'TENERO_PDT') {
    prodName = 'GRANO TENERO FINO ROSSO';
    contractType = 'PDT';
  } else if (productKey === 'TENERO_PMG') {
    prodName = 'GRANO TENERO FINO ROSSO';
    contractType = 'PMG';
  }

  const filtered = STATE.allQuotes.filter((q) => {
    const p = String(q.prodotto || '').trim().toUpperCase();
    const t = String(q.tipo || '').trim().toUpperCase();
    const s = String(q.scadenza || '').trim().toLowerCase();
    return p === prodName && t === contractType && s === 'lug-27';
  });

  filtered.sort((a, b) => (a.data > b.data ? 1 : -1));
  return filtered;
}

function calculateProductStats(quotes) {
  if (!quotes || quotes.length === 0) {
    return {
      lastPrice: 0,
      prevPrice: 0,
      delta: 0,
      pctChange: 0,
      lastDate: '',
      minPrice: 0,
      maxPrice: 0,
      avgPrice: 0
    };
  }

  const lastRow = quotes[quotes.length - 1];
  const prevRow = quotes.length > 1 ? quotes[quotes.length - 2] : lastRow;

  const lastP = parseFloat(lastRow.prezzo) || 0;
  const prevP = parseFloat(prevRow.prezzo) || lastP;
  const delta = lastP - prevP;
  const pctChange = prevP > 0 ? (delta / prevP) * 100 : 0;

  const prices = quotes.map((q) => parseFloat(q.prezzo) || 0);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const avgP = prices.reduce((a, b) => a + b, 0) / prices.length;

  return {
    lastPrice: lastP,
    prevPrice: prevP,
    delta: delta,
    pctChange: pctChange,
    lastDate: lastRow.data,
    minPrice: minP,
    maxPrice: maxP,
    avgPrice: avgP
  };
}

// =========================================================================
// RENDERING SCHERMATE (HOME vs DETTAGLIO)
// =========================================================================
function renderApp() {
  const hash = window.location.hash.replace('#', '');
  if (['duro-pdt', 'tenero-pdt', 'tenero-pmg'].includes(hash)) {
    STATE.currentProduct = hash === 'duro-pdt' ? 'DURO_PDT' : (hash === 'tenero-pdt' ? 'TENERO_PDT' : 'TENERO_PMG');
  } else {
    STATE.currentProduct = null;
  }

  if (STATE.currentProduct) {
    renderDetailView(STATE.currentProduct);
  } else {
    renderHomeView();
  }
}

function renderHomeView() {
  const container = document.getElementById('main-content');
  if (!container) return;

  const duroQuotes = getQuotesForProduct('DURO_PDT');
  const teneroPdtQuotes = getQuotesForProduct('TENERO_PDT');
  const teneroPmgQuotes = getQuotesForProduct('TENERO_PMG');

  const duroStats = calculateProductStats(duroQuotes);
  const teneroPdtStats = calculateProductStats(teneroPdtQuotes);
  const teneroPmgStats = calculateProductStats(teneroPmgQuotes);

  const todayStr = getTodayItalianStr();
  const hasToday = [duroStats, teneroPdtStats, teneroPmgStats].some((s) => s.lastDate === todayStr);
  const latestDate = duroStats.lastDate || '';

  let statusBadgeHtml = '';
  if (hasToday) {
    statusBadgeHtml = `<span class="app-sync-status status-today">🟢 Database aggiornato a Oggi</span>`;
  } else {
    statusBadgeHtml = `<span class="app-sync-status status-wait">⏳ Aggiornato al ${formatDateShort(latestDate)} (In attesa quotazione odierna)</span>`;
  }

  const lastSyncStr = STATE.lastSyncTime ? STATE.lastSyncTime.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }) : '';

  function getDeltaHtml(delta) {
    const sign = delta > 0 ? '+' : '';
    const cls = delta > 0 ? 'delta-up' : (delta < 0 ? 'delta-down' : 'delta-zero');
    return `<span class="${cls}">${sign}${delta.toFixed(2)} €/t</span>`;
  }

  container.innerHTML = `
    <div class="fade-in">
      <div class="futures-protection-container">
        <div class="futures-protection-badge">
          <span style="font-size: 1.15rem; line-height: 1;">🛡️</span>
          <span class="futures-protection-text">Contratti di Protezione Futures per i Cereali</span>
        </div>
      </div>

      <div class="status-badge-container">
        ${statusBadgeHtml}
        ${lastSyncStr ? `<div class="status-time">Ultima verifica: ore ${lastSyncStr}</div>` : ''}
      </div>

      <div class="main-question-card">
        <h1 class="main-question-title">Che quotazione ti interessa?</h1>
        <div class="main-question-sub">Seleziona una delle opzioni per visualizzare quotazione, grafico e storico</div>
      </div>

      <div class="product-buttons-list">
        <!-- 1. GRANO DURO PDT -->
        <a href="#duro-pdt" class="product-card-btn duro" id="btn-card-duro">
          <div class="product-card-left">
            <span class="product-card-icon">🌾</span>
            <div class="product-card-info">
              <span class="product-title">Grano Duro prezzo determinato</span>
              <div class="product-meta">
                <span class="badge-tag">Raccolto Luglio 2027</span>
                <span class="badge-tag">PDT</span>
              </div>
            </div>
          </div>
          <div class="product-card-right">
            <span class="product-price-preview">${duroStats.lastPrice.toFixed(2)} <small style="font-size:0.75rem;">€/t</small></span>
            <span class="product-delta-preview">${getDeltaHtml(duroStats.delta)}</span>
          </div>
        </a>

        <!-- 2. GRANO TENERO PDT -->
        <a href="#tenero-pdt" class="product-card-btn tenero-pdt" id="btn-card-tenero-pdt">
          <div class="product-card-left">
            <span class="product-card-icon">🌱</span>
            <div class="product-card-info">
              <span class="product-title">Grano Tenero prezzo determinato</span>
              <div class="product-meta">
                <span class="badge-tag">Raccolto Luglio 2027</span>
                <span class="badge-tag">PDT</span>
              </div>
            </div>
          </div>
          <div class="product-card-right">
            <span class="product-price-preview">${teneroPdtStats.lastPrice.toFixed(2)} <small style="font-size:0.75rem;">€/t</small></span>
            <span class="product-delta-preview">${getDeltaHtml(teneroPdtStats.delta)}</span>
          </div>
        </a>

        <!-- 3. GRANO TENERO PMG -->
        <a href="#tenero-pmg" class="product-card-btn tenero-pmg" id="btn-card-tenero-pmg">
          <div class="product-card-left">
            <span class="product-card-icon">🌱</span>
            <div class="product-card-info">
              <span class="product-title">Grano Tenero prezzo minimo garantito</span>
              <div class="product-meta">
                <span class="badge-tag">Raccolto Luglio 2027</span>
                <span class="badge-tag">PMG</span>
              </div>
            </div>
          </div>
          <div class="product-card-right">
            <span class="product-price-preview">${teneroPmgStats.lastPrice.toFixed(2)} <small style="font-size:0.75rem;">€/t</small></span>
            <span class="product-delta-preview">${getDeltaHtml(teneroPmgStats.delta)}</span>
          </div>
        </a>
      </div>

      <button class="home-sync-btn" id="btn-home-sync">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
        </svg>
        <span>Controlla nuove quotazioni da Gmail & Cloud</span>
      </button>
    </div>
  `;

  document.getElementById('btn-home-sync')?.addEventListener('click', () => {
    fetchQuotesData();
  });
}

function renderDetailView(productKey) {
  const container = document.getElementById('main-content');
  if (!container) return;

  window.scrollTo(0, 0);

  let prodName = 'GRANO DURO';
  let contractType = 'PDT';
  let titleShort = 'QUOTAZIONE FUTURES 🌾 GRANO DURO';
  let heroClass = 'duro';
  let chartLineColor = '#fbbf24';
  let chartFillColor = 'rgba(251, 191, 36, 0.08)';
  let pdfGuideName = 'Guida agli Impegni e Conferimento Grano Duro.pdf';

  if (productKey === 'TENERO_PDT') {
    prodName = 'GRANO TENERO FINO ROSSO';
    contractType = 'PDT';
    titleShort = 'QUOTAZIONE FUTURES 🌱 GRANO TENERO';
    heroClass = 'tenero-pdt';
    chartLineColor = '#00ff88';
    chartFillColor = 'rgba(0, 255, 136, 0.08)';
    pdfGuideName = 'Guida agli Impegni e Conferimento Grano Tenero.pdf';
  } else if (productKey === 'TENERO_PMG') {
    prodName = 'GRANO TENERO FINO ROSSO';
    contractType = 'PMG';
    titleShort = 'QUOTAZIONE FUTURES 🌱 GRANO TENERO';
    heroClass = 'tenero-pmg';
    chartLineColor = '#38bdf8';
    chartFillColor = 'rgba(56, 189, 248, 0.08)';
    pdfGuideName = 'Guida agli Impegni e Conferimento Grano Tenero.pdf';
  }

  const quotes = getQuotesForProduct(productKey);
  const stats = calculateProductStats(quotes);

  const todayStr = getTodayItalianStr();
  const isToday = stats.lastDate === todayStr;

  const statusBadge = isToday
    ? '<span class="app-sync-status status-today">🟢 Aggiornato a Oggi</span>'
    : `<span class="app-sync-status status-wait">⏳ Aggiornato al ${formatDateShort(stats.lastDate)} (In attesa oggi)</span>`;

  const deltaSign = stats.delta > 0 ? '+' : '';
  const deltaClass = stats.delta > 0 ? 'delta-up' : (stats.delta < 0 ? 'delta-down' : 'delta-zero');

  let specsHtml = '';
  if (productKey === 'DURO_PDT') {
    specsHtml = `
      <div class="hero-specs-bar">
        <span class="hero-spec-tag">Prezzo base PDT</span>
        <span class="hero-spec-dot">•</span>
        <span class="hero-spec-detail">P.S. &ge; 78</span>
        <span class="hero-spec-dot">•</span>
        <span class="hero-spec-detail">Prot. &ge; 13,5%</span>
      </div>`;
  } else {
    specsHtml = `
      <div class="hero-specs-bar">
        <span class="hero-spec-tag">Prezzo base Fino Rosso</span>
        <span class="hero-spec-dot">•</span>
        <span class="hero-spec-premio">Bologna e Giorgione: +30 €/t</span>
      </div>`;
  }

  const isTenero = productKey.startsWith('TENERO');
  const switchLabel = productKey === 'TENERO_PDT' ? 'Switch a PMG' : 'Switch a PDT';
  const switchTarget = productKey === 'TENERO_PDT' ? '#tenero-pmg' : '#tenero-pdt';

  container.innerHTML = `
    <div class="fade-in">
      <!-- Navigazione Superiore -->
      <div class="nav-action-bar">
        <a href="#home" class="btn-nav">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7"/>
          </svg>
          <span>Torna alla selezione</span>
        </a>
        ${isTenero ? `
          <a href="${switchTarget}" class="btn-nav">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
            </svg>
            <span>${switchLabel}</span>
          </a>
        ` : '<div></div>'}
      </div>

      <!-- Topbar Prodotto -->
      <div class="detail-topbar">
        <div class="detail-title-group">
          <div class="detail-title-row">
            <span class="detail-title-text">${titleShort}</span>
            <span class="pill-expiry">LUG-27</span>
            <span class="pill-contract pill-${contractType.toLowerCase()}">${contractType}</span>
          </div>
          <div>${statusBadge}</div>
        </div>
        <img src="./logo_optimized.webp" class="app-brand-logo" alt="Logo" onerror="this.style.display='none'">
      </div>

      <!-- Hero Card Prezzo Attuale -->
      <div class="hero-box ${heroClass}">
        <div class="hero-top-row">
          <div>
            <div class="hero-price-val ${heroClass}">${stats.lastPrice.toFixed(2)} <span class="hero-price-unit">€/t</span></div>
            <div class="hero-date-val">📅 <b>${formatDateItalian(stats.lastDate)}</b></div>
          </div>
          <button class="hero-law-btn" id="btn-open-pdf" title="Visualizza Guida agli Impegni e Conferimento">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v18"/>
              <path d="M7 21h10"/>
              <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
              <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
              <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
            </svg>
            <span>GUIDA</span>
          </button>
        </div>
        ${specsHtml}
        <div class="hero-delta-row">
          <span class="hero-delta-label">Differenziale da quotazione precedente:</span>
          <span class="hero-badge-delta ${deltaClass}">${deltaSign}${stats.delta.toFixed(2)} €/t (${deltaSign}${stats.pctChange.toFixed(2)}%)</span>
        </div>
      </div>

      <!-- Grafico (Sola Linea Pulita) -->
      <div class="chart-card">
        <div class="chart-wrapper">
          <canvas id="futuresChart"></canvas>
        </div>
      </div>
    </div>
  `;

  // Inizializza Grafico a sola linea
  renderChart(quotes, chartLineColor);

  document.getElementById('btn-open-pdf')?.addEventListener('click', () => {
    openPdfModal(pdfGuideName, titleShort);
  });
}

// =========================================================================
// GRAFICO CHART.JS (SOLA LINEA SENZA TOOLTIP NÉ TIMEFRAME)
// =========================================================================
function renderChart(quotes, lineColor) {
  const ctx = document.getElementById('futuresChart');
  if (!ctx || typeof Chart === 'undefined' || !quotes || quotes.length === 0) return;

  if (STATE.chartInstance) {
    STATE.chartInstance.destroy();
    STATE.chartInstance = null;
  }

  const labels = quotes.map((q) => q.data);
  const dataPoints = quotes.map((q) => parseFloat(q.prezzo));

  const pMin = Math.min(...dataPoints);
  const pMax = Math.max(...dataPoints);
  const yMin = Math.max(0, Math.floor((pMin - 5) / 5) * 5);
  const yMax = Math.ceil((pMax + 5) / 5) * 5;

  STATE.chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Quotazione €/t',
          data: dataPoints,
          borderColor: lineColor,
          backgroundColor: 'transparent',
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 0,
          pointHitRadius: 0,
          tension: 0.15,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      events: [], // Disattiva interazioni/tooltip
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#94a3b8',
            font: { family: 'JetBrains Mono', size: 10 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 6,
            callback: function(val) {
              const dStr = this.getLabelForValue(val);
              return formatDateShort(dStr);
            }
          }
        },
        y: {
          min: yMin,
          max: yMax,
          grid: { color: 'rgba(255, 255, 255, 0.06)' },
          ticks: {
            color: '#94a3b8',
            font: { family: 'JetBrains Mono', size: 10 },
            callback: (val) => `${val} €`
          }
        }
      }
    }
  });
}

// =========================================================================
// MODALE GUIDA PDF
// =========================================================================
function openPdfModal(pdfFilename, title) {
  const overlay = document.getElementById('modal-pdf');
  const titleEl = document.getElementById('modal-pdf-title');
  const linkEl = document.getElementById('modal-pdf-link');

  if (overlay && titleEl && linkEl) {
    titleEl.textContent = `Guida: ${title}`;
    linkEl.href = `./docs/${encodeURIComponent(pdfFilename)}`;
    linkEl.download = pdfFilename;
    overlay.classList.add('active');
  }
}

function closePdfModal() {
  const overlay = document.getElementById('modal-pdf');
  if (overlay) overlay.classList.remove('active');
}

// =========================================================================
// PWA INSTALLATION PROMPT
// =========================================================================
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  STATE.deferredPrompt = e;
  const banner = document.getElementById('pwa-install-banner');
  if (banner) banner.classList.add('active');
});

function setupPwaInstall() {
  const installBtn = document.getElementById('btn-pwa-install');
  installBtn?.addEventListener('click', async () => {
    if (!STATE.deferredPrompt) return;
    STATE.deferredPrompt.prompt();
    const { outcome } = await STATE.deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      const banner = document.getElementById('pwa-install-banner');
      if (banner) banner.classList.remove('active');
    }
    STATE.deferredPrompt = null;
  });
}

// =========================================================================
// INIZIALIZZAZIONE GLOBALE
// =========================================================================
window.addEventListener('DOMContentLoaded', () => {
  // 1. Carica subito i dati da localStorage per evitare flash o ritardi
  try {
    const cached = localStorage.getItem('futures_quotes_cache');
    if (cached) {
      STATE.allQuotes = JSON.parse(cached);
    }
  } catch (e) {}

  // 2. Registra Service Worker PWA senza ricaricamenti aggressivi
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js?v=2.2')
      .then((reg) => {
        console.log('PWA Service Worker registered:', reg.scope);
      })
      .catch((err) => console.warn('PWA SW failed:', err));
  }

  // 3. Setup Modale & Installazione
  document.getElementById('modal-close-btn')?.addEventListener('click', closePdfModal);
  document.getElementById('modal-pdf')?.addEventListener('click', (e) => {
    if (e.target.id === 'modal-pdf') closePdfModal();
  });
  setupPwaInstall();

  // 4. Setup Pulsante Sincronizzazione Header
  document.getElementById('btn-sync')?.addEventListener('click', () => {
    fetchQuotesData();
  });

  // 5. Ascolto Cambi Hash URL
  window.addEventListener('hashchange', () => {
    renderApp();
  });

  // 6. Primo render immediato
  renderApp();

  // 7. Aggiornamento dati in background
  fetchQuotesData();
});
