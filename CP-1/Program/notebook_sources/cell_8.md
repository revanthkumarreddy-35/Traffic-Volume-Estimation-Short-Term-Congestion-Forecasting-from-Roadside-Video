### Evaluation before making accuracy claims

The detector uses pretrained COCO weights. A confidence score is **not** detection accuracy. The confidence-band table and plots above are descriptive statistics, not a confusion matrix. No mAP, MOTA, counting RMSE, weather robustness, or forecasting score should be reported unless an appropriate evaluation has actually run.

For counting, manually annotate several complete clips with `video_path`, `direction`, `vehicle_class`, and `ground_truth_count`. Compare those rows with the v2 feature CSV using `Scripts/evaluate_annotated_counts.py` from the project workspace. The script computes hard- and soft-count MAE/RMSE on the *same* clips and reports the sample size. Sample clips across cameras, lighting, and congestion classes; keep a separate holdout set.

For detection mAP, label image frames with bounding boxes in YOLO dataset format, prepare a data YAML with train/val/test splits, and run Ultralytics `model.val(data=..., split="test")` on held-out images. For MOTA, annotate per-frame track identities and use a tracking evaluator; crossing totals alone cannot produce MOTA. Weather degradation needs weather labels and a comparison of the same metric by weather group. Do not transfer metrics from another study or a pretrained model card to this dataset.

The next-segment XGBoost score in Cell 6 is produced only when balanced source clips from every class have been processed and the held-out dates contain labeled examples. It is a sampled holdout result, not a claim about all 16,076 labeled videos.
