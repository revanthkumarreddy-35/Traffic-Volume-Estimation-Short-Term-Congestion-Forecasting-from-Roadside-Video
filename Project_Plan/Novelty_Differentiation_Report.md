# Novelty & Differentiation Report
## DSCI-41: Traffic Volume Estimation and Short-Term Congestion Forecasting from Roadside Video

**Project ID**: DSCI-41 | **Domain**: Visual Intelligence Systems | **Specialization**: AI Systems for Visual Intelligence

---

## 1. Introduction

This report presents a detailed comparison between our proposed capstone project and the existing body of research, including the faculty-assigned reference — the **Zindi Barbados Traffic Analysis Challenge** (Nov 2025 – Jan 2026). The purpose is to clearly document what has already been done, what gaps remain, and what our project will do differently to contribute new knowledge.

---

## 2. What Existing Research Has Done

### 2.1 Object Detection for Traffic (Published Papers)

Existing research papers on vehicle detection from CCTV/roadside cameras typically follow this pipeline:

**Input (Video Frame) → YOLO Detection → Bounding Boxes → Count**

| Paper Category | What They Do | What They DON'T Do |
|---|---|---|
| YOLOv8 vehicle counting papers (2023-2024) | Detect and count vehicles per frame using virtual counting lines | They stop at counting — no forecasting of future congestion |
| DeepSORT / ByteTrack tracking papers | Assign unique IDs to vehicles across frames to avoid double-counting | They test only on clear weather datasets (no rain, night, fog) |
| Perspective correction papers (Homography) | Use a 3×3 matrix to convert oblique camera angles to bird's-eye view | They correct perspective but never measure how much the correction improves downstream counting accuracy |
| Adverse weather detection papers (2024) | Test YOLOv8 on rain/fog/night images from ACDC or BDD100K datasets | They evaluate on static images only, never on continuous video streams where tracking also degrades |

**Gap identified**: Every paper treats detection, tracking, perspective correction, weather robustness, and forecasting as **isolated problems**. No published work connects them into a single end-to-end pipeline and measures how errors propagate from one stage to the next.

### 2.2 Traffic Forecasting (Published Papers)

Existing forecasting papers predict future traffic volume using time-series models:

| Paper Category | What They Do | What They DON'T Do |
|---|---|---|
| LSTM / Bi-LSTM traffic prediction papers | Predict traffic volume 15-60 minutes ahead using historical count data | Their input data comes from inductive loop sensors or GPS traces — NOT from a camera/vision system |
| CNN-LSTM hybrid papers | Combine spatial (CNN) and temporal (LSTM) features for better accuracy | They assume the input count data is perfect (no detection errors) |
| XGBoost traffic papers | Use gradient boosting with tabular features (time, day, weather) | The "weather" feature is manually entered — not automatically detected from the video |
| Graph Neural Network papers | Model spatial dependencies between multiple road segments | Require a graph of the road network — over-engineered for a single camera location |

**Gap identified**: Every forecasting paper assumes **clean, sensor-grade input data**. None of them study what happens when the input comes from a noisy, error-prone computer vision system where rain causes missed detections and night causes false positives.

### 2.3 The Reference Paper: Zindi Barbados Traffic Analysis Challenge

The faculty-assigned reference is a data science competition, not a traditional research paper. Here is exactly what the competition did and did not do:

**What the Zindi competition DID:**
- Provided 4 video streams from a roundabout in Barbados
- Required participants to predict congestion levels (free flowing / light / moderate / heavy delay) 5 minutes into the future
- Used Macro-F1 (70%) + Accuracy (30%) as the evaluation metric
- Winners used feature engineering from video (object detection → counting → tabular features → classification)

**What the Zindi competition DID NOT do:**

| Limitation | Explanation |
|---|---|
| No adverse weather testing | All Barbados videos were recorded in clear, tropical weather. There is zero rain, fog, or night-time footage in the dataset |
| No perspective handling | The cameras were fixed at specific angles. Winners did not need to handle oblique views or cross-camera generalisation |
| No real-time deployment | It was an offline competition — participants processed pre-recorded video. No live camera feed was involved |
| No uncertainty quantification | All predictions were single-class labels. No confidence intervals or "I don't know" abstention mechanism existed |
| No error propagation study | Winners did not analyse how detection errors in the vision system affected the quality of the congestion forecast |
| Single location only | The entire competition was limited to one roundabout in Barbados. No generalisation to other roads or countries was attempted |
| Backpropagation banned | The competition rules prohibited end-to-end neural network training, forcing participants to use only classical feature engineering |

---

## 3. What OUR Project Does Differently (Novel Contributions)

Our project addresses five specific gaps that neither existing research papers nor the Zindi reference competition have solved. Each contribution is designed to be independently testable and measurable — as required by the KL University capstone evaluation framework (O3 contribution isolation).

### 3.1 Contribution 1: End-to-End Vision-to-Forecast Pipeline with Error Propagation Analysis

**What exists**: Detection papers stop at counting. Forecasting papers start with clean sensor data. Nobody connects the two.

**What we do differently**: We build a single pipeline where the vision module's output (vehicle counts) feeds directly into the forecasting module. Critically, we **measure error propagation** — i.e., we quantify how much a 10% detection error during rain translates into forecasting error.

**How we measure it**:
- Run the forecaster with **ground-truth counts** (from the Zindi reference) → Record forecast accuracy (Baseline A)
- Run the forecaster with **vision-estimated counts** (from our YOLO + ByteTrack pipeline) → Record forecast accuracy (Baseline B)
- Calculate the **propagation gap** = Baseline A – Baseline B
- Report this gap per condition (clear / rain / night)

**Why it matters**: If the gap is large during rain, it tells traffic authorities that the system's forecasts should not be trusted blindly during bad weather. No prior work provides this information.

### 3.2 Contribution 2: Condition-Aware Adaptive Preprocessing

**What exists**: Current systems apply the same preprocessing to every frame regardless of weather. Papers either always apply CLAHE (brightness enhancement) or never apply it.

**What we do differently**: We build a lightweight **condition classifier** (a small CNN or even a rule-based model using histogram analysis) that automatically tags each incoming frame as one of: `clear | rain | night | fog`. Based on this tag, the system applies **condition-specific preprocessing**:

| Detected Condition | Preprocessing Applied |
|---|---|
| Clear / Daytime | None (raw frame) |
| Night / Low Light | CLAHE (Contrast Limited Adaptive Histogram Equalization) |
| Rain | Deraining filter + contrast enhancement |
| Fog | Dark Channel Prior dehazing |

**Why it matters**: Applying CLAHE to bright daytime frames actually **degrades** detection accuracy by introducing artifacts. Our adaptive approach avoids this problem. No prior traffic counting paper implements this automatic switching.

### 3.3 Contribution 3: Confidence-Weighted Soft Counting

**What exists**: Every existing vehicle counting system uses **hard counting** — if YOLO detects a vehicle (regardless of confidence), it counts as exactly 1.

**What we do differently**: We introduce **soft counting**, where each detection is weighted by its confidence score:

```
Hard count:  Car (0.95) = 1,  Car (0.55) = 1,  Total = 2
Soft count:  Car (0.95) = 0.95,  Car (0.55) = 0.55,  Total = 1.50
```

**Why it matters**: During rain or night, YOLO produces many low-confidence detections (it's "guessing"). Soft counting naturally captures this uncertainty and passes it downstream to the forecaster. The forecaster then learns that low soft-counts indicate uncertain input, enabling it to produce wider confidence intervals for its predictions.

**How we validate**: Compare hard-count-based forecasting vs. soft-count-based forecasting. We expect soft counting to produce:
- Similar accuracy during clear weather (both methods work well)
- **Better accuracy during adverse weather** (soft counting avoids over/under-counting)

### 3.4 Contribution 4: Weather-Conditioned Forecasting

**What exists**: Current LSTM and XGBoost forecasting models take only two types of input: (1) past vehicle counts and (2) time features (hour, day of week). They are completely **blind to weather conditions**.

**What we do differently**: We add the **automatically detected weather condition** (from Contribution 2's classifier) as an explicit input feature to the forecasting model:

```
Existing model input:  [count_t-1, count_t-2, ..., hour, day_of_week]
OUR model input:       [count_t-1, count_t-2, ..., hour, day_of_week, weather_tag, avg_confidence]
```

Where:
- `weather_tag` = {0: clear, 1: rain, 2: night, 3: fog} — from condition classifier
- `avg_confidence` = mean YOLO detection confidence for that time interval — from soft counting

**Why it matters**: Traffic behaves fundamentally differently during rain (slower speeds, more cautious driving, longer congestion). A model that knows it's raining can predict "congestion will last 30 minutes" instead of the standard "congestion will clear in 15 minutes." The Zindi Barbados competition did not have adverse weather data, so this capability was never developed or tested.

### 3.5 Contribution 5: Real-Time Deployment on Live Camera Feeds

**What exists**: The Zindi Barbados competition was entirely offline (pre-recorded videos processed in notebooks). All published papers also evaluate on recorded datasets.

**What we do differently**: We demonstrate our system running in **real-time** on:
1. **YouTube live traffic camera streams** (24/7 feeds from various cities)
2. **Our own recorded Indian traffic footage** (from a camera near KL University)

We build a **Streamlit dashboard** that shows:
- Live video feed with bounding boxes around detected vehicles
- Real-time vehicle count (updated every 5 minutes)
- Congestion forecast for the next 15-30 minutes
- Confidence indicator ("System is confident" vs. "Uncertain — adverse conditions detected")

**Why it matters**: This transforms the project from a research exercise into a deployable prototype. No published paper or Zindi entry has demonstrated a live, end-to-end traffic forecasting system.

---

## 4. Direct Comparison with Specific State-of-the-Art Papers

To further highlight our novelty, here is how our proposed pipeline compares directly to recent, highly-cited research papers published in 2023–2024 on similar topics.

| State-of-the-Art Paper | Their Core Approach | What They Missed | How DSCI-41 Solves It |
|---|---|---|---|
| **Chen & Chen (2024)**<br>*"CNN-LSTM Hybrid for Short-Term Traffic Flow Prediction"* | High-accuracy forecasting using spatial-temporal CNN-LSTM hybrids. | Relied entirely on clean inductive loop sensor data. Did not address vision-based detection errors. | Uses computer vision directly and feeds soft-counts + weather context into the LSTM, closing the gap between noisy vision and forecasting. |
| **Zhang et al. (2022)**<br>*"ByteTrack: Multi-Object Tracking by Associating Every Detection Box"* | Best-in-class multi-object tracking for dense traffic using YOLO. | Tested primarily on daytime/clear datasets. Fails silently during heavy rain when detection confidence drops. | Implements weather-aware adaptive preprocessing (CLAHE/derain) *before* tracking to maintain ByteTrack's accuracy at night and in rain. |
| **Sakaridis et al. (2021)**<br>*"ACDC: The Adverse Conditions Dataset"* | Trained semantic models to detect vehicles in fog, rain, and snow. | Evaluated purely on static image benchmarks. Did not track vehicles or estimate traffic volume. | Applies adverse-weather weights to a continuous video stream, enabling robust counting and flow estimation under harsh conditions. |
| **Zindi Barbados Challenge (2026)**<br>*"Traffic Analysis Winning Solutions"* | Feature engineering (time in roundabout, flow rate) + classification algorithms. | Offline only. Clean tropical weather. Single static roundabout. No error propagation study. | Real-time deployment. Handles adverse weather actively. Implements confidence-weighted counting to quantify uncertainty. |

---

## 5. Summary Comparison Table

| Feature | Existing Papers | Zindi Barbados (Reference) | OUR Project |
|---|---|---|---|
| Vehicle Detection | ✅ YOLO-based | ✅ YOLO-based | ✅ YOLOv8 (same baseline) |
| Multi-Object Tracking | ✅ DeepSORT / ByteTrack | ✅ Used by winners | ✅ ByteTrack (same baseline) |
| Perspective Handling | ✅ Homography | ❌ Not needed (fixed cameras) | ✅ Homography + cross-camera validation |
| Adverse Weather Robustness | ⚠️ Static images only | ❌ All clear weather | ✅ **Video-level testing on rain/night/fog** |
| Adaptive Preprocessing | ❌ Same for all frames | ❌ Not attempted | ✅ **Condition-specific (CLAHE/dehaze/derain)** |
| Soft Counting | ❌ Hard count only | ❌ Hard count only | ✅ **Confidence-weighted soft counts** |
| Congestion Forecasting | ⚠️ From sensors only | ✅ From video features | ✅ **From vision counts + weather tag** |
| Weather as Forecast Input | ❌ Not used | ❌ No weather data | ✅ **Auto-detected weather feeds into forecaster** |
| Error Propagation Study | ❌ Not studied | ❌ Not studied | ✅ **Measured per condition** |
| Uncertainty / Confidence | ❌ Single prediction | ❌ Single class label | ✅ **Prediction + confidence intervals** |
| Real-Time Live Demo | ❌ Offline only | ❌ Offline competition | ✅ **Live YouTube + local camera feed** |
| Indian Traffic Testing | ❌ Western data only | ❌ Barbados only | ✅ **Indian mixed traffic (autos, bikes, trucks)** |

---

## 6. How Each Novel Contribution Maps to Project Objectives

| Novel Contribution | CP-1 or CP-2 | Objective |
|---|---|---|
| End-to-End Pipeline + Error Propagation | CP-2 | O4 (Integration) + O5 (Validation) |
| Adaptive Preprocessing | CP-2 | O3 (Differentiating Contribution) |
| Confidence-Weighted Soft Counting | CP-1 (design) + CP-2 (implement) | O2 (Reference) + O3 (Contribution) |
| Weather-Conditioned Forecasting | CP-2 | O4 (Integration) |
| Real-Time Live Demo | CP-2 | O4 (Integration) + O5 (Final Demo) |

---

## 7. Conclusion

Our project builds upon the Zindi Barbados Traffic Analysis Challenge reference and extends it in five measurable ways. While the reference competition solved the problem of predicting roundabout congestion from clear-weather video, our project tackles the harder, real-world problem of maintaining accuracy under adverse conditions, quantifying uncertainty, and deploying the system in real-time on live camera feeds.

The combination of adaptive preprocessing, confidence-weighted counting, and weather-conditioned forecasting represents a genuine technical contribution that has not been published in any prior research paper on traffic volume estimation from roadside video.

---

## 8. References

1. Zindi Africa, "Barbados Traffic Analysis Challenge," 2025-2026. [Online]. Available: https://zindi.africa/competitions/barbados-traffic-analysis-challenge
2. G. Jocher et al., "Ultralytics YOLOv8," 2023. [Online]. Available: https://github.com/ultralytics/ultralytics
3. Y. Zhang et al., "ByteTrack: Multi-Object Tracking by Associating Every Detection Box," ECCV, 2022.
4. N. Wojke et al., "Simple Online and Realtime Tracking with a Deep Association Metric (DeepSORT)," ICIP, 2017.
5. S. Hochreiter and J. Schmidhuber, "Long Short-Term Memory," Neural Computation, vol. 9, no. 8, 1997.
6. T. Chen and C. Guestrin, "XGBoost: A Scalable Tree Boosting System," KDD, 2016.
7. C. Sakaridis et al., "ACDC: The Adverse Conditions Dataset with Correspondences for Semantic Driving Scene Understanding," ICCV, 2021.
8. F. Yu et al., "BDD100K: A Diverse Driving Dataset for Heterogeneous Multitask Learning," CVPR, 2020.
9. S. Bai et al., "An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling (TCN)," arXiv:1803.01271, 2018.
10. J. Redmon et al., "You Only Look Once: Unified, Real-Time Object Detection," CVPR, 2016.
