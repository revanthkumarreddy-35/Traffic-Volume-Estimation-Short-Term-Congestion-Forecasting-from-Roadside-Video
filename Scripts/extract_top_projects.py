import fitz

pdf_path = "Technology domain-wise project usecases.pdf"
doc = fitz.open(pdf_path)

# Extract full project descriptions for the most relevant AI Visual Intelligence projects
# Focus on projects with computer vision, object detection, deep learning, CNN, YOLO

# Key pages to extract full content from:
# AI domain: pages 3-347 (Artificial Intelligence section)
# AI & Autonomous Systems: pages 1237-1287

# Let's do a smarter search: find complete project blocks that heavily use CV/DL
target_keywords = [
    "object detection", "image classification", "computer vision", "cnn",
    "yolo", "image segmentation", "face detection", "face recognition",
    "pose estimation", "video analysis", "surveillance", "medical imaging",
    "defect detection", "ocr", "sign language", "emotion detection",
    "skin disease", "plant disease", "image super resolution",
    "image captioning", "vision transformer", "deep learning",
    "image recognition", "semantic segmentation", "real-time detection",
    "vehicle detection", "pedestrian detection", "drone", "satellite imagery",
    "x-ray", "retinal", "food recognition", "gesture recognition",
    "action recognition", "depth estimation", "scene understanding"
]

# Scan in chunks and find project titles + their full descriptions
projects = []
current_project = None
project_text = ""

for i in range(len(doc)):
    text = doc[i].get_text()
    lines = text.strip().split('\n')
    
    for line in lines:
        stripped = line.strip()
        # Detect project title pattern: "N. Project Title"
        import re
        title_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        
        if title_match and len(stripped) > 10 and len(stripped) < 200:
            # Save previous project if it had relevant keywords
            if current_project and project_text:
                text_lower = project_text.lower()
                score = sum(1 for kw in target_keywords if kw in text_lower)
                if score >= 2:  # At least 2 relevant keywords
                    projects.append({
                        'title': current_project,
                        'page': current_page,
                        'score': score,
                        'text': project_text
                    })
            
            current_project = stripped
            current_page = i + 1
            project_text = stripped + "\n"
        else:
            if current_project:
                project_text += line + "\n"

# Don't forget last project
if current_project and project_text:
    text_lower = project_text.lower()
    score = sum(1 for kw in target_keywords if kw in text_lower)
    if score >= 2:
        projects.append({
            'title': current_project,
            'page': current_page,
            'score': score,
            'text': project_text
        })

# Sort by relevance score
projects.sort(key=lambda x: x['score'], reverse=True)

print(f"Found {len(projects)} highly relevant projects for Visual Intelligence\n")
print("="*100)

# Print top 25 most relevant projects with full details
for idx, proj in enumerate(projects[:25]):
    print(f"\n{'='*100}")
    print(f"RANK #{idx+1} | RELEVANCE SCORE: {proj['score']} | PAGE: {proj['page']}")
    print(f"{'='*100}")
    # Print full project text (trimmed to reasonable length)
    text_lines = proj['text'].split('\n')
    for line in text_lines[:40]:  # First 40 lines
        print(line)
    if len(text_lines) > 40:
        print("... [truncated]")
    print()

doc.close()
