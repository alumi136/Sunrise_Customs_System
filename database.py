import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# 1. 強制指定載入 .env 路徑 (避免路徑錯誤)
from pathlib import Path
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

def create_connection():
    """ 建立並回傳資料庫連線物件 """
    connection = None
    try:
        # 除錯：印出目前的設定值 (檢查是否讀到 None)
        # 注意：不要印出密碼，保護安全
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_name = os.getenv("DB_NAME")
        
        if db_host is None or db_user is None:
             print("❌ 嚴重錯誤：讀取不到 .env 設定檔！變數為 None。")
             print("   請確認 .env 檔案是否在同一個資料夾下，且檔名正確。")
             return None

        connection = mysql.connector.connect(
            host=db_host,
            user=db_user,
            password=os.getenv("DB_PASSWORD"),
            database=db_name,
            port=os.getenv("DB_PORT", "3306") # 預設給 3306 避免 None 錯誤
        )
        if connection.is_connected():
            return connection
            
    except Error as e:
        print(f"❌ MySQL 連線錯誤: {e}")
        return None
    except Exception as e:
        # 捕捉其他所有 Python 錯誤 (如 TypeError)
        print(f"❌ 程式執行錯誤 (Python Error): {e}")
        return None

def close_connection(connection):
    if connection and connection.is_connected():
        connection.close()

if __name__ == "__main__":
    print("🚀 正在嘗試連線到 MySQL...")
    
    # 測試 .env 是否存在
    if not os.path.exists(".env"):
        print("⚠️ 警告：系統找不到 .env 檔案！請確認檔名是否真的是 '.env' (不是 .env.txt)")

    conn = create_connection()
    
    if conn:
        print(f"✅ 成功連線到資料庫: {os.getenv('DB_NAME')}")
        close_connection(conn)
    else:
        print("💀 連線失敗，請檢查上方錯誤訊息。")