import pdfplumber
import pandas as pd
import re
import os
import glob
import shutil
import time

# ==========================================
# 1. 系統參數與路徑設定
# ==========================================
INPUT_DIR = "./inpdf"        # 待處理檔案目錄
PROCESSED_DIR = "./overpdf"  # 處理完成檔案移入目錄
OUTPUT_CSV = "Batch_Import_Declarations.csv" # 最終彙整的 CSV 檔名

# --- 以下核心參數維持 V12.0 邏輯不變 ---
COORD_ITEM_MAX_X = 50
COORD_DESC_MIN_X = 10
COORD_DESC_MAX_X = 202
COORD_SPLIT_CCC = 202
COORD_NOISE_START = 315

GLOBAL_IGNORE_KEYWORDS = [
    "報單號碼", "主提單號碼", "生產國別", "輸出入許可文件號碼", 
    "輸出入貨品分類號列", "納稅辦法", "貨物名稱", "品牌", "規格",
    "數量", "單位", "淨重", "單價", "幣別", "FCL/FCL", "包裝說明",
    "TOTAL", "PAGE", "TERM OF", "進口報單", "項 次", "標記", 
    "貨櫃號碼", "其他申報事項", "長期委任", "未投保", "WHSU", "0CTN"
]

# ==========================================
# 2. 核心邏輯函式 (維持 V12.0 不變)
# ==========================================

def is_header_noise(text):
    if not text: return False
    clean_t = text.replace(" ", "")
    for kw in GLOBAL_IGNORE_KEYWORDS:
        if kw.replace(" ", "") in clean_t:
            return True
    return False

def extract_ccc_permit(raw_ccc_list):
    raw_text = "".join(raw_ccc_list)
    normalized = re.sub(r'[^A-Z0-9]', '', raw_text)
    
    permit_val = ""
    ccc_val = ""
    
    match_p = re.search(r'(CI\d{12}|IFB[A-Z0-9]{11})', normalized)
    if match_p:
        permit_val = match_p.group(1)
        normalized = normalized.replace(permit_val, '', 1)
        
    match_c = re.search(r'(\d{10,11})', normalized)
    if match_c:
        raw_ccc = match_c.group(1)
        if len(raw_ccc) == 11:
            ccc_val = f"{raw_ccc[:4]}.{raw_ccc[4:6]}.{raw_ccc[6:8]}.{raw_ccc[8:10]}-{raw_ccc[10]}"
        else:
            ccc_val = f"{raw_ccc[:4]}.{raw_ccc[4:6]}.{raw_ccc[6:8]}.{raw_ccc[8:10]}"
            
    return ccc_val, permit_val

def extract_country_and_clean_desc(desc_list):
    full_desc = " ".join(desc_list)
    country_val = ""
    
    country_match = re.search(r"\b([A-Z]+(?:\s+[A-Z]+)*)\s+([A-Z]{2})\b", full_desc)
    valid_codes = ['TH', 'CN', 'JP', 'US', 'VN', 'TW', 'KR', 'ID', 'MY', 'DE', 'IT', 'FR', 'GB']
    
    if country_match:
        found_code = country_match.group(2)
        if found_code in valid_codes:
            country_val = country_match.group(0)
            full_desc = full_desc.replace(country_val, " ")
            
    full_desc = re.sub(r"\b\d{13}\b", " ", full_desc)
    full_desc = re.sub(r"\b(FOB|JPY|KGM|PCE)\b", " ", full_desc)
    full_desc = full_desc.strip()
    full_desc = re.sub(r"^[\d\.\-\s]+", "", full_desc)
    full_desc = re.sub(r"\s+", " ", full_desc).strip()
    
    return full_desc, country_val

def generate_sop(ccc, permit):
    notes = []
    p = str(permit)
    c = str(ccc).replace(".", "").replace("-", "")
    
    if 'IFB' in p: notes.append("食品容器 (Food Contact) - 需檢驗")
    elif 'CI' in p: notes.append("一般查驗 (General Inspection)")
    elif 'DH' in p: notes.append("可能為免驗或核備代碼")
    
    if c.startswith('9503'): notes.append("玩具 (Toys) - 需 BSMI 檢驗")
    if c.startswith('3924'): notes.append("塑膠/美耐皿檢驗")
    if c.startswith('940'): notes.append("燈具/家具 - 注意檢驗")
    if c.startswith('691'): notes.append("陶瓷檢驗")
    if c.startswith('9603'): notes.append("刷具 - 注意動物毛/植物毛")
    if c.startswith('630') or c.startswith('570'): notes.append("紡織品 - 注意成分標示")
    if c.startswith('910'): notes.append("鐘錶/計時器 - 注意電池規定")
    
    return "；".join(notes)

# ==========================================
# 3. 單一檔案解析引擎 (V12.0 邏輯)
# ==========================================

def parse_single_pdf(pdf_path):
    # 這裡完全保留 V12.0 的核心解析流程
    items = [] 
    last_item_idx = None 
    decl_no = "Unknown"

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # 抓報單號
            p1_text = pdf.pages[0].extract_text() or ""
            decl_match = re.search(r"([A-Z]{2}/[\s\d/]+/[A-Z0-9]+)", p1_text)
            if decl_match: 
                decl_no = decl_match.group(1).replace(" ", "").replace("//", "/")

            for page_num, page in enumerate(pdf.pages):
                words = page.extract_words(keep_blank_chars=True)
                
                valid_words = []
                for w in words:
                    if not is_header_noise(w['text']):
                        valid_words.append(w)
                words = valid_words

                anchors = []
                for w in words:
                    if w['x0'] < COORD_SPLIT_CCC: 
                        if re.match(r"^\d+\.$", w['text'].strip()):
                            item_num = int(w['text'].strip().replace(".", ""))
                            anchors.append({'item': item_num, 'top': w['top']})
                anchors.sort(key=lambda x: x['top'])
                
                zones = []
                if anchors:
                    first_anchor_top = anchors[0]['top']
                    if first_anchor_top > 10: 
                        zones.append({'start_y': 0, 'end_y': first_anchor_top, 'item_id': last_item_idx})
                else:
                    zones.append({'start_y': 0, 'end_y': page.height, 'item_id': last_item_idx})
                
                for i in range(len(anchors)):
                    start_y = anchors[i]['top']
                    end_y = anchors[i+1]['top'] if i < len(anchors) - 1 else page.height
                    last_item_idx = anchors[i]['item']
                    zones.append({'start_y': start_y, 'end_y': end_y, 'item_id': anchors[i]['item']})
                
                for zone in zones:
                    z_item_id = zone['item_id']
                    if z_item_id is None: continue 
                    
                    target_item = next((it for it in items if it['item_no'] == z_item_id), None)
                    if not target_item:
                        target_item = {'item_no': z_item_id, 'desc_parts': [], 'ccc_parts': [], 'decl_no': decl_no}
                        items.append(target_item)
                    
                    zone_words = [w for w in words if zone['start_y'] <= w['top'] < zone['end_y']]
                    zone_words.sort(key=lambda w: (round(w['top']/2), w['x0']))
                    
                    for w in zone_words:
                        x = w['x0']
                        text = w['text']
                        
                        if COORD_DESC_MIN_X <= x < COORD_SPLIT_CCC:
                            if re.match(r"^\d+\.$", text.strip()): continue 
                            target_item['desc_parts'].append(text)
                            
                        elif COORD_SPLIT_CCC <= x < COORD_NOISE_START:
                            target_item['ccc_parts'].append(text)

        # 整理結果
        final_data = []
        items.sort(key=lambda x: x['item_no'])
        
        for it in items:
            ccc_val, permit_val = extract_ccc_permit(it['ccc_parts'])
            desc_val, country_val = extract_country_and_clean_desc(it['desc_parts'])
            
            barcode = ""
            full_raw_desc = " ".join(it['desc_parts'])
            bc_match = re.search(r"\b(\d{13})\b", full_raw_desc)
            if bc_match: barcode = bc_match.group(1)

            final_data.append({
                "報單號碼": it['decl_no'],
                "項次": it['item_no'],
                "貨號/條碼": barcode,
                "貨物名稱": desc_val,
                "稅則號列": ccc_val,
                "許可證號碼": permit_val,
                "生產國別": country_val,
                "申報注意事項": generate_sop(ccc_val, permit_val),
                "原始檔名": os.path.basename(pdf_path) # 新增檔名欄位以便追蹤
            })
            
        return final_data

    except Exception as e:
        print(f"❌ 解析失敗: {os.path.basename(pdf_path)} - 原因: {str(e)}")
        return []

# ==========================================
# 4. 批次處理主程式
# ==========================================

def main():
    # A. 初始化目錄
    if not os.path.exists(INPUT_DIR):
        os.makedirs(INPUT_DIR)
        print(f"⚠️ 找不到輸入目錄，已自動建立: {INPUT_DIR}")
        print("請將 PDF 檔案放入該目錄後重新執行。")
        return

    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)
        print(f"📁 已建立輸出目錄: {PROCESSED_DIR}")

    # B. 搜尋 PDF
    pdf_files = glob.glob(os.path.join(INPUT_DIR, "*.pdf"))
    if not pdf_files:
        print(f"⚠️ 在 {INPUT_DIR} 中找不到任何 PDF 檔案。")
        return

    print(f"🚀 找到 {len(pdf_files)} 個檔案，開始批次處理...")
    
    all_batch_data = []
    success_count = 0
    fail_count = 0

    # C. 迴圈處理
    for file_path in pdf_files:
        filename = os.path.basename(file_path)
        print(f"   正在處理: {filename} ...", end="\r")
        
        # 執行解析
        file_data = parse_single_pdf(file_path)
        
        # D. 判斷是否成功
        if file_data and len(file_data) > 0:
            # 成功：加入總表
            all_batch_data.extend(file_data)
            success_count += 1
            
            # 移動檔案 (Move)
            try:
                # 若目標目錄已有同名檔案，這會覆蓋或報錯，視作業系統而定
                # 這裡使用 shutil.move
                dst_path = os.path.join(PROCESSED_DIR, filename)
                if os.path.exists(dst_path):
                    os.remove(dst_path) # 若存在先刪除，確保移動成功
                shutil.move(file_path, dst_path)
            except Exception as e:
                print(f"\n⚠️ 檔案移動失敗: {filename} - {e}")
        else:
            # 失敗：不移動，留在原目錄
            fail_count += 1
            print(f"\n❌ 無法提取資料 (保留在原目錄): {filename}")

    print(f"\n\n📊 批次處理完成報告:")
    print(f"   ✅ 成功移至 {PROCESSED_DIR}: {success_count} 檔")
    print(f"   ❌ 解析失敗/無資料 (保留在 {INPUT_DIR}): {fail_count} 檔")

    # E. 輸出 CSV
    if all_batch_data:
        df = pd.DataFrame(all_batch_data)
        
        # 整理欄位
        cols = ['報單號碼', '項次', '貨號/條碼', '貨物名稱', '稅則號列', '許可證號碼', '生產國別', '申報注意事項', '原始檔名']
        df = df[cols]
        
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"💾 彙整資料已儲存至: {OUTPUT_CSV}")
    else:
        print("⚠️ 本次執行沒有產生任何有效資料。")

if __name__ == "__main__":
    main()