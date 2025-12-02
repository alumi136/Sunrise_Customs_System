import pymysql
import os
import sys
import socket
from dotenv import load_dotenv
from pathlib import Path

# 強制顯示輸出
sys.stdout.reconfigure(encoding='utf-8')

# 載入 .env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

def check_port_open(host, port):
    """ [診斷] 檢查遠端主機的 3306 Port 是否有開 (排除防火牆問題) """
    print(f"[Network Check] Pinging {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(3) # 設定 3 秒超時
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"[Network Check] ✅ Port {port} is OPEN. Network is OK.")
            return True
        else:
            print(f"[Network Check] ❌ Port {port} is CLOSED or BLOCKED (ErrCode: {result}).")
            print("   -> 請檢查雲端主機的「安全性群組 (Security Group)」是否放行 3306 Port。")
            return False
    except Exception as e:
        print(f"[Network Check] ❌ Error: {e}")
        return False
    finally:
        sock.close()

def create_connection():
    connection = None
    try:
        print("[Step 2] Reading .env config...")
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")
        db_port = int(os.getenv("DB_PORT", 3306))
        
        # 1. 先做網路診斷
        if not check_port_open(db_host, db_port):
            return None

        print(f"[Step 3] Connecting using PyMySQL... (Host: {db_host}, User: {db_user})")
        
        # 2. 建立連線 (使用 pymysql)
        connection = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_pass,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor, # 讓查詢結果變成 Dictionary 方便使用
            connect_timeout=10 # 設定 10 秒連線超時
        )
        
        if connection.open:
            print("[Success] ✅ MySQL connection established!")
            return connection
            
    except pymysql.MySQLError as e:
        print(f"[MySQL Error] Code: {e.args[0]}, Message: {e.args[1]}")
    except Exception as e:
        print(f"[System Error] {e}")
    
    return None

def close_connection(connection):
    if connection and connection.open:
        connection.close()

if __name__ == "__main__":
    print("🚀 Program started (PyMySQL Mode)")
    
    conn = create_connection()
    
    if conn:
        print(f"[Step 4] Query Test:")
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT VERSION() as ver;")
                result = cursor.fetchone()
                print(f"📊 DB Version: {result['ver']}")
        finally:
            close_connection(conn)
            print("[Step 5] Connection closed.")
    else:
        print("💀 Connection FAILED.")
    
    input("Press Enter to exit...")