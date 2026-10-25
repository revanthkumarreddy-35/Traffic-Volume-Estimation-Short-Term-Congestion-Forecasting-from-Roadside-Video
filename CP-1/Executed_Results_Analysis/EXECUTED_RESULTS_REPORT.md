# Executed v2 results audit

Update (23 October 2026): this report retains the original YOLO11-only audit.
The matched YOLOv8/YOLO11 comparison and current paper changes are documented in
[YOLOV8_YOLO11_COMPARISON_REPORT.md](YOLOV8_YOLO11_COMPARISON_REPORT.md).
The current paper is `Documents/Research paper_reference_style.pdf`.

Source: `Journal_Results_Export_v2-20261020T090346Z-1-001.zip` and the saved notebook execution outputs.

All 80 selected clips have feature rows; 48 train and 32 date-held-out clips. The saved notebook execution reused 73 completed v2 checkpoints and processed 7 remaining clips. There are 20 clips from each of four cameras and eight held-out examples of each future class. The prediction horizon is 58-69 seconds.

The 80 clips contain 95,235 processed frames and 4,761.75 seconds of source video. The tracker predicts 2,162 hard crossings (997 entering; 1,165 exiting). The exploratory soft sum is 1,572.3573; this is **not** a measured counting improvement. Class totals: {'car': 1703, 'motorcycle': 10, 'bus': 28, 'truck': 421}.

On the 32-clip holdout, XGBoost accuracy is 0.3750, macro-F1 0.3784, and the notebook-defined composite 0.3774. Persistence accuracy is 0.3438 with macro-F1 0.3354; the majority-class accuracy is 0.2500. This is a one-correct-case lead over persistence, not a robust improvement claim.

The detailed clip has 686 tracked detections (mean confidence 0.5677), 4 hard crossings, and 2.8346 soft crossings. The supplied ZIP has summary tables and figures but **not** crossing-log CSVs, manifests, or manual annotations. mAP, MOTA, count MAE/RMSE, and weather degradation remain not evaluated. The prior 50-clip YOLOv8 comparison uses different selection/settings and is not pooled with v2.

The current paper includes this original pilot as Stage A and reports cached
and expanded evaluations separately. See `CP-1/Forecasting_v3_Results/COMPARISON.md`.
