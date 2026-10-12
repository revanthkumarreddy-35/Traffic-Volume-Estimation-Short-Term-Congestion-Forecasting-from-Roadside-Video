import fitz
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

pdf_path = r"C:\Users\revan\OneDrive\Documents\4th Year\Capstone-1\Documents\DSCI-41_Traffic_Volume_Estimation_and_Short-Term_Congestion_Forecasting_from_Roadside_Video.pdf"

try:
    doc = fitz.open(pdf_path)
    output = []
    output.append(f"Total pages: {len(doc)}")
    output.append("="*80)

    for i in range(len(doc)):
        text = doc[i].get_text()
        if text.strip():
            output.append(f"\n--- PAGE {i+1} ---")
            output.append(text)

    doc.close()

    with open(r"C:\Users\revan\OneDrive\Documents\4th Year\Capstone-1\Scripts\dsci41_details.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output))

    print("Success: Written to Scripts/dsci41_details.txt")
except Exception as e:
    print(f"Error reading PDF: {e}")
