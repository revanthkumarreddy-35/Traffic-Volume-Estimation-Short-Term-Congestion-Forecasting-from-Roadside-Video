"""Create an unexecuted YOLOv8 notebook without modifying the YOLO11 notebook."""
import ast
import copy
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "CP-1/Program/CP1_Vehicle_Counter_yolov11.ipynb"
TARGET = SOURCE.with_name("CP1_Vehicle_Counter_yolov8.ipynb")
REFERENCE = ROOT / "CP-1/Journal_Results_Export_v2-20261020T090346Z-1-001.zip"

INTRO = """# CP-1: YOLOv8l comparison run

Run all cells in order in **Google Colab with a GPU**, using the same
`/content/drive/MyDrive/CP-1 Dataset` folder as your YOLO11 run.
This notebook uses pretrained `yolov8l.pt`; it does not train the detector.
Model reference: https://docs.ultralytics.com/models/yolov8/

The exact 80 source clips, future labels and 48/32 date split from your supplied
YOLO11 v2 export are embedded below. No additional CSV upload is needed.
Keep the counting lines, thresholds, inference sizes, tracker and XGBoost
settings unchanged for the comparison. Large variants are not parameter-matched.
Package versions/hardware may differ from the historical run; this is not a
controlled runtime benchmark.

All generated files use YOLOv8-specific locations; YOLO11 results are untouched.
Completed YOLOv8 clips can resume after a disconnect. Run cells from the top
after reconnecting. Do not change settings while reusing a checkpoint.
Cell 6 requires all 80 clips before scoring. The final cell creates
`Journal_Results_Export_yolov8_v2.zip` in your dataset folder.

Counts and confidence scores are not detection accuracy. mAP, MOTA and count
RMSE still require manual ground truth. The XGBoost evaluation measures
next-segment congestion classification, not detector accuracy.
"""

LOCK_SELECTION = '''
# Exact reference selection embedded from the completed YOLO11 export.
from io import StringIO
selected_pairs = pd.read_csv(StringIO(REFERENCE_PAIRS_CSV))
if len(selected_pairs) != 80 or selected_pairs["videos"].duplicated().any():
    raise ValueError("Invalid reference selection; expected 80 unique clips.")
missing_videos = sorted(set(selected_pairs["videos"]) - set(available_videos))
if missing_videos:
    raise FileNotFoundError(
        f"{len(missing_videos)} reference clips are missing from Drive. "
        f"Restore them before comparing models. First missing: {missing_videos[:5]}"
    )
current_pairs = prepare_next_segment_labels(train_df, set(available_videos))
check_columns = ["videos", "target_video_path", "next_enter_rating",
                 "congestion_enter_rating", "split", "source_time", "target_time"]
expected = selected_pairs.set_index("videos")[check_columns[1:]].astype(str)
actual = current_pairs.set_index("videos").reindex(expected.index)[check_columns[1:]].astype(str)
if not expected.equals(actual):
    raise ValueError("Train.csv labels or split differ from the reference YOLO11 run.")
'''

COMPLETENESS_CHECK = '''
# Never silently score a partial run or reuse another detector's checkpoint.
missing_keys = sorted(set(selected_keys) - set(features_df.get("video_path", [])))
if missing_keys:
    raise RuntimeError(
        f"{len(missing_keys)} selected clips are incomplete. Rerun Cell 6 before "
        f"exporting comparison results. First missing: {missing_keys[:5]}"
    )
'''

FINAL_CELL = '''
# --- Complete batch summaries, readable classification matrix and portable ZIP ---
import importlib.metadata
import json
import platform
import shutil
import sys
import zipfile
import matplotlib.pyplot as plt
from datetime import datetime, timezone

expected_keys = set(selected_pairs["videos"])
if (len(expected_keys) != 80 or set(labeled_features_df["video_path"]) != expected_keys
        or "xgb_model" not in globals()):
    raise RuntimeError("Finish all 80 clips and the evaluation in Cell 6 first.")
export_path = Path(JOURNAL_EXPORT_DIR)
shutil.copy2(FEATURES_CSV_PATH, export_path / Path(FEATURES_CSV_PATH).name)
batch = labeled_features_df
camera_summary = batch.groupby("camera_id").agg(
    clips=("video_path", "size"), frames=("total_frames", "sum"),
    duration_sec=("duration_sec", "sum"),
    entering=("entering_count", "sum"), exiting=("exiting_count", "sum"),
    hard_count=("total_unique_vehicles", "sum"), soft_count=("soft_count", "sum"),
)
camera_summary.to_csv(export_path / "camera_summary.csv")
display(camera_summary)
class_counts = batch[[f"{name}_count" for name in VEHICLE_CLASSES.values()]].sum()
class_counts.rename("predicted_crossings").to_csv(export_path / "batch_vehicle_class_counts.csv")
batch.groupby(["split", "next_enter_rating"]).agg(
    clips=("video_path", "size"), hard_count=("total_unique_vehicles", "sum"),
    soft_count=("soft_count", "sum"),
).to_csv(export_path / "future_class_summary.csv")

labels = list(encoder.classes_)
matrix = confusion_matrix(y_test, y_pred, labels=range(len(labels)))
pd.DataFrame(matrix, index=labels, columns=labels).to_csv(
    export_path / "next_segment_confusion_matrix.csv", index_label="true_label"
)
pd.DataFrame(classification_report(
    y_test, y_pred, labels=range(len(labels)), target_names=labels,
    zero_division=0, output_dict=True
)).T.to_csv(export_path / "next_segment_classification_report.csv")
fig, ax = plt.subplots(figsize=(9, 7))
im = ax.imshow(matrix, cmap="Blues")
for row in range(len(labels)):
    for col in range(len(labels)):
        r, g, b, _ = im.cmap(im.norm(matrix[row, col]))
        color = "black" if 0.2126*r + 0.7152*g + 0.0722*b > 0.5 else "white"
        ax.text(col, row, str(matrix[row, col]), ha="center", va="center",
                color=color, fontsize=16, fontweight="bold")
ax.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
ax.set_yticks(range(len(labels)), labels)
ax.set_xlabel("Predicted future congestion")
ax.set_ylabel("True future congestion")
ax.set_title("YOLOv8 features + XGBoost: held-out next-segment classification")
fig.colorbar(im, ax=ax, label="Clips")
fig.tight_layout()
fig.savefig(export_path / "next_segment_confusion_matrix.png", dpi=300)
plt.show()

versions = {}
for package in ("ultralytics", "torch", "torchvision", "numpy", "pandas",
                "xgboost", "scikit-learn", "opencv-python"):
    try:
        versions[package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        versions[package] = "not installed under this package name"
manifest = {
    "model": YOLO_MODEL_NAME, "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "reference_selection_sha256": REFERENCE_SELECTION_SHA256,
    "reference_export": REFERENCE_EXPORT_NAME, "clips": len(batch),
    "train_n": len(train_rows), "test_n": len(test_rows),
    "hard_count": int(batch["total_unique_vehicles"].sum()),
    "soft_count": float(batch["soft_count"].sum()),
    "tracker": custom_config, "counting_lines": COUNTING_LINES,
    "random_seed": RANDOM_SEED, "packages": versions,
    "python": sys.version, "platform": platform.platform(),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
    "limitations": [
        "Counts/confidences are not accuracy; no manual vehicle ground truth.",
        "Historical YOLO11 software/hardware equality is not independently verified.",
        "Large detector variants have different parameter counts.",
        "Balanced 80-clip pilot; not population-wide performance.",
    ],
}
(export_path / "run_summary.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
archive_path = Path(DRIVE_BASE) / "Journal_Results_Export_yolov8_v2.zip"
# Include per-clip settings/crossings. Large per-frame logs remain in Drive.
with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
    for file in sorted(export_path.rglob("*")):
        if file.is_file():
            archive.write(file, str(Path(export_path.name) / file.relative_to(export_path)))
    for pattern in ("*_manifest.json", "*_crossings.csv"):
        for file in sorted(Path(RUN_LOG_DIR).glob(pattern)):
            archive.write(file, str(Path(export_path.name) / "crossing_logs" / file.name))
print(f"Complete: {len(batch)} clips. Share this ZIP for the YOLOv8/YOLO11 comparison:")
print(archive_path)
print("Per-frame observation logs remain in:", RUN_LOG_DIR)
# Optional browser download (the archive is already saved in Drive):
# from google.colab import files
# files.download(str(archive_path))
'''


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Expected exactly one source anchor: {old[:90]!r}")
    return source.replace(old, new, 1)


def build():
    notebook = copy.deepcopy(json.loads(SOURCE.read_text(encoding="utf-8")))
    with zipfile.ZipFile(REFERENCE) as archive:
        candidates = [name for name in archive.namelist()
                      if name.endswith("/selected_next_segment_pairs.csv")]
        if len(candidates) != 1:
            raise ValueError("Expected one reference selection CSV")
        reference_bytes = archive.read(candidates[0])
    reference_text = reference_bytes.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(reference_text)))
    assert len(rows) == 80 and len({row["videos"] for row in rows}) == 80
    assert sum(row["split"] == "train" for row in rows) == 48
    assert sum(row["split"] == "test" for row in rows) == 32

    replacements = {
        "yolo11l.pt": "yolov8l.pt", "YOLO11": "YOLOv8",
        "extracted_features_yolo11_v2.csv": "extracted_features_yolov8_v2.csv",
        "annotated_samples_v2": "annotated_samples_yolov8_v2",
        "crossing_logs_v2": "crossing_logs_yolov8_v2",
        "Journal_Results_Export_v2": "Journal_Results_Export_yolov8_v2",
        "custom_bytetrack.yaml": "custom_bytetrack_yolov8.yaml",
    }
    for cell in notebook["cells"]:
        source = "".join(cell["source"])
        for old, new in replacements.items():
            source = source.replace(old, new)
        cell["source"] = source.splitlines(keepends=True)
        cell["metadata"] = {}
        if cell["cell_type"] == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
    notebook["cells"][0]["source"] = INTRO.splitlines(keepends=True)

    config = "".join(notebook["cells"][3]["source"])
    config += (
        "\n# Frozen selection from the user's completed YOLO11 v2 export.\n"
        f"REFERENCE_EXPORT_NAME = {REFERENCE.name!r}\n"
        f"REFERENCE_SELECTION_SHA256 = {hashlib.sha256(reference_bytes).hexdigest()!r}\n"
        f"REFERENCE_PAIRS_CSV = {reference_text!r}\n"
    )
    notebook["cells"][3]["source"] = config.splitlines(keepends=True)
    batch = "".join(notebook["cells"][6]["source"])
    batch = replace_once(
        batch, 'existing = pd.read_csv(path)',
        '''existing = pd.read_csv(path)
        if "model_name" not in existing or not existing["model_name"].eq(YOLO_MODEL_NAME).all():
            raise ValueError("Checkpoint contains a different model; use a fresh YOLOv8 output path.")''')
    batch = replace_once(
        batch,
        "future_label_pairs = prepare_next_segment_labels(train_df, set(available_videos))\n"
        "selected_pairs = select_balanced_source_clips(future_label_pairs)",
        LOCK_SELECTION.strip(),
    )
    batch = replace_once(batch, "FEATURE_COLUMNS = [", COMPLETENESS_CHECK + "\nFEATURE_COLUMNS = [")
    notebook["cells"][6]["source"] = batch.splitlines(keepends=True)
    notebook["cells"].append({
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": FINAL_CELL.lstrip().splitlines(keepends=True),
    })
    notebook["metadata"].pop("widgets", None)
    notebook["metadata"]["colab"] = {"name": TARGET.name, "provenance": []}
    notebook["metadata"]["accelerator"] = "GPU"
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            # Only the existing pip-install shell escape is non-Python syntax.
            code = "".join(line for line in cell["source"] if not line.lstrip().startswith("!"))
            ast.parse(code, filename=f"cell_{index}")
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite an existing notebook: {TARGET}")
    TARGET.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Created {TARGET} ({len(notebook['cells'])} cells, no stored outputs)")


if __name__ == "__main__":
    build()
