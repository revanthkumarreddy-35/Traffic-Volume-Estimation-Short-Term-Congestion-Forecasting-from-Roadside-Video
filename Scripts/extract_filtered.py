import fitz
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

pdf_path = r"C:\Users\revan\OneDrive\Documents\4th Year\Capstone-1\Documents\KL University Capstone Project Portal — Portfolio Intelligence, Reviews & 2,603 Project Systems.pdf"
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

with open(r"Scripts\filtered_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output))

print("Done! Written to filtered_results.txt")
