# 🌐 DSCI-41: Complete Resource & Dataset Guide
**Traffic Volume Estimation and Short-Term Congestion Forecasting from Roadside Video**

This document contains all the internet links, datasets, reference papers, and tools required to build this capstone project.

---

## 1. 🏆 Core Reference Material

### The Zindi Barbados Traffic Analysis Challenge
This is the faculty-provided reference competition. The dataset here provides the foundational video streams and congestion labels.
*   **Main Competition Page**: [Zindi Africa - Barbados Traffic Analysis Challenge](https://zindi.africa/competitions/barbados-traffic-analysis-challenge)
*   **Kaggle Mirror (Alternative Download)**: [Kaggle - Barbados Traffic Video Dataset](https://www.kaggle.com/datasets/zindi/barbados-traffic-analysis-challenge)
*   **Discussion & Starter Code**: Look at the "Discussion" and "Leaderboard" tabs on the Zindi page for baseline Google Colab notebooks.

---

## 2. 📂 Open-Source Datasets

You will use these datasets to train and fine-tune your model to handle mixed traffic and adverse weather conditions.

### A. Vehicle Detection & Counting Datasets
*   **Roboflow Universe (Traffic)**: [https://universe.roboflow.com/search?q=traffic](https://universe.roboflow.com/search?q=traffic)
    *   *Why use it:* Pre-annotated in YOLO format. Search for "Indian Traffic" or "CCTV Vehicles".
*   **UA-DETRAC**: [http://detrac-db.rit.albany.edu/](http://detrac-db.rit.albany.edu/)
    *   *Why use it:* 10 hours of video with 1.2 million annotated bounding boxes for vehicle detection.

### B. Adverse Weather Datasets (For CP-2 / O3)
*   **ACDC (Adverse Conditions Dataset)**: [https://acdc.ethz.ch/](https://acdc.ethz.ch/)
    *   *Why use it:* specifically designed for fog, nighttime, rain, and snow.
*   **BDD100K (Berkeley DeepDrive)**: [https://bdd-data.berkeley.edu/](https://bdd-data.berkeley.edu/)
    *   *Why use it:* One of the largest driving datasets with 100,000 videos, heavily annotated with weather condition tags (rain, clear, overcast).

---

## 3. 🛠️ Code Repositories & Libraries

These are the official GitHub repositories for the algorithms you will implement.

*   **Ultralytics YOLOv8 (Object Detection)**: [https://github.com/ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
    *   *Installation:* `pip install ultralytics`
*   **ByteTrack (Multi-Object Tracking)**: [https://github.com/ifzhang/ByteTrack](https://github.com/ifzhang/ByteTrack)
*   **XGBoost (Congestion Forecasting)**: [https://xgboost.readthedocs.io/](https://xgboost.readthedocs.io/)
*   **OpenCV (Perspective Correction & Preprocessing)**: [https://opencv.org/](https://opencv.org/)
    *   *Installation:* `pip install opencv-python`

---

## 4. 🎥 Real-Time Live Feed Tools

To demonstrate your project working in real-time for your final CP-2 review.

*   **VidGear (To stream YouTube Live Cameras)**: [https://abhitronix.github.io/vidgear/](https://abhitronix.github.io/vidgear/)
    *   *Installation:* `pip install vidgear`
    *   *Usage:* Allows you to pipe a YouTube live traffic stream directly into your Python OpenCV code.
*   **EarthCam (Find live cameras)**: [https://www.earthcam.com/](https://www.earthcam.com/)
*   **YouTube Live Traffic Search**: Search YouTube for `Live highway traffic camera 24/7` to find streams you can use for your demo.

---

## 5. 📄 Key Research Papers (For Your Literature Review)

If your faculty asks for the actual PDF papers you studied to come up with your novelty, here are the links to the original publications:

1.  **YOLOv8 Official Documentation / Paper**: 
    [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) (Note: YOLOv8 doesn't have a formal academic paper, the repo is the official citation).
2.  **ByteTrack (Zhang et al., 2022)**: 
    *ByteTrack: Multi-Object Tracking by Associating Every Detection Box* - [https://arxiv.org/abs/2110.06864](https://arxiv.org/abs/2110.06864)
3.  **ACDC Dataset Paper (Sakaridis et al., 2021)**: 
    *ACDC: The Adverse Conditions Dataset with Correspondences* - [https://arxiv.org/abs/2104.13395](https://arxiv.org/abs/2104.13395)
4.  **TCN for Forecasting (Bai et al., 2018)**: 
    *An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling* - [https://arxiv.org/abs/1803.01271](https://arxiv.org/abs/1803.01271)
5.  **CNN-LSTM Hybrids**: 
    Search Google Scholar for *"CNN-LSTM Short-Term Traffic Flow Prediction"* to find dozens of 2023/2024 implementations.

---

## 💡 Pro-Tip for KL University CP-1 Review
Do **NOT** download all these datasets right now. 
1. For **CP-1**, you only need to download the **Zindi Barbados Dataset** and install **YOLOv8 / OpenCV**.
2. For **CP-2**, you will download ACDC/BDD100K to train the adverse weather models.
