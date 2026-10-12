# =============================================================================
# CP-1 OBJECTIVE 1: Zindi-Style Traffic Congestion Classification
# =============================================================================
# Pipeline: Video → YOLO11 Detection → ByteTrack Tracking → Feature Engineering → XGBoost
#
# HOW TO USE IN GOOGLE COLAB:
# 1. Open Google Colab (colab.research.google.com)
# 2. Create a new notebook
# 3. Copy each "CELL" section below into a separate Colab code cell
# 4. Run them in order (Cell 1 → Cell 2 → Cell 3 → ...)
#
# IMPORTANT: Change runtime to T4 GPU before starting!
# (Runtime → Change runtime type → T4 GPU)
# =============================================================================


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 1: SETUP & INSTALLATION                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# --- Mount Google Drive ---
from google.colab import drive
drive.mount('/content/drive')

# --- Install required packages ---
!pip install -U "ultralytics>=8.3.0" "xgboost>=2.0.0" -q

# --- Verify GPU ---
import torch
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
else:
    print("⚠️ WARNING: No GPU detected! Go to Runtime → Change runtime type → T4 GPU")

# --- Import all libraries ---
import os
import cv2
import numpy as np
import pandas as pd
from glob import glob
from ultralytics import YOLO
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

print("\n✅ All packages installed and imported successfully!")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 2: DATA DISCOVERY                                                 ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# --- Define paths ---
# ⚠️ IMPORTANT: Update this path to match YOUR Google Drive folder structure!
DRIVE_BASE = "/content/drive/MyDrive/CP-1 Dataset"

# Camera folders
CAMERA_FOLDERS = {
    "camera1": os.path.join(DRIVE_BASE, "normanniles1"),
    "camera2": os.path.join(DRIVE_BASE, "normanniles2"),
    "camera3": os.path.join(DRIVE_BASE, "normanniles3"),
    "camera4": os.path.join(DRIVE_BASE, "normanniles4"),
    "added":   os.path.join(DRIVE_BASE, "added"),
}

# --- Discover all video files ---
all_videos = {}
total_count = 0

for cam_name, cam_path in CAMERA_FOLDERS.items():
    if os.path.exists(cam_path):
        # Search for mp4 files (also check inside subfolders)
        videos = glob(os.path.join(cam_path, "**", "*.mp4"), recursive=True)
        all_videos[cam_name] = sorted(videos)
        total_count += len(videos)
        print(f"📹 {cam_name}: {len(videos)} videos found")
    else:
        all_videos[cam_name] = []
        print(f"❌ {cam_name}: Folder not found at {cam_path}")

print(f"\n📊 Total videos discovered: {total_count}")

# --- Load Train.csv labels ---
# ⚠️ IMPORTANT: Make sure you uploaded Train.csv to your Google Drive!
train_csv_path = os.path.join(DRIVE_BASE, "CSV", "Train.csv")

if os.path.exists(train_csv_path):
    train_df = pd.read_csv(train_csv_path)
    print(f"\n✅ Train.csv loaded: {len(train_df)} rows, {len(train_df.columns)} columns")
    print(f"Columns: {list(train_df.columns)}")
    print(f"\nFirst 5 rows:")
    display(train_df.head())

    # Check label distribution
    if 'congestion_enter_rating' in train_df.columns:
        print(f"\n📊 Congestion Enter Rating Distribution:")
        print(train_df['congestion_enter_rating'].value_counts())
    if 'congestion_exit_rating' in train_df.columns:
        print(f"\n📊 Congestion Exit Rating Distribution:")
        print(train_df['congestion_exit_rating'].value_counts())
else:
    print(f"\n⚠️ Train.csv NOT FOUND at: {train_csv_path}")
    print("Please download Train.csv from Zindi and upload it to your Google Drive CP-1 Dataset folder")

# --- Load SampleSubmission.csv ---
sample_sub_path = os.path.join(DRIVE_BASE, "CSV", "SampleSubmission.csv")
if os.path.exists(sample_sub_path):
    sample_sub = pd.read_csv(sample_sub_path)
    print(f"\n✅ SampleSubmission.csv loaded: {len(sample_sub)} rows")
    print(f"Columns: {list(sample_sub.columns)}")
    display(sample_sub.head())
else:
    print(f"\n⚠️ SampleSubmission.csv NOT FOUND at: {sample_sub_path}")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 3: YOLO11 DETECTION — SINGLE VIDEO TEST                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# --- Load pre-trained YOLO11 model ---
model = YOLO("yolo11l.pt")  # large model for max accuracy
print("✅ YOLO11l model loaded successfully!")

# --- Define vehicle classes (COCO dataset class IDs) ---
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# --- Pick a test video ---
# Get the first available video from any camera
test_video = None
for cam_name, videos in all_videos.items():
    if len(videos) > 0:
        test_video = videos[0]
        print(f"🎬 Test video: {os.path.basename(test_video)} (from {cam_name})")
        break

if test_video is None:
    print("❌ No videos found! Check your Google Drive path.")
else:
    # --- Run YOLO11 detection on first frame ---
    cap = cv2.VideoCapture(test_video)
    ret, frame = cap.read()
    cap.release()

    if ret:
        # Run detection
        results = model(frame, verbose=False)
        result = results[0]

        # Filter for vehicles only
        vehicle_detections = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            if cls_id in VEHICLE_CLASSES:
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                vehicle_detections.append({
                    "class": VEHICLE_CLASSES[cls_id],
                    "confidence": round(conf, 3),
                    "bbox": [int(x1), int(y1), int(x2), int(y2)]
                })

        print(f"\n🚗 Vehicles detected in first frame: {len(vehicle_detections)}")
        for det in vehicle_detections:
            print(f"   {det['class']}: confidence={det['confidence']}")

        # --- Draw bounding boxes and display ---
        annotated_frame = result.plot()

        # Convert BGR to RGB for display in Colab
        from google.colab.patches import cv2_imshow
        print("\n📸 Annotated frame:")
        cv2_imshow(annotated_frame)
    else:
        print("❌ Could not read the test video!")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 4: YOLO11 + BYTETRACK TRACKING                                   ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

def process_video_with_tracking(video_path, model, max_frames=None, show_sample=False):
    """
    Process a single video with YOLO11 + ByteTrack tracking.
    Returns per-frame tracking data and video metadata.
    """
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if max_frames is None:
        max_frames = total_frames

    # Storage for tracking results
    frame_data = []
    unique_track_ids = set()
    class_track_ids = defaultdict(set)  # {class_name: set of track_ids}
    all_bbox_areas = []
    all_confidences = []
    sample_frame = None
    
    # Line counter state
    track_history = {} # track_id: previous_cy
    line_cross_counts = defaultdict(int) # class_name: count

    frame_idx = 0
    while cap.isOpened() and frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break

        # Run YOLO11 + ByteTrack tracking
        results = model.track(
            frame,
            persist=True,          # Keep track IDs across frames
            tracker="bytetrack.yaml",  # Use ByteTrack
            verbose=False,
            classes=list(VEHICLE_CLASSES.keys()),  # Only detect vehicles
            conf=0.25              # Confidence threshold
        )

        result = results[0]
        frame_vehicles = 0

        if result.boxes is not None and result.boxes.id is not None:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                track_id = int(box.id[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                bbox_area = (x2 - x1) * (y2 - y1)
                
                # Minimum area filter (pseudo-ROI) - ignores tiny background cars
                if bbox_area < 400:
                    continue

                if cls_id in VEHICLE_CLASSES:
                    cls_name = VEHICLE_CLASSES[cls_id]
                    unique_track_ids.add(track_id)
                    class_track_ids[cls_name].add(track_id)
                    all_bbox_areas.append(bbox_area)
                    all_confidences.append(conf)
                    frame_vehicles += 1
                    
                    # Line Crossing Logic
                    cy = (y1 + y2) / 2
                    crossing_line_y = height // 2
                    
                    if track_id in track_history:
                        prev_cy = track_history[track_id]
                        # Check if it crossed the line (top-down or bottom-up)
                        if (prev_cy < crossing_line_y and cy >= crossing_line_y) or \
                           (prev_cy > crossing_line_y and cy <= crossing_line_y):
                            line_cross_counts[cls_name] += 1
                    
                    track_history[track_id] = cy

        frame_data.append({
            "frame_idx": frame_idx,
            "vehicles_in_frame": frame_vehicles,
            "active_tracks": len(unique_track_ids)
        })

        # Save a sample annotated frame (middle of video)
        if show_sample and frame_idx == total_frames // 2:
            sample_frame = result.plot()

        frame_idx += 1

    cap.release()

    # Compute features
    duration_sec = frame_idx / fps if fps > 0 else 1
    features = {
        "filename": os.path.basename(video_path),
        "total_frames": frame_idx,
        "fps": fps,
        "duration_sec": round(duration_sec, 2),
        "resolution": f"{width}x{height}",

        # Vehicle counts (using line crossing instead of total tracks)
        "total_unique_vehicles": sum(line_cross_counts.values()),
        "car_count": line_cross_counts.get("car", 0),
        "truck_count": line_cross_counts.get("truck", 0),
        "bus_count": line_cross_counts.get("bus", 0),
        "motorcycle_count": line_cross_counts.get("motorcycle", 0),

        # Density & flow features
        "avg_vehicles_per_frame": round(np.mean([f["vehicles_in_frame"] for f in frame_data]), 3) if frame_data else 0,
        "max_vehicles_per_frame": max([f["vehicles_in_frame"] for f in frame_data]) if frame_data else 0,
        "flow_rate_per_min": round(sum(line_cross_counts.values()) / (duration_sec / 60), 3) if duration_sec > 0 else 0,

        # Detection quality features
        "avg_bbox_area": round(np.mean(all_bbox_areas), 2) if all_bbox_areas else 0,
        "avg_confidence": round(np.mean(all_confidences), 3) if all_confidences else 0,
        "std_bbox_area": round(np.std(all_bbox_areas), 2) if all_bbox_areas else 0,
    }

    return features, sample_frame


# --- Test tracking on one video ---
if test_video:
    print(f"🔄 Processing: {os.path.basename(test_video)}")
    print("   This may take 1-2 minutes...")

    features, sample = process_video_with_tracking(
        test_video, model, show_sample=True
    )

    print(f"\n✅ Tracking complete!")
    print(f"   📊 Features extracted:")
    for key, val in features.items():
        print(f"      {key}: {val}")

    if sample is not None:
        print(f"\n📸 Sample tracked frame (with Track IDs):")
        from google.colab.patches import cv2_imshow
        cv2_imshow(sample)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 5: BATCH PROCESSING — EXTRACT FEATURES FROM ALL VIDEOS            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# --- Parse video filename to extract camera and timestamp ---
def parse_video_filename(filename):
    """
    Parse filename like 'normanniles1_2025-10-26-14-09-45.mp4'
    Returns camera_id and timestamp string.
    """
    name = os.path.splitext(filename)[0]  # Remove .mp4
    parts = name.split("_", 1)
    camera_id = parts[0] if len(parts) > 0 else "unknown"
    timestamp_str = parts[1] if len(parts) > 1 else "unknown"
    return camera_id, timestamp_str


# --- Process videos in batches ---
def batch_process_videos(video_list, model, camera_name, max_videos=None):
    """
    Process multiple videos and extract features for each.
    """
    if max_videos:
        video_list = video_list[:max_videos]

    all_features = []
    total = len(video_list)

    for i, video_path in enumerate(video_list):
        filename = os.path.basename(video_path)
        print(f"   [{i+1}/{total}] Processing {filename}...", end=" ")

        try:
            features, _ = process_video_with_tracking(video_path, model)
            features["camera"] = camera_name
            camera_id, ts = parse_video_filename(filename)
            features["camera_id"] = camera_id
            features["timestamp"] = ts
            all_features.append(features)
            print(f"✅ {features['total_unique_vehicles']} vehicles")
        except Exception as e:
            print(f"❌ Error: {e}")

    return all_features


# --- Run batch processing ---
# ⚠️ IMPORTANT: Start with a small sample to test! Then increase max_videos.
MAX_VIDEOS_PER_CAMERA = 10  # Set to None to process ALL videos (will take hours)

print("=" * 60)
print("🚀 BATCH PROCESSING — Feature Extraction")
print("=" * 60)

all_features = []
for cam_name, videos in all_videos.items():
    if len(videos) == 0:
        continue
    print(f"\n📹 Camera: {cam_name} ({len(videos)} videos, processing {MAX_VIDEOS_PER_CAMERA or 'ALL'})")
    cam_features = batch_process_videos(videos, model, cam_name, max_videos=MAX_VIDEOS_PER_CAMERA)
    all_features.extend(cam_features)

# Convert to DataFrame
features_df = pd.DataFrame(all_features)
print(f"\n✅ Feature extraction complete!")
print(f"   Total videos processed: {len(features_df)}")
display(features_df.head(10))

# Save to Google Drive
features_csv_path = os.path.join(DRIVE_BASE, "extracted_features.csv")
features_df.to_csv(features_csv_path, index=False)
print(f"\n💾 Features saved to: {features_csv_path}")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 6: XGBOOST CONGESTION CLASSIFIER                                  ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, f1_score, accuracy_score
from sklearn.preprocessing import LabelEncoder

# --- Merge features with Train.csv labels ---
# ⚠️ You may need to adjust this merge logic based on the actual Train.csv column names
# The key is to match each video's features with its congestion label

if 'train_df' in dir() and train_df is not None:
    print("📋 Merging extracted features with Train.csv labels...")

    # Attempt to merge on filename
    # Adjust the merge key based on actual Train.csv structure
    merged_df = features_df.copy()

    # --- Define features and target ---
    feature_columns = [
        "total_unique_vehicles",
        "car_count", "truck_count", "bus_count", "motorcycle_count",
        "avg_vehicles_per_frame", "max_vehicles_per_frame",
        "flow_rate_per_min",
        "avg_bbox_area", "avg_confidence", "std_bbox_area"
    ]

    print(f"\n📊 Feature columns: {feature_columns}")
    print(f"   Total samples: {len(merged_df)}")

    # NOTE: The actual merge with labels depends on Train.csv structure.
    # After examining Train.csv in Cell 2, update this section accordingly.
    # For now, we prepare the feature matrix:

    X = merged_df[feature_columns].fillna(0)
    print(f"\n✅ Feature matrix X shape: {X.shape}")
    display(X.describe())

    # --- If labels are available, train the classifier ---
    # Uncomment and modify once you know the label column name:
    #
    # label_col = "congestion_enter_rating"  # or whatever the column is called
    # y_raw = merged_df[label_col]
    # le = LabelEncoder()
    # y = le.fit_transform(y_raw)
    # print(f"Classes: {le.classes_}")
    #
    # # Split data
    # X_train, X_test, y_train, y_test = train_test_split(
    #     X, y, test_size=0.2, random_state=42, stratify=y
    # )
    #
    # # Train XGBoost
    # xgb_model = xgb.XGBClassifier(
    #     n_estimators=200,
    #     max_depth=6,
    #     learning_rate=0.1,
    #     objective='multi:softmax',
    #     num_class=len(le.classes_),
    #     use_label_encoder=False,
    #     eval_metric='mlogloss',
    #     random_state=42,
    #     tree_method='gpu_hist'  # Use GPU for faster training
    # )
    #
    # xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=10)
    #
    # # Evaluate
    # y_pred = xgb_model.predict(X_test)
    # print("\n📊 Classification Report:")
    # print(classification_report(y_test, y_pred, target_names=le.classes_))
    #
    # # Zindi scoring: Macro-F1 (70%) + Accuracy (30%)
    # macro_f1 = f1_score(y_test, y_pred, average='macro')
    # acc = accuracy_score(y_test, y_pred)
    # zindi_score = 0.7 * macro_f1 + 0.3 * acc
    # print(f"\n🏆 Zindi Score: {zindi_score:.4f}")
    # print(f"   Macro-F1: {macro_f1:.4f} (70% weight)")
    # print(f"   Accuracy: {acc:.4f} (30% weight)")

else:
    print("⚠️ Train.csv not loaded. Please upload it to your Google Drive.")
    print("   You can still use the extracted features for analysis!")


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CELL 7: VISUALIZATION & RESULTS                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

import matplotlib.pyplot as plt

# --- 1. Vehicle Count Distribution ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Total vehicles per video
axes[0, 0].hist(features_df["total_unique_vehicles"], bins=20, color="#4CAF50", edgecolor="white")
axes[0, 0].set_title("Distribution of Total Vehicles per Video", fontweight="bold")
axes[0, 0].set_xlabel("Total Unique Vehicles")
axes[0, 0].set_ylabel("Frequency")

# Vehicle type breakdown
vehicle_types = ["car_count", "truck_count", "bus_count", "motorcycle_count"]
type_means = features_df[vehicle_types].mean()
colors = ["#2196F3", "#FF9800", "#9C27B0", "#F44336"]
axes[0, 1].bar(["Car", "Truck", "Bus", "Motorcycle"], type_means, color=colors, edgecolor="white")
axes[0, 1].set_title("Average Vehicle Count by Type", fontweight="bold")
axes[0, 1].set_ylabel("Average Count")

# Flow rate per camera
if "camera" in features_df.columns:
    camera_flow = features_df.groupby("camera")["flow_rate_per_min"].mean()
    axes[1, 0].bar(camera_flow.index, camera_flow.values, color="#FF5722", edgecolor="white")
    axes[1, 0].set_title("Average Flow Rate by Camera", fontweight="bold")
    axes[1, 0].set_ylabel("Vehicles / Minute")
    axes[1, 0].tick_params(axis="x", rotation=45)

# Average confidence by camera
if "camera" in features_df.columns:
    camera_conf = features_df.groupby("camera")["avg_confidence"].mean()
    axes[1, 1].bar(camera_conf.index, camera_conf.values, color="#673AB7", edgecolor="white")
    axes[1, 1].set_title("Average Detection Confidence by Camera", fontweight="bold")
    axes[1, 1].set_ylabel("Confidence")
    axes[1, 1].tick_params(axis="x", rotation=45)

plt.tight_layout()
plt.savefig(os.path.join(DRIVE_BASE, "vehicle_analysis_charts.png"), dpi=150, bbox_inches="tight")
plt.show()
print("💾 Charts saved to Google Drive!")

# --- 2. Feature Correlation Heatmap ---
fig, ax = plt.subplots(figsize=(12, 8))
corr_cols = [
    "total_unique_vehicles", "car_count", "truck_count",
    "avg_vehicles_per_frame", "flow_rate_per_min",
    "avg_bbox_area", "avg_confidence"
]
corr_matrix = features_df[corr_cols].corr()

im = ax.imshow(corr_matrix, cmap="RdYlBu_r", aspect="auto", vmin=-1, vmax=1)
ax.set_xticks(range(len(corr_cols)))
ax.set_yticks(range(len(corr_cols)))
ax.set_xticklabels(corr_cols, rotation=45, ha="right", fontsize=9)
ax.set_yticklabels(corr_cols, fontsize=9)

# Add correlation values
for i in range(len(corr_cols)):
    for j in range(len(corr_cols)):
        text = ax.text(j, i, f"{corr_matrix.iloc[i, j]:.2f}",
                      ha="center", va="center", color="black", fontsize=8)

plt.colorbar(im)
plt.title("Feature Correlation Heatmap", fontweight="bold", fontsize=14)
plt.tight_layout()
plt.savefig(os.path.join(DRIVE_BASE, "correlation_heatmap.png"), dpi=150, bbox_inches="tight")
plt.show()

print("\n" + "=" * 60)
print("🎉 CP-1 OBJECTIVE 1 — PIPELINE COMPLETE!")
print("=" * 60)
print(f"   Videos processed: {len(features_df)}")
print(f"   Features extracted: {len(feature_columns)} per video")
print(f"   Results saved to: {DRIVE_BASE}")
print("\n📌 Next steps:")
print("   1. Upload Train.csv to merge labels with features")
print("   2. Uncomment the XGBoost training code in Cell 6")
print("   3. Increase MAX_VIDEOS_PER_CAMERA to process more data")
print("   4. Submit predictions to Zindi!")
