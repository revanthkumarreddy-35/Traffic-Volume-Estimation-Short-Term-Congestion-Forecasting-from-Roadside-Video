import fitz
import re

pdf_path = "Technology domain-wise project usecases.pdf"
doc = fitz.open(pdf_path)

print(f"Total pages: {len(doc)}")
print("="*80)

# Keywords related to AI Visual Intelligence, Deep Learning, Object Detection
keywords = [
    "object detection", "image classification", "computer vision",
    "deep learning", "convolutional neural network", "cnn",
    "image segmentation", "visual", "yolo", "resnet", "image recognition",
    "face detection", "face recognition", "pose estimation",
    "autonomous", "video analysis", "surveillance", "medical imaging",
    "defect detection", "anomaly detection", "ocr", "optical character",
    "scene understanding", "action recognition", "gesture recognition",
    "image generation", "gan", "generative", "visual intelligence",
    "neural network", "transfer learning", "feature extraction",
    "semantic segmentation", "instance segmentation", "panoptic",
    "real-time detection", "traffic", "vehicle detection", "pedestrian",
    "drone", "satellite", "remote sensing", "agricultural",
    "skin disease", "retinal", "x-ray", "ct scan", "mri",
    "food recognition", "plant disease", "wildlife", "species",
    "sign language", "emotion detection", "facial expression",
    "depth estimation", "3d reconstruction", "point cloud",
    "image super resolution", "image enhancement", "denoising",
    "visual question answering", "image captioning", "vision transformer",
    "vit", "attention mechanism"
]

# First, let's understand the structure - extract table of contents / domain headers
print("\n--- SCANNING FOR DOMAIN HEADERS AND STRUCTURE ---\n")

# Look at first 30 pages for TOC/structure
for i in range(min(30, len(doc))):
    text = doc[i].get_text()
    if text.strip():
        # Look for domain/category headers
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if len(line) > 5 and len(line) < 150:
                # Check if it looks like a header (all caps, or numbered section)
                if (line.isupper() or 
                    re.match(r'^\d+[\.\)]\s', line) or
                    'domain' in line.lower() or
                    'project' in line.lower() or
                    'technology' in line.lower() or
                    'use case' in line.lower() or
                    'usecase' in line.lower()):
                    print(f"  Page {i+1}: {line[:120]}")

print("\n" + "="*80)
print("\n--- SEARCHING FOR AI/VISUAL INTELLIGENCE PROJECTS ---\n")

# Now search all pages for keyword matches
matched_sections = []
current_section = ""
current_page = 0

for i in range(len(doc)):
    text = doc[i].get_text().lower()
    
    # Check if any keyword matches
    matches = [kw for kw in keywords if kw in text]
    
    if matches:
        full_text = doc[i].get_text()
        # Extract meaningful content
        lines = full_text.strip().split('\n')
        
        # Look for project titles, use cases, objectives
        for j, line in enumerate(lines):
            line_lower = line.strip().lower()
            # Check if this line contains relevant keywords
            line_matches = [kw for kw in keywords if kw in line_lower]
            if line_matches and len(line.strip()) > 15:
                # Get context (surrounding lines)
                start = max(0, j-2)
                end = min(len(lines), j+5)
                context = '\n'.join(lines[start:end])
                matched_sections.append({
                    'page': i+1,
                    'keywords': line_matches,
                    'line': line.strip(),
                    'context': context
                })

# Deduplicate and print top results
seen = set()
count = 0
for section in matched_sections:
    key = section['line'][:80]
    if key not in seen and count < 150:
        seen.add(key)
        print(f"Page {section['page']} | Keywords: {', '.join(section['keywords'][:3])}")
        print(f"  >> {section['line'][:200]}")
        print(f"  Context:")
        for ctx_line in section['context'].split('\n'):
            print(f"     {ctx_line[:200]}")
        print()
        count += 1

print(f"\nTotal unique matches found: {len(seen)}")
doc.close()
