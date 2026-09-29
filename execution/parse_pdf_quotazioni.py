"""
Modulo Deterministico per l'estrazione delle quotazioni Grano Duro e Grano Tenero
da file PDF CAI (PDT/PMG) e da testo/HTML del corpo email.
Conforme all'architettura a 3 livelli (Livello 3 - Execution).
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import pypdf

# Mapping mesi in italiano per parsing date
MESI_IT = {
    'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
    'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12,
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
    'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
}

def parse_data_string(data_str: str) -> Optional[str]:
    """Converte date come '18-set-26' o '18 settembre 2026' in 'YYYY-MM-DD'."""
    if not data_str:
        return None
    data_str = data_str.strip().lower()
    
    # Formato '18-set-26' o '18-set-2026'
    m_short = re.search(r'(\d{1,2})[-/\s]([a-z]{3})[-/\s](\d{2,4})', data_str)
    if m_short:
        giorno, mese_txt, anno_raw = m_short.groups()
        mese = MESI_IT.get(mese_txt)
        if mese:
            anno = int(anno_raw)
            if anno < 100:
                anno += 2000
            return f"{anno:04d}-{mese:02d}-{int(giorno):02d}"
            
    # Formato '18 settembre 2026'
    m_long = re.search(r'(\d{1,2})\s+([a-z]+)\s+(\d{4})', data_str)
    if m_long:
        giorno, mese_txt, anno = m_long.groups()
        mese = MESI_IT.get(mese_txt)
        if mese:
            return f"{int(anno):04d}-{mese:02d}-{int(giorno):02d}"
            
    return None

def extract_quotes_from_text(text: str, source_name: str = "Email/PDF") -> List[Dict[str, Any]]:
    """
    Estrae le quotazioni sia di GRANO DURO sia di GRANO TENERO FINO ROSSO da un testo.
    Supporta testo plain o HTML (con tabelle).
    """
    if not text:
        return []

    # Pulizia HTML se presente (es. tabella incollata nel corpo email)
    if any(tag in text.lower() for tag in ["<html", "<table", "<tr", "<td", "<p", "<div", "<br"]):
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "html.parser")
            text = soup.get_text(separator=" ")
        except Exception:
            text = re.sub(r'<[^>]+>', ' ', text)

    results = []
    
    # 1. Riconoscimento della data delle quotazioni
    data_quotazione = None
    
    # Cerca 'Quotazioni valide il: 18-set-26' o 'Quotazioni indicative del: 18-set-26'
    m_valide = re.search(r'Quotazioni\s+(?:valide|indicative)\s+(?:il|del)\s*:\s*([0-9]{1,2}-[a-z]{3}-[0-9]{2,4})', text, re.IGNORECASE)
    if m_valide:
        data_quotazione = parse_data_string(m_valide.group(1))
        
    if not data_quotazione:
        # Cerca 'odierne: 18 settembre 2026' o 'del: 18 settembre 2026'
        m_odierne = re.search(r'(?:odierne|del)\s*:\s*([0-9]{1,2}\s+[a-z]+\s+[0-9]{4})', text, re.IGNORECASE)
        if m_odierne:
            data_quotazione = parse_data_string(m_odierne.group(1))

    # ==========================
    # 2. GRANO DURO (PDT)
    # ==========================
    pattern_duro = re.search(
        r'GRANO\s+DURO\b(.*?)(?:GRANO\s+TENERO|MAIS|SOIA|COLZA|Ricordiamo|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    blocco_duro = pattern_duro.group(1) if pattern_duro else text

    # Estrae quotazioni Grano Duro lug-27 (ed eventuale lug-28)
    righe_duro = re.findall(
        r'([a-z]{3}-\d{2})\s+([0-9]+(?:\.[0-9]+)?)\s*(?:Eur/ton|€/t|€/ton)?',
        blocco_duro,
        re.IGNORECASE
    )
    for scadenza, prezzo_str in righe_duro:
        scad = scadenza.lower()
        if scad == 'lug-26':
            continue  # Escludi le scadenze passate
        if scad in ['lug-27', 'lug-28']:
            try:
                prezzo_val = float(prezzo_str)
                # Verifica che non sia confuso con un anno o un valore anomalo
                if 120 <= prezzo_val <= 600:
                    results.append({
                        "data": data_quotazione,
                        "scadenza": scad,
                        "prezzo": prezzo_val,
                        "tipo": "PDT",
                        "prodotto": "GRANO DURO",
                        "fonte": source_name
                    })
            except Exception:
                pass

    # ==========================
    # 3. GRANO TENERO FINO ROSSO (PMG e PDT)
    # ==========================
    pattern_tenero = re.search(
        r'GRANO\s+TENERO\s+FINO\s+ROSSO\b(.*?)(?:GRANO\s+TENERO\s+BOLOGNA|GRANO\s+DURO|MAIS|SOIA|COLZA|Ricordiamo|$)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    blocco_tenero = pattern_tenero.group(1) if pattern_tenero else text

    # Formato A: riga lug-27 con due valori numerici: es. "lug-27 210 Eur/ton 232 Eur/ton"
    m_double = re.search(
        r'lug-27\s+([0-9]+(?:\.[0-9]+)?)\s*(?:Eur/ton|€/t|€/ton)?\s+([0-9]+(?:\.[0-9]+)?)\s*(?:Eur/ton|€/t|€/ton)?',
        blocco_tenero,
        re.IGNORECASE
    )
    if m_double:
        pmg_val = float(m_double.group(1))
        pdt_val = float(m_double.group(2))
        
        results.append({
            "data": data_quotazione,
            "scadenza": "lug-27",
            "prezzo": pmg_val,
            "tipo": "PMG",
            "prodotto": "GRANO TENERO FINO ROSSO",
            "premio_bologna_giorgione": 30.0,
            "fonte": source_name
        })
        results.append({
            "data": data_quotazione,
            "scadenza": "lug-27",
            "prezzo": pdt_val,
            "tipo": "PDT",
            "prodotto": "GRANO TENERO FINO ROSSO",
            "premio_bologna_giorgione": 30.0,
            "fonte": source_name
        })
    else:
        # Formato B: valori separati con esplicita etichetta PMG e PDT
        m_pmg = re.search(r'lug-27.*?PMG.*?([0-9]+(?:\.[0-9]+)?)', blocco_tenero, re.IGNORECASE | re.DOTALL)
        m_pdt = re.search(r'lug-27.*?PDT.*?([0-9]+(?:\.[0-9]+)?)', blocco_tenero, re.IGNORECASE | re.DOTALL)
        if m_pmg:
            results.append({
                "data": data_quotazione,
                "scadenza": "lug-27",
                "prezzo": float(m_pmg.group(1)),
                "tipo": "PMG",
                "prodotto": "GRANO TENERO FINO ROSSO",
                "premio_bologna_giorgione": 30.0,
                "fonte": source_name
            })
        if m_pdt:
            results.append({
                "data": data_quotazione,
                "scadenza": "lug-27",
                "prezzo": float(m_pdt.group(1)),
                "tipo": "PDT",
                "prodotto": "GRANO TENERO FINO ROSSO",
                "premio_bologna_giorgione": 30.0,
                "fonte": source_name
            })

    return results

def extract_quotes_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Estrae le quotazioni direttamente da un file PDF allegato."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"File PDF non trovato: {pdf_path}")
        
    full_text = ""
    with open(pdf_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

    filename = os.path.basename(pdf_path)
    return extract_quotes_from_text(full_text, source_name=f"PDF ({filename})")
