# Vehicle counter v2: how to run and report it

For the new accuracy-improvement workflow, open `CP1_Congestion_Improved.ipynb`.
See [FORECASTING_V3_README.md](FORECASTING_V3_README.md) for CPU reuse of completed
features, chronological validation, and optional expanded GPU extraction.

## YOLOv8 comparison run

Open `CP1_Vehicle_Counter_yolov8.ipynb` in Google Colab, select a GPU runtime,
and run all cells in order. It uses `yolov8l.pt` with the same tracking/counting
settings as the active YOLO11 notebook. The exact 80 clips and 48/32 split from
the completed YOLO11 v2 export are embedded in the notebook; it checks the
available clips and labels before batch processing.

Outputs are separate: `extracted_features_yolov8_v2.csv`,
`crossing_logs_yolov8_v2/`, `annotated_samples_yolov8_v2/`, and
`Journal_Results_Export_yolov8_v2/`, all under the same Drive dataset directory.
The final cell writes `Journal_Results_Export_yolov8_v2.zip` there. Share that ZIP
after execution for the journal comparison. It includes batch summaries,
XGBoost predictions/metrics, a readable classification confusion matrix,
single-clip charts, crossing events, and run manifests. Per-frame logs remain
in Drive rather than making the ZIP unnecessarily large.

Interrupted runs resume completed YOLOv8 clips. Keep settings unchanged when
resuming; the notebook requires all 80 clips before evaluating. Do not interpret
more predicted crossings or higher confidence as better detection accuracy.
Historical package/hardware equivalence is not verified, and the two large
model variants have different parameter counts.

## Original YOLO11 run

Open `CP1_Vehicle_Counter_yolov11.ipynb` in Google Colab and run cells in order. The notebook expects videos and `CSV/Train.csv` under `/content/drive/MyDrive/CP-1 Dataset`. A GPU is strongly recommended. Published notebooks have cleared execution outputs; measured results are provided separately.

The notebook now writes `extracted_features_yolo11_v2.csv`, `crossing_logs_v2/`, and `Journal_Results_Export_v2/`. It does not reuse old feature rows, because their counting lines, tracker lifetime, and feature definitions differ. Cell 6 samples source clips across all four future congestion classes and camera views, with 25–26 October 2025 held out by date. The target is the next contiguous *labeled segment* (horizon recorded in seconds), not necessarily a full minute. Processed clips are checkpointed; interrupted clips restart from frame zero.

Crossing logs record the per-frame tracked positions and each crossing event. The hard count is one crossing per tracker ID per clip. The soft count is the sum of mean detection confidences for those crossed tracks; it is an exploratory weighted count, **not** a validated improvement. Review the line placement and several annotated samples per camera. If two runs differ by one crossing, compare the event log, track observations, and run manifest before attributing the difference to the detector.

To evaluate counting, copy `manual_count_annotations_template.csv` to a new CSV and enter eight rows for each fully annotated clip: each of car/motorcycle/bus/truck, for entering and exiting, including zeros. Use the exact relative `video_path` from the v2 feature CSV. After copying the v2 feature CSV and crossing logs from Drive to your machine, run:

```powershell
py Scripts/evaluate_annotated_counts.py --features "path/to/extracted_features_yolo11_v2.csv" --ground-truth "path/to/annotated_counts.csv" --crossing-log-dir "path/to/crossing_logs_v2" --output-dir "path/to/count_evaluation"
```

The script reports hard and soft MAE/RMSE on the same annotated clips. It refuses partial annotations. For detection mAP, prepare held-out bounding-box labels and use Ultralytics `model.val(data="dataset.yaml", split="test")`. MOTA additionally requires per-frame track-identity annotations. Weather comparisons require clip-level weather labels and a sufficiently sized group in each condition. None of these can be inferred from confidence scores or the existing Zindi congestion labels alone.

The current paper reports the original v2 comparison, cached classifier selection,
and expanded YOLO11 experiment as separate stages. See
[the current comparison](../Forecasting_v3_Results/COMPARISON.md).
New runs need their own verification before replacing measured paper results.
