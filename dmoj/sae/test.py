import json
import time
from analyzer.metrics import analyze_code

def main():
    file_name = "test.txt"
    test_lang = "cpp" 

    try:
        with open(file_name, "r", encoding="utf-8") as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error! File '{file_name}' is not found!")
        return

    print(f"Static analisis for: {test_lang.upper()}...")
    
    start_time = time.perf_counter()
    
    try:
        metrics = analyze_code(source_code, test_lang)
        
        calc_time = time.perf_counter() - start_time
        
        print("\nAnalisis ended")
        print(f"Analisis time: {calc_time:.5f} sec.\n")
        
        print("Metrics:")
        print(json.dumps(metrics, indent=4, ensure_ascii=False))
        
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()