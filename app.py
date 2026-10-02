"""
Applicazione Web Streamlit: Monitoraggio Quotazioni Futures Cereali
- Grano Duro PDT (Raccolto Luglio 2027)
- Grano Tenero PDT (Raccolto Luglio 2027)
- Grano Tenero PMG (Raccolto Luglio 2027)
Design: Wall Street / Bloomberg Terminal - Mobile First (Smartphone Friendly)
"""

import os
import io
import math
import time
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

# Configurazione robusta dei percorsi di sistema (funziona sia su Streamlit Cloud sia in locale)
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXEC_DIR = os.path.join(BASE_DIR, "execution")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if EXEC_DIR not in sys.path:
    sys.path.insert(0, EXEC_DIR)

# Import moduli di esecuzione locali
try:
    import execution.storage_manager as storage_manager
except Exception:
    import storage_manager

try:
    import execution.fetch_gmail_quotes as fetch_gmail_quotes
except Exception:
    import fetch_gmail_quotes

# Riferimenti sicuri alle funzioni necessarie
load_quotes = storage_manager.load_quotes
add_quotes = storage_manager.add_quotes
get_quotes_for_selection = storage_manager.get_quotes_for_selection
get_delta_for_selection = storage_manager.get_delta_for_selection
sync_from_github = getattr(storage_manager, "sync_from_github", lambda: 0)
get_latest_db_date = getattr(storage_manager, "get_latest_db_date", lambda: "")

fetch_quotes_from_gmail = fetch_gmail_quotes.fetch_quotes_from_gmail
check_and_sync_today_quotes = getattr(fetch_gmail_quotes, "check_and_sync_today_quotes", None)

import streamlit.components.v1 as components

# Sincronizzazione PWA automatica alla radice del server
try:
    from execution.setup_pwa import configure_pwa
    configure_pwa()
except Exception:
    pass

load_dotenv()

# Configurazione Pagina Streamlit e Icona Ufficiale
ICON_PATH = os.path.join(os.path.dirname(__file__), "static", "icon-192.png")
PAGE_ICON = ICON_PATH if os.path.exists(ICON_PATH) else "🌾"

st.set_page_config(
    page_title="Futures Grano - Quotazioni Giornaliere",
    page_icon=PAGE_ICON,
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Iniezione sicura dei metadati PWA nel documento principale
components.html("""
<script>
(function() {
    try {
        const targetDoc = window.parent ? window.parent.document : document;
        const targetNav = window.parent ? window.parent.navigator : navigator;
        const head = targetDoc.head || document.head;
        targetDoc.title = 'Futures Grano - Quotazioni Giornaliere';
        
        function createOrUpdate(tag, attrs) {
            let sel = tag;
            if (attrs.rel) sel += '[rel="' + attrs.rel + '"]';
            if (attrs.name) sel += '[name="' + attrs.name + '"]';
            let el = head.querySelector(sel);
            if (!el) {
                el = targetDoc.createElement(tag);
                head.appendChild(el);
            }
            for (let k in attrs) {
                el.setAttribute(k, attrs[k]);
            }
        }
        
        createOrUpdate('link', { rel: 'manifest', href: '/app/static/manifest.json' });
        createOrUpdate('link', { rel: 'apple-touch-icon', href: '/app/static/icon-180.png' });
        createOrUpdate('link', { rel: 'icon', type: 'image/png', sizes: '192x192', href: '/app/static/icon-192.png' });
        createOrUpdate('link', { rel: 'shortcut icon', href: '/app/static/favicon.png' });
        createOrUpdate('meta', { name: 'theme-color', content: '#030712' });
        createOrUpdate('meta', { name: 'application-name', content: 'Futures Grano' });
        createOrUpdate('meta', { name: 'mobile-web-app-capable', content: 'yes' });
        createOrUpdate('meta', { name: 'apple-mobile-web-app-capable', content: 'yes' });
        createOrUpdate('meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' });
        createOrUpdate('meta', { name: 'apple-mobile-web-app-title', content: 'Futures Grano' });
        
        if ('serviceWorker' in targetNav) {
            targetNav.serviceWorker.register('/sw.js', { scope: '/' })
                .then(function(reg) { console.log('PWA Service Worker registrato:', reg.scope); })
                .catch(function(err) { console.warn('PWA SW error:', err); });
        }
    } catch(e) {
        console.warn('Errore iniezione PWA head:', e);
    }
})();
</script>
""", height=0, width=0)

# =========================================================================
# CSS GLOBALE MOBILE-FIRST (BLOOMBERG WALL STREET THEME)
# =========================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700;800&display=block');

    :root {
        color-scheme: dark !important;
    }

    *, *::before, *::after {
        box-sizing: border-box;
    }

    html, body, #root, .stApp {
        background-color: #030712 !important;
        background: #030712 !important;
        color: #f1f5f9 !important;
        overflow-x: hidden;
        max-width: 100vw;
    }

    /* Ottimizzazione contenitore principale per smartphone con ampio respiro in fondo */
    .block-container {
        padding-top: 0px !important;
        padding-bottom: clamp(140px, 20vh, 200px) !important;
        padding-left: clamp(0.4rem, 2.5vw, 0.85rem) !important;
        padding-right: clamp(0.4rem, 2.5vw, 0.85rem) !important;
        max-width: 680px !important;
    }

    .stApp {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 'Plus Jakarta Sans', sans-serif;
    }

    /* ------------------------------------------------------------- */
    /* NASCONDI TASSATIVAMENTE ELEMENTI NATIVI STREAMLIT / GITHUB    */
    /* ------------------------------------------------------------- */
    header[data-testid="stHeader"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    [data-testid="stDecoration"] {
        display: none !important;
    }

    [data-testid="stToolbar"],
    .stDeployButton,
    [data-testid="stDeployButton"],
    .stAppDeployButton,
    #MainMenu,
    [data-testid="stMainMenu"],
    .stMainMenu,
    [data-testid="main-menu-list"],
    div[data-testid="stStatusWidget"],
    div[data-testid="stConnectionStatus"],
    [data-testid="manage-app-button"],
    [data-testid="stManageAppButton"],
    .stManageAppButton,
    #manage-app-button,
    button[kind="manageAppButton"],
    [class*="manageApp" i],
    [class*="ManageApp" i],
    [id*="manageApp" i],
    [aria-label*="manage app" i],
    [title*="Manage app" i],
    div:has(> button[data-testid="manage-app-button"]),
    footer,
    [data-testid="stFooter"],
    .viewerBadge_container__1QSob,
    [class*="viewerBadge"],
    [class*="ViewerBadge"],
    [class*="ProfileButton"],
    [class*="profileButton"],
    [data-testid="stToolbar"] a[href*="github.com"],
    [data-testid="stToolbar"] button[title*="GitHub"],
    [data-testid="stToolbar"] [title*="GitHub"],
    [data-testid="stToolbar"] [aria-label*="GitHub" i],
    [data-testid="stToolbar"] [title*="source" i],
    [data-testid="stToolbar"] [aria-label*="source" i],
    [data-testid="stToolbar"] [title*="repository" i],
    [data-testid="stToolbar"] [title*="Fork" i],
    [data-testid="stToolbarActions"],
    [data-testid="stToolbarActions"] a,
    [data-testid="stToolbarActions"] button,
    a[href*="github.com"],
    button[title*="GitHub"],
    svg[title*="GitHub"],
    svg[aria-label*="GitHub"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* Iframe invisibili per iniezioni PWA/JS e contenitori vuoti */
    iframe[height="0"], iframe[width="0"],
    div[data-testid="element-container"]:has(iframe[height="0"]),
    div[data-testid="element-container"]:has(> div > iframe[height="0"]),
    div[data-testid="stVerticalBlock"] > div:has(iframe[height="0"]) {
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }

    /* ------------------------------------------------------------- */
    /* SCHERMATA PRINCIPALE (SELEZIONE)                             */
    /* ------------------------------------------------------------- */
    .futures-protection-container {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 6px !important;
        margin-bottom: 14px !important;
        padding: 0 2px;
    }
    .futures-protection-badge {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(26, 38, 64, 0.8) 100%);
        border: 1px solid rgba(245, 158, 11, 0.4);
        border-radius: 9999px;
        padding: 5px 16px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08);
        transition: all 0.3s ease;
    }
    .futures-protection-badge:hover {
        border-color: rgba(245, 158, 11, 0.8);
        box-shadow: 0 6px 20px rgba(245, 158, 11, 0.35);
        transform: translateY(-1px);
    }
    .futures-protection-text {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(0.76rem, 2.7vw, 0.88rem);
        font-weight: 700;
        letter-spacing: 0.015em;
        background: linear-gradient(90deg, #f59e0b 0%, #fef08a 50%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
    }

    .main-question-card {
        background: linear-gradient(145deg, #090e1a 0%, #111c33 100%);
        border: 1.5px solid #1e293b;
        border-radius: 14px;
        padding: 12px 16px !important;
        margin: 0 0 18px 0 !important;
        text-align: center;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        position: relative;
        overflow: hidden;
    }
    .main-question-card::before {
        content: '';
        position: absolute;
        top: 0; left: 10%; right: 10%;
        height: 2px;
        background: linear-gradient(90deg, transparent, #f59e0b, #00ff88, #38bdf8, transparent);
    }
    .main-question-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(1.10rem, 4.1vw, 1.36rem) !important;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.02em;
        line-height: 1.25 !important;
        margin: 0;
    }
    .main-question-sub {
        font-size: clamp(0.75rem, 2.4vw, 0.85rem) !important;
        color: #94a3b8;
        margin-top: 5px !important;
        font-weight: 500;
        line-height: 1.25 !important;
    }

    /* Separazione netta dei container dei tre bottoni */
    div.st-key-btn_duro_pdt,
    div.st-key-btn_tenero_pdt,
    div.st-key-btn_tenero_pmg,
    div[class*="st-key-btn_duro_pdt"],
    div[class*="st-key-btn_tenero_pdt"],
    div[class*="st-key-btn_tenero_pmg"] {
        margin-bottom: 14px !important;
    }

    /* Stile comune per i tre bottoni della schermata di scelta */
    .st-key-btn_duro_pdt button,
    .st-key-btn_tenero_pdt button,
    .st-key-btn_tenero_pmg button,
    div[class*="st-key-btn_duro_pdt"] button,
    div[class*="st-key-btn_tenero_pdt"] button,
    div[class*="st-key-btn_tenero_pmg"] button,
    button[aria-label*="Grano Duro"],
    button[aria-label*="Tenero prezzo determinato"],
    button[aria-label*="prezzo minimo"] {
        width: 100% !important;
        min-height: 54px !important;
        border-radius: 12px !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: clamp(0.98rem, 3.5vw, 1.14rem) !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 9px 14px !important;
        line-height: 1.25 !important;
        white-space: normal !important;
        text-align: center !important;
    }

    .st-key-btn_duro_pdt button p,
    .st-key-btn_tenero_pdt button p,
    .st-key-btn_tenero_pmg button p,
    div[class*="st-key-btn_duro_pdt"] button p,
    div[class*="st-key-btn_tenero_pdt"] button p,
    div[class*="st-key-btn_tenero_pmg"] button p,
    button[aria-label*="Grano Duro"] p,
    button[aria-label*="Tenero prezzo determinato"] p,
    button[aria-label*="prezzo minimo"] p {
        font-size: clamp(0.98rem, 3.5vw, 1.14rem) !important;
        line-height: 1.2 !important;
    }

    /* ------------------------------------------------------------- */
    /* ANIMAZIONI LAMPEGGIAMENTO TENUE (SOLO SCRITTA, RITMO LENTO)  */
    /* ------------------------------------------------------------- */
    @keyframes gentle-text-blink-ocra {
        0%, 100% {
            opacity: 1;
            filter: brightness(1);
            color: #df9e38 !important;
            text-shadow: 0 0 10px rgba(223, 158, 56, 0.45);
        }
        50% {
            opacity: 0.78;
            filter: brightness(0.92);
            color: #df9e38 !important;
            text-shadow: 0 0 3px rgba(223, 158, 56, 0.15);
        }
    }

    @keyframes gentle-text-blink-lampone {
        0%, 100% {
            opacity: 1;
            filter: brightness(1);
            color: #e02b55 !important;
            text-shadow: 0 0 10px rgba(224, 43, 85, 0.50);
        }
        50% {
            opacity: 0.78;
            filter: brightness(0.92);
            color: #e02b55 !important;
            text-shadow: 0 0 3px rgba(224, 43, 85, 0.15);
        }
    }

    @keyframes gentle-text-blink-cobalto {
        0%, 100% {
            opacity: 1;
            filter: brightness(1);
            color: #388bfd !important;
            text-shadow: 0 0 10px rgba(56, 139, 253, 0.50);
        }
        50% {
            opacity: 0.78;
            filter: brightness(0.92);
            color: #388bfd !important;
            text-shadow: 0 0 3px rgba(56, 139, 253, 0.15);
        }
    }

    /* 1. Grano Duro PDT (Giallo Ocra) */
    .st-key-btn_duro_pdt button,
    div[class*="st-key-btn_duro_pdt"] button,
    button[aria-label*="Grano Duro"] {
        background: linear-gradient(135deg, #1c1404 0%, #2e2008 100%) !important;
        border: 1.5px solid rgba(223, 158, 56, 0.65) !important;
        box-shadow: 0 4px 18px rgba(223, 158, 56, 0.18) !important;
    }
    .st-key-btn_duro_pdt button *,
    .st-key-btn_duro_pdt button p,
    div[class*="st-key-btn_duro_pdt"] button *,
    div[class*="st-key-btn_duro_pdt"] button p,
    button[aria-label*="Grano Duro"] *,
    button[aria-label*="Grano Duro"] p {
        color: #df9e38 !important;
        animation: gentle-text-blink-ocra 4.0s infinite ease-in-out !important;
    }
    .st-key-btn_duro_pdt button:hover,
    div[class*="st-key-btn_duro_pdt"] button:hover,
    button[aria-label*="Grano Duro"]:hover {
        background: linear-gradient(135deg, #2e2008 0%, #45300b 100%) !important;
        border-color: #fef08a !important;
        box-shadow: 0 6px 24px rgba(223, 158, 56, 0.35) !important;
        transform: translateY(-2px) !important;
    }
    .st-key-btn_duro_pdt button:hover *,
    div[class*="st-key-btn_duro_pdt"] button:hover *,
    button[aria-label*="Grano Duro"]:hover * {
        color: #fef08a !important;
    }

    /* 2. Grano Tenero PDT (Rosso Lampone) */
    .st-key-btn_tenero_pdt button,
    div[class*="st-key-btn_tenero_pdt"] button,
    button[aria-label*="Tenero prezzo determinato"] {
        background: linear-gradient(135deg, #240b13 0%, #35101c 100%) !important;
        border: 1.5px solid rgba(224, 43, 85, 0.65) !important;
        box-shadow: 0 4px 18px rgba(224, 43, 85, 0.20) !important;
    }
    .st-key-btn_tenero_pdt button *,
    .st-key-btn_tenero_pdt button p,
    div[class*="st-key-btn_tenero_pdt"] button *,
    div[class*="st-key-btn_tenero_pdt"] button p,
    button[aria-label*="Tenero prezzo determinato"] *,
    button[aria-label*="Tenero prezzo determinato"] p {
        color: #e02b55 !important;
        animation: gentle-text-blink-lampone 4.0s infinite ease-in-out !important;
    }
    .st-key-btn_tenero_pdt button:hover,
    div[class*="st-key-btn_tenero_pdt"] button:hover,
    button[aria-label*="Tenero prezzo determinato"]:hover {
        background: linear-gradient(135deg, #35101c 0%, #4c1729 100%) !important;
        border-color: #fb7185 !important;
        box-shadow: 0 6px 24px rgba(224, 43, 85, 0.40) !important;
        transform: translateY(-2px) !important;
    }
    .st-key-btn_tenero_pdt button:hover *,
    div[class*="st-key-btn_tenero_pdt"] button:hover *,
    button[aria-label*="Tenero prezzo determinato"]:hover * {
        color: #fecdd3 !important;
    }

    /* 3. Grano Tenero PMG (Blu Cobalto) */
    .st-key-btn_tenero_pmg button,
    div[class*="st-key-btn_tenero_pmg"] button,
    button[aria-label*="prezzo minimo"] {
        background: linear-gradient(135deg, #091a36 0%, #0f274f 100%) !important;
        border: 1.5px solid rgba(56, 139, 253, 0.65) !important;
        box-shadow: 0 4px 18px rgba(56, 139, 253, 0.20) !important;
    }
    .st-key-btn_tenero_pmg button *,
    .st-key-btn_tenero_pmg button p,
    div[class*="st-key-btn_tenero_pmg"] button *,
    div[class*="st-key-btn_tenero_pmg"] button p,
    button[aria-label*="prezzo minimo"] *,
    button[aria-label*="prezzo minimo"] p {
        color: #388bfd !important;
        animation: gentle-text-blink-cobalto 4.0s infinite ease-in-out !important;
    }
    .st-key-btn_tenero_pmg button:hover,
    div[class*="st-key-btn_tenero_pmg"] button:hover,
    button[aria-label*="prezzo minimo"]:hover {
        background: linear-gradient(135deg, #0f274f 0%, #17386d 100%) !important;
        border-color: #60a5fa !important;
        box-shadow: 0 6px 24px rgba(56, 139, 253, 0.40) !important;
        transform: translateY(-2px) !important;
    }
    .st-key-btn_tenero_pmg button:hover *,
    div[class*="st-key-btn_tenero_pmg"] button:hover *,
    button[aria-label*="prezzo minimo"]:hover * {
        color: #bfdbfe !important;
    }

    /* ------------------------------------------------------------- */
    /* INDICATORE DI CARICAMENTO / ATTENDI (PULSAZIONE MORBIDA)      */
    /* ------------------------------------------------------------- */
    @keyframes blink-attendi {
        0%, 100% {
            opacity: 1;
            filter: drop-shadow(0 0 10px rgba(251, 191, 36, 0.65));
            transform: scale(1);
        }
        50% {
            opacity: 0.28;
            filter: drop-shadow(0 0 3px rgba(251, 191, 36, 0.15));
            transform: scale(0.985);
        }
    }

    .attendi-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: clamp(26px, 7vh, 46px) 16px;
        margin: 16px 0;
        background: linear-gradient(145deg, #090e1a 0%, #111c33 100%);
        border: 1px solid #1e293b;
        border-radius: 14px;
        text-align: center;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
    }

    .attendi-text {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(1.3rem, 5.5vw, 1.85rem);
        font-weight: 800;
        color: #fbbf24;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        animation: blink-attendi 1.48s infinite ease-in-out;
    }

    /* ------------------------------------------------------------- */
    /* MASCHERA DEDICATA: TOP BAR & BADGE                            */
    /* ------------------------------------------------------------- */
    .app-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #0b1120;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 6px 12px;
        margin-bottom: 8px;
        gap: 8px;
    }
    .app-title-text {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(0.78rem, 3.4vw, 0.98rem);
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        line-height: 1.25;
    }
    .app-expiry-pill {
        color: #f59e0b;
        font-size: clamp(0.68rem, 2.5vw, 0.80rem);
        font-weight: 800;
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.35);
        padding: 1px 6px;
        border-radius: 4px;
        white-space: nowrap;
    }
    .app-contract-pill {
        font-size: clamp(0.68rem, 2.5vw, 0.80rem);
        font-weight: 800;
        padding: 1px 7px;
        border-radius: 4px;
        white-space: nowrap;
    }
    .pill-pmg {
        color: #38bdf8;
        background: rgba(56, 189, 248, 0.15);
        border: 1px solid rgba(56, 189, 248, 0.4);
    }
    .pill-pdt {
        color: #34d399;
        background: rgba(52, 211, 153, 0.15);
        border: 1px solid rgba(52, 211, 153, 0.4);
    }
    .app-sync-status {
        font-family: 'JetBrains Mono', monospace;
        font-size: clamp(0.68rem, 2.5vw, 0.78rem);
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 5px;
        display: inline-block;
        width: fit-content;
    }
    .status-today {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(52, 211, 153, 0.35);
    }
    .status-wait {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }

    /* ------------------------------------------------------------- */
    /* HERO CARD PREZZO                                              */
    /* ------------------------------------------------------------- */
    .hero-box {
        background: linear-gradient(135deg, #090e1a 0%, #0f172a 100%);
        border: 1.5px solid #1e293b;
        border-radius: 12px;
        padding: clamp(10px, 3vw, 14px) clamp(12px, 3.5vw, 16px);
        margin-bottom: 8px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
    .hero-box-duro::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2.5px;
        background: linear-gradient(90deg, #f59e0b, #10b981);
    }
    .hero-box-tenero-pdt::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2.5px;
        background: linear-gradient(90deg, #10b981, #00ff88);
    }
    .hero-box-tenero-pmg::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2.5px;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
    }

    .hero-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
    }
    .hero-price-section {
        display: flex;
        flex-direction: column;
        min-width: 0;
    }
    .hero-price-val {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(1.85rem, 7.2vw, 2.45rem);
        font-weight: 800;
        line-height: 1.0;
        letter-spacing: -0.03em;
        white-space: nowrap;
        display: inline-flex;
        align-items: baseline;
    }
    .hero-price-val-duro {
        color: #fbbf24;
        text-shadow: 0 0 20px rgba(251, 191, 36, 0.4);
    }
    .hero-price-val-tenero-pdt {
        color: #00ff88;
        text-shadow: 0 0 20px rgba(0, 255, 136, 0.4);
    }
    .hero-price-val-tenero-pmg {
        color: #38bdf8;
        text-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
    }
    .hero-price-unit {
        font-size: clamp(1.05rem, 4vw, 1.35rem);
        font-weight: 700;
        color: #94a3b8;
        margin-left: 4px;
    }
    .hero-date-val {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: clamp(0.72rem, 2.5vw, 0.82rem);
        color: #cbd5e1;
        font-weight: 600;
        margin-top: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Pulsante Guida (Icona Bilancia della Legge) - Animazione continua e uniforme */
    @keyframes law-pulse {
        0%, 100% {
            border-color: rgba(245, 158, 11, 0.35);
            box-shadow: 0 0 0 rgba(245, 158, 11, 0), 0 2px 6px rgba(0, 0, 0, 0.4);
            color: #f59e0b;
            background: rgba(245, 158, 11, 0.08);
        }
        50% {
            border-color: rgba(245, 158, 11, 0.75);
            box-shadow: 0 0 10px rgba(245, 158, 11, 0.30), 0 2px 6px rgba(0, 0, 0, 0.4);
            color: #fef08a;
            background: rgba(245, 158, 11, 0.18);
        }
    }

    .hero-law-btn {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        border-radius: 10px;
        border: 1.5px solid rgba(245, 158, 11, 0.35);
        text-decoration: none !important;
        animation: law-pulse 4.5s infinite ease-in-out;
        cursor: pointer;
        padding: 3px;
        user-select: none;
        flex-shrink: 0;
    }
    .hero-law-btn:hover {
        transform: scale(1.08);
        border-color: #fbbf24 !important;
        box-shadow: 0 0 18px rgba(245, 158, 11, 0.7) !important;
        background: rgba(245, 158, 11, 0.3) !important;
        color: #ffffff !important;
    }
    .hero-law-btn:active {
        transform: scale(0.96);
    }
    .law-btn-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.50rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        margin-top: 1px;
        line-height: 1;
        text-transform: uppercase;
    }

    /* Specifiche tecniche */
    .hero-specs-bar {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 6px;
        padding: 4px 8px;
        margin-top: 7px;
        font-family: 'JetBrains Mono', monospace;
        font-size: clamp(0.64rem, 2.2vw, 0.72rem);
    }
    .hero-spec-tag {
        font-weight: 700;
        color: #f1f5f9;
    }
    .hero-spec-dot {
        color: #64748b;
        font-size: 0.7rem;
    }
    .hero-spec-detail {
        color: #94a3b8;
    }
    .hero-spec-premio {
        color: #f59e0b;
        font-weight: 800;
        background: rgba(245, 158, 11, 0.12);
        border: 1px solid rgba(245, 158, 11, 0.35);
        padding: 1px 6px;
        border-radius: 4px;
    }

    /* Differenziale rispetto a quotazione precedente */
    .hero-delta-row {
        margin-top: 8px;
        padding-top: 7px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 6px;
    }
    .hero-delta-label {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: clamp(0.68rem, 2.3vw, 0.77rem);
        font-weight: 600;
        color: #94a3b8;
    }
    .hero-badge-delta {
        font-family: 'JetBrains Mono', monospace;
        font-size: clamp(0.72rem, 2.4vw, 0.81rem);
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 6px;
        white-space: nowrap;
    }
    .delta-up { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .delta-down { background: rgba(244, 63, 94, 0.2); color: #f43f5e; }
    .delta-zero { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }

    /* Barra navigazione / switch rapido */
    .nav-actions-row {
        display: flex;
        gap: 8px;
        margin-bottom: 8px;
    }
    .st-key-btn_back_home > button {
        background: #111c33 !important;
        border: 1px solid #334155 !important;
        color: #cbd5e1 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 6px 12px !important;
        font-size: 0.84rem !important;
    }
    .st-key-btn_back_home > button:hover {
        border-color: #64748b !important;
        color: #ffffff !important;
        background: #1e293b !important;
    }

    .st-key-btn_switch_twin > button {
        background: linear-gradient(135deg, #090e1a 0%, #1e293b 100%) !important;
        border: 1px solid #475569 !important;
        color: #f8fafc !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        padding: 6px 12px !important;
        font-size: 0.84rem !important;
    }
    .st-key-btn_switch_twin > button:hover {
        border-color: #38bdf8 !important;
        color: #38bdf8 !important;
    }

    /* Grafico Touch-Friendly su Smartphone */
    [data-testid="stPlotlyChart"],
    .js-plotly-plot,
    .plot-container {
        touch-action: pan-y !important;
        user-select: none !important;
        -webkit-user-select: none !important;
    }

</style>
""", unsafe_allow_html=True)


# =========================================================================
# GESTIONE SESSION STATE
# =========================================================================
if "selected_product" not in st.session_state:
    st.session_state.selected_product = None  # Valori: 'DURO_PDT', 'TENERO_PDT', 'TENERO_PMG'

if "app_boot_sync_done" not in st.session_state:
    st.session_state.app_boot_sync_done = False

if "last_sync_time" not in st.session_state:
    st.session_state.last_sync_time = 0

if "force_sync" not in st.session_state:
    st.session_state.force_sync = False

if "sync_feedback" not in st.session_state:
    st.session_state.sync_feedback = ""



# =========================================================================
# ASSET CACHED (LOGO E GUIDE PDF)
# =========================================================================
# =========================================================================
# ASSET CACHED (LOGO E GUIDE PDF) & SUPPORTO INSTALLAZIONE PWA
# =========================================================================
@st.cache_data
def get_optimized_logo():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "static", "icon-192.png"),
        os.path.join(base_dir, "icon-192.png"),
        os.path.join(base_dir, "logo_optimized.webp"),
    ]
    for c in candidates:
        if os.path.exists(c):
            with open(c, "rb") as f:
                mime = "image/png" if c.endswith(".png") else "image/webp"
                return mime, base64.b64encode(f.read()).decode()
    return None, None

@st.cache_data
def get_pwa_assets_b64():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_180_path = os.path.join(base_dir, "static", "icon-180.png")
    icon_192_path = os.path.join(base_dir, "static", "icon-192.png")
    manifest_path = os.path.join(base_dir, "static", "manifest.json")
    
    b64_180 = ""
    b64_192 = ""
    b64_manifest = ""
    
    if os.path.exists(icon_180_path):
        with open(icon_180_path, "rb") as f:
            b64_180 = base64.b64encode(f.read()).decode("utf-8")
    if os.path.exists(icon_192_path):
        with open(icon_192_path, "rb") as f:
            b64_192 = base64.b64encode(f.read()).decode("utf-8")
    if os.path.exists(manifest_path):
        with open(manifest_path, "rb") as f:
            b64_manifest = base64.b64encode(f.read()).decode("utf-8")
            
    return b64_180, b64_192, b64_manifest

def inject_pwa_head():
    """Inietta i meta-tag e il manifest PWA nell'head del browser principale per installazione Android, iOS e Windows in modo invisibile."""
    import streamlit.components.v1 as components
    js_code = """
    <script>
    (function() {
        try {
            const targetDoc = window.parent ? window.parent.document : document;
            const head = targetDoc.head || document.head;
            
            function createOrUpdate(tag, attrs) {
                let sel = tag;
                if (attrs.rel) sel += '[rel="' + attrs.rel + '"]';
                if (attrs.name) sel += '[name="' + attrs.name + '"]';
                let el = head.querySelector(sel);
                if (!el) {
                    el = targetDoc.createElement(tag);
                    head.appendChild(el);
                }
                el.className = 'pwa-custom-icon';
                for (let k in attrs) {
                    el.setAttribute(k, attrs[k]);
                }
            }

            // 1. Manifest PWA per Windows, Android, Chrome, Edge
            createOrUpdate('link', { rel: 'manifest', href: '/app/static/manifest.json' });
            createOrUpdate('meta', { name: 'mobile-web-app-capable', content: 'yes' });
            createOrUpdate('meta', { name: 'theme-color', content: '#030712' });

            // 2. Icona Apple iOS (180x180)
            createOrUpdate('link', { rel: 'apple-touch-icon', sizes: '180x180', href: '/app/static/icon-180.png' });
            createOrUpdate('link', { rel: 'apple-touch-icon-precomposed', sizes: '180x180', href: '/app/static/icon-180.png' });
            createOrUpdate('meta', { name: 'apple-mobile-web-app-capable', content: 'yes' });
            createOrUpdate('meta', { name: 'apple-mobile-web-app-title', content: 'Futures Grano' });
            createOrUpdate('meta', { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' });

            // 3. Icone Standard ad alta definizione
            createOrUpdate('link', { rel: 'icon', type: 'image/png', sizes: '192x192', href: '/app/static/icon-192.png' });
            createOrUpdate('link', { rel: 'shortcut icon', href: '/app/static/icon-192.png' });

            targetDoc.title = 'Futures Grano - Quotazioni Giornaliere';
        } catch(err) {
            console.warn('[PWA] Iniezione DOM PWA:', err);
        }
    })();
    </script>
    """
    components.html(js_code, height=0, width=0)

# Esegui iniezione PWA per smartphone e PC
inject_pwa_head()

@st.cache_data
def get_pdf_guida(product_key: str):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if "DURO" in product_key:
        filename = "Guida agli Impegni e Conferimento Grano Duro.pdf"
    else:
        filename = "Guida agli Impegni e Conferimento Grano Tenero.pdf"

    candidates = [
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "static", filename),
        os.path.join(base_dir, "APP ON LINE PER VISUALIZZARE PREZZO GRANO DURO", filename),
        os.path.join(base_dir, "APP ON LINE PER VISUALIZZARE PREZZO GRANO TENERO", filename),
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, "rb") as f:
                    data = f.read()
                    return data, base64.b64encode(data).decode("utf-8"), filename
            except Exception:
                pass
    return None, "", filename

logo_mime, logo_b64 = get_optimized_logo()
logo_html = f'<img src="data:{logo_mime};base64,{logo_b64}" style="width:46px; height:46px; border-radius:8px; border:1px solid #334155; object-fit:cover; box-shadow:0 2px 8px rgba(0,0,0,0.5);">' if logo_b64 else ''

# Dizionario traduzione date in italiano
mesi_it = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
}
giorni_it = {
    0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì",
    4: "Venerdì", 5: "Sabato", 6: "Domenica"
}

# =========================================================================
# CACHE DATI E QUERY ULTRA VELOCE
# =========================================================================
@st.cache_data(ttl=60)
def get_cached_quotes_for_selection(prodotto: str, tipo: str, scadenza: str = "lug-27"):
    return get_quotes_for_selection(prodotto=prodotto, tipo=tipo, scadenza=scadenza)

@st.cache_data(ttl=60)
def get_cached_delta(prodotto: str, tipo: str, scadenza: str = "lug-27"):
    return get_delta_for_selection(prodotto=prodotto, tipo=tipo, scadenza=scadenza)

# =========================================================================
# PROCESSO DI AGGIORNAMENTO GIORNALIERO E SINCRONIZZAZIONE
# =========================================================================
def perform_app_sync(force: bool = False, show_msg: bool = True):
    """
    Esegue il processo di aggiornamento giornaliero delle quotazioni cereali:
    1. Sincronizzazione cloud da repository GitHub (riceve le ultime quotazioni salvate da qualsiasi sorgente).
    2. Scansione email IMAP SSL da casella Gmail con estrazione PDF/immagini/corpo email.
    3. Deduplicazione, archiviazione locale e push verso GitHub.
    4. Pulizia automatica della cache Streamlit per aggiornare grafici e metriche.
    """
    placeholder = st.empty()
    if show_msg:
        placeholder.markdown("""
        <div class="attendi-container">
            <div class="attendi-text">⏳ Verifica e aggiornamento quotidiano quotazioni in corso...</div>
        </div>
        """, unsafe_allow_html=True)

    try:
        new_q, is_t, logs = check_and_sync_today_quotes(scan_depth=30)
        st.cache_data.clear()
        st.session_state.last_sync_time = time.time()
        st.session_state.app_boot_sync_done = True

        all_q = load_quotes()
        oggi_str = datetime.now().strftime("%Y-%m-%d")
        ha_oggi = any(q.get("data") == oggi_str for q in all_q)

        if new_q:
            st.session_state.sync_feedback = f"✅ Trovate {len(new_q)} nuove quotazioni archiviate nel database!"
            placeholder.empty()
            st.rerun()
        elif ha_oggi or is_t:
            st.session_state.sync_feedback = "🟢 Database aggiornato alla seduta odierna."
        else:
            last_d = all_q[-1].get("data") if all_q else "N.D."
            st.session_state.sync_feedback = f"Verifica completata: ultima quotazione ufficiale {last_d}."
    except Exception as e:
        print(f"Errore processo aggiornamento: {e}")
        st.session_state.sync_feedback = "Verifica completata."
    finally:
        placeholder.empty()

def check_today_quotes_flow():
    """
    Workflow di sincronizzazione automatica all'apertura dell'app:
    Esegue la sincronizzazione immediata ad ogni apertura o ricaricamento dell'app:
    - Se l'app viene avviata (app_boot_sync_done is False)
    - Oppure se nel database manca la quotazione della data odierna (evitando solo loop continui nello stesso secondo)
    """
    now_ts = time.time()
    all_quotes = load_quotes()
    oggi_str = datetime.now().strftime("%Y-%m-%d")
    ha_oggi = any(q.get("data") == oggi_str for q in all_quotes)

    needs_check = (
        (not st.session_state.get("app_boot_sync_done", False)) or
        (not ha_oggi and (now_ts - st.session_state.get("last_sync_time", 0) > 8))
    )

    if needs_check:
        perform_app_sync(force=True, show_msg=True)


# Esecuzione centralizzata della sincronizzazione e aggiornamento automatico all'avvio della app
check_today_quotes_flow()

# =========================================================================
# 1. SCHERMATA PRINCIPALE (SELEZIONE PRODOTTO)
# =========================================================================
if st.session_state.selected_product is None:
    all_raw_quotes = load_quotes()
    oggi_str = datetime.now().strftime("%Y-%m-%d")
    ha_quotazione_oggi = any(q.get("data") == oggi_str for q in all_raw_quotes)
    last_db_date = all_raw_quotes[-1].get("data") if all_raw_quotes else ""

    if last_db_date:
        try:
            ld_dt = datetime.strptime(last_db_date, "%Y-%m-%d")
            ld_str = f"{giorni_it[ld_dt.weekday()]} {ld_dt.day} {mesi_it[ld_dt.month]} {ld_dt.year}"
        except Exception:
            ld_str = last_db_date
    else:
        ld_str = "N.D."

    last_check_str = ""
    if st.session_state.get("last_sync_time", 0) > 0:
        last_check_str = datetime.fromtimestamp(st.session_state.last_sync_time).strftime("%H:%M")

    check_badge = f'<div style="font-size: 0.74rem; color: #94a3b8; margin-top: 4px; font-weight: 500;">Ultima verifica automatica: ore {last_check_str}</div>' if last_check_str else ''

    if ha_quotazione_oggi:
        status_banner = f'<div style="text-align:center; margin-top: 4px; margin-bottom: 8px;"><span class="app-sync-status status-today">🟢 Database aggiornato a Oggi</span>{check_badge}</div>'
    else:
        status_banner = f'<div style="text-align:center; margin-top: 4px; margin-bottom: 8px;"><span class="app-sync-status status-wait">⏳ Aggiornato al {ld_str} (in attesa di quotazione odierna)</span>{check_badge}</div>'

    # Spaziatura ampia ed elegante tra i riquadri della schermata principale
    st.markdown("""<style>
        .block-container {
            padding-top: 0px !important;
            margin-top: -10px !important;
        }
        div[data-testid="stVerticalBlock"] {
            gap: 0.95rem !important;
        }
    </style>""", unsafe_allow_html=True)

    # Banner di protezione in testa
    main_banner_html = f"""<div class="futures-protection-container">
<div class="futures-protection-badge">
<span style="font-size: 1.15rem; line-height: 1;">🛡️</span>
<span class="futures-protection-text">Contratti di Protezione Futures per i Cereali</span>
</div>
</div>
{status_banner}
<div class="main-question-card">
<h1 class="main-question-title">Che quotazione ti interessa?</h1>
<div class="main-question-sub">Seleziona una delle opzioni per visualizzare la quotazione e il grafico</div>
</div>"""
    st.markdown(main_banner_html, unsafe_allow_html=True)

    # 1. Grano Duro PDT
    if st.button("🌾 Grano Duro prezzo determinato - Raccolto Luglio 2027", use_container_width=True, key="btn_duro_pdt"):
        st.session_state.selected_product = "DURO_PDT"
        st.rerun()

    # 2. Grano Tenero PDT
    if st.button("🌱 Grano Tenero prezzo determinato - Raccolto Luglio 2027", use_container_width=True, key="btn_tenero_pdt"):
        st.session_state.selected_product = "TENERO_PDT"
        st.rerun()

    # 3. Grano Tenero PMG
    if st.button("🌱 Grano Tenero prezzo minimo garantito - Raccolto Luglio 2027", use_container_width=True, key="btn_tenero_pmg"):
        st.session_state.selected_product = "TENERO_PMG"
        st.rerun()

    # Iniezione sicura per garantire colori del carattere, lampeggiamento tenue e reset scroll al tocco
    components.html("""
    <script>
    (function() {
        function triggerScrollTop() {
            try {
                window.scrollTo(0, 0);
                if (document.documentElement) document.documentElement.scrollTop = 0;
                if (document.body) document.body.scrollTop = 0;
                if (window.parent && window.parent !== window) {
                    try { window.parent.scrollTo(0, 0); } catch(e) {}
                    try { window.parent.postMessage({ action: 'SCROLL_TOP' }, '*'); } catch(e) {}
                }
            } catch(e) {}
        }

        function styleButtons() {
            try {
                const targetDoc = window.parent ? window.parent.document : document;
                const buttons = targetDoc.querySelectorAll('button');
                buttons.forEach(btn => {
                    const txt = (btn.textContent || btn.innerText || '').trim();
                    if (!btn.dataset.scrollBound) {
                        btn.addEventListener('click', triggerScrollTop, { passive: true });
                        btn.dataset.scrollBound = 'true';
                    }
                    if (txt.includes('Grano Duro')) {
                        btn.style.setProperty('background', 'linear-gradient(135deg, #1c1404 0%, #2e2008 100%)', 'important');
                        btn.style.setProperty('border', '1.5px solid rgba(223, 158, 56, 0.70)', 'important');
                        btn.querySelectorAll('p, span, div').forEach(el => {
                            el.style.setProperty('color', '#df9e38', 'important');
                            el.style.setProperty('animation', 'gentle-text-blink-ocra 4.0s infinite ease-in-out', 'important');
                        });
                    } else if (txt.includes('Grano Tenero') && txt.includes('determinato')) {
                        btn.style.setProperty('background', 'linear-gradient(135deg, #240b13 0%, #35101c 100%)', 'important');
                        btn.style.setProperty('border', '1.5px solid rgba(224, 43, 85, 0.70)', 'important');
                        btn.querySelectorAll('p, span, div').forEach(el => {
                            el.style.setProperty('color', '#e02b55', 'important');
                            el.style.setProperty('animation', 'gentle-text-blink-lampone 4.0s infinite ease-in-out', 'important');
                        });
                    } else if (txt.includes('Grano Tenero') && (txt.includes('minimo') || txt.includes('garantito'))) {
                        btn.style.setProperty('background', 'linear-gradient(135deg, #091a36 0%, #0f274f 100%)', 'important');
                        btn.style.setProperty('border', '1.5px solid rgba(56, 139, 253, 0.70)', 'important');
                        btn.querySelectorAll('p, span, div').forEach(el => {
                            el.style.setProperty('color', '#388bfd', 'important');
                            el.style.setProperty('animation', 'gentle-text-blink-cobalto 4.0s infinite ease-in-out', 'important');
                        });
                    }
                });
            } catch(e) {
                console.warn('Errore applicazione stili bottoni:', e);
            }
        }
        styleButtons();
        setTimeout(styleButtons, 50);
        setTimeout(styleButtons, 200);
        setTimeout(styleButtons, 600);
    })();
    </script>
    """, height=0, width=0)

    st.stop()


# =========================================================================
# 2. SCHERMATA DEDICATA AL PRODOTTO SELEZIONATO
# =========================================================================
# Reset immediato e forzato dello scroll verso l'alto (in cima) all'apertura del dettaglio
components.html("""
<script>
(function() {
    function resetToTop() {
        try {
            window.scrollTo(0, 0);
            if (document.documentElement) document.documentElement.scrollTop = 0;
            if (document.body) document.body.scrollTop = 0;

            const pDoc = window.parent ? window.parent.document : document;
            if (pDoc) {
                pDoc.querySelectorAll('.main, section.main, [data-testid="stMain"], [data-testid="stAppViewContainer"], .block-container').forEach(el => {
                    el.scrollTop = 0;
                });
            }

            if (window.parent && window.parent !== window) {
                try {
                    window.parent.scrollTo(0, 0);
                    if (window.parent.document.documentElement) window.parent.document.documentElement.scrollTop = 0;
                    if (window.parent.document.body) window.parent.document.body.scrollTop = 0;
                } catch(e) {}
                try {
                    window.parent.postMessage({ action: 'SCROLL_TOP' }, '*');
                } catch(e) {}
            }
        } catch(e) {}
    }
    resetToTop();
    requestAnimationFrame(resetToTop);
    setTimeout(resetToTop, 15);
    setTimeout(resetToTop, 60);
    setTimeout(resetToTop, 150);
    setTimeout(resetToTop, 350);
    setTimeout(resetToTop, 700);
    setTimeout(resetToTop, 1200);
    setTimeout(resetToTop, 1800);
})();
</script>
""", height=0, width=0)

# Stile bilanciato per le 3 opzioni: tasto navigazione visibile al 100% senza essere tagliato
st.markdown("""<style>
    .block-container,
    div[data-testid="stMainBlockContainer"],
    div[data-testid="stAppViewBlockContainer"],
    section[data-testid="stMain"] > div:first-child {
        padding-top: 0px !important;
        margin-top: -34px !important;
    }
    section[data-testid="stMain"] {
        padding-top: 0px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding-top: 0px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        margin-top: 6px !important;
        margin-bottom: 2px !important;
    }
    div[data-testid="element-container"]:has(iframe[height="0"]),
    div[data-testid="element-container"]:has(style),
    div[data-testid="stVerticalBlock"] > div:has(iframe[height="0"]),
    div[data-testid="stVerticalBlock"] > div:has(style:only-child) {
        display: none !important;
        position: absolute !important;
        top: -9999px !important;
        height: 0 !important;
        width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    .st-key-btn_back_home > button,
    .st-key-btn_switch_twin > button {
        margin-top: 0px !important;
        padding: 3px 10px !important;
        min-height: 34px !important;
    }
    .app-topbar {
        margin-top: 1px !important;
        margin-bottom: 5px !important;
        padding: 4px 10px !important;
    }
</style>""", unsafe_allow_html=True)

product_key = st.session_state.selected_product

# Mappatura parametri in base al prodotto
if product_key == "DURO_PDT":
    prod_name = "GRANO DURO"
    tipo_contratto = "PDT"
    title_short = "QUOTAZIONE FUTURES 🌾 GRANO DURO"
    hero_class = "hero-box-duro"
    price_val_class = "hero-price-val-duro"
    chart_line_color = "#fbbf24"
    chart_fill_color = "rgba(251, 191, 36, 0.08)"
elif product_key == "TENERO_PDT":
    prod_name = "GRANO TENERO FINO ROSSO"
    tipo_contratto = "PDT"
    title_short = "QUOTAZIONE FUTURES 🌱 GRANO TENERO"
    hero_class = "hero-box-tenero-pdt"
    price_val_class = "hero-price-val-tenero-pdt"
    chart_line_color = "#00ff88"
    chart_fill_color = "rgba(0, 255, 136, 0.08)"
else:  # TENERO_PMG
    prod_name = "GRANO TENERO FINO ROSSO"
    tipo_contratto = "PMG"
    title_short = "QUOTAZIONE FUTURES 🌱 GRANO TENERO"
    hero_class = "hero-box-tenero-pmg"
    price_val_class = "hero-price-val-tenero-pmg"
    chart_line_color = "#38bdf8"
    chart_fill_color = "rgba(56, 189, 248, 0.08)"

# 1. Interrogazione preliminare database
quotes = get_cached_quotes_for_selection(prodotto=prod_name, tipo=tipo_contratto, scadenza="lug-27")
oggi_str = datetime.now().strftime("%Y-%m-%d")
ha_quotazione_oggi = any(q.get("data") == oggi_str for q in (quotes or []))

if not quotes:
    st.warning(f"Nessuna quotazione registrata per {prod_name} {tipo_contratto} (lug-27).")
    if st.button("⬅️ Torna alla selezione"):
        st.session_state.selected_product = None
        st.rerun()
    st.stop()

stats = get_cached_delta(prodotto=prod_name, tipo=tipo_contratto, scadenza="lug-27")

# Preparazione DataFrame per il grafico
df = pd.DataFrame(quotes)
df["data"] = pd.to_datetime(df["data"])
df = df.sort_values("data")

# Mostra le quotazioni coerentemente a partire dal 1° Giugno 2026
# per garantire lo stesso formato e orizzonte temporale uniforme a tutti e tre i prodotti
df_june = df[df["data"] >= "2026-06-01"]
if len(df_june) >= 15:
    df = df_june
elif len(df) > 80:
    df = df.tail(80)

last_row = df.iloc[-1]
prev_row = df.iloc[-2] if len(df) > 1 else last_row

last_p = stats["last_price"]
prev_p = stats["prev_price"]
delta_p = stats["delta"]
pct_p = stats["pct_change"]

delta_class = "delta-up" if delta_p > 0 else ("delta-down" if delta_p < 0 else "delta-zero")
delta_sign = "+" if delta_p > 0 else ""

oggi_str = datetime.now().strftime("%Y-%m-%d")
last_date_str = last_row["data"].strftime("%Y-%m-%d")
is_today = (last_date_str == oggi_str)

data_dt = last_row["data"]
data_estesa = f"{giorni_it[data_dt.weekday()]} {data_dt.day} {mesi_it[data_dt.month]} {data_dt.year}"

# Status badge e dicitura data
if is_today:
    status_badge = '<span class="app-sync-status status-today">🟢 Aggiornato a Oggi</span>'
else:
    status_badge = f'<span class="app-sync-status status-wait">⏳ Aggiornato al {data_dt.strftime("%d/%m/%Y")} (In attesa oggi)</span>'

date_display_html = f'<div class="hero-date-val">📅 <b>{data_estesa}</b></div>'

# Pill del contratto
contract_pill = (
    '<span class="app-contract-pill pill-pdt">PDT</span>'
    if tipo_contratto == "PDT" else
    '<span class="app-contract-pill pill-pmg">PMG</span>'
)

# Guida PDF
pdf_bytes, pdf_b64, pdf_filename = get_pdf_guida(product_key)
pdf_link_attr = f'href="data:application/pdf;base64,{pdf_b64}" download="{pdf_filename}" target="_blank" rel="noopener noreferrer"' if pdf_b64 else 'href="#"'

# ----------------- BARRA DI NAVIGAZIONE E AZIONI IN TESTA -----------------
nav_col1, nav_col2 = st.columns([1, 1])
with nav_col1:
    if st.button("⬅️ Torna alla selezione", key="btn_back_home", use_container_width=True):
        st.session_state.selected_product = None
        st.rerun()

with nav_col2:
    # Se Grano Tenero, consenti il rapido switch PDT <-> PMG
    if "TENERO" in product_key:
        twin_key = "TENERO_PMG" if product_key == "TENERO_PDT" else "TENERO_PDT"
        twin_label = "Switch a PMG" if product_key == "TENERO_PDT" else "Switch a PDT"
        if st.button(f"🔄 {twin_label}", key="btn_switch_twin", use_container_width=True):
            st.session_state.selected_product = twin_key
            st.rerun()

# ----------------- 1. TOP BAR COMPATTA -----------------
topbar_html = f"""<div class="app-topbar">
<div>
<div class="app-title-text">
<span>{title_short}</span>
<span class="app-expiry-pill">LUG-27</span>
{contract_pill}
</div>
<div style="margin-top: 4px;">
{status_badge}
</div>
</div>
<div style="flex: 0 0 auto;">
{logo_html}
</div>
</div>"""
st.markdown(topbar_html, unsafe_allow_html=True)

# ----------------- 2. HERO CARD PREZZO ATTUALE -----------------
# Specifiche in base al prodotto
if "DURO" in product_key:
    specs_html = """<div class="hero-specs-bar">
<span class="hero-spec-tag">Prezzo base PDT</span>
<span class="hero-spec-dot">•</span>
<span class="hero-spec-detail">P.S. &ge; 78</span>
<span class="hero-spec-dot">•</span>
<span class="hero-spec-detail">Prot. &ge; 13,5%</span>
</div>"""
else:
    specs_html = """<div class="hero-specs-bar">
<span class="hero-spec-tag">Prezzo base Fino Rosso</span>
<span class="hero-spec-dot">•</span>
<span class="hero-spec-premio">Bologna e Giorgione: +30 €/t</span>
</div>"""

hero_html = f"""<div class="hero-box {hero_class}">
<div class="hero-top-row">
<div class="hero-price-section">
<div class="hero-price-val {price_val_class}">{last_p:.2f} <span class="hero-price-unit">€/t</span></div>
{date_display_html}
</div>
<a {pdf_link_attr} class="hero-law-btn" title="Visualizza Guida agli Impegni e Conferimento (PDF)">
<div style="width:20px; height:20px; display:flex; align-items:center; justify-content:center;">
<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
<path d="M12 3v18"/>
<path d="M7 21h10"/>
<path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
<path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
</svg>
</div>
<span class="law-btn-text">GUIDA</span>
</a>
</div>
{specs_html}
<div class="hero-delta-row">
<span class="hero-delta-label">Differenziale dalla quotazione precedente:</span>
<span class="hero-badge-delta {delta_class}">{delta_sign}{delta_p:.2f} €/ton</span>
</div>
</div>"""
st.markdown(hero_html, unsafe_allow_html=True)

# ----------------- 3. GRAFICO PLOTLY WALL STREET CON SCALATURA DINAMICA -----------------
p_min = df["prezzo"].min()
p_max = df["prezzo"].max()
p_std = df["prezzo"].std()
if pd.isna(p_std) or p_std == 0:
    p_std = 3.0

# Scalatura asse Y con pad basato su deviazione standard
pad_y = 1.25 * p_std
y_min_dyn = max(0, math.floor((p_min - pad_y) / 5) * 5)
y_max_dyn = math.ceil((p_max + pad_y) / 5) * 5
if y_max_dyn - y_min_dyn < 20:
    y_min_dyn = max(0, y_min_dyn - 10)
    y_max_dyn += 10

fig = go.Figure()

# Area e linea quotazioni
fig.add_trace(go.Scatter(
    x=df["data"],
    y=df["prezzo"],
    mode="lines+markers",
    name="Quotazione €/t",
    line=dict(color=chart_line_color, width=2.5, shape="linear"),
    marker=dict(
        size=4.5,
        color=chart_line_color,
        symbol="circle",
        line=dict(color="#ffffff", width=0.8)
    ),
    fill="tozeroy",
    fillcolor=chart_fill_color,
    hoverinfo="skip"
))

# Evidenziazione ultimo punto
fig.add_trace(go.Scatter(
    x=[df["data"].iloc[-1]],
    y=[last_p],
    mode="markers",
    name="Ultimo Prezzo",
    marker=dict(
        size=9,
        color="#ffffff",
        line=dict(color=chart_line_color, width=3)
    ),
    hoverinfo="skip"
))

# Layout mobile compatto ed elegante (solo andamento e valori assi X e Y)
fig.update_layout(
    height=280,
    margin=dict(l=10, r=10, t=14, b=30),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(11, 17, 32, 0.75)",
    showlegend=False,
    xaxis=dict(
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.05)",
        tickfont=dict(color="#94a3b8", size=10, family="JetBrains Mono"),
        linecolor="#1e293b",
        tickmode="linear",
        tick0="2026-06-01",
        dtick="M1",
        tickformat="%b %y",
        showspikes=False
    ),
    yaxis=dict(
        range=[y_min_dyn, y_max_dyn],
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.06)",
        tickfont=dict(color="#94a3b8", size=10, family="JetBrains Mono"),
        ticksuffix=" €",
        linecolor="#1e293b",
        showspikes=False
    ),
    hovermode=False,
    dragmode=False
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "displayModeBar": False,
        "staticPlot": False,
        "scrollZoom": False,
        "doubleClick": False
    }
)

# Spazio aggiuntivo sul fondo (sfondo scuro) per consentire lo scroll completo oltre i badge/creator
st.markdown("""
<div class="app-bottom-spacer" style="height: 140px; width: 100%; pointer-events: none;"></div>
""", unsafe_allow_html=True)

