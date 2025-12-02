import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
from database import create_connection, close_connection  # 匯入我們寫好的連線程式

# --- 系統設定 ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class CustomsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 視窗設定
        self.title("昇洋正式報關系統 (Sunrise Customs System)")
        self.geometry("1100x700")
        self.minsize(800, 600)
        
        # 字體設定
        self.main_font = ("Microsoft YaHei UI", 14)
        self.header_font = ("Microsoft YaHei UI", 20, "bold")

        # 用戶狀態
        self.current_user = None  # 儲存登入者資訊 (Dict)

        # 啟動登入畫面
        self.show_login_screen()

    # ==========================
    # 畫面 1: 登入頁面
    # ==========================
    def show_login_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.login_frame = ctk.CTkFrame(self, corner_radius=15)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self.login_frame, text="昇洋物流報關系統", font=self.header_font).pack(pady=(30, 20), padx=50)

        self.entry_user = ctk.CTkEntry(self.login_frame, placeholder_text="使用者帳號", width=250, font=self.main_font)
        self.entry_user.pack(pady=10, padx=20)
        # 預設幫您填好 admin (方便測試，上線可移除)
        self.entry_user.insert(0, "admin")

        self.entry_pass = ctk.CTkEntry(self.login_frame, placeholder_text="密碼", show="*", width=250, font=self.main_font)
        self.entry_pass.pack(pady=10, padx=20)

        self.btn_login = ctk.CTkButton(self.login_frame, text="登入系統", width=250, font=self.main_font, command=self.verify_login)
        self.btn_login.pack(pady=(20, 30), padx=20)

        self.lbl_msg = ctk.CTkLabel(self.login_frame, text="", text_color="red", font=("Arial", 12))
        self.lbl_msg.pack(pady=(0, 10))

    def verify_login(self):
        """ [核心] 連接 MySQL 驗證帳號密碼 """
        user_input = self.entry_user.get().strip()
        pass_input = self.entry_pass.get().strip()

        if not user_input or not pass_input:
            self.lbl_msg.configure(text="❌ 請輸入帳號與密碼")
            return

        # 鎖定按鈕避免重複點擊
        self.btn_login.configure(state="disabled", text="連線驗證中...")
        self.lbl_msg.configure(text="⏳ 連線資料庫中...", text_color="blue")
        self.update() # 強制刷新畫面

        # 使用執行緒 (Thread) 避免介面卡死
        threading.Thread(target=self._login_thread, args=(user_input, pass_input)).start()

    def _login_thread(self, user, pwd):
        """ 背景執行資料庫查詢 """
        conn = create_connection()
        
        if conn:
            try:
                with conn.cursor() as cursor:
                    # 查詢使用者
                    sql = "SELECT * FROM users WHERE username=%s AND password=%s"
                    cursor.execute(sql, (user, pwd))
                    result = cursor.fetchone() # 取得第一筆結果

                    if result:
                        # 登入成功
                        self.current_user = result # 存下使用者資料
                        print(f"登入成功: {result['real_name']} ({result['role']})")
                        # 回到主執行緒更新 UI
                        self.after(0, self.setup_main_interface)
                    else:
                        # 帳密錯誤
                        self.after(0, lambda: self._login_failed("❌ 帳號或密碼錯誤"))
            except Exception as e:
                self.after(0, lambda: self._login_failed(f"❌ 系統錯誤: {str(e)}"))
            finally:
                close_connection(conn)
        else:
            self.after(0, lambda: self._login_failed("❌ 無法連線至資料庫 (請檢查網路/VPN)"))

    def _login_failed(self, msg):
        self.lbl_msg.configure(text=msg, text_color="red")
        self.btn_login.configure(state="normal", text="登入系統")

    # ==========================
    # 畫面 2: 主操作介面
    # ==========================
    def setup_main_interface(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 側邊欄 ===
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        role_text = "管理員" if self.current_user['role'] == 'admin' else "一般用戶"
        ctk.CTkLabel(self.sidebar, text=f"昇洋報關\n{self.current_user['real_name']}", font=self.header_font).grid(row=0, column=0, padx=20, pady=20)
        ctk.CTkLabel(self.sidebar, text=f"[{role_text}]", text_color="gray").grid(row=1, column=0)

        self.create_sidebar_btn("📦 進口查詢 (主頁)", 2, command=self.show_search_page)
        self.create_sidebar_btn("📋 歷史報單", 3, command=lambda: print("開發中..."))
        
        # 管理員權限控管
        if self.current_user['role'] == 'admin':
            ctk.CTkFrame(self.sidebar, height=2, fg_color="gray50").grid(row=4, column=0, sticky="ew", padx=20, pady=10)
            self.create_sidebar_btn("🗄️ 資料庫維護", 5)

        ctk.CTkButton(self.sidebar, text="登出", fg_color="transparent", border_width=1, command=self.show_login_screen).grid(row=7, column=0, padx=20, pady=20)

        # === 內容區 ===
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.show_search_page()

    def create_sidebar_btn(self, text, row, command=None):
        btn = ctk.CTkButton(self.sidebar, text=text, height=40, corner_radius=8, fg_color="transparent", anchor="w", command=command, font=self.main_font)
        btn.grid(row=row, column=0, sticky="ew", padx=20, pady=5)

    # ==========================
    # 功能: 產品查詢頁面 (連接 DB)
    # ==========================
    def show_search_page(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

        # 搜尋框
        search_panel = ctk.CTkFrame(self.main_area)
        search_panel.pack(fill="x", pady=(0, 10))
        
        self.entry_keyword = ctk.CTkEntry(search_panel, placeholder_text="輸入 條碼 / 品名 / 稅號", width=300, font=self.main_font)
        self.entry_keyword.pack(side="left", padx=20, pady=20)
        self.entry_keyword.bind("<Return>", lambda event: self.search_data()) # 按 Enter 查詢

        ctk.CTkButton(search_panel, text="🔍 查詢", width=100, command=self.search_data, font=self.main_font).pack(side="left", padx=10)

        # 表格區
        self.tree_frame = ctk.CTkFrame(self.main_area)
        self.tree_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Microsoft YaHei UI", 11), rowheight=30)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 12, "bold"))

        cols = ("barcode", "name", "ccc", "permit", "note")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        self.tree.heading("barcode", text="貨號/條碼")
        self.tree.heading("name", text="貨物名稱")
        self.tree.heading("ccc", text="預設稅則")
        self.tree.heading("permit", text="許可證")
        self.tree.heading("note", text="SOP 注意事項")

        self.tree.column("barcode", width=130)
        self.tree.column("name", width=300)
        self.tree.column("ccc", width=120)
        self.tree.column("permit", width=120)
        self.tree.column("note", width=250)
        
        # 卷軸
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # 載入初始資料 (最新 50 筆)
        self.search_data(init=True)

    def search_data(self, init=False):
        """ [核心] 從資料庫撈取產品資料 """
        keyword = self.entry_keyword.get().strip()
        
        # 清空舊資料
        for row in self.tree.get_children():
            self.tree.delete(row)

        conn = create_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    if init:
                        # 初始顯示前 50 筆
                        sql = "SELECT barcode, name_en, default_ccc_code, default_permit_code, risk_note FROM products ORDER BY product_id DESC LIMIT 50"
                        cursor.execute(sql)
                    else:
                        # 模糊搜尋
                        sql = """
                            SELECT barcode, name_en, default_ccc_code, default_permit_code, risk_note 
                            FROM products 
                            WHERE barcode LIKE %s OR name_en LIKE %s OR default_ccc_code LIKE %s 
                            LIMIT 100
                        """
                        param = f"%{keyword}%"
                        cursor.execute(sql, (param, param, param))
                    
                    rows = cursor.fetchall()
                    for r in rows:
                        # 處理 None 值避免顯示 None
                        note = r['risk_note'] if r['risk_note'] else ""
                        permit = r['default_permit_code'] if r['default_permit_code'] else ""
                        self.tree.insert("", "end", values=(r['barcode'], r['name_en'], r['default_ccc_code'], permit, note))
                        
            except Exception as e:
                print(f"查詢錯誤: {e}")
                messagebox.showerror("錯誤", f"查詢失敗: {e}")
            finally:
                close_connection(conn)

if __name__ == "__main__":
    app = CustomsApp()
    app.mainloop()