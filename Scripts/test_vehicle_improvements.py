"""Offline checks for notebook logic; no video files or GPU required."""

import ast
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pandas as pd

from evaluate_annotated_counts import CELLS, evaluate

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "CP-1/Program/notebook_sources"


def load_functions(filename, names, namespace):
    module = ast.parse((SOURCES / filename).read_text(encoding="utf-8"))
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(ast.Module(body=functions, type_ignores=[]), filename, "exec"), namespace)
    return namespace


def main():
    geometry = load_functions("cell_5.py", {"segment_intersection", "crossing_direction"}, {})
    intersects = geometry["segment_intersection"]
    direction = geometry["crossing_direction"]
    assert intersects((0, 5), (10, 5), (5, 4), (5, 6))
    assert direction((0, 5), (10, 5), (5, 4), (5, 6)) == "exiting"
    assert not intersects((0, 5), (10, 5), (11, 4), (11, 6))
    assert not intersects((0, 5), (10, 5), (5, 4), (5, 5))

    labels = pd.read_csv(ROOT / "CP-1/Data/Zindi_Labels/Train.csv")
    namespace = load_functions(
        "cell_6.py", {"prepare_next_segment_labels", "select_balanced_source_clips"},
        {"pd": pd, "np": np, "TEST_DATES": {"2025-10-25", "2025-10-26"},
         "TRAIN_CLIPS_PER_CAMERA_CLASS": 3, "TEST_CLIPS_PER_CAMERA_CLASS": 2,
         "RANDOM_SEED": 42},
    )
    paired = namespace["prepare_next_segment_labels"](labels, set(labels["videos"]))
    selected = namespace["select_balanced_source_clips"](paired)
    assert len(selected) > 0
    assert set(selected["next_enter_rating"]) == set(labels["congestion_enter_rating"])
    assert set(selected["split"]) == {"train", "test"}
    assert (selected["gap_sec"].between(0, 2)).all()
    assert set(selected.loc[selected["split"] == "test", "source_date"]) <= {"2025-10-25", "2025-10-26"}
    print("Selected clip counts by split and future class:")
    print(selected.groupby(["split", "next_enter_rating"]).size().to_string())

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        notebook = ast.parse((SOURCES / "cell_5.py").read_text(encoding="utf-8"))
        definitions = [node for node in notebook.body if isinstance(node, ast.FunctionDef)]
        namespace = {
            "cv2": cv2, "np": np, "pd": pd, "os": os, "json": json, "math": math,
            "re": re, "defaultdict": defaultdict, "datetime": datetime,
            "timezone": timezone, "GLOBAL_TRACKING_STATE": {},
            "make_video_key": lambda _: "normanniles1/synthetic.mp4",
            "COUNTING_LINES": {"default": ((0.05, 0.50), (0.95, 0.50))},
            "VEHICLE_CLASSES": {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"},
            "TRACKER_CONFIG_PATH": "custom_bytetrack.yaml", "YOLO_MODEL_NAME": "test_weights.pt",
            "RUN_LOG_DIR": str(root), "custom_config": {"tracker_type": "bytetrack"},
        }
        exec(compile(ast.Module(body=definitions, type_ignores=[]), "cell_5.py", "exec"), namespace)

        class FakeCapture:
            def __init__(self, _):
                self.index = 0
            def isOpened(self):
                return self.index < 3
            def get(self, prop):
                return {cv2.CAP_PROP_FPS: 10, cv2.CAP_PROP_FRAME_COUNT: 3,
                        cv2.CAP_PROP_FRAME_WIDTH: 64, cv2.CAP_PROP_FRAME_HEIGHT: 64}[prop]
            def read(self):
                if self.index >= 3:
                    return False, None
                self.index += 1
                return True, np.zeros((64, 64, 3), dtype=np.uint8)
            def release(self):
                pass

        class Coordinates:
            def __init__(self, values):
                self.values = np.array(values)
            def cpu(self):
                return self
            def numpy(self):
                return self.values

        class FakeBoxes(list):
            id = [1]

        class FakeTracker:
            def __init__(self):
                self.resets = 0
            def reset(self):
                self.resets += 1

        class FakeModel:
            def __init__(self):
                self.tracker = FakeTracker()
                self.predictor = SimpleNamespace(trackers=[self.tracker])
                self.frame_index = 0
            def track(self, *_args, **_kwargs):
                center_y = (28, 32, 36)[self.frame_index % 3]
                self.frame_index += 1
                box = SimpleNamespace(cls=[2], id=[1], conf=[0.8],
                                      xyxy=[Coordinates([24, center_y - 4, 34, center_y + 4])])
                return [SimpleNamespace(boxes=FakeBoxes([box]))]

        original_capture = cv2.VideoCapture
        cv2.VideoCapture = FakeCapture
        try:
            fake_model = FakeModel()
            for _ in range(2):
                features, _, _ = namespace["process_video_with_tracking"](
                    "synthetic.mp4", fake_model
                )
                assert features["total_unique_vehicles"] == 1
                assert features["exiting_count"] == 1
                assert abs(features["soft_count"] - 0.8) < 1e-12
            assert fake_model.tracker.resets == 2
            events = pd.read_csv(features["crossing_log"])
            assert len(events) == 1 and events.iloc[0]["frame_idx"] == 2
            assert len(json.loads(events.iloc[0]["track_confidence_history"])) == 3
        finally:
            cv2.VideoCapture = original_capture

        video_key = "normanniles1/example.mp4"
        pd.DataFrame([{
            "video_path": video_key, "crossing_log": "/content/drive/example_crossings.csv"
        }]).to_csv(root / "features.csv", index=False)
        pd.DataFrame([{
            "direction": "entering", "vehicle_class": "car", "mean_track_confidence": 0.8
        }]).to_csv(root / "example_crossings.csv", index=False)
        pd.DataFrame([{
            "video_path": video_key, "direction": direction,
            "vehicle_class": vehicle_class,
            "ground_truth_count": 1 if (direction, vehicle_class) == ("entering", "car") else 0,
        } for direction, vehicle_class in sorted(CELLS)]).to_csv(root / "truth.csv", index=False)
        metrics = evaluate(root / "features.csv", root / "truth.csv", root, root / "results")
        assert metrics["per_clip_total"]["hard"]["mae"] == 0
        assert abs(metrics["per_clip_total"]["soft"]["mae"] - 0.2) < 1e-12
        assert metrics["annotated_direction_class_cells"] == 8
    print("Geometry, tracker reset, on-line crossing, label selection, and count evaluation checks passed")


if __name__ == "__main__":
    main()
