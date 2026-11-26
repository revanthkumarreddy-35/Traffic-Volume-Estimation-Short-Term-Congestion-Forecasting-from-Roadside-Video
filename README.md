# Roadside vehicle counting and next-segment congestion classification

Pretrained YOLOv8l/YOLO11l detect vehicles, ByteTrack maintains tracks, and a
finite tripwire produces directional counts. A separate classifier predicts the
**next contiguous labelled segment's congestion class** from source-video features.
The detectors are not fine-tuned. Congestion-classification accuracy is distinct
from detection or counting accuracy.

## Start here

| Task | File |
|---|---|
| Read the research paper | [PDF](Research_Paper/Comparative_Evaluation_of_YOLOv8l_and_YOLO11l_for_Roadside_Traffic_Monitoring_and_Next-Segment_Congestion_Classification.pdf) |
| Calibrate road-arm gates and process all four camera folders (new experiment) | [CP1_Junction_Movement_v4.ipynb](CP-1/Program/CP1_Junction_Movement_v4.ipynb) · [Instructions](CP-1/Program/JUNCTION_V4_README.md) |
| Reuse completed features or run the expanded experiment | [CP1_Congestion_Improved.ipynb](CP-1/Program/CP1_Congestion_Improved.ipynb) |
| Process videos with YOLO11 | [CP1_Vehicle_Counter_yolov11.ipynb](CP-1/Program/CP1_Vehicle_Counter_yolov11.ipynb) |
| Run the matched YOLOv8 pilot | [CP1_Vehicle_Counter_yolov8.ipynb](CP-1/Program/CP1_Vehicle_Counter_yolov8.ipynb) |
| Understand settings and checkpoint recovery | [Forecasting instructions](CP-1/Program/FORECASTING_V3_README.md) |
| Compare measured results | [Comparison](CP-1/Forecasting_v3_Results/COMPARISON.md) · [Expanded audit](CP-1/Forecasting_v3_Results/Expanded_Analysis/yolo11/expanded_01/REPORT.md) |
| Check this repository review | [Review record](REVIEW.md) |

## Dataset source

The project uses the [Barbados Traffic Analysis Challenge dataset on Zindi](https://zindi.africa/competitions/barbados-traffic-analysis-challenge/data).
This official data page provides the video-download locations and `Train.csv`
congestion labels for the four Norman Niles roundabout camera views in Barbados.
See [data setup and attribution](CP-1/Data/README.md) for the required folder layout.

## What the experiments show

| Stage | Detector features / classifier | Train / test clips | Accuracy | Macro-F1 |
|---|---|---:|---:|---:|
| A: original matched pilot | YOLOv8l / original XGBoost | 48 / 32 | 37.500% | 0.3542 |
| A: original matched pilot | YOLO11l / original XGBoost | 48 / 32 | 37.500% | 0.3784 |
| B: cached feature evaluation | YOLOv8l / selected regularized XGBoost | 48 / 32 | 40.625% | 0.4033 |
| B: cached feature evaluation | YOLO11l / selected regularized XGBoost | 48 / 32 | 50.000% | 0.4941 |
| C: expanded evaluation | YOLO11l / selected logistic regression | 448 / 64 | 71.875% | 0.4283 |

Stage C has 52 free-flowing, six heavy-delay, five light-delay and one
moderate-delay evaluation clip. Its accuracy is **below** majority (81.25%) and
source-label persistence (79.6875%). Its balanced accuracy is 46.731% and its
macro-F1 is slightly above persistence (0.4179). It cannot be compared with
Stage B as a controlled accuracy improvement: the samples, class proportions,
features and selected classifier changed. No matched expanded YOLOv8 run exists.

All evaluation dates had already been examined. These are exploratory results;
none establishes universal detector superiority. Manual bounding boxes, track
identities and crossing counts are unavailable, so detection mAP, MOTA and count
MAE/RMSE are not reported. Confidence-weighted counts are uncalibrated model outputs.

## Run in VS Code with the Colab extension

For the new **junction-movement** workflow, use
[CP1_Junction_Movement_v4.ipynb](CP-1/Program/CP1_Junction_Movement_v4.ipynb)
and follow [calibration → pilot → batch → evaluation](CP-1/Program/JUNCTION_V4_README.md).
It covers all videos in the four camera folders after camera-specific gates and
annotated pilots are reviewed. New counting/forecasting results have not yet been
measured. The instructions below reproduce the earlier single-tripwire workflow.

1. Open `CP1_Congestion_Improved.ipynb` and connect a Colab kernel.
2. Edit the **configuration cell before Run All**. Use `RUN_MODE = 'cached'` and
   `DETECTOR = 'yolo11'` or `'yolov8'` to reuse embedded features without video
   inference. The checked-in configuration retains the completed experiment's
   `RUN_MODE = 'expanded'` setting; that mode needs a GPU and your video dataset.
3. Mount your Google Drive account. The default dataset directory is
   `/content/drive/MyDrive/CP-1 Dataset`. For expanded mode it must contain
   `CSV/Train.csv` and the four `normanniles1` through `normanniles4` video folders.
4. For a new expanded experiment, use a new `EXPERIMENT_NAME` and first set
   `PLAN_ONLY = True`. Review the inventory, then set it to `False` for extraction.
   Keep configuration, labels, selection and detector code unchanged when resuming
   an existing experiment. The notebook skips complete checkpoints.
5. Results and ZIP files are saved in Drive under
   `CP-1 Dataset/Forecasting_v3/<detector>/`. Download them through Google Drive;
   browser-only `files.download()` is not needed in VS Code.

Published notebooks have execution outputs cleared. CSV predictions, metrics and
figures retain the measured evidence. Re-running fits new classifiers; dependency
versions can change exact predictions. Original exports are kept separately.

## Review published evidence

The repository retains measured predictions, metrics, figures, and evaluation records for review:

- [Matched YOLOv8l/YOLO11l comparison](CP-1/Executed_Results_Analysis/YOLOV8_YOLO11_COMPARISON_REPORT.md)
- [Cached and expanded comparison](CP-1/Forecasting_v3_Results/COMPARISON.md)
- [Expanded evaluation report](CP-1/Forecasting_v3_Results/Archives/expanded_01/evaluation/REPORT.md)
- [Manual playback review record](CP-1/Manual_Review/MANUAL_REVIEW_NOTES.md)

The repository provides runnable Colab notebooks and their supporting modules under `CP-1/Program/`.

## Repository contents and evidence

- `CP-1/Program/`: reusable notebooks, forecasting module, extraction templates,
  manual-count annotation template and usage instructions.
- `CP-1/Data/Zindi_Labels/Train.csv`: the existing congestion-label table used by
  the offline checks. See [data notes](CP-1/Data/README.md) for schema and placement.
- `CP-1/Executed_Results_Analysis/`: Stage-A comparisons and figure/reference audits.
- The small YOLO11 v2 ZIP and `Journal_Results_Export_yolov8_v2/`: original pilot
  exports required by the cached-data reader and the matched-selection checks.
- `CP-1/Forecasting_v3_Results/`: Stage-B exports, Stage-C evaluation CSVs/figure,
  run metadata and verification reports. Large tracking logs and model binaries
  are local artifacts. The retained evaluation reports document the archived results; original expanded ZIP files and full clip logs remain local artifacts.
- `Research_Paper/`: current publication PDF.
- `CP-1/Program/`: runnable notebooks and supporting Python modules.

Raw videos, download manifests, fitted models, execution-output backups,
administrative records, chat history, third-party reference PDFs, superseded
drafts and one-time cleanup scripts are excluded from the current published tree.
Local copies are retained. Earlier commits are not rewritten by this cleanup.

## Authors

Puligadda Charishma, Althi Bhargavi, Nossam Revanth Kumar Reddy, and
Alavalapati Naga Thanmai. Guide: Dr. T. Praveen.
