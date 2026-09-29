"""
Modulo Deterministico per l'estrazione delle quotazioni Grano Duro e Grano Tenero da immagini (PNG/JPG)
inserite nelle email dei Consorzi Agrari d'Italia (CAI).
Conforme all'architettura a 3 livelli (Livello 3 - Execution).
"""

import os
import re
import json
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from PIL import Image
import cv2
import numpy as np

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

def _run_ocr_on_image(image_path: str) -> List[Dict[str, Any]]:
    """
    Esegue l'OCR sull'immagine.
    Su Windows utilizza l'engine nativo Windows.Media.Ocr ad altissima precisione.
    Su Linux / altri sistemi operativi prova pytesseract se disponibile.
    """
    # 1. Su Windows, usa lo script PowerShell nativo ad alta fedeltà
    if os.name == 'nt':
        ps_script = os.path.join(os.path.dirname(__file__), "win_ocr.ps1")
        if os.path.exists(ps_script):
            try:
                cmd = [
                    "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", ps_script, "-ImagePath", os.path.abspath(image_path)
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout.strip(), strict=False)
                    if isinstance(data, dict):
                        data = [data]
                    return data
            except Exception as e:
                print(f"[OCR] Errore esecuzione win_ocr: {e}")

    # 2. Fallback con pytesseract se installato
    try:
        import pytesseract
        text = pytesseract.image_to_string(Image.open(image_path), lang='ita+eng')
        lines = []
        for line in text.split('\n'):
            line_s = line.strip()
            if line_s:
                lines.append({"Text": line_s, "Words": []})
        return lines
    except Exception:
        pass

    return []

def extract_quotes_from_image(
    image_path: str,
    fallback_date: Optional[str] = None,
    source_name: str = "Email"
) -> List[Dict[str, Any]]:
    """
    Estrae le quotazioni sia di GRANO DURO sia di GRANO TENERO (PMG e PDT) dall'immagine tabella.
    Ritorna una lista di dizionari conformi allo schema del database.
    """
    if not os.path.exists(image_path):
        return []

    try:
        im = Image.open(image_path)
    except Exception:
        return []

    # Ignora immagini troppo piccole (es. icone, loghi < 250x250)
    if im.width < 250 or im.height < 250:
        return []

    scale_y = im.height / 824.0
    scale_x = im.width / 580.0

    final_date = fallback_date or datetime.now().strftime("%Y-%m-%d")
    results = []

    # ==============================================================
    # 1. ESTRAZIONE GRANO DURO (Sezione inferiore: circa Y 620-720)
    # ==============================================================
    try:
        y1_gd = int(620 * scale_y)
        y2_gd = int(720 * scale_y)
        x1_gd = int(130 * scale_x)
        x2_gd = int(578 * scale_x)

        crop_gd = im.crop((x1_gd, y1_gd, x2_gd, y2_gd))
        if crop_gd.mode == "RGBA":
            bg = Image.new("RGB", crop_gd.size, (255, 255, 255))
            bg.paste(crop_gd, mask=crop_gd.split()[3])
            crop_rgb = bg
        else:
            crop_rgb = crop_gd.convert("RGB")

        crop_np = np.array(crop_rgb)
        crop_cv = cv2.cvtColor(crop_np, cv2.COLOR_RGB2BGR)
        crop_hires = cv2.resize(crop_cv, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)

        temp_gd = os.path.join(os.path.dirname(image_path), f"_temp_ocr_gd_{os.getpid()}_{os.path.basename(image_path)}")
        cv2.imwrite(temp_gd, crop_hires)
        lines_gd = _run_ocr_on_image(temp_gd)
        if os.path.exists(temp_gd):
            os.remove(temp_gd)

        p_duro_27 = None
        p_duro_28 = None
        duro_nums = []
        for line in lines_gd:
            txt = line.get("Text", "")
            nums = re.findall(r'\b(2\d{2}|3\d{2})\b', txt.replace(" ", ""))
            words = line.get("Words", [])
            y_coord = words[0].get("Y", 0) if words else 0
            for n in nums:
                val = float(n)
                if 220 <= val <= 350:
                    duro_nums.append((val, y_coord))

        if duro_nums:
            duro_nums.sort(key=lambda item: item[1])
            p_duro_27 = duro_nums[0][0]
            if len(duro_nums) > 1 and duro_nums[1][0] != p_duro_27:
                p_duro_28 = duro_nums[1][0]

        if p_duro_27:
            results.append({
                "data": final_date,
                "scadenza": "lug-27",
                "prezzo": p_duro_27,
                "tipo": "PDT",
                "prodotto": "GRANO DURO",
                "fonte": source_name
            })
        if p_duro_28:
            results.append({
                "data": final_date,
                "scadenza": "lug-28",
                "prezzo": p_duro_28,
                "tipo": "PDT",
                "prodotto": "GRANO DURO",
                "fonte": source_name
            })
    except Exception as e:
        print(f"[OCR] Errore estrazione Grano Duro: {e}")

    # ==============================================================
    # 2. ESTRAZIONE GRANO TENERO (Sezione centrale: circa Y 370-490)
    # ==============================================================
    try:
        y1_gt = int(370 * scale_y)
        y2_gt = int(490 * scale_y)
        x1_gt = int(130 * scale_x)
        x2_gt = int(578 * scale_x)

        crop_gt = im.crop((x1_gt, y1_gt, x2_gt, y2_gt))
        if crop_gt.mode == "RGBA":
            bg = Image.new("RGB", crop_gt.size, (255, 255, 255))
            bg.paste(crop_gt, mask=crop_gt.split()[3])
            crop_rgb = bg
        else:
            crop_rgb = crop_gt.convert("RGB")

        crop_np = np.array(crop_rgb)
        crop_cv = cv2.cvtColor(crop_np, cv2.COLOR_RGB2BGR)
        crop_hires = cv2.resize(crop_cv, (0, 0), fx=2.5, fy=2.5, interpolation=cv2.INTER_LANCZOS4)

        temp_gt = os.path.join(os.path.dirname(image_path), f"_temp_ocr_gt_{os.getpid()}_{os.path.basename(image_path)}")
        cv2.imwrite(temp_gt, crop_hires)
        lines_gt = _run_ocr_on_image(temp_gt)
        if os.path.exists(temp_gt):
            os.remove(temp_gt)

        crop_w = crop_hires.shape[1]
        col_div = int(crop_w * 0.68)

        pmg_candidates = []
        pdt_candidates = []

        for l in lines_gt:
            txt = l.get("Text", "")
            words = l.get("Words", [])
            y_val = words[0].get("Y", 0) if words else 0
            x_val = words[0].get("X", 0) if words else 0

            nums = re.findall(r'\b(1\d{2}|2\d{2}|3\d{2})\b', txt.replace(" ", ""))
            for n in nums:
                val = float(n)
                if 160 <= val <= 350:
                    if x_val < col_div:
                        pmg_candidates.append((val, y_val, x_val))
                    else:
                        pdt_candidates.append((val, y_val, x_val))

        pmg_candidates.sort(key=lambda item: item[1])
        pdt_candidates.sort(key=lambda item: item[1])

        pmg_val = pmg_candidates[0][0] if pmg_candidates else None
        pdt_val = pdt_candidates[0][0] if pdt_candidates else None

        if pmg_val:
            results.append({
                "data": final_date,
                "scadenza": "lug-27",
                "prezzo": pmg_val,
                "tipo": "PMG",
                "prodotto": "GRANO TENERO FINO ROSSO",
                "premio_bologna_giorgione": 30.0,
                "fonte": source_name
            })
        if pdt_val:
            results.append({
                "data": final_date,
                "scadenza": "lug-27",
                "prezzo": pdt_val,
                "tipo": "PDT",
                "prodotto": "GRANO TENERO FINO ROSSO",
                "premio_bologna_giorgione": 30.0,
                "fonte": source_name
            })
    except Exception as e:
        print(f"[OCR] Errore estrazione Grano Tenero: {e}")

    # ==============================================================
    # 3. FALLBACK FULL OCR (Se non è stato estratto nulla dai ritagli)
    # ==============================================================
    if not results:
        try:
            full_ocr = _run_ocr_on_image(image_path)
            full_text = " ".join([l.get("Text", "") for l in full_ocr])
            from execution.parse_pdf_quotazioni import extract_quotes_from_text
            extracted = extract_quotes_from_text(full_text, source_name=source_name)
            for q in extracted:
                if not q.get("data"):
                    q["data"] = final_date
            if extracted:
                results.extend(extracted)
        except Exception:
            pass

    return results
