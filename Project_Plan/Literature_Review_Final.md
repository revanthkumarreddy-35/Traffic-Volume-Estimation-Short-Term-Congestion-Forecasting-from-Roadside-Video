# Literature Review
## Traffic Volume Estimation and Short-Term Congestion Forecasting from Roadside Video
### DSCI-41 | Capstone Project

---

## 1. Introduction

Intelligent Transportation Systems (ITS) increasingly rely on automated vehicle counting from roadside CCTV cameras as a cost-effective alternative to traditional loop detectors and radar-based sensors. While significant progress has been made in object detection and multi-object tracking, reliable vehicle perception under real-world conditions, including occlusions, varying vehicle scales, and complex intersection geometries, remains an active research challenge. This literature review examines the state-of-the-art methods in object detection, multi-object tracking, camera perspective handling, adverse weather robustness, and short-term traffic forecasting, with a focus on identifying the algorithms best suited for building a real-time vehicle counting and congestion prediction pipeline.

---

## 2. Reference Paper: Zindi Barbados Traffic Analysis Challenge (2025-2026)

The Barbados Traffic Analysis Challenge, hosted on the Zindi platform, serves as the primary reference for this project. The competition provided 4 streams of video data from the Norman Niles Roundabout in Barbados and tasked 1,855 participants with predicting congestion ratings for each 5-minute segment. The evaluation metric combined Macro-F1 Score (70% weight) with Accuracy (30% weight). A critical constraint prohibited back-propagation during training or inference, forcing participants to rely on feature engineering from detected objects rather than end-to-end video classification.

The winning solutions (Team4Star, iam-dante, Team Egy) consistently employed a three-stage pipeline: (i) YOLO-based vehicle detection, (ii) feature engineering from tracking trajectories, and (iii) time-series classification using gradient boosting or ensemble methods. This pipeline validates the detection-tracking-forecasting architecture adopted in our proposed methodology.

---

## 3. Object Detection Algorithms

### 3.1 Evolution of YOLO (You Only Look Once)

The YOLO architecture, first proposed by Redmon et al. (2016), revolutionized real-time object detection by performing detection in a single forward pass. Unlike two-stage detectors such as Faster R-CNN (Ren et al., 2015), YOLO divides the input image into a grid and simultaneously predicts bounding box coordinates, objectness scores, and class probabilities.

| Version | Year | Authors | Key Innovation | Speed (FPS) | mAP (COCO) |
|---------|------|---------|---------------|-------------|------------|
| YOLOv3 | 2018 | Redmon and Farhadi | Multi-scale prediction, Darknet-53 backbone | ~65 | 33.0% |
| YOLOv4 | 2020 | Bochkovskiy et al. | CSPDarknet53, Mish activation, mosaic augmentation | ~65 | 43.5% |
| YOLOv5 | 2020 | Jocher et al. | PyTorch-native, anchor-based, Focus module | ~140 | 50.7% |
| YOLOv7 | 2022 | Wang et al. | E-ELAN architecture, trainable bag-of-freebies | ~120 | 56.8% |
| YOLOv8 | 2023 | Jocher et al. | Anchor-free, decoupled head, C2f module | ~80 | 53.9% |
| YOLOv9 | 2024 | Wang et al. | Programmable Gradient Information (PGI), GELAN | ~85 | 55.6% |
| YOLO11 | 2024 | Ultralytics | C3k2 blocks, SPPF, attention modules | ~75 | 56.1% |

YOLOv8 (Jocher et al., 2023) introduces anchor-free detection and a decoupled prediction head, which improves detection of vehicles at unusual scales. Its multi-scale Feature Pyramid Network (FPN) enables simultaneous detection of both large trucks and small motorcycles within the same frame.

### 3.2 Faster R-CNN

Faster R-CNN (Ren et al., 2015) is a two-stage detector consisting of a Region Proposal Network (RPN) followed by a classification head. While it generally achieves higher mAP on static images, its processing speed of 5-15 FPS renders it unsuitable for real-time traffic video analysis where 25-30 FPS throughput is required.

### 3.3 SSD (Single Shot MultiBox Detector)

SSD (Liu et al., 2016) provides a middle ground between YOLO and Faster R-CNN by using multi-scale feature maps for detection without region proposals. While faster than Faster R-CNN at ~46 FPS, it has been largely superseded by the YOLO family for traffic applications due to YOLO's superior accuracy-speed trade-off.

### 3.4 Object Detection in Traffic Videos: Survey Findings

A comprehensive survey published in IEEE Transactions on Intelligent Transportation Systems (2023) evaluates object detection architectures specifically for traffic scenarios. The survey confirms that one-stage detectors (YOLO family) dominate real-time traffic applications, while two-stage detectors remain relevant for offline analysis where accuracy is prioritized over speed. Recent implementations, such as YOLO with Centroid Tracking (2024), demonstrate scalable counting systems achieving over 95% accuracy in high-density urban traffic when combined with tracking algorithms.

---

## 4. Multi-Object Tracking Algorithms

Object detection alone is insufficient for vehicle counting, as the same vehicle detected across consecutive frames would be counted multiple times. Multi-object tracking (MOT) algorithms assign persistent identities to detected objects across frames.

### 4.1 SORT (Simple Online and Realtime Tracking)

SORT (Bewley et al., 2016) uses a Kalman Filter for state estimation combined with the Hungarian algorithm for data association based on Intersection over Union (IoU). While extremely fast, it suffers from frequent identity switches when objects are temporarily occluded.

### 4.2 DeepSORT

DeepSORT (Wojke et al., 2017) extends SORT by incorporating a deep appearance descriptor, which is a small CNN that encodes the visual features of each detected object. This appearance model enables re-identification of vehicles after short occlusions. The association cost function combines both motion (Mahalanobis distance) and appearance (cosine distance) metrics. However, the computational overhead of the appearance model reduces processing speed, making it less suitable for dense traffic scenarios.

### 4.3 ByteTrack

ByteTrack (Zhang et al., 2022) introduces a fundamentally different approach by associating every detection box, including low-confidence detections, rather than discarding them. The algorithm performs two-step matching: it first associates high-confidence detections with existing tracks using IoU, then matches remaining low-confidence detections to recover tracks that were temporarily lost due to occlusion. This approach achieves 80.3 MOTA on the MOT17 benchmark while running at 30+ FPS, demonstrating superior performance in dense, occluded traffic scenes without requiring a computationally expensive appearance model.

### 4.4 BoT-SORT

BoT-SORT (Aharon et al., 2022) combines camera motion compensation with Kalman filtering and Re-ID features. It achieves the highest MOTA scores on standard MOT benchmarks (e.g., 80.5 MOTA on MOT17) by compensating for camera shake and incorporating appearance features. However, its computational cost is significantly higher than ByteTrack.

### 4.5 StrongSORT

StrongSORT (Du et al., 2023) builds upon DeepSORT with improved feature extraction using OSNet for appearance modeling and enhanced Camera Motion Compensation (CMC). It provides high-precision tracking but at slower speeds, making it more suitable for offline processing or scenarios with unstable camera installations.

### 4.6 Traffic Impact Assessment using YOLOv5 and ByteTrack

Ng, Goh, and Tee (2023) present a practical Traffic Impact Assessment System that integrates YOLOv5 for vehicle detection with ByteTrack for multi-object tracking, specifically designed to address heavy traffic congestion in Malaysia. Their system allows users to draw specific regions and counting lines across camera feeds to record vehicle counts per junction. Notably, the study includes a comparative evaluation of ByteTrack against StrongSORT and OC-SORT, confirming ByteTrack's superior balance of speed and accuracy for real-time traffic monitoring. The system also analyzes vehicle idling time by region, providing data to support intelligent signal light systems that adapt to real-time traffic loads. This paper is particularly relevant to our project as it validates the YOLO + ByteTrack pipeline for real-world traffic assessment and demonstrates the practical feasibility of user-defined counting regions in CCTV feeds.

### Tracking Algorithm Comparison

| Algorithm | Year | MOTA (MOT17) | Speed | Occlusion Handling | Re-ID | Suitability |
|-----------|------|-------------|-------|-------------------|-------|-------------|
| SORT | 2016 | 59.8 | Very Fast | Poor | None | Simple scenes |
| DeepSORT | 2017 | 75.4 | Medium | Good | Excellent | Fixed cameras |
| ByteTrack | 2022 | 80.3 | Fast | Excellent | Good | Dense traffic |
| BoT-SORT | 2022 | 80.5 | Slow | Excellent | Excellent | Benchmarks |
| StrongSORT | 2023 | 79.6 | Medium | Very Good | Excellent | Offline analysis |

---

## 5. Camera Perspective Handling

### 5.1 The Perspective Problem

Roadside cameras are typically mounted at oblique angles, causing size and shape distortions that introduce counting errors. Vehicles far from the camera appear significantly smaller than nearby vehicles, and the same physical road area maps to different pixel areas at different depths.

### 5.2 Homography-Based Perspective Transform

The standard solution is to apply a homography matrix to transform the oblique camera view into a Bird's Eye View (BEV). This involves selecting 4 or more corresponding reference points on the road surface (e.g., lane markings) and computing a 3x3 homography matrix H using OpenCV's findHomography() function. The transformation maps camera-view coordinates to top-down coordinates: BEV_point = H * camera_point.

### 5.3 SDD-UNet

SDD-UNet (2024) proposes a Spatial-Transformer Double Decoder-UNet architecture that converts single-camera perspective views directly to Bird's Eye View using deep learning, eliminating the need for manual calibration point selection. It bridges the gap between simulation-based training and real-world traffic monitoring by minimizing geometric distortion automatically.

### 5.4 CAMOT

Camera Angle-aware Multi-Object Tracking (CAMOT) dynamically estimates camera parameters during tracking, allowing the system to automatically adapt to different camera installations without manual recalibration. This is particularly valuable for large-scale deployments across multiple intersections with varying camera setups.

### 5.5 Automatic Vanishing Point Detection

Recent approaches (Dubska et al., 2024) use automatic vanishing point detection to compute homography matrices from arbitrary surveillance feeds. This eliminates the need for manual calibration and enables the transformation of any uncalibrated CCTV stream into a top-down view for trajectory extraction and vehicle counting.

---

## 6. Adverse Weather and Low-Light Detection

### 6.1 The Challenge

Detection accuracy degrades significantly under adverse conditions. Research consistently shows the following performance impacts:

| Condition | Effect on Detection | Typical mAP Drop |
|-----------|-------------------|------------------|
| Heavy Rain | Reflections, water droplets on lens, reduced contrast | 15-25% |
| Night / Low Light | Dark frames, headlight glare, loss of color information | 20-35% |
| Dense Fog | Reduced visibility, blurred edges, low contrast | 25-40% |
| Snow | White-out conditions, obscured road markings | 15-30% |

### 6.2 Data Augmentation Approaches

Researchers consistently use synthetic weather augmentation as a first-line defense. Libraries such as Albumentations (Buslaev et al., 2020) allow the application of synthetic rain, fog, and darkness to training images, forcing the model to learn condition-invariant features. Recent work by Tranheden et al. (2023) demonstrates that diffusion models (e.g., Instruct Pix2Pix) can generate more realistic weather-based augmentations than traditional image processing techniques, resulting in improved generalization from clear-weather training data to adverse conditions.

### 6.3 Specialized Adverse Weather Datasets

| Dataset | Year | Authors | Conditions | Size | Application |
|---------|------|---------|-----------|------|-------------|
| ACDC | 2021 | Sakaridis et al. | Fog, Night, Rain, Snow | 4,006 images | Semantic segmentation, object detection |
| BDD100K | 2020 | Yu et al. | Day, Night, Rain, Overcast | 100,000 images | Multi-task learning |
| DAWN | 2020 | Kenk and Hassaballah | Fog, Rain, Sand, Snow | 1,000 images | Weather-specific detection |
| ExDark | 2019 | Loh and Chan | Low-light exclusive | 7,363 images | Nighttime detection |
| Foggy Cityscapes | 2018 | Sakaridis et al. | Synthetic fog on urban scenes | 5,000 images | Domain adaptation |

### 6.4 Architecture Modifications for Adverse Weather

Recent research proposes targeted modifications to detection architectures:
- SCConv (Self-Calibrated Convolutions) by Liu et al. (2024): Reduces feature redundancy and improves detection in noisy, weather-degraded images by dynamically calibrating convolutional kernels.
- Focaler-EIoU Loss by Tong et al. (2023): A custom loss function that focuses training on hard-to-detect objects, such as rain-obscured or fog-blurred vehicles, by dynamically adjusting the learning signal based on detection difficulty.
- ECL-YOLOv11 (2024): Adds Convolutional Edge-enhancement (CE) using Sobel operators and Context-guided Multi-scale Fusion (AENet) to preserve boundary information under blurred conditions.

### 6.5 Image Preprocessing Pipeline

Before feeding frames to the detector, several preprocessing techniques are commonly applied:
- CLAHE (Contrast Limited Adaptive Histogram Equalization) by Zuiderveld (1994): Enhances local contrast in low-light images without amplifying noise. Widely used for nighttime traffic image enhancement.
- Dark Channel Prior by He et al. (2009): A dehazing algorithm that estimates atmospheric light and transmission maps to recover clear images from foggy inputs.
- AOD-Net by Li et al. (2017): An end-to-end trainable dehazing network that directly produces clear images from hazy inputs without intermediate estimation steps.
- Zero-DCE by Guo et al. (2020): A zero-reference deep curve estimation network for low-light image enhancement that does not require paired training data.

### 6.6 Domain Adaptation

Given the "domain gap" between clear-weather training data and adverse-weather deployment, domain-adaptive frameworks are a major research focus. Kennerley et al. (2023) demonstrate that adversarial learning and feature alignment techniques can significantly reduce the performance gap when models trained on clear-weather datasets are deployed in adverse conditions, without requiring extensive retraining.

---

## 7. Short-Term Traffic Congestion Forecasting

### 7.1 Overview

Once vehicle counts are obtained from the perception pipeline, time-series forecasting models predict future traffic volume. The field has evolved from statistical methods (ARIMA) to deep learning architectures that capture complex spatiotemporal dependencies.

### 7.2 LSTM (Long Short-Term Memory)

LSTM (Hochreiter and Schmidhuber, 1997) is a Recurrent Neural Network (RNN) variant that maintains memory cells to learn long-term dependencies in sequential data. For traffic prediction, the input is typically a sequence of past vehicle counts (e.g., last 12 five-minute intervals representing 1 hour of history), and the output is the predicted vehicle count for the next 1-3 intervals (5-15 minutes ahead). LSTM remains the standard baseline for traffic prediction, with MAE typically 5-15% of actual counts. A comprehensive survey by Ma et al. (2024) in IEEE Intelligent Transportation Systems Magazine confirms that LSTM-based methods remain the most frequently cited architecture for time-series traffic flow prediction.

### 7.3 Bi-LSTM (Bidirectional LSTM)

Bi-LSTM processes the time series in both forward and backward directions, capturing both past trends and future context simultaneously. This bidirectional processing has been shown to improve prediction accuracy by 3-8% over standard LSTM in traffic applications, as demonstrated by Cui et al. (2020).

### 7.4 CNN-LSTM Hybrid

CNN-LSTM hybrids (Chen and Chen, 2024) use 1D-CNN layers to extract local temporal patterns (e.g., short bursts of traffic), then feed these extracted features into an LSTM for longer-range sequence modeling. This architecture achieves faster convergence and better captures periodic patterns such as daily rush hours. A 2024 survey confirms that CNN-LSTM combinations consistently outperform standalone models in traffic prediction tasks, with the CNN component capturing spatial correlations and the LSTM handling temporal dependencies.

### 7.5 Temporal Convolutional Network (TCN)

TCN (Bai et al., 2018) uses dilated causal convolutions instead of recurrence for sequence modeling. Unlike LSTM, TCN is fully parallelizable during training, handles longer sequences more efficiently, and avoids the vanishing gradient problem. Comparative studies show TCN achieving comparable or superior accuracy to LSTM while training 2-5x faster. TCN is increasingly preferred in 2024-2025 literature for real-time traffic applications.

### 7.6 Graph Convolutional Networks (GCN) for Traffic

Graph-based methods (Li et al., 2018; Yu et al., 2018) model road networks as graphs where intersections are nodes and roads are edges. DCRNN (Diffusion Convolutional Recurrent Neural Network) and STGCN (Spatio-Temporal Graph Convolutional Network) capture both spatial dependencies (how congestion at one intersection affects neighboring intersections) and temporal patterns. While powerful for city-wide prediction, GCN-based methods are more complex to implement and require network topology data.

### 7.7 Attention Mechanisms

Hierarchical-Attention-LSTM adds attention mechanisms that dynamically weigh the importance of different time steps. The model focuses on the most informative parts of the input sequence, for example giving more weight to rush-hour data when predicting evening congestion. Recent work by Zhang et al. (2024) demonstrates that attention-enhanced models improve prediction accuracy by 5-12% over standard LSTM, particularly for irregular traffic patterns.

### 7.8 XGBoost (Gradient Boosting)

XGBoost (Chen and Guestrin, 2016) is a gradient boosting framework that operates on tabular features such as vehicle count, time of day, day of week, and weather conditions. It is fast, highly interpretable, and frequently competitive with deep learning models for structured traffic data. Many Zindi competition winners used XGBoost with engineered features, validating its effectiveness for this specific problem domain.

### Forecasting Model Comparison

| Model | Accuracy | Training Speed | Interpretability | Best For |
|-------|----------|---------------|-----------------|----------|
| LSTM | Good | Slow | Low | Standard baseline, temporal patterns |
| Bi-LSTM | Very Good | Slow | Low | Bidirectional temporal dependencies |
| CNN-LSTM | Very Good | Medium | Low | Periodic patterns (rush hours) |
| TCN | Very Good | Fast | Low | Long sequences, real-time systems |
| GCN-based | Excellent | Very Slow | Low | City-wide, network-level prediction |
| Attention-LSTM | Excellent | Very Slow | Medium | Irregular patterns, research |
| XGBoost | Good | Very Fast | High | Interpretable features, quick results |

---

## 8. Research Gap and Proposed Contribution

The existing literature reveals the following critical gaps:

1. No existing traffic pipeline integrates end-to-end vision-to-forecast with error propagation analysis. Current systems treat detection, tracking, and forecasting as independent modules without quantifying how detection errors cascade into forecasting inaccuracies.

2. Standard object detectors use hard counting (binary 1 or 0), which causes data instability during poor visibility conditions. No traffic forecasting system has adopted confidence-weighted soft counting to represent detection uncertainty as a continuous probability value fed directly to the forecaster.

3. Existing weather-robust detection systems are reactive (applying the same preprocessing regardless of conditions) rather than adaptive (automatically detecting the current weather condition and applying condition-specific enhancement).

4. While attention mechanisms and hybrid architectures improve forecasting accuracy, no system feeds real-time weather classification as an explicit input feature to the forecaster, enabling condition-sensitive predictions with quantified uncertainty bounds.

This project addresses these gaps by proposing a unified pipeline that integrates YOLOv8 detection, ByteTrack tracking, confidence-weighted soft counting, adaptive weather preprocessing, and time-series congestion forecasting into a single, end-to-end system.

---

## 9. References (Sorted by Relevance to Project)

### Directly Related to Project Pipeline

1. Ng, J.J., Goh, K.O.M. and Tee, C. (2023). Traffic Impact Assessment System using YOLOv5 and ByteTrack. Journal of Informatics and Web Engineering, 2(2), pp. 99-113.
2. Zindi Africa (2024). Barbados Traffic Analysis Challenge. Zindi Competition Documentation.
3. Zhang, Y., Sun, P., Jiang, Y., Yu, D., Weng, F., Yuan, Z., Luo, P., Liu, W. and Wang, X. (2022). ByteTrack: Multi-Object Tracking by Associating Every Detection Box. ECCV 2022.
4. Jocher, G., Chaurasia, A. and Qiu, J. (2023). Ultralytics YOLOv8. GitHub: ultralytics/ultralytics.
5. Wojke, N., Bewley, A. and Paulus, D. (2017). Simple Online and Realtime Tracking with a Deep Association Metric (DeepSORT). ICIP 2017.
6. Redmon, J., Divvala, S., Girshick, R. and Farhadi, A. (2016). You Only Look Once: Unified, Real-Time Object Detection. CVPR 2016.

### Detection & Tracking Baselines

7. Ren, S., He, K., Girshick, R. and Sun, J. (2015). Faster R-CNN: Towards Real-Time Object Detection with Region Proposal Networks. NeurIPS 2015.

### Adverse Weather Datasets & Preprocessing

8. Sakaridis, C., Dai, D. and Van Gool, L. (2021). ACDC: The Adverse Conditions Dataset with Correspondences for Semantic Driving Scene Understanding. ICCV 2021.
9. Yu, F., Chen, H., Wang, X., Xian, W., Chen, Y., Liu, F., Madhavan, V. and Darrell, T. (2020). BDD100K: A Diverse Driving Dataset for Heterogeneous Multitask Learning. CVPR 2020.
10. He, K., Sun, J. and Tang, X. (2009). Single Image Haze Removal Using Dark Channel Prior. CVPR 2009.
11. Guo, C., Li, C., Guo, J., Loy, C.C., Hou, J., Kwong, S. and Cong, R. (2020). Zero-Reference Deep Curve Estimation for Low-Light Image Enhancement (Zero-DCE). CVPR 2020.
12. Zuiderveld, K. (1994). Contrast Limited Adaptive Histogram Equalization (CLAHE). Graphics Gems IV, Academic Press.

### Forecasting Models

13. Hochreiter, S. and Schmidhuber, J. (1997). Long Short-Term Memory. Neural Computation, 9(8), pp. 1735-1780.
14. Chen, L. and Chen, X. (2024). CNN-LSTM Hybrid for Short-Term Traffic Flow Prediction. IEEE Transactions on ITS.
15. Bai, S., Kolter, J.Z. and Koltun, V. (2018). An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling (TCN). arXiv:1803.01271.
16. Chen, T. and Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. KDD 2016.
