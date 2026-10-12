import base64
import gzip
import json
import re
import sys

# Read the HTML file
filepath = r'C:\Users\revan\.gemini\antigravity-ide\brain\8268e107-9d39-4b48-8eee-29f64a2abb93\.system_generated\steps\78\content.md'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the gzipped data
match = re.search(r'const DATA_BASE_GZIP="([^"]+)"', content)
if not match:
    print("Could not find DATA_BASE_GZIP")
    sys.exit(1)

b64_data = match.group(1)
print(f"Found base64 data, length: {len(b64_data)}")

# Decode and decompress
compressed = base64.b64decode(b64_data)
print(f"Compressed size: {len(compressed)} bytes")

decompressed = gzip.decompress(compressed)
print(f"Decompressed size: {len(decompressed)} bytes")

text = decompressed.decode('utf-8')

# Save the full decompressed data
with open('decompressed_data.txt', 'w', encoding='utf-8') as f:
    f.write(text[:500000])  # First 500K chars for analysis

# Try to parse as JSON
try:
    data = json.loads(text)
    print(f"\nParsed as JSON. Type: {type(data)}")
    if isinstance(data, list):
        print(f"Number of items: {len(data)}")
        if len(data) > 0:
            print(f"\nFirst item keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'not a dict'}")
            print(f"\nFirst item preview:")
            print(json.dumps(data[0], indent=2, ensure_ascii=False)[:2000])
    elif isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
except json.JSONDecodeError:
    print("Not valid JSON, showing first 2000 chars:")
    print(text[:2000])

# Now search for traffic violation related projects
print("\n\n" + "="*80)
print("SEARCHING FOR TRAFFIC VIOLATION RELATED PROJECTS")
print("="*80)

keywords = ['traffic violation', 'traffic enforcement', 'violation detection', 
            'violation enforcement', 'urban traffic', 'traffic monitoring',
            'traffic safety', 'vehicle detection', 'CCTV']

text_lower = text.lower()
for kw in keywords:
    positions = []
    start = 0
    while True:
        pos = text_lower.find(kw, start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1
    if positions:
        print(f"\n'{kw}' found {len(positions)} times")
        for p in positions[:3]:
            context_start = max(0, p - 200)
            context_end = min(len(text), p + 300)
            print(f"  ...{text[context_start:context_end]}...")
            print()
