"""
Modulo di utilità condivise per la pipeline di elaborazione quotazioni cereali.
Include la normalizzazione delle date in lingua italiana e helper comuni.
"""

import re
from typing import Optional

# Mapping mesi in italiano per parsing date (abbreviati ed estesi)
MESI_IT = {
    'gen': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mag': 5, 'giu': 6,
    'lug': 7, 'ago': 8, 'set': 9, 'ott': 10, 'nov': 11, 'dic': 12,
    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4, 'maggio': 5, 'giugno': 6,
    'luglio': 7, 'agosto': 8, 'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
}

def parse_data_string(data_str: str) -> Optional[str]:
    """
    Converte date come '18-set-26' o '18 settembre 2026' in formato standard 'YYYY-MM-DD'.
    Supporta separatori vari (- / spazio) e formati ad anno a 2 o 4 cifre.
    """
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
