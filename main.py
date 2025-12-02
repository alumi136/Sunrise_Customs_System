import customtkinter as ctk
from tkinter import ttk, messagebox
import threading
import os
import subprocess
import sys
from database import create_connection, close_connection

# --- 系統設定 ---
ctk.set_appearance_mode("Light")  # 強制淺色模式以符合您的白底黑字需求
ctk.set_default_color_theme("blue")

class CustomsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 視窗設定
        self.title("昇洋報關/報驗系統 (Sunrise Customs System)") # 修改標題
        self.geometry("1200x768") # 稍微加大以容納新欄位
        self.minsize(1024, 600)
        
        # 字體設定
        self.main_font = ("Microsoft YaHei UI", 12)
        # 側邊欄專用粗體
        self.sidebar_font = ("Microsoft YaHei UI", 14, "bold") 
        self.header_font = ("Microsoft YaHei UI", 24, "bold")

        # 用戶狀態
        self.current_user = None

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

        # 標題修正
        ctk.CTkLabel(self.login_frame, text="昇洋報關/報驗系統", font=self.header_font).pack(pady=(30, 20), padx=50)

        self.entry_user = ctk.CTkEntry(self.login_frame, placeholder_text="使用者帳號", width=250, font=self.main_font)
        self.entry_user.pack(pady=10, padx=20)
        self.entry_user.insert(0, "admin") # 預設 admin

        self.entry_pass = ctk.CTkEntry(self.login_frame, placeholder_text="密碼", show="*", width=250, font=self.main_font)
        self.entry_pass.pack(pady=10, padx=20)

        self.btn_login = ctk.CTkButton(self.login_frame, text="登入系統", width=250, font=self.main_font, command=self.verify_login)
        self.btn_login.pack(pady=(20, 30), padx=20)

        self.lbl_msg = ctk.CTkLabel(self.login_frame, text="", text_color="red", font=("Arial", 12))
        self.lbl_msg.pack(pady=(0, 10))

    def verify_login(self):
        user_input = self.entry_user.get().strip()
        pass_input = self.entry_pass.get().strip()

        if not user_input or not pass_input:
            self.lbl_msg.configure(text="❌ 請輸入帳號與密碼")
            return

        self.btn_login.configure(state="disabled", text="連線驗證中...")
        self.lbl_msg.configure(text="⏳ 連線資料庫中...", text_color="blue")
        self.update()

        threading.Thread(target=self._login_thread, args=(user_input, pass_input)).start()

    def _login_thread(self, user, pwd):
        conn = create_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    sql = "SELECT * FROM users WHERE username=%s AND password=%s"
                    cursor.execute(sql, (user, pwd))
                    result = cursor.fetchone()

                    if result:
                        self.current_user = result
                        self.after(0, self.setup_main_interface)
                    else:
                        self.after(0, lambda: self._login_failed("❌ 帳號或密碼錯誤"))
            except Exception as e:
                self.after(0, lambda: self._login_failed(f"❌ 系統錯誤: {str(e)}"))
            finally:
                close_connection(conn)
        else:
            self.after(0, lambda: self._login_failed("❌ 無法連線至資料庫"))

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

        # === 側邊欄 (Sidebar) ===
        # 使用淺灰色背景，類似您的圖片
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#EBEBEB") 
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        # 用戶資訊區塊
        role_display = "系統管理員" if self.current_user['role'] == 'admin' else "報關人員"
        
        # 紅色框標題區 (模擬圖片效果)
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=10, pady=(20, 10))
        
        ctk.CTkLabel(title_frame, text="昇洋報關", font=("Microsoft YaHei UI", 20, "bold"), text_color="black").pack()
        ctk.CTkLabel(title_frame, text=role_display, font=("Microsoft YaHei UI", 16, "bold"), text_color="black").pack()

        ctk.CTkLabel(self.sidebar, text=f"[{self.current_user['real_name']}]", text_color="gray").grid(row=1, column=0, pady=(0, 20))

        # === 藍色框區域 (功能選單) ===
        # 修改：字體改為黑色、粗體，hover 效果保留藍色
        self.create_sidebar_btn("📦 進口查詢 (主頁)", 2, command=self.show_search_page)
        self.create_sidebar_btn("📋 歷史報單", 3, command=lambda: messagebox.showinfo("提示", "功能開發中"))
        
        if self.current_user['role'] == 'admin':
            # 分隔線
            ctk.CTkFrame(self.sidebar, height=2, fg_color="gray70").grid(row=4, column=0, sticky="ew", padx=20, pady=10)
            self.create_sidebar_btn("🗄️ 資料庫維護", 5)

        # 登出按鈕 (底部)
        btn_logout = ctk.CTkButton(self.sidebar, text="登出", 
                                   fg_color="transparent", 
                                   border_width=1, 
                                   border_color="gray",
                                   text_color="black", # 黑色字體
                                   font=self.main_font,
                                   command=self.show_login_screen)
        btn_logout.grid(row=7, column=0, padx=20, pady=20, sticky="ew")

        # === 內容區 ===
        self.main_area = ctk.CTkFrame(self, fg_color="transparent") # 透明背景，透出底色
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.show_search_page()

    def create_sidebar_btn(self, text, row, command=None):
        """ 建立側邊欄按鈕，強制黑色粗體字 """
        btn = ctk.CTkButton(self.sidebar, 
                            text=text, 
                            height=50, 
                            corner_radius=8, 
                            fg_color="transparent", 
                            text_color="black",      # 修改：字體改為黑色
                            font=self.sidebar_font,  # 修改：使用粗體
                            anchor="w", 
                            hover_color="#D0D0D0",   # 滑鼠移過去變深灰
                            command=command)
        btn.grid(row=row, column=0, sticky="ew", padx=15, pady=5)

    # ==========================
    # 功能: 產品/歷史查詢頁面
    # ==========================
    def show_search_page(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

        # 搜尋框區塊
        search_panel = ctk.CTkFrame(self.main_area, fg_color="#D0D0D0") # 淺灰背景
        search_panel.pack(fill="x", pady=(0, 10))
        
        self.entry_keyword = ctk.CTkEntry(search_panel, placeholder_text="輸入 條碼 / 品名 / 稅號", width=400, font=self.main_font)
        self.entry_keyword.pack(side="left", padx=20, pady=20)
        self.entry_keyword.bind("<Return>", lambda event: self.search_data())

        ctk.CTkButton(search_panel, text="🔍 查詢", width=120, command=self.search_data, font=self.main_font).pack(side="left", padx=10)

        # 表格區
        self.tree_frame = ctk.CTkFrame(self.main_area)
        self.tree_frame.pack(fill="both", expand=True)

        # Treeview 樣式設定
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        font=("Microsoft YaHei UI", 11), 
                        rowheight=30,
                        background="white",
                        foreground="black")
        style.configure("Treeview.Heading", 
                        font=("Microsoft YaHei UI", 12, "bold"),
                        background="#E0E0E0",
                        foreground="black")

        # 修改：新增 decl_no (報單號碼) 為第一欄
        cols = ("decl_no", "barcode", "name", "ccc", "permit", "note")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show="headings")
        
        self.tree.heading("decl_no", text="報單號碼") # 新增
        self.tree.heading("barcode", text="貨號/條碼")
        self.tree.heading("name", text="貨物名稱")
        self.tree.heading("ccc", text="申報稅則")
        self.tree.heading("permit", text="許可證 (點兩下開啟)") # 提示使用者
        self.tree.heading("note", text="SOP 注意事項")

        self.tree.column("decl_no", width=160, anchor="center")
        self.tree.column("barcode", width=140, anchor="center")
        self.tree.column("name", width=350)
        self.tree.column("ccc", width=120, anchor="center")
        self.tree.column("permit", width=150, anchor="center") # 許可證
        self.tree.column("note", width=250)
        
        # 綁定雙擊事件 (用於開啟 PDF)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # 卷軸
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # 載入初始資料
        self.search_data(init=True)

    def search_data(self, init=False):
        keyword = self.entry_keyword.get().strip()
        
        for row in self.tree.get_children():
            self.tree.delete(row)

        conn = create_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    # 修改 SQL：使用 JOIN 連結三個表，以取得報單號碼
                    base_sql = """
                        SELECT 
                            d.decl_no, 
                            p.barcode, 
                            p.name_en, 
                            i.applied_ccc_code, 
                            i.applied_permit_no, 
                            p.risk_note
                        FROM declaration_items i
                        JOIN products p ON i.product_id = p.product_id
                        JOIN declarations d ON i.declaration_id = d.declaration_id
                    """
                    
                    if init:
                        # 初始顯示最新進口的 50 筆
                        sql = base_sql + " ORDER BY d.import_date DESC, i.item_id ASC LIMIT 50"
                        cursor.execute(sql)
                    else:
                        # 模糊搜尋
                        sql = base_sql + """
                            WHERE p.barcode LIKE %s 
                               OR p.name_en LIKE %s 
                               OR i.applied_ccc_code LIKE %s
                               OR d.decl_no LIKE %s
                            ORDER BY d.import_date DESC LIMIT 100
                        """
                        param = f"%{keyword}%"
                        cursor.execute(sql, (param, param, param, param))
                    
                    rows = cursor.fetchall()
                    for r in rows:
                        note = r['risk_note'] if r['risk_note'] else ""
                        permit = r['applied_permit_no'] if r['applied_permit_no'] else ""
                        
                        self.tree.insert("", "end", values=(
                            r['decl_no'], 
                            r['barcode'], 
                            r['name_en'], 
                            r['applied_ccc_code'], 
                            permit, 
                            note
                        ))
                        
            except Exception as e:
                print(f"查詢錯誤: {e}")
                messagebox.showerror("錯誤", f"查詢失敗: {e}")
            finally:
                close_connection(conn)

    def on_tree_double_click(self, event):
        """ 處理雙擊事件：開啟許可證 PDF """
        # 1. 判斷點擊的是哪一列
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        # 2. 判斷點擊的是哪一欄 (column)
        column_id = self.tree.identify_column(event.x)
        
        # 欄位索引對照: #1=decl_no, #2=barcode, #3=name, #4=ccc, #5=permit
        if column_id == "#5":  # 這是許可證欄位
            values = self.tree.item(item_id, "values")
            permit_no = values[4] # 取得許可證號碼

            if permit_no and permit_no != "None":
                self.open_permit_file(permit_no)
            else:
                messagebox.showinfo("提示", "此項目沒有許可證號碼")

    def open_permit_file(self, permit_no):
        """ 開啟 PDF 檔案的邏輯 """
        # 設定檔案存放資料夾 (請在專案目錄下建立這個資料夾)
        pdf_folder = "PDF_Files"
        
        # 假設檔名規則是：許可證號.pdf (例如 IFB14DJ6532506-01.pdf)
        # 您需要處理檔名中的特殊字元，這裡先簡單示範
        filename = f"{permit_no}.pdf"
        filepath = os.path.join(pdf_folder, filename)

        # 檢查檔案是否存在
        if os.path.exists(filepath):
            try:
                if sys.platform == "win32":
                    os.startfile(filepath) # Windows 原生開啟
                else:
                    subprocess.call(["xdg-open", filepath]) # Linux/Mac
            except Exception as e:
                messagebox.showerror("錯誤", f"無法開啟檔案: {e}")
        else:
            # 檔案不存在的提示
            # messagebox.showwarning("找不到檔案", f"系統找不到對應的 PDF 檔：\n{filepath}\n\n請確認是否已將檔案放入 PDF_Files 資料夾。")
            
            # (開發測試用) 為了讓您看到效果，如果沒有檔案，我先印出訊息
            print(f"嘗試開啟: {filepath}")
            messagebox.showinfo("開發模式", f"您點擊了許可證：{permit_no}\n\n未來請建立資料夾 'PDF_Files' 並放入 '{filename}' 即可自動開啟。")

if __name__ == "__main__":
    app = CustomsApp()
    app.mainloop()