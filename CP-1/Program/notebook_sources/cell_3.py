# --- Project configuration (Google Colab) ---
DRIVE_BASE = "/content/drive/MyDrive/CP-1 Dataset"
YOLO_MODEL_NAME = "yolo11l.pt"  # Pretrained COCO detector; not trained on this dataset.
RESUME_FEATURE_EXTRACTION = True  # Completed clips only; partial tracker state is not recoverable.
FEATURES_CSV_PATH = os.path.join(DRIVE_BASE, "extracted_features_yolo11_v2.csv")
ANNOTATION_DIR = os.path.join(DRIVE_BASE, "annotated_samples_v2")
RUN_LOG_DIR = os.path.join(DRIVE_BASE, "crossing_logs_v2")
JOURNAL_EXPORT_DIR = os.path.join(DRIVE_BASE, "Journal_Results_Export_v2")
TRAIN_CSV_PATH = os.path.join(DRIVE_BASE, "CSV", "Train.csv")
SAMPLE_SUBMISSION_PATH = os.path.join(DRIVE_BASE, "CSV", "SampleSubmission.csv")
TRACKER_CONFIG_PATH = "custom_bytetrack.yaml"

# Source clips are sampled by their *next* labeled time segment. These defaults
# select up to 3 training and 2 held-out clips per camera and future class.
TRAIN_CLIPS_PER_CAMERA_CLASS = 3
TEST_CLIPS_PER_CAMERA_CLASS = 2
TEST_DATES = {"2025-10-25", "2025-10-26"}
RANDOM_SEED = 42
MAX_UNLABELED_VIDEOS_PER_CAMERA = 0  # Set >0 only for a separate exploratory run.

VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
COUNTING_LINES = {
    "default": ((0.05, 0.50), (0.95, 0.50)),
    # Calibrate each line against an annotated frame before comparing cameras.
    # "normanniles1": ((0.05, 0.52), (0.95, 0.52)),
}
CAMERA_FOLDERS = {
    "camera1": os.path.join(DRIVE_BASE, "normanniles1"),
    "camera2": os.path.join(DRIVE_BASE, "normanniles2"),
    "camera3": os.path.join(DRIVE_BASE, "normanniles3"),
    "camera4": os.path.join(DRIVE_BASE, "normanniles4"),
    "added": os.path.join(DRIVE_BASE, "added"),
}
for directory in (ANNOTATION_DIR, RUN_LOG_DIR, JOURNAL_EXPORT_DIR):
    os.makedirs(directory, exist_ok=True)

def make_video_key(video_path):
    """Return the Train.csv-compatible relative path."""
    rel_path = os.path.relpath(video_path, DRIVE_BASE).replace("\\", "/")
    return os.path.basename(video_path) if rel_path.startswith("..") else rel_path

all_videos = {}
for cam_name, cam_path in CAMERA_FOLDERS.items():
    all_videos[cam_name] = sorted(glob(os.path.join(cam_path, "**", "*.mp4"), recursive=True)) if os.path.isdir(cam_path) else []
    print(f"{cam_name}: {len(all_videos[cam_name])} videos")
print(f"Total videos: {sum(map(len, all_videos.values()))}; model: {YOLO_MODEL_NAME}")
print(f"New feature output (old CSV retained): {FEATURES_CSV_PATH}")

train_df = pd.read_csv(TRAIN_CSV_PATH) if os.path.isfile(TRAIN_CSV_PATH) else None
sample_sub = pd.read_csv(SAMPLE_SUBMISSION_PATH) if os.path.isfile(SAMPLE_SUBMISSION_PATH) else None
print(f"Train labels: {len(train_df) if train_df is not None else 'not found'}")
if train_df is not None:
    display(train_df.head())
