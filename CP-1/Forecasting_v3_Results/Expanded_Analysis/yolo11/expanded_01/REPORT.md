# Expanded YOLO11 forecasting review — 25 October 2026

The completed run used **448 training and 64 evaluation clips**, retaining 48
historical training features and processing 464 new clips. The validation-selected
classifier is **logistic regression with context/motion features**, not XGBoost.
Its 34 inputs are extracted from pretrained YOLO11l detections/tracks plus context.

## Verified results

| Method | Correct | Accuracy | Balanced accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
| selected_model | 46/64 | 71.875% | 46.731% | 0.428289 |
| original_settings_recomputed | 48/64 | 75.000% | 34.135% | 0.368447 |
| majority | 52/64 | 81.250% | 25.000% | 0.224138 |
| persistence_label_baseline | 51/64 | 79.688% | 40.096% | 0.417881 |

The selected pipeline has **71.875% accuracy** and **0.428289 macro-F1**. Always
predicting free-flowing traffic scores 81.25% accuracy because 52/64 evaluation
clips are free flowing. Persistence scores 79.6875%. Therefore the selected
pipeline does not beat these baselines on accuracy. Its macro-F1 exceeds majority
by 0.204151, and persistence by
only 0.010408.
Balanced accuracy measures mean class recall and is also above the baselines.
These metrics describe different trade-offs; they do not establish an overall win.

## Class-level performance

| Class | Test clips | Correct | Recall | F1 |
|---|---:|---:|---:|---:|
| free flowing | 52 | 40 | 76.9% | 0.8602 |
| heavy delay | 6 | 3 | 50.0% | 0.5000 |
| light delay | 5 | 3 | 60.0% | 0.3529 |
| moderate delay | 1 | 0 | 0.0% | 0.0000 |

There is only one moderate-delay test clip; the model misclassified it. Scores
for that class are particularly uncertain. The old balanced test had eight clips
per class. The 50% cached score and this 71.875% score use different samples and
class proportions, so their difference is not a controlled accuracy improvement.
There is no matching expanded YOLOv8 result yet; cached YOLOv8 is not a fair
comparison against this expanded YOLO11 pipeline.

## Dataset availability and quality

The Drive inventory contains 18,532 accessible
videos across four camera folders and matches 15,892
of the 16,076 labelled paths. There are 184
labelled paths missing from Drive, 2,640 videos
without matching rows in Train.csv, and 20 invalid label timing records. Their
lists are retained with the run. Unlabelled videos do not support scored
congestion evaluation without reference labels.

## Audit

The ZIP matches its extracted evaluation files. Input-feature and checkpoint
hashes agree. All four methods' saved predictions independently reproduce their
accuracy, balanced accuracy and macro-F1. The confusion matrix, class reports,
class counts, validation fold sizes/averages and validation winner agree.
Source/target labels and timestamps match the original Train.csv and contiguous
segment pairing. No human congestion labels or future timestamps are input features.

The new 64-clip test shares no source/target video with historical source clips;
0 source/target pairs are within two minutes of a historical source or
target time. Training targets precede the evaluation period. The 464 newly
processed clips' manifests and crossing logs agree with frame/count summaries;
observation-log files exist and all manifests record Ultralytics
8.4.184. These are consistency checks, not measured
vehicle-detection or counting accuracy. No joblib artifact was loaded or retrained.

All evaluation dates remain 25–26 October 2025, from the previously examined
recording week. This is broader coverage, not confirmation on new independent
dates. Keep settings frozen and assess additional untouched labelled traffic
before a stronger generalization claim. Integration of these results into the
paper is recorded separately in `PAPER_INTEGRATION.json` alongside this report.

Raw run: `Archives/expanded_01/`; machine-readable review: `AUDIT.json` alongside
this report. The original downloaded ZIP and logs are preserved in place.
