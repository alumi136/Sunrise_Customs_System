import pdfplumber
import pandas as pd
import re
import os

# ==========================================
# 1. 系統參數設定
# ==========================================
PDF_PATH = "./inpdf/G2123放行報單.pdf"
OUTPUT_CSV = "G2123_Corrected.csv"

# 物理座標界線 (不變)
COORD_ITEM_MAX_X = 50
COORD_DESC_MIN_X = 10       # 確保抓到品名開頭
COORD_SPLIT_CCC = 202       # 左欄(品名)與中欄(稅則)的分界
COORD_NOISE_START = 315     # 右側雜訊區起點

# 強力表頭過濾庫 (新增大量干擾詞)
GLOBAL_IGNORE_KEYWORDS = [
    "報單號碼", "主提單號碼", "生產國別", "輸出入許可文件號碼", 
    "輸出入貨品分類號列", "納稅辦法", "貨物名稱", "品牌", "規格",
    "數量", "單位", "淨重", "單價", "幣別", "FCL/FCL", "包裝說明",
    "TOTAL", "PAGE", "TERM OF", "進口報單", "項 次", "標記", 
    "貨櫃號碼", "其他申報事項", "長期委任", "未投保", "WHSU", "0CTN"
]

# ==========================================
# 2. 核心邏輯函式
# ==========================================

def is_header_noise(text):
    """檢查是否為表頭/頁尾雜訊"""
    if not text: return False
    # 移除空白後檢查，避免 "項 次" 這種間隔干擾
    clean_t = text.replace(" ", "")
    for kw in GLOBAL_IGNORE_KEYWORDS:
        if kw.replace(" ", "") in clean_t:
            return True
    return False

def extract_ccc_permit(raw_ccc_list):
    """
    智慧分離稅則與許可證
    邏輯：先標準化 -> 拔除許可證 -> 剩下的就是稅則
    """
    # 合併並標準化 (只保留英數)
    raw_text = "".join(raw_ccc_list)
    normalized = re.sub(r'[^A-Z0-9]', '', raw_text)
    
    permit_val = ""
    ccc_val = ""
    
    # 1. 優先提取許可證 (CI + 12碼數字 OR IFB + 11碼英數)
    # 使用 search 尋找
    match_p = re.search(r'(CI\d{12}|IFB[A-Z0-9]{11})', normalized)
    if match_p:
        permit_val = match_p.group(1)
        # 關鍵：從字串中移除許可證，避免干擾 CCC
        normalized = normalized.replace(permit_val, '', 1)
        
    # 2. 提取稅則 (剩下的字串中找 10 或 11 碼數字)
    match_c = re.search(r'(\d{10,11})', normalized)
    if match_c:
        raw_ccc = match_c.group(1)
        if len(raw_ccc) == 11:
            ccc_val = f"{raw_ccc[:4]}.{raw_ccc[4:6]}.{raw_ccc[6:8]}.{raw_ccc[8:10]}-{raw_ccc[10]}"
        else:
            ccc_val = f"{raw_ccc[:4]}.{raw_ccc[4:6]}.{raw_ccc[6:8]}.{raw_ccc[8:10]}"
            
    return ccc_val, permit_val

def extract_country_and_clean_desc(desc_list):
    """
    提取生產國別並清洗貨物名稱
    邏輯：在品名中搜尋國別特徵 -> 提取 -> 刪除 -> 清洗剩餘文字
    """
    full_desc = " ".join(desc_list)
    country_val = ""
    
    # 1. 搜尋生產國別 (特徵：英文單字 + 2碼大寫代碼)
    # 例如: THAILAND TH, UNITED STATES US
    # 使用 Regex 尋找獨立的國名標籤
    country_match = re.search(r"\b([A-Z]+(?:\s+[A-Z]+)*)\s+([A-Z]{2})\b", full_desc)
    
    # 驗證是否為常見國碼 (避免誤判商品型號)
    valid_codes = ['TH', 'CN', 'JP', 'US', 'VN', 'TW', 'KR', 'ID', 'MY', 'DE', 'IT', 'FR', 'GB']
    
    if country_match:
        found_code = country_match.group(2)
        if found_code in valid_codes:
            country_val = country_match.group(0) # 完整字串 "THAILAND TH"
            # 從描述中移除
            full_desc = full_desc.replace(country_val, " ")
            
    # 2. 清洗剩餘的貨物名稱
    # 移除 13 碼條碼
    full_desc = re.sub(r"\b\d{13}\b", " ", full_desc)
    # 移除常見雜訊
    full_desc = re.sub(r"\b(FOB|JPY|KGM|PCE)\b", " ", full_desc)
    # 移除開頭的非文字符號 (殘留的 1. 或 -)
    full_desc = full_desc.strip()
    full_desc = re.sub(r"^[\d\.\-\s]+", "", full_desc)
    # 壓縮多餘空白
    full_desc = re.sub(r"\s+", " ", full_desc).strip()
    
    return full_desc, country_val

def generate_sop(ccc, permit):
    """SOP 邏輯"""
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
# 3. 解析引擎 (V12.0)
# ==========================================

def parse_pdf_v12(pdf_path):
    print(f"🚀 啟動 V12.0 解析: {pdf_path}")
    
    items = [] 
    last_item_idx = None 
    
    with pdfplumber.open(pdf_path) as pdf:
        
        # 1. 抓取報單號
        decl_no = "Unknown"
        p1_text = pdf.pages[0].extract_text() or ""
        decl_match = re.search(r"([A-Z]{2}/[\s\d/]+/[A-Z0-9]+)", p1_text)
        if decl_match: 
            decl_no = decl_match.group(1).replace(" ", "").replace("//", "/")

        # 2. 遍歷每一頁
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words(keep_blank_chars=True)
            
            # --- A. 預處理：過濾全域雜訊 ---
            valid_words = []
            for w in words:
                if not is_header_noise(w['text']):
                    valid_words.append(w)
            words = valid_words

            # --- B. 找出錨點 ---
            anchors = []
            for w in words:
                if w['x0'] < COORD_SPLIT_CCC: 
                    if re.match(r"^\d+\.$", w['text'].strip()):
                        item_num = int(w['text'].strip().replace(".", ""))
                        anchors.append({'item': item_num, 'top': w['top']})
            anchors.sort(key=lambda x: x['top'])
            
            # --- C. 定義區塊 ---
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
            
            # --- D. 提取文字 ---
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
                    
                    # 左欄: 品名與項次
                    if COORD_DESC_MIN_X <= x < COORD_SPLIT_CCC:
                        if re.match(r"^\d+\.$", text.strip()): continue # 跳過錨點本身
                        target_item['desc_parts'].append(text)
                        
                    # 中欄: 稅則與許可證
                    elif COORD_SPLIT_CCC <= x < COORD_NOISE_START:
                        target_item['ccc_parts'].append(text)
                    
                    # 右欄: 雜訊 -> 丟棄

    # 4. 輸出與後處理
    final_data = []
    items.sort(key=lambda x: x['item_no'])
    
    for it in items:
        # 分離 CCC 與 Permit
        ccc_val, permit_val = extract_ccc_permit(it['ccc_parts'])
        
        # 分離 Country 與 Description
        desc_val, country_val = extract_country_and_clean_desc(it['desc_parts'])
        
        # 抓取條碼 (從 desc_parts 原始列表裡找比較保險，雖然 clean_desc 已經移除了)
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
            "申報注意事項": generate_sop(ccc_val, permit_val)
        })
        
    return final_data

# ==========================================
# 4. 主程式
# ==========================================
def main():
    if not os.path.exists(PDF_PATH):
        print(f"檔案不存在: {PDF_PATH}")
        return

    result = parse_pdf_v12(PDF_PATH)
    
    df = pd.DataFrame(result)
    cols = ['報單號碼', '項次', '貨號/條碼', '貨物名稱', '稅則號列', '許可證號碼', '生產國別', '申報注意事項']
    df = df[cols]
    
    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"✅ V12.0 處理完成! 檔案已儲存: {OUTPUT_CSV}")
    print(df.head().to_string())

if __name__ == "__main__":
    main()