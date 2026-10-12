import base64
import gzip
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

filepath = r'C:\Users\revan\.gemini\antigravity-ide\brain\8268e107-9d39-4b48-8eee-29f64a2abb93\.system_generated\steps\78\content.md'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract USE_CASE_CORE_GZIP
match = re.search(r'USE_CASE_CORE_GZIP="([^"]+)"', content)
if not match:
    print("Could not find USE_CASE_CORE_GZIP")
    sys.exit(1)

b64_data = match.group(1)
compressed = base64.b64decode(b64_data)
decompressed = gzip.decompress(compressed)
text = decompressed.decode('utf-8')

print(f"Decompressed size: {len(text)} bytes")

# Parse as JSON
data = json.loads(text)
print(f"Type: {type(data)}")

if isinstance(data, list):
    print(f"Total projects: {len(data)}")
    if len(data) > 0 and isinstance(data[0], dict):
        print(f"Keys: {list(data[0].keys())}")
elif isinstance(data, dict):
    print(f"Keys: {list(data.keys())[:20]}")

# Search for traffic violation projects
results = []

def search_in_obj(obj, path=""):
    """Recursively search for traffic violation content"""
    if isinstance(obj, str):
        lower = obj.lower()
        if 'traffic violation' in lower or 'violation enforcement' in lower or 'violation detection' in lower:
            return True
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if search_in_obj(v, f"{path}.{k}"):
                return True
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if search_in_obj(item, f"{path}[{i}]"):
                return True
    return False

# Find projects with traffic violation content
if isinstance(data, list):
    for idx, item in enumerate(data):
        if search_in_obj(item):
            results.append((idx, item))
elif isinstance(data, dict):
    for key, val in data.items():
        if isinstance(val, list):
            for idx, item in enumerate(val):
                if search_in_obj(item):
                    results.append((key, idx, item))
        elif isinstance(val, dict):
            if search_in_obj(val):
                results.append((key, val))

print(f"\n{'='*80}")
print(f"FOUND {len(results)} MATCHING PROJECTS")
print(f"{'='*80}")

for r in results:
    with open(r'Scripts\traffic_project_found.txt', 'w', encoding='utf-8') as f:
        f.write(json.dumps(r[-1], indent=2, ensure_ascii=False))
    print(json.dumps(r[-1], indent=2, ensure_ascii=False)[:5000])
    print("\n---\n")

# Also search more broadly for traffic + detection/enforcement
print("\n\nBROADER SEARCH: Projects with 'traffic' in title/description")
print("="*80)
broader = []

def get_title(obj):
    if isinstance(obj, dict):
        for k in ['title', 'name', 'projectTitle', 'useCase', 'id']:
            if k in obj:
                return str(obj[k])
    return ""

def has_traffic_keyword(obj):
    text = json.dumps(obj).lower()
    return 'traffic' in text and ('detect' in text or 'enforce' in text or 'violat' in text or 'vehicle' in text or 'cctv' in text)

if isinstance(data, list):
    for idx, item in enumerate(data):
        if has_traffic_keyword(item):
            title = get_title(item)
            broader.append((idx, title, item))
elif isinstance(data, dict):
    for key, val in data.items():
        if isinstance(val, dict) and has_traffic_keyword(val):
            title = get_title(val)
            broader.append((key, title, val))

print(f"Found {len(broader)} projects")
for b in broader[:10]:
    item = b[-1]
    title = b[1] if len(b) > 2 else b[0]
    print(f"\n  ID/Key: {b[0]}")
    print(f"  Title: {title}")
    # Print first 1000 chars
    print(f"  Preview: {json.dumps(item, ensure_ascii=False)[:1000]}")
    print()
