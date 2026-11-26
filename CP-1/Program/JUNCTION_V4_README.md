# Junction movements: all four camera folders

Open **[CP1_Junction_Movement_v4.ipynb](CP1_Junction_Movement_v4.ipynb)** in VS Code with your Colab extension. This is the new road-arm counting experiment; the earlier notebooks reproduce the paper's single-tripwire experiments.

The implementation is ready for calibration and pilot runs. **No new dataset-wide counts or accuracy results have been measured locally.** Raw videos are on your Drive, and the road gates for all four views still need to be placed on actual reference frames. The notebook obtains those frames directly from Drive without spending GPU inference time.

## Run sequence

1. Connect a Colab GPU runtime and run all cells with the default `STAGE='calibrate'` and `CALIBRATION_METHOD='draw'`. Cell 1 installs the pinned detector/analysis packages; restart the kernel if it reports that already-loaded packages changed. Cell 2 mounts Drive and writes the four embedded Python modules into the runtime. No separate module upload is needed. If you already ran the earlier slider version, rerun Cells 2-4 after opening the updated notebook; the existing configuration is preserved.
2. Cell 3 contains the settings. The dataset root is `/content/drive/MyDrive/CP-1 Dataset`. Cell 4 inventories every MP4 recursively in `normanniles1`, `normanniles2`, `normanniles3` and `normanniles4`, and creates reference PNGs for all four views. Other folders such as `added` are not part of this four-camera batch.
3. Cell 4 creates `Draw_Camera_Gates.html` inside the Drive calibration folder. Download that single HTML file through Google Drive and open it in Chrome or Edge (a Drive HTML preview will not run the drawing page). All four original reference pictures are embedded, so no image upload or coordinate entry is needed. Select a camera and gate A/B/C, then **click the two ends of a line across the road and click once toward the junction**. You may also drag the line and then click its junction side. Use Undo or Redraw to correct a gate. Draw A/B/C, click **Save this camera**, and repeat for all cameras. Finally click **Download gates_drawn.json**. Back in the notebook, choose that JSON in the upload control and click **Import drawn gates**. The import checks the reference-picture hashes, dimensions and gate geometry, and backs up the previous calibration. A/B/C meanings belong to that camera; gate A does not automatically represent the same physical road in every view. The previous slider editor remains available with `CALIBRATION_METHOD='sliders'`.
4. Set `STAGE='pilot'` in Cell 3. Run Cell 3 and the cells below it. By default the pilot processes three clips per camera and saves annotated MP4s. Camera 2 preferentially uses the three clips you reported as having no visible disturbance: `2025-10-25-16-46-45`, `2025-10-25-17-33-45`, and `2025-10-26-13-10-45`. The other cameras need their own visual checks. For a camera-2-only first test, set `PILOT_CAMERAS=['normanniles2']`; change it back to all four and review their pilots before the batch.
5. Open the pilot `annotated.mp4` files in Drive. Verify every gate and entry/exit direction. Red dots mark the vehicle **bottom centre** used for crossings. Inspect `gate_events.csv` and `journeys.csv` to confirm that left-to-upper and left-to-right movements are separate. Click the pilot-review button only after this visual check. This records geometry review, not counting accuracy. Changing gates/settings invalidates their pilot review. Use a new experiment name if the full batch has already begun.
6. Set `STAGE='batch'` and rerun Cell 3 downward. The batch processes **all inventoried videos**, including unlabelled videos, without per-camera/date sample limits. It requires a reviewed pilot for each camera. Keep the detector, inventory, calibration, package versions and counting settings unchanged while resuming. Completed clips are checked and skipped; interrupted clips restart from frame zero. Keep only one runtime writing an experiment folder.
7. After every planned clip has completed, set `STAGE='evaluate'` and rerun Cell 3 downward. Only valid labelled source/next-segment pairs are scored. Three consecutive source clips provide the traffic history. Numeric preprocessing is fitted inside chronological training folds. Source/future human congestion labels never become model inputs. The default October 25-26, 2025 evaluation dates were examined before and remain exploratory; a different evaluation needs a new `EVALUATION_NAME` and an appropriate frozen protocol.
8. The last code cell writes `Junction_v4_Results.zip` in Drive. Download it through Google Drive, which works with the VS Code Colab extension. Per-frame logs and annotated pilot videos stay in their clip folders rather than making the archive excessively large.

The pilot prints a rough full-run duration based on actual processing. Thousands of clips can require substantial runtime; keep the estimate in mind before starting the batch. Pilot clips are processed again as part of the separate full-batch contract. Resuming verifies saved outputs and rereads source videos to check their SHA256; this can take I/O time even when detector inference is skipped.

See the [camera-2 gate-placement example](examples/camera2_gate_example.png) for A = left, B = upper and C = right, with green inside-point arrows toward the junction. This AI-annotated illustration explains the layout; choose exact coordinates on the notebook's original reference frame. [Image provenance and prompts](examples/camera2_gate_example_NOTES.md).

## What is counted

- A **gate entry** is a tracked bottom-centre crossing from the outside of a road-arm gate toward its configured junction-side point. A gate exit is the opposite crossing. Each gate spans the actual road cross-section; the triangle drawn over the grass is not used as a default geometry.
- A **complete journey** records both an entry gate and a different exit gate for the same continuously observed track segment, for example A→B or A→C. The two gate events are not counted as two completed journeys.
- A **partial/incomplete track** has a missing entry or exit, a tracking gap/jump, ambiguous multi-gate movement, or no observed gate crossing. Same-gate returns are recorded separately from the between-road routes. The algorithm does not fill in an origin or destination by guessing.
- Track state resets between clips. A vehicle whose entry is in one clip and exit in the next is therefore incomplete in these per-clip journey outputs. Gate events still provide entry/exit information where observed. These outputs are **not a count of every physical vehicle using the junction**.
- Counts are per camera. Vehicle IDs are not matched across overlapping camera views, so summing camera totals does not establish a unique physical-vehicle total.
- Vehicle classes are car, motorcycle, bus and truck. Per-road, per-route and per-class outputs are exported. Confidence-weighted complete-journey sums are uncalibrated and do not establish lower counting error.

For manual validation of v4, use the same displayed gates and bottom-centre convention. The old single-line annotations and v4 journey annotations are different quantities and must not be substituted for one another.

## Video-quality review

Frame sampling compares brightness/colour and optionally reads the burned-in camera clock with Tesseract OCR. It records candidates for colour shifts and clock discontinuities. OCR can misread a clock or miss corruption; isolated screenshots and these automatic flags cannot establish exact missing intervals. When OCR cannot run or read a clock, the clip records that continuity is unverified. Colour changes alone do not invalidate a count.

Quality flags do not automatically exclude clips, alter labels or repair footage. Review them on both correct and incorrect predictions. The manually reported camera-1 disturbances and camera-2 colour change are retained in [the review notes](../Manual_Review/MANUAL_REVIEW_NOTES.md). No prediction is assumed to be wrong because of a video disturbance without further evidence. A failed/incomplete decode is recorded as a processing failure and is not checkpointed as complete. After three consecutive processing failures, the batch stops so a systemic error does not repeat across the entire dataset.

## Files saved to Drive

```text
CP-1 Dataset/Junction_v4/
  calibration/camera_gates_01/
    normanniles1.png ... normanniles4.png
    gates.json
    pilot_reviews.json
  yolo11/junction_01/
    pilots/<pilot-id>/clips/<camera>/<clip-id>/annotated.mp4
    pilots/<pilot-id>/manual_annotations/
    contract.json
    model_weights.json
    junction_features.csv
    pending_videos.csv
    processing_failures.csv
    batch_status.json
    clips/<camera>/<clip-id>/
      observations.csv
      frame_counts.csv
      gate_events.csv
      journeys.csv
      quality_flags.csv
      features.json
      manifest.json
    evaluations/historical_week_01/
      selected_pairs.csv
      excluded_pairs.csv
      evaluation_contract.json
      validation_folds.csv
      validation_ranking.csv
      selected_model.json
      selected_model.joblib
      evaluation_predictions.csv
      evaluation_metrics.csv
      split_class_distribution.csv
      classification_report.csv
      confusion_matrix.csv
      confusion_matrix.png
      REPORT.md
    Junction_v4_Results.zip
```

YOLOv8 uses the parallel `yolov8/<experiment>/` tree. Repeat its pilot and full run with the **same gates, video inventory and forecasting protocol** for a matched detector comparison. No new detector-superiority claim is made by merely implementing both options.

## Forecasting comparison

The default target remains the next contiguous labelled segment, not the original competition's longer forecasting task. Candidate families use either current clip measurements or current-plus-past contiguous history. Both families are compared on the same eligible cohort, avoiding a comparison of different samples. Candidate classifiers are regularized logistic regression, shallow regularized XGBoost and random forest; logistic regression also compares balanced and unweighted fitting. Selection uses mean chronological validation macro-F1, with accuracy and candidate name as tie-breakers.

The evaluation exports the selected model, each feature family's validation winner, training-majority and human-source-label persistence. Persistence is a reference baseline using a provided human label; that label is not available as a model input. Accuracy, macro-F1, balanced accuracy and per-class results must be read together. More data and new route features do not guarantee improvement.

All videos receive count features, but videos with no congestion labels cannot be scored as forecasting targets. Their measured history may be used only if timestamps and continuity are available. Missing/nonconsecutive history is excluded explicitly rather than padded from future videos. The evaluation saves exclusion reasons and a fixed split contract. New-date independence requires provenance review; changing a configuration date alone does not establish an untouched test set.

## Manual counts and measured counting error

Pilot templates contain blanks and `annotation_status=pending`. `manual_journey_counts.csv` requires every ordered pair of different gates and every vehicle class, including zeros. Count only completed journeys with both gate crossings visible within the same full clip. `manual_gate_counts.csv` instead records per-gate entry/exit counts. Ambiguous/partial review must not be entered as a complete full-clip annotation.

After you fill a template, the notebook's final markdown cell shows the function call for calculating MAE/RMSE. The evaluator rejects missing classes/routes, duplicate rows, blanks, negative/fractional counts, and pending/uncertain annotations. It does not infer reference counts from detector outputs. Scores describe the annotated clips only; the development pilot is not an independent final test.

## If the widget does not display

The drawing page runs as a normal local HTML file; it does not require notebook JavaScript support. Only the JSON upload and pilot-review controls use standard ipywidgets. If the upload widget is unavailable, upload `gates_drawn.json` into the same Drive calibration folder and run this extra notebook cell:

```python
drawing_tools.import_drawn_gates(
    CALIBRATION_FOLDER,
    (CALIBRATION_FOLDER/'gates_drawn.json').read_bytes())
```

You can download an unfinished drawing draft and resume it in the browser later. Drawn JSON is bound to the original reference pictures, so another camera's image or a generated illustration cannot silently replace the actual calibration. Pilot-direction review is still required; use a widget-capable notebook client for that step. For a view needing 2-6 gates rather than three, the underlying geometry validator supports IDs A-F, but the simple mouse editor is specifically for the three-road A/B/C workflow.

## Verification and primary documentation

Run locally:

```powershell
py -B Scripts/test_junction_v4.py
```

These tests use synthetic trajectories, synthetic video and a fake detector, plus real CPU classifier fitting. They check movement separation, finite gate intersections, partial tracks, gaps/identity switches, line dwell, source/label leakage, chronological model selection, blank-annotation rejection, checkpoint resume/tamper detection, and embedded notebook/source equality. They do not claim GPU or full-dataset execution.

The optional `py -B Scripts/test_junction_drawing_browser.py` additionally checks real mouse clicks, line dragging, resized-picture coordinates, undo/redraw, four-camera saving, JSON download and drawing resumption in an isolated headless Chrome/Edge profile. It requires Node 22+ and Chrome/Edge. Browser drawings are then checked by the Python calibration importer. The normal test suite also verifies that updates preserve an executed notebook's configuration and unrelated outputs.

Technical references: [Ultralytics tracking](https://docs.ultralytics.com/modes/track/), [ByteTrack API](https://docs.ultralytics.com/reference/trackers/byte_tracker/), and [chronological evaluation guidance](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data). Dataset: [Zindi Barbados Traffic Analysis Challenge](https://zindi.africa/competitions/barbados-traffic-analysis-challenge/data).
