import csv
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from database import create_connection, close_connection

# 設定標準輸出編碼，避免 Windows 終端機亂碼
sys.stdout.reconfigure(encoding='utf-8')

def import_csv_to_db(csv_filename):
    # 1. 檢查檔案是否存在
    if not os.path.exists(csv_filename):
        print(f"❌ 錯誤: 找不到檔案 '{csv_filename}'")
        return 0, None

    conn = create_connection()
    if not conn:
        return 0, None

    try:
        cursor = conn.cursor()
        print(f"🚀 開始匯入 '{csv_filename}' ...")

        # 2. 自動偵測編碼 (UTF-8, UTF-8-sig, Big5)
        encodings = ['utf-8', 'utf-8-sig', 'utf-16', 'big5']
        decoded_file = None
        
        for enc in encodings:
            try:
                f = open(csv_filename, mode='r', encoding=enc, newline='')
                f.readline() # 試讀一行
                f.seek(0)    # 回到開頭
                decoded_file = f
                print(f"ℹ️ 偵測到檔案編碼: {enc}")
                break
            except UnicodeDecodeError:
                f.close()
                continue
        
        if not decoded_file:
            print("❌ 錯誤: 無法識別檔案編碼。")
            return 0, None

        # 3. 開始讀取與寫入資料庫
        with decoded_file as csvfile:
            reader = csv.DictReader(csvfile)
            
            count_new_prod = 0
            count_update_prod = 0
            count_items = 0
            decl_no_set = set() # 用集合來儲存不重複的報單號碼

            for row in reader:
                # --- 欄位對應 (Mapping) ---
                decl_no = row.get('報單號碼', '').strip()
                seq_no = row.get('項次', '0').strip()
                barcode = row.get('貨號/條碼', '').strip()
                name_en = row.get('貨物名稱', '').strip()
                ccc_code = row.get('稅則號列', '').strip()
                permit = row.get('許可證號碼', '').strip()
                note = row.get('申報注意事項', '').strip()
                origin_country = row.get('生產國別', '').strip() # 新增產地欄位

                # 防呆：若無條碼則跳過
                if not barcode:
                    continue
                
                # 記錄報單號碼
                if decl_no:
                    decl_no_set.add(decl_no)

                # ---------------------------------------------------------
                # A. 處理產品主檔 (Products) - 加入 origin_country
                # ---------------------------------------------------------
                sql_prod = """
                    INSERT INTO products (barcode, name_en, default_ccc_code, default_permit_code, risk_note, origin_country)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name_en = VALUES(name_en),
                        default_ccc_code = VALUES(default_ccc_code),
                        default_permit_code = VALUES(default_permit_code),
                        risk_note = VALUES(risk_note),
                        origin_country = VALUES(origin_country);
                """
                cursor.execute(sql_prod, (barcode, name_en, ccc_code, permit, note, origin_country))
                
                if cursor.rowcount == 1:
                    count_new_prod += 1
                elif cursor.rowcount == 2: # MySQL UPDATE 回傳 2 代表有變更
                    count_update_prod += 1

                # 取得 product_id
                cursor.execute("SELECT product_id FROM products WHERE barcode = %s", (barcode,))
                prod_row = cursor.fetchone()
                if not prod_row:
                    continue
                product_id = prod_row['product_id']

                # ---------------------------------------------------------
                # B. 處理報單主檔 (Declarations)
                # ---------------------------------------------------------
                sql_decl = "INSERT IGNORE INTO declarations (decl_no, status) VALUES (%s, '已放行')"
                cursor.execute(sql_decl, (decl_no,))
                
                cursor.execute("SELECT declaration_id FROM declarations WHERE decl_no = %s", (decl_no,))
                result_decl = cursor.fetchone()
                if result_decl:
                    declaration_id = result_decl['declaration_id']
                else:
                    continue

                # ---------------------------------------------------------
                # C. 處理報單明細 (Declaration_Items)
                # ---------------------------------------------------------
                check_sql = "SELECT item_id FROM declaration_items WHERE declaration_id=%s AND seq_no=%s"
                cursor.execute(check_sql, (declaration_id, seq_no))
                if cursor.fetchone():
                    # 若已存在則更新
                    update_item_sql = """
                        UPDATE declaration_items 
                        SET product_id=%s, applied_ccc_code=%s, applied_permit_no=%s
                        WHERE declaration_id=%s AND seq_no=%s
                    """
                    cursor.execute(update_item_sql, (product_id, ccc_code, permit, declaration_id, seq_no))
                else:
                    # 不存在則新增
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
            print(f"   📦 產品資料處理: {count_new_prod + count_update_prod} 筆")
            print(f"   📝 報單明細處理: {count_items} 筆")
            print("-" * 30)
            
            # 回傳匯入筆數與報單號碼列表，供視窗顯示用
            return count_items, list(decl_no_set)

    except Exception as e:
        print(f"❌ 匯入過程中發生錯誤: {e}")
        conn.rollback()
        return 0, None
    finally:
        close_connection(conn)

def select_file_and_import():
    """
    建立隱藏的主視窗，並開啟檔案選擇對話框
    """
    # 建立主視窗但隱藏 (不顯示空白視窗)
    root = tk.Tk()
    root.withdraw()

    # 開啟檔案選擇對話框
    file_path = filedialog.askopenfilename(
        title="請選擇要匯入的 CSV 檔案",
        filetypes=[("CSV 檔案", "*.csv"), ("所有檔案", "*.*")]
    )

    if file_path:
        # 呼叫匯入邏輯
        count, decl_nos = import_csv_to_db(file_path)
        
        if decl_nos is not None:
            decl_str = ", ".join(decl_nos)
            # 顯示成功訊息視窗
            messagebox.showinfo(
                "匯入成功", 
                f"✅ 資料匯入完成！\n\n📄 報單號碼: {decl_str}\n📊 總匯入筆數: {count} 筆"
            )
        else:
            # 顯示失敗訊息視窗
            messagebox.showerror("匯入失敗", "❌ 匯入過程中發生錯誤，請檢查終端機 (Terminal) 的錯誤訊息。")
    else:
        print("使用者取消選擇檔案。")

if __name__ == "__main__":
    select_file_and_import()