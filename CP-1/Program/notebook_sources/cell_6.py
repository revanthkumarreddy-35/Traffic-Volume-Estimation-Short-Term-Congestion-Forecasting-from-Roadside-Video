# --- Balanced clip extraction and genuine next-segment congestion prediction ---
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

def load_existing_features(path):
    if RESUME_FEATURE_EXTRACTION and os.path.isfile(path):
        existing = pd.read_csv(path)
        if "video_path" in existing.columns:
            existing = existing.drop_duplicates("video_path", keep="last")
            return existing.to_dict("records"), set(existing["video_path"].astype(str))
    return [], set()

def save_feature_checkpoint(rows, path):
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.drop_duplicates("video_path", keep="last")
        table.to_csv(path, index=False)
    return table

def prepare_next_segment_labels(labels, available_video_keys):
    """Pair each source clip with the next *contiguous* labeled segment in its camera."""
    required = {"videos", "view_label", "datetimestamp_start", "datetimestamp_end", "congestion_enter_rating"}
    missing = required - set(labels.columns)
    if missing:
        raise ValueError(f"Train.csv is missing columns: {sorted(missing)}")
    table = labels.copy()
    table["source_time"] = pd.to_datetime(table["datetimestamp_start"], errors="coerce")
    table["segment_end"] = pd.to_datetime(table["datetimestamp_end"], errors="coerce")
    table = table.dropna(subset=["source_time", "segment_end", "congestion_enter_rating"])
    table = table.sort_values(["view_label", "source_time", "videos"]).drop_duplicates("videos")
    group = table.groupby("view_label", sort=False)
    table["target_time"] = group["source_time"].shift(-1)
    table["target_video_path"] = group["videos"].shift(-1)
    table["next_enter_rating"] = group["congestion_enter_rating"].shift(-1)
    table["gap_sec"] = (table["target_time"] - table["segment_end"]).dt.total_seconds()
    table["horizon_sec"] = (table["target_time"] - table["source_time"]).dt.total_seconds()
    table = table[
        table["videos"].isin(available_video_keys)
        & table["next_enter_rating"].notna()
        & table["gap_sec"].between(0, 2)
        & (table["horizon_sec"] > 0)
    ].copy()
    table["source_date"] = table["source_time"].dt.strftime("%Y-%m-%d")
    table["camera_id"] = table["videos"].str.split("/").str[0]
    table["split"] = np.where(table["source_date"].isin(TEST_DATES), "test", "train")
    return table

def select_balanced_source_clips(pairs):
    selected = []
    for (camera_id, split, target), group in pairs.groupby(["camera_id", "split", "next_enter_rating"]):
        limit = TEST_CLIPS_PER_CAMERA_CLASS if split == "test" else TRAIN_CLIPS_PER_CAMERA_CLASS
        selected.append(group.sample(n=min(limit, len(group)), random_state=RANDOM_SEED))
    if not selected:
        return pairs.iloc[0:0].copy()
    return pd.concat(selected, ignore_index=True).sort_values(["split", "camera_id", "source_time"])

available_videos = {make_video_key(path): path for paths in all_videos.values() for path in paths}
if train_df is None:
    raise FileNotFoundError("Train.csv is needed for balanced next-segment selection")
future_label_pairs = prepare_next_segment_labels(train_df, set(available_videos))
selected_pairs = select_balanced_source_clips(future_label_pairs)
selected_pairs.to_csv(os.path.join(JOURNAL_EXPORT_DIR, "selected_next_segment_pairs.csv"), index=False)
print(f"Selected {len(selected_pairs)} source clips with a contiguous future label.")
print(selected_pairs.groupby(["split", "next_enter_rating"]).size().to_string() if len(selected_pairs) else "No eligible clips")

all_features, processed_videos = load_existing_features(FEATURES_CSV_PATH)
selected_keys = list(dict.fromkeys(selected_pairs["videos"].tolist()))
if MAX_UNLABELED_VIDEOS_PER_CAMERA > 0:
    for paths in all_videos.values():
        selected_keys.extend(make_video_key(path) for path in paths[:MAX_UNLABELED_VIDEOS_PER_CAMERA])
selected_keys = list(dict.fromkeys(selected_keys))
saved_samples = 0
for index, video_key in enumerate(selected_keys, start=1):
    if video_key in processed_videos:
        print(f"[{index}/{len(selected_keys)}] Already checkpointed: {video_key}")
        continue
    video_path = available_videos[video_key]
    print(f"[{index}/{len(selected_keys)}] Processing {video_key}")
    try:
        row, sample, _ = process_video_with_tracking(video_path, model, show_sample=saved_samples < 8)
        if row is None:
            print("Interrupted; rerun Cell 6 to restart this clip from frame zero")
            break
        all_features.append(row)
        processed_videos.add(video_key)
        save_feature_checkpoint(all_features, FEATURES_CSV_PATH)
        if sample is not None and saved_samples < 8:
            sample_path = os.path.join(ANNOTATION_DIR, f"{Path(video_path).stem}_sample.jpg")
            cv2.imwrite(sample_path, sample)
            saved_samples += 1
    except Exception as error:
        print(f"Could not process {video_key}: {type(error).__name__}: {error}")

features_df = save_feature_checkpoint(all_features, FEATURES_CSV_PATH)
print(f"Completed feature rows: {len(features_df)}; saved at {FEATURES_CSV_PATH}")
display(features_df.head())

FEATURE_COLUMNS = [
    "total_unique_vehicles", "entering_count", "exiting_count", "car_count",
    "truck_count", "bus_count", "motorcycle_count", "avg_vehicles_per_frame",
    "max_vehicles_per_frame", "flow_rate_per_min", "avg_bbox_area",
    "std_bbox_area", "avg_confidence", "soft_count",
]

if not features_df.empty and not selected_pairs.empty:
    labeled_features_df = features_df.merge(
        selected_pairs[["videos", "source_time", "target_time", "source_date", "split",
                        "next_enter_rating", "congestion_enter_rating", "horizon_sec"]],
        left_on="video_path", right_on="videos", how="inner", validate="one_to_one"
    )
    print(f"Matched future labels: {len(labeled_features_df)}/{len(selected_pairs)} selected clips")
    print(labeled_features_df.groupby(["split", "next_enter_rating"]).size().to_string())
    labeled_features_df.to_csv(os.path.join(JOURNAL_EXPORT_DIR, "next_segment_features.csv"), index=False)
else:
    labeled_features_df = pd.DataFrame()

if not labeled_features_df.empty:
    train_rows = labeled_features_df[labeled_features_df["split"] == "train"].copy()
    test_rows = labeled_features_df[labeled_features_df["split"] == "test"].copy()
    all_classes = sorted(train_df["congestion_enter_rating"].dropna().unique())
    training_classes = set(train_rows["next_enter_rating"])
    test_classes = set(test_rows["next_enter_rating"])
    enough = (len(train_rows) >= 20 and len(test_rows) >= 8
              and training_classes == set(all_classes) and test_classes == set(all_classes))
    if enough:
        encoder = LabelEncoder().fit(all_classes)
        X_train = train_rows[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0)
        X_test = test_rows[FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0)
        y_train = encoder.transform(train_rows["next_enter_rating"])
        y_test = encoder.transform(test_rows["next_enter_rating"])
        xgb_model = xgb.XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.08,
            subsample=0.9, colsample_bytree=0.9,
            objective="multi:softprob", eval_metric="mlogloss",
            tree_method="hist", random_state=RANDOM_SEED,
        )
        xgb_model.fit(X_train, y_train)
        y_pred = xgb_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        macro_f1 = f1_score(y_test, y_pred, labels=range(len(all_classes)),
                            average="macro", zero_division=0)
        persistence_pred = encoder.transform(test_rows["congestion_enter_rating"])
        persistence_accuracy = accuracy_score(y_test, persistence_pred)
        persistence_macro_f1 = f1_score(y_test, persistence_pred,
                                        labels=range(len(all_classes)), average="macro", zero_division=0)
        majority_class = train_rows["next_enter_rating"].mode().iloc[0]
        majority_pred = encoder.transform([majority_class] * len(test_rows))
        majority_accuracy = accuracy_score(y_test, majority_pred)
        print("Next-segment prediction; train dates before holdout dates:")
        print(f"Train: {len(train_rows)}; test: {len(test_rows)}; horizon range: "
              f"{test_rows['horizon_sec'].min():.0f}-{test_rows['horizon_sec'].max():.0f} sec")
        print(classification_report(y_test, y_pred, labels=range(len(all_classes)),
                                    target_names=encoder.classes_, zero_division=0))
        print("Confusion matrix (rows=true, columns=predicted):")
        print(confusion_matrix(y_test, y_pred, labels=range(len(all_classes))))
        print(f"Accuracy={accuracy:.4f}; macro-F1={macro_f1:.4f}; "
              f"Zindi-style composite={0.7 * macro_f1 + 0.3 * accuracy:.4f}")
        print(f"Persistence baseline: accuracy={persistence_accuracy:.4f}; "
              f"macro-F1={persistence_macro_f1:.4f}; "
              f"majority-class accuracy={majority_accuracy:.4f}")
        prediction_rows = test_rows[["video_path", "source_time", "target_time", "next_enter_rating"]].copy()
        prediction_rows["predicted_next_enter_rating"] = encoder.inverse_transform(y_pred)
        prediction_rows["persistence_prediction"] = test_rows["congestion_enter_rating"].values
        prediction_rows.to_csv(os.path.join(JOURNAL_EXPORT_DIR, "next_segment_holdout_predictions.csv"), index=False)
        pd.DataFrame([{
            "train_n": len(train_rows), "test_n": len(test_rows),
            "train_dates": ",".join(sorted(train_rows["source_date"].unique())),
            "test_dates": ",".join(sorted(test_rows["source_date"].unique())),
            "accuracy": accuracy, "macro_f1": macro_f1,
            "zindi_style_score": 0.7 * macro_f1 + 0.3 * accuracy,
            "persistence_accuracy": persistence_accuracy,
            "persistence_macro_f1": persistence_macro_f1,
            "majority_class_accuracy": majority_accuracy,
        }]).to_csv(os.path.join(JOURNAL_EXPORT_DIR, "next_segment_holdout_metrics.csv"), index=False)
    else:
        print("Prediction evaluation skipped: finish processing selected clips and ensure all "
              "four future classes occur in training, with at least 20 train and 8 test clips.")
        print(f"Available train/test: {len(train_rows)}/{len(test_rows)}; "
              f"train classes: {sorted(training_classes)}; test classes: {sorted(test_classes)}")
