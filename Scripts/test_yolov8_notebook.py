"""Offline validation of the comparison notebook; no model download/inference."""
import ast
import io
import json
import os
import zipfile
from types import SimpleNamespace

import numpy as np
import pandas as pd

from create_yolov8_notebook import LOCK_SELECTION, REFERENCE, ROOT, SOURCE, TARGET


def main():
    notebook = json.loads(TARGET.read_text(encoding="utf-8"))
    original = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert any('yolo11l.pt' in ''.join(cell['source']) for cell in original['cells'])
    for cell in notebook["cells"]:
        # Execution outputs are optional; validate executable logic in either state.
        if cell["cell_type"] == "code":
            ast.parse("".join(line for line in cell["source"]
                              if not line.lstrip().startswith("!")))

    config = ast.parse("".join(notebook["cells"][3]["source"]))
    assignments = {}
    for node in config.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                assignments[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    assert assignments["YOLO_MODEL_NAME"] == "yolov8l.pt"
    reference_text = assignments["REFERENCE_PAIRS_CSV"]
    with zipfile.ZipFile(REFERENCE) as archive:
        key = next(name for name in archive.namelist()
                   if name.endswith("/selected_next_segment_pairs.csv"))
        assert reference_text == archive.read(key).decode("utf-8-sig")
    pairs = pd.read_csv(io.StringIO(reference_text))
    namespace = {
        "pd": pd, "np": np, "os": os,
        "REFERENCE_PAIRS_CSV": reference_text,
        "available_videos": dict.fromkeys(pairs["videos"], "unused.mp4"),
        "train_df": pd.read_csv(ROOT / "CP-1/Data/Zindi_Labels/Train.csv"),
        "TEST_DATES": assignments["TEST_DATES"],
        "YOLO_MODEL_NAME": "yolov8l.pt", "RESUME_FEATURE_EXTRACTION": True,
    }
    batch_ast = ast.parse("".join(notebook["cells"][6]["source"]))
    definitions = [node for node in batch_ast.body if isinstance(node, ast.FunctionDef)]
    exec(compile(ast.Module(body=definitions, type_ignores=[]), "batch_functions", "exec"), namespace)
    exec(LOCK_SELECTION, namespace)
    assert namespace["selected_pairs"]["split"].value_counts().to_dict() == {"train": 48, "test": 32}
    assert namespace["selected_pairs"].groupby(["split", "next_enter_rating"]).size().tolist() == [8]*4 + [12]*4
    missing_key = pairs.iloc[0]["videos"]
    namespace["available_videos"].pop(missing_key)
    try:
        exec(LOCK_SELECTION, namespace)
        raise AssertionError("Missing clip was not rejected")
    except FileNotFoundError:
        pass
    namespace["available_videos"][missing_key] = "unused.mp4"
    namespace["train_df"].loc[
        namespace["train_df"]["videos"] == missing_key, "congestion_enter_rating"
    ] = "changed-label"
    try:
        exec(LOCK_SELECTION, namespace)
        raise AssertionError("Changed labels were not rejected")
    except ValueError:
        pass
    namespace["os"] = SimpleNamespace(path=SimpleNamespace(isfile=lambda _: True))
    namespace["pd"] = SimpleNamespace(read_csv=lambda _: pd.DataFrame(
        [{"video_path": "clip.mp4", "model_name": "yolo11l.pt"}]))
    try:
        namespace["load_existing_features"]("unused.csv")
        raise AssertionError("YOLO11 checkpoint was not rejected")
    except ValueError:
        pass
    namespace["pd"] = SimpleNamespace(read_csv=lambda _: pd.DataFrame(
        [{"video_path": "clip.mp4", "model_name": "yolov8l.pt"}]))
    _, keys = namespace["load_existing_features"]("unused.csv")
    assert keys == {"clip.mp4"}
    config_source = "".join(notebook["cells"][3]["source"]).split("# Frozen selection")[0]
    for forbidden in ('"extracted_features_yolo11_v2.csv"', '"crossing_logs_v2"',
                      '"Journal_Results_Export_v2"', '"annotated_samples_v2"'):
        assert forbidden not in config_source
    print("PASS: syntax, exact 80 clips/48-32 split, reference labels,")
    print("missing-clip guard, changed-label guard, model-specific resume and isolated paths.")
    print("Both notebooks were checked without editing them. GPU inference was not run.")


if __name__ == "__main__":
    main()
