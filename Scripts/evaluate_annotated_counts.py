"""Evaluate hard and confidence-weighted counts on completely annotated clips.

Example:
  py Scripts/evaluate_annotated_counts.py --features extracted_features_yolo11_v2.csv \
    --ground-truth annotated_counts.csv --crossing-log-dir crossing_logs_v2 \
    --output-dir count_evaluation

Every clip must have eight rows: entering/exiting x car/motorcycle/bus/truck,
including zero counts. This prevents partial annotations from inflating results.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

CLASSES = ("car", "motorcycle", "bus", "truck")
DIRECTIONS = ("entering", "exiting")
CELLS = {(direction, vehicle_class) for direction in DIRECTIONS for vehicle_class in CLASSES}


def validate_ground_truth(table):
    required = {"video_path", "direction", "vehicle_class", "ground_truth_count"}
    if not required.issubset(table.columns):
        raise ValueError(f"Ground truth needs columns {sorted(required)}")
    if table.empty:
        raise ValueError("No annotated rows. Fill the template with complete clips first.")
    table = table.copy()
    table["ground_truth_count"] = pd.to_numeric(table["ground_truth_count"], errors="raise")
    if (table["ground_truth_count"] < 0).any() or not np.all(table["ground_truth_count"] % 1 == 0):
        raise ValueError("Ground-truth counts must be nonnegative integers")
    if table.duplicated(["video_path", "direction", "vehicle_class"]).any():
        raise ValueError("Duplicate clip/direction/class annotations")
    for video_path, group in table.groupby("video_path"):
        actual = set(zip(group["direction"], group["vehicle_class"]))
        if actual != CELLS:
            raise ValueError(f"{video_path}: expected all 8 direction/class rows; missing={sorted(CELLS - actual)}; extra={sorted(actual - CELLS)}")
    return table


def summarize_errors(truth, prediction):
    errors = np.asarray(prediction, dtype=float) - np.asarray(truth, dtype=float)
    return {"mae": float(np.mean(np.abs(errors))), "rmse": float(np.sqrt(np.mean(errors ** 2))),
            "mean_error": float(np.mean(errors))}


def evaluate(features_path, ground_truth_path, crossing_log_dir, output_dir):
    truth = validate_ground_truth(pd.read_csv(ground_truth_path))
    features = pd.read_csv(features_path)
    if not {"video_path", "crossing_log"}.issubset(features.columns):
        raise ValueError("Features CSV needs video_path and crossing_log columns from the v2 notebook")
    features = features.drop_duplicates("video_path", keep="last").set_index("video_path")
    detailed = []
    for video_path, group in truth.groupby("video_path", sort=True):
        if video_path not in features.index:
            raise ValueError(f"Annotated clip has no v2 features: {video_path}")
        log_value = str(features.at[video_path, "crossing_log"])
        crossing_path = Path(log_value)
        if crossing_log_dir is not None:
            crossing_path = crossing_log_dir / crossing_path.name
        if not crossing_path.is_file():
            raise FileNotFoundError(f"Crossing log missing: {crossing_path}")
        crossings = pd.read_csv(crossing_path)
        required = {"direction", "vehicle_class", "mean_track_confidence"}
        if not required.issubset(crossings.columns):
            raise ValueError(f"{crossing_path}: missing {sorted(required - set(crossings.columns))}")
        if not crossings.empty:
            scores = pd.to_numeric(crossings["mean_track_confidence"], errors="raise")
            if not scores.between(0, 1).all():
                raise ValueError(f"{crossing_path}: confidence outside [0, 1]")
            crossings = crossings.assign(mean_track_confidence=scores)
        for row in group.itertuples(index=False):
            matched = crossings[
                (crossings["direction"] == row.direction)
                & (crossings["vehicle_class"] == row.vehicle_class)
            ]
            detailed.append({
                "video_path": video_path, "direction": row.direction,
                "vehicle_class": row.vehicle_class,
                "ground_truth_count": int(row.ground_truth_count),
                "hard_count": len(matched),
                "soft_count": float(matched["mean_track_confidence"].sum()),
            })
    table = pd.DataFrame(detailed)
    by_clip = table.groupby("video_path", as_index=False)[
        ["ground_truth_count", "hard_count", "soft_count"]
    ].sum()
    summary = {
        "annotated_clips": len(by_clip), "annotated_direction_class_cells": len(table),
        "soft_count_definition": "sum of each crossed track's mean YOLO confidence",
        "per_clip_total": {
            "hard": summarize_errors(by_clip["ground_truth_count"], by_clip["hard_count"]),
            "soft": summarize_errors(by_clip["ground_truth_count"], by_clip["soft_count"]),
        },
        "per_direction_class_cell": {
            "hard": summarize_errors(table["ground_truth_count"], table["hard_count"]),
            "soft": summarize_errors(table["ground_truth_count"], table["soft_count"]),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "count_errors_by_direction_class.csv", index=False)
    by_clip.to_csv(output_dir / "count_errors_by_clip.csv", index=False)
    with (output_dir / "count_metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--crossing-log-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.features, args.ground_truth, args.crossing_log_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
