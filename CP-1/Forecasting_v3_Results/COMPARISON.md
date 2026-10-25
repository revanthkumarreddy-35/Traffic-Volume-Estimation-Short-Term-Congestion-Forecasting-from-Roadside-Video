# Forecasting v3: reviewed cached results, 23 October 2026

The downloaded Colab exports confirm **YOLO11: 50.0% accuracy (16/32),
macro-F1 0.494118**, and **YOLOv8: 40.625% (13/32), macro-F1
0.403305**. These are next-segment congestion-classification scores.
Detection and vehicle-count accuracy remain unmeasured.

## Comparison and provenance

| Detector features | Selected classifier | Correct | Accuracy | Macro-F1 |
|---|---|---:|---:|---:|
| yolo11 | regularized_xgb_base | 16/32 | 50.000% | 0.494118 |
| yolov8 | regularized_xgb_context | 13/32 | 40.625% | 0.403305 |

Both runs use the same 48 training and 32 test clips, labels, seed, candidate
selection procedure, and package versions. Model selection uses mean macro-F1
on three chronological training-date validation folds, before test evaluation.
YOLO11's selected classifier uses 14 base features; YOLOv8's selected classifier
uses 28 base/context features. This compares selected forecasting pipelines;
it does not isolate the detector's contribution while holding the classifier
and feature set fixed.

The YOLO11 pipeline leads by **9.375 percentage points**, three additional correct
clips, and 0.090813 macro-F1 on this test set.
Both are correct on 10 clips; only YOLO11 is correct on
6; only YOLOv8 is correct on 3;
both are incorrect on 13.

Colab packages: scikit-learn 1.6.1,
XGBoost 3.4.1, pandas 2.2.3,
NumPy 2.1.3. Exports are stored in
`Forecasting_v3_yolo11_cached/` and `Forecasting_v3_yolov8_cached/`.
Earlier local outputs remain in `Local_Runs/yolo11/` and `Local_Runs/yolov8/`; use the downloaded
Colab values above when reporting these completed runs. Software differences
explain why earlier local F1/control results need not exactly reproduce these
exports. Model artifacts were not loaded during review.

## Colab controls on the same 32 clips

| Detector features | Method | Correct | Accuracy | Macro-F1 |
|---|---|---:|---:|---:|
| yolo11 | selected_model | 16/32 | 50.000% | 0.494118 |
| yolo11 | original_settings_recomputed | 13/32 | 40.625% | 0.409821 |
| yolo11 | majority | 8/32 | 25.000% | 0.100000 |
| yolo11 | persistence_label_baseline | 11/32 | 34.375% | 0.335415 |
| yolov8 | selected_model | 13/32 | 40.625% | 0.403305 |
| yolov8 | original_settings_recomputed | 11/32 | 34.375% | 0.317647 |
| yolov8 | majority | 8/32 | 25.000% | 0.100000 |
| yolov8 | persistence_label_baseline | 11/32 | 34.375% | 0.335415 |

Against the corresponding refitted original-settings control, the selected
YOLO11 pipeline gains 9.375 percentage points (three clips); the YOLOv8 pipeline
gains 6.25 percentage points (two clips). Archived v2 accuracy was 37.5% for
both detectors. The descriptive v3 differences from v2 are +12.5 points for
YOLO11 and +3.125 for YOLOv8. Historical comparisons change software,
preprocessing and row order and do not isolate a single cause.

## Performance by congestion class

| Class | YOLO11 correct | YOLO11 F1 | YOLOv8 correct | YOLOv8 F1 |
|---|---:|---:|---:|---:|
| free flowing | 5/8 | 0.5882 | 5/8 | 0.5263 |
| heavy delay | 4/8 | 0.5333 | 3/8 | 0.4286 |
| light delay | 5/8 | 0.5882 | 1/8 | 0.1250 |
| moderate delay | 2/8 | 0.2667 | 4/8 | 0.5333 |

YOLO11 performs better on light delay, while YOLOv8 performs better on moderate
delay. Free-flowing recall is equal. YOLO11 is the stronger selected forecasting
pipeline on this particular evaluation, without establishing universal or
detector-level superiority.

## Verification and interpretation

For each export, predictions independently reproduce the selected model's
accuracy, macro-F1, confusion matrix and per-class report. The exports match
all archived v2 holdout paths and labels, with no duplicate paths or training
targets crossing the 25 October split. Validation averages and selected
candidates match saved fold scores. Baseline counts agree; original-settings
baseline F1 cannot be independently recomputed because its predictions were
not exported. Detector identity is checked from every feature row.

The same test clips from 25-26 October 2025 were examined before this experiment.
Report this as an exploratory cached-feature improvement. Independent testing
with frozen settings and untouched dates/cameras remains necessary. Expanded
GPU extraction was not part of these cached runs. Later experimental stages
are reported separately and must retain their own test conditions and baselines.

Machine-readable audits: `Audits/COLAB_YOLO11_REVIEW.json`,
`Audits/COLAB_YOLOV8_REVIEW.json`, `Audits/COLAB_COMPARISON.json`.
Matched predictions: `Audits/colab_matched_holdout_predictions.csv`.
Original downloaded ZIPs are retained once each in `Archives/`.

<!-- expanded-yolo11-review -->
## Expanded YOLO11 run reviewed on 25 October 2026

The new experiment used 448 training and 64 evaluation clips and selected
`logistic_context` using training-date validation. This is a different sample
from the cached comparison above, with 52/64 free-flowing clips.

| Method | Correct | Accuracy | Balanced accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| selected_model | 46/64 | 71.875% | 46.731% | 0.428289 |
| original_settings_recomputed | 48/64 | 75.000% | 34.135% | 0.368447 |
| majority | 52/64 | 81.250% | 25.000% | 0.224138 |
| persistence_label_baseline | 51/64 | 79.688% | 40.096% | 0.417881 |

The selected model's 71.875% accuracy is below majority (81.25%) and persistence
(79.6875%). It has higher macro-F1 and balanced accuracy, with only a small
macro-F1 lead over persistence. Do not describe the increase from the old 50%
as a controlled improvement: sample/class proportions changed. No matched
expanded YOLOv8 run has been supplied. Detection/counting accuracy is unmeasured.

Full [expanded review](Expanded_Analysis/yolo11/expanded_01/REPORT.md) and
[machine-readable audit](Expanded_Analysis/yolo11/expanded_01/AUDIT.json).
The cached results above remain valid for their original 32-clip comparison.
