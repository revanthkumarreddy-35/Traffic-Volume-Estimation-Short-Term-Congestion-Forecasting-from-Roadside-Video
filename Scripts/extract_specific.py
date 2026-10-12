import fitz

pdf_path = "Technology domain-wise project usecases.pdf"
doc = fitz.open(pdf_path)

# Extract full content for specific pages
# Project 19 (pages 21-22), Project 38 (pages 39-41)
target_pages = list(range(21, 24)) + list(range(39, 43))

for p in target_pages:
    if p < len(doc):
        text = doc[p].get_text()
        print(f"\n{'='*80}")
        print(f"PAGE {p+1}")
        print(f"{'='*80}")
        print(text)

doc.close()
