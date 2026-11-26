# Manual review findings

## Counting scope clarification — 1 November 2026

The user identified that traffic arriving from the left in camera 2 can follow two different branches. Inspection of the active improved notebook's embedded processor, its configuration and the saved clip-6 manifest confirms that route-specific junction counting is **not implemented** in the evaluated workflow.

- The configured line is a single horizontal finite tripwire from `(48, 270)` to `(912, 270)` for the `960 x 540` frame. The expanded configuration uses the same normalized default for every camera, with no active per-road gates.
- The processor records at most one crossing for each track ID within a clip. Its `entering` and `exiting` strings describe image-line crossing direction: upward and downward, respectively. They have not been calibrated to physical entry/exit at every road arm.
- These outputs do not distinguish left-to-right from left-to-upper-road journeys. A vehicle that stays on one side of the configured line contributes no tripwire crossing even if it passes through the visible junction.
- The earlier manual instruction to count at this line is suitable for checking the historical line-crossing outputs only. It is insufficient for measuring all junction traffic or turning movements. Prior wording that implied physical junction entry/exit was too broad.
- To evaluate junction movements, define calibrated gates or regions at the road arms for each camera and record each observed origin-to-destination journey. Entry and exit gate events must be distinguished from the completed journey count; vehicles lost to occlusion or clip boundaries need an incomplete/unknown category.
- Keep manual counts for the existing tripwire separate from any new junction-movement counts. Neither should be substituted for the other when assessing saved results. All manual reference counts remain pending.

Code evidence: [counting configuration](../Program/notebook_sources/forecasting_expanded.py), [crossing and per-track count logic](../Program/notebook_sources/cell_5.py), and [executed clip-6 manifest](../Forecasting_v3_Results/Archives/expanded_01/crossing_logs/normanniles2_normanniles2_2025-10-26-14-42-45.mp4_manifest.json). The supplied red-line sketch is a conceptual description, not a calibrated gate definition.

Implementation follow-up: a separate [v4 notebook](../Program/CP1_Junction_Movement_v4.ipynb) and [run instructions](../Program/JUNCTION_V4_README.md) now provide per-camera road-arm calibration, entry/exit gate events and origin/destination journeys for all videos in the four camera folders. Actual gate placement and annotated-pilot review must be completed in Colab before batch inference. New dataset-wide counts and accuracy have not yet been measured. Its manual-count convention uses the displayed vehicle bottom-centre and calibrated gates, rather than the old horizontal centre-line definition. The clip observations below remain the original playback-quality review.

## Clip 1: normanniles1_2025-10-26-14-47-45.mp4

- Source path: `normanniles1/normanniles1_2025-10-26-14-47-45.mp4`
- Following target: `normanniles1/normanniles1_2025-10-26-14-48-45.mp4`
- Review date: 1 November 2026.
- Evidence: the user reports the same disturbance in Google Drive preview and local VLC playback. The supplied screenshots show vehicle fragments/overlapping vehicle images near the disturbance.
- Approximate onset: 48 seconds of playback. The exact affected frame range has not been established.
- Timestamp evidence in the local-playback screenshots: camera clock `10:48:28` at playback `00:47`; `10:48:29` and then `10:48:24` within playback `00:48`; `10:48:25` at `00:50`; `10:48:27` at `00:51`.
- Assessment: a reproducible video-quality/decoding disturbance with a backwards camera-clock jump. This is evidence against a problem confined to Drive preview. The exact recording, encoding or decoding cause has not been established from the screenshots.
- Full-clip manual reference count: **not yet established**. Do not enter an assumed count or treat a partial-interval count as a full-clip reference.
- Next manual action: record clearly observable crossings with their time interval, mark ambiguous events separately, and continue with clip 2. The earlier part of the clip still requires review before it can be treated as a reliable interval.
- Forecasting interpretation: the supplied target label is `free flowing`; the selected model predicted `light delay`. The disturbance may be relevant to extracted features, but its contribution to this prediction has not been established. The following target clip needs its own congestion/quality review.

The existing evaluation and its sample are retained. This finding does not justify removing a misclassified clip to improve the reported score. Any later quality-screened experiment should define a rule and apply it consistently to all eligible clips, with exclusions and original results documented.

Evidence files supplied by the user: `Screenshot (94).png` through `Screenshot (98).png`, plus the earlier Drive-preview screenshots. The video itself has not been inspected frame by frame by the assistant.

## Clip 2: normanniles1_2025-10-26-15-35-45.mp4

- Source path: `normanniles1/normanniles1_2025-10-26-15-35-45.mp4`
- Following target: `normanniles1/normanniles1_2025-10-26-15-36-45.mp4`
- Review date: 1 November 2026.
- User observation: a jump from seconds 27 to 31.
- Screenshot evidence: the embedded camera clock reads `11:36:27` in one screenshot and `11:36:32` in another. The latter shows player elapsed time `00:48` of `00:59`. No screenshot directly shows `11:36:31` or the consecutive frames at the reported transition.
- Timing interpretation: the screenshots suggest the reported seconds refer to the camera clock. Do not assume that playback `00:27` through `00:31` is the affected interval. Exact playback/frame positions, missing duration and whether frames are absent have not been verified.
- Assessment: **reported timing discontinuity; pending consecutive-frame/local-playback verification**. The provided evidence is from Google Drive preview. Local-playback confirmation for clip 1 does not independently confirm clip 2.
- Full-clip manual reference count: **not yet established**. Record clear crossing events, but do not invent counts for any unobservable interval. Mark the full count uncertain if the jump prevents an unambiguous crossing count.
- Forecasting interpretation: the supplied target label is `free flowing`; the selected model predicted `light delay`. The timing concern has not been established as the cause of that error.
- Next listed source clip: `normanniles2/normanniles2_2025-10-25-16-46-45.mp4`.

Both flagged clips are from camera 1 and were selected for review because of classification errors. This is not a representative sample for estimating the prevalence of recording problems. Review correctly classified clips and other cameras as well before drawing dataset-wide conclusions.

## Clip 3: normanniles2_2025-10-25-16-46-45.mp4

- Source path: `normanniles2/normanniles2_2025-10-25-16-46-45.mp4`
- Following target: `normanniles2/normanniles2_2025-10-25-16-47-45.mp4`
- Review date: 1 November 2026.
- User observation: no disturbance in this video.
- Assessment: **no visible playback disturbance reported by the user**. This does not independently verify vehicle counts, tracking or the following target's congestion label.
- Full-clip manual reference count: **pending**. Count physical vehicle crossings of the configured finite line, separately for entering/exiting cars, motorcycles, buses and trucks. A clean playback report is not a zero-vehicle count.
- Counting line: `(48, 270)` to `(912, 270)` in the original `960 x 540` frame (mid-height, 5% to 95% of image width).
- Forecasting interpretation: the supplied following-target label is `free flowing`; the selected model predicted `heavy delay`. Playback disturbance has not been reported for this source, so the label/prediction mismatch still needs investigation through source counts and target review.
- Next listed source clip: `normanniles2/normanniles2_2025-10-25-17-33-45.mp4`.

## Clip 4: normanniles2_2025-10-25-17-33-45.mp4

- Source path: `normanniles2/normanniles2_2025-10-25-17-33-45.mp4`
- Following target: `normanniles2/normanniles2_2025-10-25-17-34-45.mp4`
- Review date: 1 November 2026.
- User observation: no visible disturbance in this video.
- Assessment: **no visible playback disturbance reported by the user**. Vehicle counting and target-label review are separate checks and remain pending.
- Full-clip manual reference count: **pending**; no crossing counts have been supplied.
- Counting line: `(48, 270)` to `(912, 270)` in the original `960 x 540` frame. Record entering and exiting crossings separately for cars, motorcycles, buses and trucks.
- Forecasting interpretation: the supplied following-target label is `free flowing`; the selected model predicted `heavy delay`. A cause for this prediction error has not been established.
- Next listed source clip: `normanniles2/normanniles2_2025-10-26-13-10-45.mp4`.

## Clip 5: normanniles2_2025-10-26-13-10-45.mp4

- Source path: `normanniles2/normanniles2_2025-10-26-13-10-45.mp4`
- Following target: `normanniles2/normanniles2_2025-10-26-13-11-45.mp4`
- Review date: 1 November 2026.
- User observation: no visible disturbance reported.
- Assessment: **no visible playback disturbance reported by the user**. Vehicle counting and target-label review remain pending.
- Full-clip manual reference count: **pending**; no crossing counts have been supplied.
- Counting line: `(48, 270)` to `(912, 270)` in the original `960 x 540` frame. Record entering and exiting crossings separately for cars, motorcycles, buses and trucks.
- Forecasting interpretation: the supplied following-target label is `free flowing`; the selected model predicted `moderate delay`. A cause for this prediction error has not been established.
- Next listed source clip: `normanniles2/normanniles2_2025-10-26-14-42-45.mp4`.

## Clip 6: normanniles2_2025-10-26-14-42-45.mp4

- Source path: `normanniles2/normanniles2_2025-10-26-14-42-45.mp4`
- Following target: `normanniles2/normanniles2_2025-10-26-14-43-45.mp4`
- Review date: 1 November 2026.
- User observation: a disturbance in which the colour changes from white to orange.
- Screenshot evidence: two Google Drive preview frames at approximately `00:14` of `01:00`, with embedded camera times `10:43:01` and `10:43:02`. The scene appears warmer/brighter in the latter frame. These still images do not establish a missing-frame interval or its cause.
- Assessment: **reported colour/brightness shift around 14 seconds**. This is recorded separately from the timing discontinuities in clips 1 and 2. No local-playback confirmation or frame-by-frame inspection has been supplied for clip 6.
- Manual counting suitability: **not determined**. A colour shift alone does not make the count invalid. Continue counting if vehicles and line crossings remain unambiguous; record any actual occlusion, jump or ambiguous crossing separately. No full-clip reference count has been supplied.
- Counting line: `(48, 270)` to `(912, 270)` in the original `960 x 540` frame. Record entering and exiting crossings separately for cars, motorcycles, buses and trucks.
- Forecasting interpretation: the supplied following-target label is `free flowing`; the selected model predicted `light delay`. Neither a detection failure nor a causal link between the colour shift and this prediction has been established.
- Next listed source clip: `normanniles2/normanniles2_2025-10-26-17-06-45.mp4`.

Review progress after clip 6: three clips with no visible disturbance reported (3, 4, 5), two with timing/visual-discontinuity concerns (1, 2), one with a reported colour/brightness shift (6), and six clips awaiting playback-quality review (7-12). All manual reference counts remain pending.
