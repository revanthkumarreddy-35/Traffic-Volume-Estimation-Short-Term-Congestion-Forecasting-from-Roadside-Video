# Abstract: Objective 1 (Baseline Vehicle Counter)
**DSCI-41: Traffic Volume Estimation and Short-Term Congestion Forecasting**

**Objective:** Build the Baseline Vehicle Counter (CP-1 Perception Phase)

Intelligent Transportation Systems (ITS) increasingly rely on roadside camera networks for traffic flow analysis; however, accurate vehicle counting remains challenging due to occlusions, varying vehicle scales, and complex urban intersection layouts. This objective focuses on developing a robust, real-time baseline vehicle perception module capable of accurately detecting, classifying, and tracking multiple vehicle types (e.g., cars, trucks, buses, motorcycles) from continuous CCTV video streams. 

The proposed methodology leverages the state-of-the-art YOLOv8 object detection architecture to achieve high-precision spatial localization and classification of vehicles within complex traffic scenes, specifically utilizing the Barbados Traffic Analysis dataset for training and validation. To convert static frame-by-frame detections into continuous trajectory counts, the system integrates the ByteTrack multi-object tracking algorithm, which effectively mitigates identity switching and tracking loss during vehicle occlusions by associating every detection box rather than solely relying on high-confidence thresholds. 

The output of this baseline module is a continuous time-series stream of traffic volume (hard counts categorized by vehicle class), which serves as the fundamental ground-truth input required for subsequent time-series congestion forecasting models. By establishing a highly accurate perception baseline, this objective lays the critical foundation required to evaluate and quantify the performance degradation caused by adverse weather conditions in later phases of the project.
