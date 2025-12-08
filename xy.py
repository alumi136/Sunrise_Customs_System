import pdfplumber
import pandas as pd

# 設定 PDF 檔案路徑
file_path = "./inpdf/G2099 放行報單.pdf"  # 請確認檔名正確

def inspect_pdf_coordinates(path):
    print(f"🕵️‍♀️ 正在分析 PDF 座標結構: {path}")
    
    try:
        with pdfplumber.open(path) as pdf:
            page = pdf.pages[0] # 只看第一頁
            words = page.extract_words(keep_blank_chars=True)
            
            print(f"📄 頁面尺寸: 寬 {page.width}, 高 {page.height}")
            print("-" * 60)
            print(f"{'文字內容':<30} | {'X0 (左邊界)':<10} | {'X1 (右邊界)':<10} | {'Top (垂直高度)'}")
            print("-" * 60)
            
            # 我們只列印出「項次 1」附近的文字來分析
            # 假設項次 1 大約在垂直高度 100~300 之間 (依之前的經驗)
            target_words = []
            
            start_logging = False
            for w in words:
                text = w['text']
                
                # 當看到 "1." 開頭時開始記錄，看到 "2." 結束，這樣才不會印太多
                if text.strip() == '1.':
                    start_logging = True
                elif text.strip() == '2.':
                    break
                
                if start_logging:
                    # 為了方便閱讀，過濾掉太短的符號，除非它是項次
                    if len(text) > 1 or text.isdigit() or text == '.':
                        print(f"{text:<30} | {float(w['x0']):<10.2f} | {float(w['x1']):<10.2f} | {float(w['top']):.2f}")

    except Exception as e:
        print(f"錯誤: {e}")

if __name__ == "__main__":
    inspect_pdf_coordinates(file_path)