import customtkinter as ctk
from tkinter import ttk
import tkinter as limited_tk

# 設定外觀模式 (System 會跟隨 Windows 11 的深色/淺色設定)
ctk.set_appearance_mode("System")  
# 設定主題顏色 (深藍色系符合商務專業感)
ctk.set_default_color_theme("blue")  

class CustomsApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- 視窗基礎設定 ---
        self.title("昇洋正式報關系統 (Sunrise Customs System)")
        self.geometry("1100x700") # 寬敞的初始尺寸
        self.minsize(800, 600)
        
        # 設定字體 (使用微軟正黑體，避免中文變醜)
        self.main_font = ("Microsoft YaHei UI", 14)
        self.header_font = ("Microsoft YaHei UI", 20, "bold")

        # 初始化變數
        self.current_user_role = None 

        # --- 啟動登入畫面 ---
        self.show_login_screen()

    def show_login_screen(self):
        """ 顯示登入畫面 """
        # 清空畫面
        for widget in self.winfo_children():
            widget.destroy()

        # 建立登入框架 (置中)
        self.login_frame = ctk.CTkFrame(self, corner_radius=15)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")

        # 標題
        label_title = ctk.CTkLabel(self.login_frame, text="昇洋物流報關系統", font=self.header_font)
        label_title.pack(pady=(30, 20), padx=50)

        # 帳號輸入
        self.entry_user = ctk.CTkEntry(self.login_frame, placeholder_text="使用者帳號", width=250, font=self.main_font)
        self.entry_user.pack(pady=10, padx=20)

        # 密碼輸入
        self.entry_pass = ctk.CTkEntry(self.login_frame, placeholder_text="密碼", show="*", width=250, font=self.main_font)
        self.entry_pass.pack(pady=10, padx=20)

        # 登入按鈕
        btn_login = ctk.CTkButton(self.login_frame, text="登入系統", width=250, font=self.main_font, command=self.verify_login)
        btn_login.pack(pady=(20, 30), padx=20)

        # 模擬提示 (開發階段用)
        label_hint = ctk.CTkLabel(self.login_frame, text="測試帳號: admin / user\n密碼任意", text_color="gray", font=("Arial", 10))
        label_hint.pack(pady=(0, 20))

    def verify_login(self):
        """ 驗證登入邏輯 (之後這裡要連接 MySQL) """
        username = self.entry_user.get()
        # 模擬驗證
        if username == "admin":
            self.current_user_role = "admin"
            self.setup_main_interface()
        elif username == "user":
            self.current_user_role = "user"
            self.setup_main_interface()
        else:
            # 錯誤提示
            self.entry_user.configure(border_color="red")
            
    def setup_main_interface(self):
        """ 建立主操作介面 (側邊欄 + 內容區) """
        # 清空登入畫面
        for widget in self.winfo_children():
            widget.destroy()

        # --- 格狀佈局設定 ---
        # 0欄=側邊欄(固定寬度), 1欄=內容區(自動縮放)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 左側：側邊導航欄 (Sidebar) ===
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1) # 讓登出按鈕推到底部

        # 側邊欄標題
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="昇洋報關\n管理中心", font=self.header_font)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # 側邊欄按鈕 (共用功能)
        self.btn_home = self.create_sidebar_btn("📦 進口查詢 (主頁)", 1)
        self.btn_history = self.create_sidebar_btn("📋 歷史報單", 2)
        
        # 側邊欄按鈕 (管理者限定)
        if self.current_user_role == "admin":
            self.btn_db = self.create_sidebar_btn("🗄️ 資料庫維護", 3)
            self.btn_users = self.create_sidebar_btn("👤 人員權限", 4)
            # 區隔線
            line = ctk.CTkFrame(self.sidebar_frame, height=2, fg_color="gray")
            line.grid(row=5, column=0, sticky="ew", padx=20, pady=20)

        # 登出按鈕
        self.btn_logout = ctk.CTkButton(self.sidebar_frame, text="登出系統", fg_color="transparent", border_width=2, 
                                        text_color=("gray10", "#DCE4EE"), command=self.show_login_screen)
        self.btn_logout.grid(row=7, column=0, padx=20, pady=20)

        # === 右側：主內容區 (Main Content) ===
        self.main_area = ctk.CTkFrame(self, fg_color="transparent") # 透明背景
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # 這裡預設顯示「查詢頁面」
        self.show_search_page()

    def create_sidebar_btn(self, text, row):
        """ 快速建立側邊欄按鈕的輔助函式 """
        btn = ctk.CTkButton(self.sidebar_frame, text=text, height=40, corner_radius=8, 
                            fg_color="transparent", text_color=("gray10", "#DCE4EE"), 
                            hover_color=("gray70", "gray30"), anchor="w", font=self.main_font)
        btn.grid(row=row, column=0, sticky="ew", padx=20, pady=5)
        return btn

    def show_search_page(self):
        """ 顯示主頁：條碼查詢與結果顯示 """
        # 清空右側內容
        for widget in self.main_area.winfo_children():
            widget.destroy()

        # 1. 頂部搜尋區
        search_frame = ctk.CTkFrame(self.main_area, corner_radius=10)
        search_frame.pack(fill="x", pady=(0, 20))

        lbl_hint = ctk.CTkLabel(search_frame, text="🔍 快速查詢 (請掃描條碼或輸入貨號):", font=self.main_font)
        lbl_hint.pack(side="left", padx=20, pady=20)

        entry_search = ctk.CTkEntry(search_frame, placeholder_text="在此輸入條碼 (例如: 4550480496986)", width=400, font=self.main_font)
        entry_search.pack(side="left", padx=10, pady=20)

        btn_search = ctk.CTkButton(search_frame, text="查詢", width=100, font=self.main_font)
        btn_search.pack(side="left", padx=20, pady=20)

        # 2. 中間結果顯示區 (預留給資料庫表格)
        # 這裡我們先用 Treeview 模擬，因為它是顯示數據最好的方式
        result_frame = ctk.CTkFrame(self.main_area, corner_radius=10)
        result_frame.pack(fill="both", expand=True)

        lbl_result = ctk.CTkLabel(result_frame, text="📦 產品主檔與歷史紀錄", font=self.header_font)
        lbl_result.pack(anchor="w", padx=20, pady=(20, 10))

        # 使用 ttk.Treeview 來顯示表格 (因為 CustomTkinter 目前還沒有原生表格元件)
        # 我們需要一點 style 設定讓它在深色模式下好看一點
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Microsoft YaHei UI", 11), rowheight=30)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 12, "bold"))

        columns = ("barcode", "name", "ccc", "permit", "note")
        tree = ttk.Treeview(result_frame, columns=columns, show="headings", height=15)
        
        # 定義欄位
        tree.heading("barcode", text="貨號/條碼")
        tree.heading("name", text="貨物名稱")
        tree.heading("ccc", text="稅則號列")
        tree.heading("permit", text="許可證號")
        tree.heading("note", text="注意事項 (SOP)")

        tree.column("barcode", width=150)
        tree.column("name", width=300)
        tree.column("ccc", width=120)
        tree.column("permit", width=150)
        tree.column("note", width=250)

        # 模擬插入一筆資料 (未來這裡會連動 MySQL)
        tree.insert("", "end", values=("4550480496986", "Oval Melamine Tray...", "3924.10.00.90-6", "DH99...", "⚠️ 塑膠/美耐皿檢驗"))
        tree.insert("", "end", values=("4549892963605", "Glockenspiel Piano", "9503.00.71.00-8", "2020...", "⚠️ 玩具 BSMI 檢驗"))

        tree.pack(fill="both", expand=True, padx=20, pady=20)

        # 3. 底部狀態列
        status_label = ctk.CTkLabel(self.main_area, text=f"當前使用者: {self.current_user_role} | 資料庫連線: 待連線", text_color="gray")
        status_label.pack(side="bottom", anchor="e", pady=10)

if __name__ == "__main__":
    app = CustomsApp()
    app.mainloop()