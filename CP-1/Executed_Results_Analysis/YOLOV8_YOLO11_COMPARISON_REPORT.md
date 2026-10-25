# Matched YOLOv8l and YOLO11l results

Verified: identical 80 clips, 48/32 split, labels, frame counts, FPS, resolutions and tripwire positions.

| Method | Correct / 32 | Accuracy | Macro-F1 | Composite |
|---|---:|---:|---:|---:|
| YOLOv8l features + XGBoost | 12 | 0.3750 | 0.3542 | 0.3604 |
| YOLO11l features + XGBoost | 12 | 0.3750 | 0.3784 | 0.3774 |
| Persistence | 11 | 0.3438 | 0.3354 | 0.3379 |
| Training-majority | 8 | 0.2500 | 0.1000 | 0.1450 |

YOLOv8l: 2,142 hard crossings, 1,600.4317 soft sum. YOLO11l: 2,162 hard crossings, 1,572.3573 soft sum.

Neither predicted counts nor confidence scores establish counting accuracy. Both classifiers get 12 cases correct; macro-F1 differs by 0.0242. No significance or equivalence claim is supported.

Paired correctness: {"both_correct": 11, "only_yolov8_correct": 1, "only_yolo11_correct": 1, "both_incorrect": 19, "different_predictions": 9}

The YOLOv8 final-session manifest is available, but per-clip manifests/crossing logs are absent from this supplied folder. Historical software/hardware equality cannot be verified.

Current source paper: `Documents/Paper_Sources/Research paper_updated_authors.docx`. The formatted paper is `Documents/Research paper_reference_style.docx`. Figures 1-3 and tables 2-3, 5-6 retain YOLO11 results. Table 4 compares both classifiers and baselines; Table 7 adds counts; Figure 4 compares classification matrices. The confidence bands are Figure 2 and box-area/flow plots are Figure 3, following reading order.

The current paper includes named authors and linked prior literature in Related
Work. Published studies use different datasets and protocols; their reported
performance is not a matched benchmark against these experiments. Later cached
and expanded evaluations appear as separate stages in the paper and comparison.
