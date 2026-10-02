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
# Importazione utility condivise per date (DRY)
try:
    from execution.utils import MESI_IT, parse_data_string
except ImportError:
    from utils import MESI_IT, parse_data_string

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

    # 2. Fallback universale con pytesseract (Linux / Streamlit Community Cloud)
    try:
        import pytesseract
        from pytesseract import Output
        
        # Assicura modalità RGB (rimuovendo canale alpha che confonde Tesseract)
        img_raw = Image.open(image_path)
        if img_raw.mode == "RGBA":
            bg = Image.new("RGB", img_raw.size, (255, 255, 255))
            bg.paste(img_raw, mask=img_raw.split()[3])
            img_ocr = bg
        else:
            img_ocr = img_raw.convert("RGB")

        langs_to_try = ['ita', 'eng', 'ita+eng', None]
        for lang in langs_to_try:
            try:
                kwargs = {'output_type': Output.DICT}
                if lang:
                    kwargs['lang'] = lang
                data = pytesseract.image_to_data(img_ocr, **kwargs)
                lines_dict = {}
                n_boxes = len(data.get('text', []))
                for i in range(n_boxes):
                    w_text = str(data['text'][i]).strip()
                    if not w_text:
                        continue
                    line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
                    if line_key not in lines_dict:
                        lines_dict[line_key] = []
                    lines_dict[line_key].append({
                        "Text": w_text,
                        "X": data['left'][i],
                        "Y": data['top'][i],
                        "Width": data['width'][i],
                        "Height": data['height'][i]
                    })
                lines = []
                for line_key, words in lines_dict.items():
                    full_text = " ".join([w["Text"] for w in words])
                    lines.append({"Text": full_text, "Words": words})
                if lines:
                    return lines
            except Exception:
                pass

            try:
                kwargs = {}
                if lang:
                    kwargs['lang'] = lang
                text = pytesseract.image_to_string(img_ocr, **kwargs)
                lines = []
                for line in text.split('\n'):
                    line_s = line.strip()
                    if line_s:
                        lines.append({"Text": line_s, "Words": []})
                if lines:
                    return lines
            except Exception:
                pass
    except Exception as e:
        print(f"[OCR] Errore generale pytesseract: {e}")

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

        # Ingrandimento 2.5x con interpolazione Lanczos di Pillow (zero dipendenze cv2/numpy)
        new_size_gd = (int(crop_rgb.width * 2.5), int(crop_rgb.height * 2.5))
        crop_hires = crop_rgb.resize(new_size_gd, Image.Resampling.LANCZOS)

        temp_gd = os.path.join(os.path.dirname(image_path), f"_temp_ocr_gd_{os.getpid()}_{os.path.basename(image_path)}")
        crop_hires.save(temp_gd)
        lines_gd = _run_ocr_on_image(temp_gd)
        if os.path.exists(temp_gd):
            os.remove(temp_gd)

        p_duro_27 = None
        p_duro_28 = None
        duro_nums = []
        for line in lines_gd:
            txt = line.get("Text", "")
            # Cerca numeri a 3 cifre coerenti con il range 120-600 €/t
            nums = re.findall(r'\b([1-5]\d{2})\b', txt.replace(" ", ""))
            words = line.get("Words", [])
            y_coord = words[0].get("Y", 0) if words else 0
            for n in nums:
                val = float(n)
                if 120 <= val <= 600:
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

        # Ingrandimento 2.5x con interpolazione Lanczos di Pillow (zero dipendenze cv2/numpy)
        new_size_gt = (int(crop_rgb.width * 2.5), int(crop_rgb.height * 2.5))
        crop_hires = crop_rgb.resize(new_size_gt, Image.Resampling.LANCZOS)

        temp_gt = os.path.join(os.path.dirname(image_path), f"_temp_ocr_gt_{os.getpid()}_{os.path.basename(image_path)}")
        crop_hires.save(temp_gt)
        lines_gt = _run_ocr_on_image(temp_gt)
        if os.path.exists(temp_gt):
            os.remove(temp_gt)

        crop_w = crop_hires.width
        col_div = int(crop_w * 0.68)

        pmg_candidates = []
        pdt_candidates = []

        for l in lines_gt:
            txt = l.get("Text", "")
            words = l.get("Words", [])
            y_val = words[0].get("Y", 0) if words else 0
            x_val = words[0].get("X", 0) if words else 0

            # Cerca numeri a 3 cifre coerenti con il range 120-600 €/t
            nums = re.findall(r'\b([1-5]\d{2})\b', txt.replace(" ", ""))
            for n in nums:
                val = float(n)
                if 120 <= val <= 600:
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
