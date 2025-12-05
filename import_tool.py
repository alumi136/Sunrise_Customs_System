import csv
import os
import sys
import re
from database import create_connection, close_connection

# 設定標準輸出編碼
sys.stdout.reconfigure(encoding='utf-8')

def is_ccc_code(value):
    """ [核心邏輯] 判斷字串是否長得像稅則號列 (例如 3924.90.00.90-9) """
    # 規則：包含小數點，且開頭是數字，長度大於 8
    # 寬鬆檢查：只要有 'xxxx.xx' 的格式就當作錨點
    pattern = r'^\d{4}\.\d{2}'
    return re.match(pattern, value.strip()) is not None

def fix_row_data(row, line_num):
    """ 
    [智慧修復] 處理因為逗號導致欄位位移的資料 
    預期欄位數: 7
    0:報單號, 1:項次, 2:條碼, 3:品名, 4:稅則, 5:許可證, 6:備註
    """
    # 如果欄位數剛好是 7，且第 5 欄(index 4)看起來像稅號，那就不用修
    if len(row) == 7 and is_ccc_code(row[4]):
        return {
            'decl_no': row[0], 'seq_no': row[1], 'barcode': row[2],
            'name': row[3], 'ccc': row[4], 'permit': row[5], 'note': row[6]
        }

    # === 開始修復 ===
    # 1. 尋找「稅則號列」在哪裡？ (這就是錨點)
    ccc_index = -1
    for idx, col in enumerate(row):
        # 從第 3 欄開始找，避免誤判前面的數字
        if idx >= 3 and is_ccc_code(col):
            ccc_index = idx
            break
    
    if ccc_index == -1:
        print(f"   ⚠️ 第 {line_num} 行無法識別稅則號列，跳過此行。(內容: {row})")
        return None

    # 2. 根據錨點重新組裝
    # 條碼是 Index 2，所以品名是從 Index 3 到 ccc_index 之前的所有欄位合併
    try:
        decl_no = row[0]
        seq_no = row[1]
        barcode = row[2]
        
        # [關鍵] 將中間被切開的品名接回去 (用逗號連接)
        name_parts = row[3 : ccc_index]
        name = ", ".join(name_parts).strip() # 這裡我們把被誤切的逗號補回去
        
        ccc = row[ccc_index]
        
        # 處理後面的欄位 (許可證 & 備註)
        # 有時候後面如果還有逗號，也可能導致欄位變多，這裡做簡單處理
        remaining = row[ccc_index + 1 : ]
        
        permit = remaining[0] if len(remaining) > 0 else ""
        # 如果備註也被逗號切開，也把它接回去
        note = ", ".join(remaining[1:]) if len(remaining) > 1 else (remaining[1] if len(remaining) == 1 else "")

        return {
            'decl_no': decl_no, 'seq_no': seq_no, 'barcode': barcode,
            'name': name, 'ccc': ccc, 'permit': permit, 'note': note
        }
    except IndexError:
        print(f"   ❌ 第 {line_num} 行結構嚴重錯誤，無法修復。")
        return None

def import_csv_to_db(csv_filename="Import_Data_F9354.csv"):
    
    if not os.path.exists(csv_filename):
        # 相容舊檔名
        if os.path.exists("Import_Data.csv"):
            csv_filename = "Import_Data.csv"
        else:
            print(f"❌ 錯誤: 找不到檔案 '{csv_filename}'")
            return

    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        print(f"🚀 開始匯入 '{csv_filename}' (啟用智慧欄位修復)...")

        # 自動偵測編碼
        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'big5']
        decoded_file = None
        
        for enc in encodings:
            try:
                f = open(csv_filename, mode='r', encoding=enc, newline='')
                f.readline() # 試讀
                f.seek(0)
                decoded_file = f
                print(f"ℹ️ 使用編碼: {enc}")
                break
            except UnicodeDecodeError:
                f.close()
                continue
        
        if not decoded_file:
            print("❌ 無法讀取檔案編碼")
            return

        with decoded_file as csvfile:
            # 改用 csv.reader (取得原始 List)，而不是 DictReader (依賴標題)
            # 這樣我們才能手動處理欄位錯位
            reader = csv.reader(csvfile)
            
            # 跳過標題列
            header = next(reader, None) 
            
            count_success = 0
            line_num = 1 # 標題是第1行，資料從第2行開始

            for row in reader:
                line_num += 1
                if not row: continue # 跳過空行

                # 呼叫修復邏輯
                data = fix_row_data(row, line_num)
                if not data:
                    continue

                # 取出修復後的資料
                decl_no = data['decl_no']
                seq_no = data['seq_no']
                barcode = data['barcode']
                name_en = data['name']
                ccc_code = data['ccc']
                permit = data['permit']
                note = data['note']

                if not barcode: continue

                # --- 資料庫寫入 (與之前相同) ---
                
                # A. Products
                # 這裡加入預防措施：確保 ccc_code 不會過長 (雖然我們已經加大了 DB)
                if len(ccc_code) > 100: ccc_code = ccc_code[:100]

                sql_prod = """
                    INSERT INTO products (barcode, name_en, default_ccc_code, default_permit_code, risk_note)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name_en = VALUES(name_en),
                        default_ccc_code = VALUES(default_ccc_code),
                        default_permit_code = VALUES(default_permit_code),
                        risk_note = VALUES(risk_note);
                """
                cursor.execute(sql_prod, (barcode, name_en, ccc_code, permit, note))
                
                # 取得 product_id
                cursor.execute("SELECT product_id FROM products WHERE barcode = %s", (barcode,))
                prod_row = cursor.fetchone()
                if not prod_row: continue
                product_id = prod_row['product_id']

                # B. Declarations
                sql_decl = "INSERT IGNORE INTO declarations (decl_no, status) VALUES (%s, '已放行')"
                cursor.execute(sql_decl, (decl_no,))
                
                cursor.execute("SELECT declaration_id FROM declarations WHERE decl_no = %s", (decl_no,))
                result_decl = cursor.fetchone()
                if not result_decl: continue
                declaration_id = result_decl['declaration_id']

                # C. Declaration Items
                check_sql = "SELECT item_id FROM declaration_items WHERE declaration_id=%s AND seq_no=%s"
                cursor.execute(check_sql, (declaration_id, seq_no))
                if cursor.fetchone():
                    update_sql = """
                        UPDATE declaration_items 
                        SET product_id=%s, applied_ccc_code=%s, applied_permit_no=%s
                        WHERE declaration_id=%s AND seq_no=%s
                    """
                    cursor.execute(update_sql, (product_id, ccc_code, permit, declaration_id, seq_no))
                else:
                    insert_sql = """
                        INSERT INTO declaration_items 
                        (declaration_id, product_id, seq_no, applied_ccc_code, applied_permit_no)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (declaration_id, product_id, seq_no, ccc_code, permit))
                
                count_success += 1

            conn.commit()
            print("-" * 30)
            print(f"✅ 智慧匯入完成！成功處理: {count_success} 筆")
            print("-" * 30)

    except Exception as e:
        print(f"❌ 錯誤: {e}")
        conn.rollback()
    finally:
        close_connection(conn)

if __name__ == "__main__":
    import_csv_to_db("Import_Data_F9354.csv")
    input("按 Enter 鍵離開...")