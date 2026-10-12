import base64
import gzip
import json
import re
import sys

filepath = r'C:\Users\revan\.gemini\antigravity-ide\brain\8268e107-9d39-4b48-8eee-29f64a2abb93\.system_generated\steps\78\content.md'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Find ALL gzipped data blocks
pattern = r'const\s+(\w+)\s*=\s*"([A-Za-z0-9+/=]{100,})"'
matches = list(re.finditer(pattern, content))

print(f"Found {len(matches)} large data constants:")
for m in matches:
    name = m.group(1)
    data = m.group(2)
    print(f"  {name}: {len(data)} chars")

# Also search for GZIP patterns
gzip_pattern = r'(\w+_GZIP)\s*=\s*"([^"]+)"'
gzip_matches = list(re.finditer(gzip_pattern, content))
print(f"\nFound {len(gzip_matches)} GZIP data blocks:")
for m in gzip_matches:
    name = m.group(1)
    data = m.group(2)
    print(f"  {name}: {len(data)} chars")
    
    # Decompress each one
    try:
        compressed = base64.b64decode(data)
        decompressed = gzip.decompress(compressed)
        text = decompressed.decode('utf-8')
        print(f"    Decompressed: {len(text)} bytes")
        
        # Check if it contains traffic-related content
        if 'traffic' in text.lower():
            print(f"    *** CONTAINS 'traffic' ***")
            # Find and print traffic violation contexts
            text_lower = text.lower()
            for kw in ['traffic violation', 'traffic enforcement', 'violation detection', 'traffic']:
                pos = text_lower.find(kw)
                if pos != -1:
                    ctx_start = max(0, pos - 300)
                    ctx_end = min(len(text), pos + 500)
                    print(f"\n    Context for '{kw}':")
                    print(f"    {text[ctx_start:ctx_end]}")
                    break
        
        # Try parse as JSON to understand structure
        try:
            data_parsed = json.loads(text)
            if isinstance(data_parsed, dict):
                print(f"    JSON dict keys: {list(data_parsed.keys())[:10]}")
                # Check nested content
                for key in data_parsed:
                    val = data_parsed[key]
                    if isinstance(val, list) and len(val) > 0:
                        print(f"    {key}: list of {len(val)} items")
                        if isinstance(val[0], dict):
                            print(f"      First item keys: {list(val[0].keys())[:10]}")
                    elif isinstance(val, dict):
                        print(f"    {key}: dict with keys {list(val.keys())[:5]}")
            elif isinstance(data_parsed, list):
                print(f"    JSON list: {len(data_parsed)} items")
        except:
            print(f"    Not valid JSON")
            
    except Exception as e:
        print(f"    Error: {e}")

# Also look for inline project data that might not be gzipped
print("\n\nSearching for project title patterns in HTML...")
# Search for patterns like project titles in the raw HTML
for kw in ['traffic violation', 'Traffic Violation', 'violation enforcement', 'Violation Enforcement',
           'traffic monitoring', 'Traffic Monitoring', 'CCTV', 'vehicle detection']:
    pos = content.lower().find(kw.lower())
    if pos != -1:
        ctx_start = max(0, pos - 200)
        ctx_end = min(len(content), pos + 300)
        print(f"\nFound '{kw}' in HTML at position {pos}:")
        print(content[ctx_start:ctx_end])
