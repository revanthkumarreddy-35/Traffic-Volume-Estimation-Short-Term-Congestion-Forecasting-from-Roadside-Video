# 🚦 Capstone Project Roadmap: DSCI-41
**Traffic Volume Estimation and Short-Term Congestion Forecasting from Roadside Video**

> **Domain**: Visual Intelligence Systems
> **Primary Specialization**: AI Systems for Visual Intelligence
> **Reference Source**: Zindi (Barbados Traffic Analysis Challenge)

## 📌 Project Overview
Many cities have roadside cameras but no reliable traffic counts. Turning video into vehicle counts is difficult due to oblique camera angles, occlusion in dense traffic, mixed vehicle types, and adverse weather (rain, low light). 

This project aims to build a robust **computer vision pipeline** to accurately detect, classify, and count vehicles under these harsh conditions, and then use those counts to **forecast short-term traffic congestion**.

---

## 🎯 The 5 Official Objectives (CP-1 & CP-2 Split)

As per the official KL University guidelines, the project is strictly divided into two semesters.

### ภาค Semester VII: Capstone Project 1 (Perception & Baseline)

> [!NOTE]
> CP-1 focuses entirely on **Computer Vision (Object Detection & Tracking)**. The goal is to build a reliable vehicle counter from video feeds.

*   **Objective 1 (O1): Build the Baseline Vehicle Counter**
    *   *Task*: Set up the data pipeline, acquire roadside traffic video datasets (with reference vehicle counts), and build a baseline object detection model (e.g., YOLO) to count vehicles under fixed camera geometry.
    *   *Deliverable*: A working prototype that detects and counts cars in clear, daytime conditions.
*   **Objective 2 (O2): Handle Mixed Vehicle Types and Oblique Perspectives (The Reference)**
    *   *Task*: Upgrade the baseline to correctly classify multiple vehicle types (cars, trucks, motorcycles) and handle tricky, angled camera perspectives (oblique views) where objects look distorted.
    *   *Deliverable*: A perspective-robust counting system with measured baseline accuracy against the reference dataset.

### ภาค Semester VIII: Capstone Project 2 (Contribution, Forecasting & Integration)

> [!IMPORTANT]
> CP-2 focuses on **Robustness (Handling Weather/Occlusion)** and **Time-Series Forecasting (Predicting Congestion)**.

*   **Objective 3 (O3): Sustain Accuracy Under Occlusion, Rain, and Low Light (The Contribution)**
    *   *Task*: This is your major technical contribution. You must train and optimize the vision model to maintain high accuracy when cars are blocked by other cars (occlusion), during heavy rain, and at night. 
    *   *Deliverable*: A documented performance comparison showing how your model beats the baseline under adverse conditions.
*   **Objective 4 (O4): Forecast Near-Term Congestion from Estimated Volumes (Integration)**
    *   *Task*: Connect a forecasting model (like LSTM, TCN, or XGBoost) to the vision pipeline. It takes the rolling vehicle counts from O3 and predicts traffic volume/congestion 15-30 minutes into the future.
    *   *Deliverable*: The complete integrated system (Vision Pipeline ➔ Forecasting Engine ➔ Dashboard/Warning System).
*   **Objective 5 (O5): Complete Independent Acceptance and Impact Validation**
    *   *Task*: Execute a rigorous testing campaign. Run mandatory negative tests (testing the system until it fails) and validate the final predictions against real-world reference counts.
    *   *Deliverable*: A final validation report, research paper/technical article, and the project demonstration video.

---

## 🌍 SDG Mapping & Measurable Impact

To meet the Dean-Academics requirement for SDG mapping, this project targets:

*   **SDG 9 (Industry, Innovation and Infrastructure):** By providing low-cost, AI-driven traffic telemetry without requiring expensive in-ground sensors.
*   **SDG 11 (Sustainable Cities and Communities):** By enabling proactive traffic management to reduce urban congestion, lowering fuel consumption and emissions.

**Measurable KPIs (How you will be graded):**
1.  **Counting Accuracy under adverse conditions**: Must exceed the baseline reference by at least 3 percentage points.
2.  **Congestion Forecast Error**: Must score ≥ 80/100 on the evaluation rubric.
3.  **Critical-scene failure rate**: Must reduce failure rates during rain/night by at least 20% compared to the baseline.

---

## 🛠️ Recommended Tech Stack (Software Only)
*   **Computer Vision**: Python, PyTorch, YOLO (v8/v10) / Faster R-CNN, DeepSORT / ByteTrack (for tracking).
*   **Perspective Handling**: OpenCV (for Homography and perspective transforms).
*   **Forecasting**: PyTorch (LSTMs/TCNs) or Scikit-learn/XGBoost.
*   **Deployment/Dashboard**: Streamlit or FastAPI + React (for the traffic authority warning dashboard).
*   **Environment**: Docker, Git (Reproducible environments are mandatory).

---

## 📖 Mandatory Admin Requirements
1.  **Team Structure (4 Members):**
    *   *Member 1*: Vision Model Architecture Lead (O1) - Focuses on the core object detection and counting pipeline.
    *   *Member 2*: Geometry & Perspective Lead (O2) - Focuses on handling oblique camera angles and perspective transformations.
    *   *Member 3*: Adverse Conditions & Dataset Lead (O3) - Focuses on training the model for rain, night, and occlusion robustness.
    *   *Member 4*: Application, Forecasting & Validation Lead (O4 & O5) - Focuses on the time-series congestion forecasting and the dashboard integration.
2.  **Research Diary**: Since this is a pure software project, all team members must maintain a hardbound engineering research diary documenting the iterative model training process, hyperparameter tuning, and dataset annotations.
3.  **Video Logs**: Each member must submit individual video logs explaining their specific code and contributions.
