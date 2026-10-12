# 📚 Literature Review & Algorithm Study
## DSCI-41: Traffic Volume Estimation and Short-Term Congestion Forecasting from Roadside Video

---

## 1. Reference Paper: Zindi Barbados Traffic Analysis Challenge

### Competition Overview
- **Platform**: Zindi (Africa's largest data science competition platform)
- **Prize**: $11,000 USD total
- **Participants**: 1,855 joined, 216 active
- **Timeline**: Nov 2025 – Jan 2026 (Completed)
- **Data**: 4 streams of video data from the **Norman Niles Roundabout** in Barbados
- **License**: CC-BY SA 4.0

### Problem Statement
> *"Can you predict traffic flow to identify the root causes of traffic in a Barbados roundabout?"*

Participants were given video feeds from 4 cameras at a roundabout. For each 5-minute time segment, they had to predict a **congestion rating** (one of 4 classes) for both the **entrance** and **exit** of each camera's view.

### Evaluation Metric
The competition used **Multi-Metric Evaluation**:
- **Macro-F1 Score (70% weight)**: Measures balanced performance across all 4 congestion classes (important because some classes are rare).
- **Accuracy (30% weight)**: Overall percentage of correct predictions.

### Key Constraint
> **Back-propagation is not allowed in training or inference.**

This is a critical rule — it forces participants to use **feature engineering from video** (object detection, tracking, counting) rather than training an end-to-end neural network directly on the raw video frames.

### Competition Winners & Their Approaches
| Rank | Team | Methodology |
|------|------|-------------|
| 1st ($4,500) | Team4Star (21db, wuuthraad) | Feature engineering from video + time-series classification |
| 2nd ($2,500) | iam-dante | Object detection + movement pattern analysis |
| 3rd ($1,500) | Team Egy (Belal_Emad, Mohamed_abdelrazik) | Vehicle tracking + flow rate features |
| Best Analysis | TeamTraffic_Solvers (nymfree, keystats) | Interpretable contributing factor analysis |

### What Top Solutions Did
1. **Object Detection & Tracking**: Used YOLO-based models to detect vehicles (cars, buses, taxis) and tracked their movement through the roundabout.
2. **Feature Engineering**: Extracted features like vehicle counts, entry/exit timings, time spent in roundabout, and flow rates.
3. **Time-Series Classification**: Treated it as a sequential problem — predicting congestion 5 minutes into the future based on 15 minutes of prior video data.
4. **Class Imbalance Handling**: Used techniques to ensure "heavy delay" instances (which are rarer) were not ignored.
5. **Interpretability**: Winning solutions focused on explaining *why* congestion occurred (e.g., "high bus count at entrance 2 correlates with heavy delay at exit 3").

---

## 2. Object Detection Algorithms (CP-1: O1 & O2)

### 2.1 YOLO Family (You Only Look Once)

YOLO is the dominant algorithm for real-time vehicle detection in traffic video analytics.

| Version | Year | Key Innovation | Speed (FPS) | mAP (COCO) |
|---------|------|----------------|-------------|-------------|
| YOLOv5 | 2020 | PyTorch-native, anchor-based | ~140 | 50.7% |
| YOLOv7 | 2022 | E-ELAN architecture, trainable bag-of-freebies | ~120 | 56.8% |
| **YOLOv8** | **2023** | **Anchor-free, decoupled head, state-of-the-art** | **~80** | **53.9%** |
| YOLOv9 | 2024 | Programmable Gradient Information (PGI) | ~85 | 55.6% |
| YOLOv10 | 2024 | NMS-free, consistent dual assignments | ~90 | 54.4% |
| YOLO11 | 2024 | C3k2 blocks, SPPF, attention modules | ~75 | 56.1% |

> [!TIP]
> **Recommended for your project**: Start with **YOLOv8** as the baseline (most widely used and documented). For CP-2, consider upgrading to **YOLO11** with custom adverse-weather modules.

### 2.2 How YOLO Works (Summary)
1. **Single-pass detection**: Unlike older methods (R-CNN) that scan an image multiple times, YOLO divides the image into a grid and predicts bounding boxes + class probabilities in a single forward pass.
2. **Anchor-free (v8+)**: YOLOv8 eliminates preset anchor boxes, instead predicting object centers directly. This improves detection of vehicles at unusual scales.
3. **Multi-scale detection**: Uses a Feature Pyramid Network (FPN) to detect both large trucks and small motorcycles in the same frame.

### 2.3 Faster R-CNN (Alternative)
- **Architecture**: Two-stage detector (Region Proposal Network + classifier).
- **Accuracy**: Generally higher mAP than YOLO on static images.
- **Speed**: ~5–15 FPS (much slower than YOLO).
- **When to use**: When accuracy matters more than speed (e.g., offline analysis of recorded video).

> [!NOTE]
> For **real-time traffic video**, YOLO is strongly preferred over Faster R-CNN due to its speed advantage. Research consistently shows YOLOv8 achieves >95% accuracy in vehicle counting when combined with tracking.

---

## 3. Multi-Object Tracking Algorithms (CP-1: O1 & O2)

After detecting vehicles in each frame, you need to **track** them across frames to count unique vehicles (not count the same car twice).

### 3.1 DeepSORT (Deep Simple Online and Realtime Tracking)
- **How it works**: Combines a Kalman Filter (predicts where the object will move next) with a deep appearance descriptor (a small CNN that encodes what the car "looks like").
- **Strengths**: Excellent at re-identifying vehicles after short occlusions (e.g., a car hidden behind a bus for 2 seconds).
- **Weaknesses**: Slower than ByteTrack due to the appearance model; struggles in very crowded scenes.
- **Key metric**: MOTA (Multi-Object Tracking Accuracy), IDF1 (Identity F1 Score).

### 3.2 ByteTrack
- **How it works**: Uses **every detection box** (even low-confidence ones) for association. Two-step matching: first matches high-confidence detections, then uses remaining low-confidence ones to recover lost tracks.
- **Strengths**: Faster than DeepSORT; handles heavy occlusion better because it doesn't discard low-confidence detections.
- **Weaknesses**: No appearance model, so it can confuse similar-looking vehicles.

### 3.3 BoT-SORT (2022)
- **How it works**: Combines camera motion compensation + Kalman filter + Re-ID features.
- **Strengths**: Best MOTA scores on MOT benchmarks; handles camera shake well.

### Comparison Table

| Algorithm | Speed | Occlusion Handling | Re-ID After Loss | Best For |
|-----------|-------|-------------------|-------------------|----------|
| DeepSORT | Medium | Good | Excellent | Fixed cameras with moderate traffic |
| **ByteTrack** | **Fast** | **Excellent** | Good | **Dense traffic, crowded scenes** |
| BoT-SORT | Slow | Excellent | Excellent | Research benchmarks |

> [!TIP]
> **Recommended for your project**: Use **ByteTrack** for CP-1 (faster, handles dense traffic well). In CP-2, consider adding a lightweight Re-ID module on top for rain/night conditions where appearance features help.

---

## 4. Perspective Handling & Camera Geometry (CP-1: O2)

### 4.1 The Problem
Roadside cameras are mounted at oblique angles (not directly overhead). This causes:
- **Size distortion**: Cars far away appear much smaller than cars nearby.
- **Shape distortion**: Vehicles look "squished" or stretched depending on the viewing angle.
- **Counting errors**: The same physical area covers different pixel areas at different depths.

### 4.2 Homography-Based Perspective Transform
The most common solution is to apply a **homography matrix** to transform the oblique view into a **Bird's Eye View (BEV)**.

**How it works:**
1. Select 4+ corresponding points on the road surface (e.g., lane markings) in both the camera view and a top-down reference.
2. Compute the 3x3 homography matrix `H` using OpenCV's `cv2.findHomography()`.
3. Apply the transformation: `BEV_point = H * camera_point`.

### 4.3 Recent Research Methods (2023-2024)
| Method | Description |
|--------|-------------|
| **SDD-UNet** | Deep learning model that directly converts oblique views to BEV images |
| **CAMOT** | Camera Angle-aware Multi-Object Tracking — dynamically estimates camera angles |
| **Automated Calibration** | Uses blob detection or transformer models to auto-detect calibration points |
| **Two-Camera Fusion** | Uses two viewpoints to recover trajectories lost to occlusion |

> [!IMPORTANT]
> For your project, start with **manual homography** (select 4 points on the road using OpenCV) for CP-1. In CP-2, you can automate this process as part of the "cross-camera generalisation" KPI.

---

## 5. Adverse Weather & Low-Light Detection (CP-2: O3)

This is your **differentiating contribution** — the core technical novelty of your project.

### 5.1 The Challenge
| Condition | Effect on Detection |
|-----------|-------------------|
| **Rain** | Reflections, water droplets on lens, reduced contrast |
| **Night/Low Light** | Dark frames, headlight glare, loss of color information |
| **Occlusion** | Vehicles hidden behind other vehicles, especially in dense traffic |
| **Fog** | Reduced visibility, blurred edges |

### 5.2 Research Methods to Handle Adverse Conditions

#### A. Data Augmentation (Simplest, Most Common)
- Apply synthetic rain, fog, and darkness to training images using libraries like **Albumentations** or **imgaug**.
- Train the model on a mix of clean + augmented images so it learns to detect vehicles under all conditions.

#### B. Transfer Learning with Adverse Weather Datasets
Key datasets for training robust models:
| Dataset | Conditions | Size |
|---------|-----------|------|
| **ACDC** (Adverse Conditions Dataset with Correspondences) | Fog, Night, Rain, Snow | 4,006 images |
| **DAWN** (Detection in Adverse Weather Nature) | Fog, Rain, Sand, Snow | 1,000 images |
| **BDD100K** | Day, Night, Rain, Overcast | 100K images |
| **ExDark** | Low-light exclusive | 7,363 images |

#### C. Architecture Modifications (Advanced)
Recent papers propose modifying the YOLO backbone to handle weather:
- **SCConv (Self-Calibrated Convolutions)**: Reduces feature redundancy, improves detection in noisy images.
- **Focaler-EIoU Loss**: Custom loss function that focuses training on hard-to-detect objects (like rain-obscured vehicles).
- **ECL-YOLOv11**: Adds Convolutional Edge-enhancement (CE) and Context-guided Multi-scale Fusion (AENet) to preserve boundary information under blurred conditions.

#### D. Image Preprocessing Pipeline
Before feeding frames to the detector:
1. **Dehazing/Defogging**: Apply dark channel prior or AOD-Net.
2. **Low-Light Enhancement**: Use CLAHE (Contrast Limited Adaptive Histogram Equalization) or Zero-DCE.
3. **Rain Streak Removal**: Apply image deraining networks (e.g., DerainNet).

> [!TIP]
> **Recommended approach for CP-2 (O3)**:
> 1. Start with **Data Augmentation** + **Transfer Learning** using ACDC/BDD100K (easiest to implement, strong results).
> 2. Add **CLAHE preprocessing** for night images.
> 3. If time permits, modify the YOLO backbone with SCConv for your final contribution.

---

## 6. Short-Term Congestion Forecasting (CP-2: O4)

### 6.1 Overview
Once you have vehicle counts from the vision pipeline, you feed them into a **time-series forecasting model** to predict future traffic volume.

### 6.2 Algorithms Studied in Literature

#### A. LSTM (Long Short-Term Memory)
- **Type**: Recurrent Neural Network (RNN) variant.
- **How it works**: Maintains a "memory cell" that can learn long-term dependencies in sequential data.
- **Input**: Sequence of past vehicle counts (e.g., last 12 five-minute intervals = 1 hour of history).
- **Output**: Predicted vehicle count for the next 1-3 intervals (5-15 minutes ahead).
- **Performance**: Standard baseline for traffic prediction. MAE typically 5-15% of actual counts.

#### B. Bi-LSTM (Bidirectional LSTM)
- **How it works**: Processes the time series in both forward and backward directions.
- **Benefit**: Captures both past trends and future context.

#### C. CNN-LSTM Hybrid
- **How it works**: Uses 1D-CNN to extract local temporal patterns, then feeds them to an LSTM for sequence modeling.
- **Benefit**: Faster convergence, better at capturing periodic patterns (e.g., rush hour repeats daily).

#### D. Temporal Convolutional Network (TCN)
- **How it works**: Uses dilated causal convolutions instead of recurrence.
- **Benefit**: Parallelizable (faster to train than LSTM), handles longer sequences better.
- **Status**: Increasingly preferred over LSTM in 2024-2025 literature.

#### E. Hierarchical-Attention-LSTM
- **How it works**: Adds attention mechanisms to weigh the importance of different time steps.
- **Benefit**: Focuses on the most informative parts of the input sequence (e.g., gives more weight to rush-hour data when predicting evening congestion).

#### F. XGBoost / LightGBM (Gradient Boosting)
- **Type**: Traditional ML (not deep learning).
- **Input**: Tabular features (vehicle count, time of day, day of week, weather code).
- **Benefit**: Fast, interpretable, often competitive with deep learning for structured data.
- **Status**: Many Zindi competition winners used gradient boosting with engineered features.

### Comparison Table

| Model | Accuracy | Training Speed | Interpretability | Best For |
|-------|----------|---------------|-----------------|----------|
| LSTM | Good | Slow | Low | Standard baseline |
| CNN-LSTM | Very Good | Medium | Low | Capturing periodic patterns |
| **TCN** | **Very Good** | **Fast** | Low | **Long sequences, real-time** |
| Attention-LSTM | Excellent | Very Slow | Medium | Research/best accuracy |
| **XGBoost** | **Good** | **Very Fast** | **High** | **Interpretable features, quick results** |

> [!TIP]
> **Recommended approach for CP-2 (O4)**:
> 1. Start with **XGBoost** as a strong baseline (fast, interpretable — matches the Zindi winner approach).
> 2. Implement **LSTM or TCN** as the deep learning alternative.
> 3. Compare both and report which works better for your dataset. This comparison itself is valuable for your research paper.

---

## 7. End-to-End System Architecture (How Everything Connects)

```
Roadside Video ──▶ Preprocess (CLAHE, Dehaze) ──▶ YOLOv8 Detection ──▶ ByteTrack Tracking ──▶ Counting Logic (Virtual Lines)
                                                                                                        │
                                                                                                 Vehicle Counts
                                                                                                 (time series)
                                                                                                        │
                                                                                                        ▼
Dashboard (Streamlit/React) ◀── Congestion Warning ◀── LSTM/TCN or XGBoost Forecaster ◀── Feature Engineering (time, day, weather)
```

---

## 8. Recommended Algorithms for Each Objective

| Objective | Algorithm | Why |
|-----------|-----------|-----|
| **O1**: Baseline counter | YOLOv8 + ByteTrack + Virtual Line counting | Industry standard, well-documented, fast |
| **O2**: Mixed vehicles & perspective | YOLOv8 (multi-class) + OpenCV Homography | Handles multiple vehicle types + corrects oblique angle |
| **O3**: Rain/Night robustness | YOLOv8 + ACDC/BDD100K fine-tuning + CLAHE + Data Augmentation | Proven techniques from 2024 literature |
| **O4**: Congestion forecasting | XGBoost (baseline) + LSTM/TCN (deep learning) | XGBoost for interpretability, LSTM/TCN for accuracy comparison |
| **O5**: Validation | Macro-F1 + Accuracy (matching Zindi metric) | Directly aligned with the reference competition |

---

## 9. Key Research Papers to Cite

1. **Redmon et al. (2016)** — "You Only Look Once: Unified, Real-Time Object Detection" — *Original YOLO paper*
2. **Jocher et al. (2023)** — "Ultralytics YOLOv8" — *Current state-of-the-art detector*
3. **Wojke et al. (2017)** — "Simple Online and Realtime Tracking with a Deep Association Metric" — *DeepSORT*
4. **Zhang et al. (2022)** — "ByteTrack: Multi-Object Tracking by Associating Every Detection Box" — *ByteTrack*
5. **Hochreiter & Schmidhuber (1997)** — "Long Short-Term Memory" — *LSTM foundational paper*
6. **Chen & Chen (2024)** — "CNN-LSTM Hybrid for Short-Term Traffic Flow Prediction" — *Hybrid forecasting*
7. **Bai et al. (2018)** — "An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling" — *TCN vs LSTM comparison*
8. **Sakaridis et al. (2021)** — "ACDC: The Adverse Conditions Dataset with Correspondences" — *Key adverse weather dataset*
9. **Yu et al. (2020)** — "BDD100K: A Diverse Driving Dataset for Heterogeneous Multitask Learning" — *BDD100K dataset*
10. **Chen & Guestrin (2016)** — "XGBoost: A Scalable Tree Boosting System" — *XGBoost*
