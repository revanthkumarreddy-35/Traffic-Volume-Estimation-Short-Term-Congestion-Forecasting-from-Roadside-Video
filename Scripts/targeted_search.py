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

match = re.search(r'USE_CASE_CORE_GZIP="([^"]+)"', content)
b64_data = match.group(1)
compressed = base64.b64decode(b64_data)
decompressed = gzip.decompress(compressed)
text = decompressed.decode('utf-8')
data = json.loads(text)

print(f"Total projects: {len(data)}")

# Search specifically for traffic-related projects under AI/Visual Intelligence specialization
print("\n" + "="*80)
print("ALL PROJECTS WITH 'traffic' IN TITLE OR DESCRIPTION")
print("="*80)

for item in data:
    title = item.get('title', '').lower()
    impact = item.get('impact', '').lower()
    dom = item.get('dom', '').lower()
    item_json = json.dumps(item).lower()
    
    if 'traffic' in title or 'traffic' in impact or ('traffic' in item_json and ('vehicle' in item_json or 'detect' in item_json or 'cctv' in item_json or 'surveillance' in item_json)):
        specs = [s['name'] for s in item.get('specializations', [])]
        print(f"\n  ID: {item['id']}")
        print(f"  Title: {item['title']}")
        print(f"  Domain: {item.get('dom', 'N/A')}")
        print(f"  Specializations: {specs}")
        print(f"  Source: {item.get('org', 'N/A')}")
        print(f"  URL: {item.get('url', 'N/A')}")
        print(f"  Impact: {item.get('impact', 'N/A')[:300]}")
        print()

# Also search for Visual Intelligence specialization projects with object detection
print("\n" + "="*80)
print("AI SYSTEMS FOR VISUAL INTELLIGENCE PROJECTS WITH OBJECT DETECTION / YOLO / CCTV / VEHICLE")
print("="*80)

vi_keywords = ['object detection', 'yolo', 'vehicle detection', 'cctv', 'surveillance',
               'traffic', 'pedestrian', 'license plate', 'anomaly detection video',
               'real-time detection', 'video analytics', 'image classification']

count = 0
for item in data:
    specs = [s['name'] for s in item.get('specializations', [])]
    is_vi = any('visual intelligence' in s.lower() for s in specs)
    
    if is_vi:
        item_text = json.dumps(item).lower()
        matched_kws = [kw for kw in vi_keywords if kw in item_text]
        
        if matched_kws:
            count += 1
            print(f"\n  #{count} | ID: {item['id']}")
            print(f"  Title: {item['title']}")
            print(f"  Domain: {item.get('dom', 'N/A')}")
            print(f"  Matched Keywords: {matched_kws}")
            print(f"  Source: {item.get('org', 'N/A')}")
            print(f"  URL: {item.get('url', 'N/A')}")
            print(f"  Stack: {item.get('stack', [])}")
            print(f"  Impact: {item.get('impact', 'N/A')[:400]}")
            # Print specializations
            for s in item.get('specializations', []):
                primary = "PRIMARY" if s.get('primary') else "Related"
                print(f"  Spec [{primary}]: {s['name']}")
            print()

print(f"\nTotal Visual Intelligence projects with detection keywords: {count}")
