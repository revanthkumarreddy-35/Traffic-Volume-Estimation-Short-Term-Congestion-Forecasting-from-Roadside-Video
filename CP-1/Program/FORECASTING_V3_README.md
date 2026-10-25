# Improved congestion forecasting

Open **CP1_Congestion_Improved.ipynb** with a Colab GPU kernel in VS Code.
The active notebook is now configured for `RUN_MODE = 'expanded'` and
`DETECTOR = 'yolo11'`. Select a GPU (for example T4), restart the kernel if needed,
and run from the top. The notebook first audits filenames and labels, then
processes only the selected clips and fits the congestion classifiers.

For the earlier 80-clip CPU experiment, switch to `RUN_MODE = 'cached'`.
That mode uses the completed feature exports embedded in the notebook and
does not spend GPU time reprocessing videos.
Set `DETECTOR = 'yolo11'` or `'yolov8'` to select the feature set.

Both notebook modes mount Google Drive and save all generated reports, charts,
models and ZIP archives under `My Drive/CP-1 Dataset/Forecasting_v3/<detector>/`.
The mounted path is `/content/drive/MyDrive/CP-1 Dataset`. Cached evaluation
files use the `cached_evaluation/` subfolder; expanded evaluation files use
`evaluation/`. Expanded outputs use an additional experiment subfolder:
`Forecasting_v3/<detector>/expanded_01/`. In VS Code, run the final save cell to copy a completed runtime result
into this folder without retraining, then download the ZIP from Google Drive.

Changes implemented:

- Three chronological validation folds, on 22, 23 and 24 October. Each fold fits
  preprocessing and models only to earlier clips whose target precedes the fold.
- Fixed candidate list including the original XGBoost settings, shallower and
  regularized XGBoost, random forest and logistic regression. Selection uses
  validation macro-F1, with accuracy as a tie-breaker, before evaluation.
- Camera identity, cyclic time-of-day, directional/class proportions, normalized
  box area, density ratios and soft/hard ratio, alongside the original features.
- Optional normalized image motion, slow-motion fraction, density trend and
  box-area occupancy proxy derived from observation logs. These require complete
  log coverage, otherwise that feature family is omitted with an explicit message.
- Fold results, fitted model, feature schema, input hash, package versions,
  classification report, confusion matrix, predictions and ZIP export.

No human source or future congestion label is a model input. Persistence uses the
source label only as a separately reported baseline. No detector accuracy metrics
are invented from congestion predictions.

## Larger experiment

Set `RUN_MODE = 'expanded'`, select a GPU and run from the top. The notebook mounts
the same `CP-1 Dataset` folder. Defaults select up to 400 additional training clips
(20 per camera/date on 20–24 October) and retain the old completed training clips.
It also selects up to 64 new evaluation clips on 25–26 October, excluding previous
clips and two-minute neighborhoods. Sampling never uses future labels.

Labels are read from `CP-1 Dataset/CSV/Train.csv`; change `LABELS_RELATIVE_PATH`
in the configuration only if your copy is elsewhere. MP4 files do not need
embedded attributes. The label file must contain video paths, camera identity,
start/end timestamps and congestion ratings. Missing/unknown/conflicting labels
are reported as errors. Invalid segment durations are listed separately and
excluded from source/target pairing; 20 such rows exist in the supplied CSV.

The plan and checkpoints are stored in
`CP-1 Dataset/Forecasting_v3/<detector>/<EXPERIMENT_NAME>/` (default `expanded_01`).
Completed clips resume; interrupted or incomplete videos restart from frame zero.
A configuration/selection signature prevents resuming with incompatible settings.
Keep settings unchanged while resuming. Stop other notebooks writing the same
output folder before starting another session.

Resume uses the verified original `selected_pairs.csv`, rather than drawing a
different selection after an environment change. It pins the saved Ultralytics
version and checks that each saved source/target label and timestamp still
matches Train.csv. Old v4 contracts are upgraded only after these checks and
with the original contract retained as `checkpoint_contract.v4.json`.
The original selected-plan bytes and completed feature rows are retained.
If the version was already imported before a downgrade, restart the Colab
kernel and Run All so the saved version is actually used.

A remaining mismatch prints the exact changed fields and writes
`checkpoint_mismatch.json` beside the checkpoint. Do not delete a checkpoint or
change the experiment name just to bypass this error: restore the reported
settings, labels or processor code first. A new experiment name starts a separate
run and does not automatically reuse the old run's completed clips.

Default label-only preview: 448 training and 64 evaluation clips, reusing 48
completed training features. Up to 464 additional clips need GPU extraction.
Actual counts depend on video availability. Set `PLAN_ONLY = True` to create
the inventory and plan without processing videos, then set it back to `False`
and run from the top to start extraction. Do not change clip limits while
resuming; choose a new experiment name for a different experiment.

Outputs include `dataset_inventory.csv`, missing/unlabelled video lists,
`invalid_label_timing.csv`, `selected_pairs.csv`, `extracted_features.csv`,
crossing/observation logs and `matched_features.csv`. Evaluation exports include
balanced accuracy, macro-F1, per-class support, predictions for all baselines,
readable confusion matrices, models and a ZIP containing the run metadata.
Raw tracking logs stay in Drive rather than making the ZIP very large.

Natural class proportions differ from the original balanced sample. Compare the
selected model with the recomputed baselines on the same new evaluation set.
Do not compare accuracy across differently sampled sets as a direct improvement.
The dates were previously examined, so new dates/cameras are still needed for an
independent final test. Do not tune again using the new evaluation results.

## Local run and results

From the project root:

```powershell
py CP-1/Program/congestion_forecasting_v3.py --model yolo11
py CP-1/Program/congestion_forecasting_v3.py --model yolov8
```

Local outputs go to `CP-1/Forecasting_v3_Results/Local_Runs/<detector>/`.
Reviewed Colab exports are in `Forecasting_v3_yolo11_cached/` and
`Forecasting_v3_yolov8_cached/`, with original download ZIPs in `Archives/`
and verification JSON/CSV files in `Audits/` under `Forecasting_v3_Results`.
The original-settings
baseline is retrained under the local software, sorted rows and preprocessing;
its result can differ from the archived 37.5% runs. Package versions and input
hashes are saved for this reason. The current paper reports the original v2 pilot,
cached-feature re-evaluation and expanded YOLO11 experiment as three distinct
stages, with their own test conditions and baselines. See
`Documents/Research paper_reference_style.pdf` and the integration provenance
in the expanded analysis folder.
