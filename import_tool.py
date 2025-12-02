import csv
import os
import sys
from database import create_connection, close_connection

# 設定標準輸出編碼，避免 Windows 終端機亂碼
sys.stdout.reconfigure(encoding='utf-8')

def import_csv_to_db(csv_filename="Import_Data.csv"):
    # 1. 檢查檔案是否存在
    if not os.path.exists(csv_filename):
        print(f"❌ 錯誤: 找不到檔案 '{csv_filename}'")
        print("   請確認檔案已放入專案目錄中。")
        return

    conn = create_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        print(f"🚀 開始匯入 '{csv_filename}' ...")

        # 2. 開啟 CSV 檔案 (使用 utf-8-sig 以自動處理 BOM)
        with open(csv_filename, mode='r', encoding='utf-8-sig', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # 統計變數
            count_new_prod = 0
            count_update_prod = 0
            count_items = 0

            for row in reader:
                # --- 欄位對應 (Mapping) ---
                # CSV header: 報單號碼, 項次, 貨號/條碼, 貨物名稱, 稅則號列, 許可證號碼, 申報注意事項
                decl_no = row.get('報單號碼', '').strip()
                seq_no = row.get('項次', '0').strip()
                barcode = row.get('貨號/條碼', '').strip()
                name_en = row.get('貨物名稱', '').strip()
                ccc_code = row.get('稅則號列', '').strip()
                permit = row.get('許可證號碼', '').strip()
                note = row.get('申報注意事項', '').strip()

                # 簡單防呆：如果沒有條碼，就跳過 (或使用流水號，這裡先跳過)
                if not barcode:
                    print(f"   ⚠️ 跳過無條碼項目: 第 {seq_no} 項 - {name_en[:10]}...")
                    continue

                # ---------------------------------------------------------
                # A. 處理產品主檔 (Products)
                # ---------------------------------------------------------
                # 邏輯: 如果條碼已存在 -> 更新資料; 如果不存在 -> 新增
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
                
                # 判斷是新增還是更新 (透過 rowcount)
                if cursor.rowcount == 1:
                    count_new_prod += 1
                elif cursor.rowcount == 2: # MySQL UPDATE 回傳 2 代表有變更
                    count_update_prod += 1

                # 取得 product_id (給後面用)
                cursor.execute("SELECT product_id FROM products WHERE barcode = %s", (barcode,))
                product_id = cursor.fetchone()['product_id']

                # ---------------------------------------------------------
                # B. 處理報單主檔 (Declarations)
                # ---------------------------------------------------------
                # 邏輯: 如果報單號不存在則新增 (使用 INSERT IGNORE)
                # 這裡暫時沒有進口日期，先留空
                sql_decl = "INSERT IGNORE INTO declarations (decl_no, status) VALUES (%s, '已放行')"
                cursor.execute(sql_decl, (decl_no,))
                
                # 取得 declaration_id
                cursor.execute("SELECT declaration_id FROM declarations WHERE decl_no = %s", (decl_no,))
                result_decl = cursor.fetchone()
                if result_decl:
                    declaration_id = result_decl['declaration_id']
                else:
                    # 理論上不會發生，除非 INSERT 失敗
                    print(f"❌ 無法取得報單 ID: {decl_no}")
                    continue

                # ---------------------------------------------------------
                # C. 處理報單明細 (Declaration_Items)
                # ---------------------------------------------------------
                # 邏輯: 紀錄這次進口的歷程
                sql_item = """
                    INSERT INTO declaration_items 
                    (declaration_id, product_id, seq_no, applied_ccc_code, applied_permit_no)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql_item, (declaration_id, product_id, seq_no, ccc_code, permit))
                count_items += 1

            # 全部完成後提交 (Commit)
            conn.commit()
            
            print("-" * 30)
            print("✅ 匯入完成！統計結果：")
            print(f"   📦 新增產品資料: {count_new_prod} 筆")
            print(f"   🔄 更新產品資料: {count_update_prod} 筆")
            print(f"   📝 建立歷史紀錄: {count_items} 筆")
            print("-" * 30)

    except Exception as e:
        print(f"❌ 匯入過程中發生錯誤: {e}")
        conn.rollback() # 發生錯誤則回滾，避免資料不完整
    finally:
        close_connection(conn)

if __name__ == "__main__":
    import_csv_to_db()
    input("按 Enter 鍵離開...")