# --- YOLO11 + ByteTrack: independent clips, reproducible crossings ---
import copy
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone

GLOBAL_TRACKING_STATE = {}
JOURNAL_RESULT_CONTEXT = None

def unsharp_mask(image, kernel_size=(5, 5), sigma=1.0, amount=1.5):
    blurred = cv2.GaussianBlur(image, kernel_size, sigma)
    return cv2.addWeighted(image, 1 + amount, blurred, -amount, 0)

def get_adaptive_params(width, height):
    pixels = width * height
    if pixels < 854 * 480:
        return {"apply_sharpen": True, "imgsz": 1280, "conf": 0.05, "line_thick": 1}
    if pixels <= 1920 * 1080:
        return {"apply_sharpen": False, "imgsz": 1280, "conf": 0.05, "line_thick": 2}
    return {"apply_sharpen": False, "imgsz": 1920, "conf": 0.05, "line_thick": 4}

def segment_intersection(a, b, c, d):
    def cross(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    ab_c, ab_d = cross(a, b, c), cross(a, b, d)
    cd_a, cd_b = cross(c, d, a), cross(c, d, b)
    return ab_c * ab_d < 0 and cd_a * cd_b < 0

def line_side(a, b, point):
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])

def crossing_direction(a, b, old, new):
    line_x, line_y = b[0] - a[0], b[1] - a[1]
    move_x, move_y = new[0] - old[0], new[1] - old[1]
    return "exiting" if line_x * move_y - line_y * move_x > 0 else "entering"

def camera_id_from_path(video_path):
    return os.path.basename(video_path).split("_", 1)[0].lower()

def line_for_video(video_path, width, height):
    normalized = COUNTING_LINES.get(camera_id_from_path(video_path), COUNTING_LINES["default"])
    return tuple((int(round(x * width)), int(round(y * height))) for x, y in normalized)

def reset_tracker_for_new_clip(model):
    """ByteTrack's IDs/history must not carry into an unrelated video."""
    predictor = getattr(model, "predictor", None)
    trackers = getattr(predictor, "trackers", None)
    if trackers:
        for tracker in trackers:
            tracker.reset()

def generate_heatmap(points, width, height, background_frame):
    if not points or background_frame is None:
        return background_frame
    heat = np.zeros((height, width), dtype=np.float32)
    for x, y in points:
        if 0 <= x < width and 0 <= y < height:
            heat[y, x] += 1
    heat = cv2.GaussianBlur(heat, (15, 15), 0)
    if heat.max() <= 0:
        return background_frame
    colored = cv2.applyColorMap(np.uint8(255 * heat / heat.max()), cv2.COLORMAP_JET)
    result = background_frame.copy()
    blended = cv2.addWeighted(colored, 0.6, background_frame, 0.4, 0)
    result[heat > 0] = blended[heat > 0]
    return result

def process_video_with_tracking(video_path, model, max_frames=None, show_sample=False):
    """Process one full clip; return features, sample, heatmap or three Nones if interrupted."""
    global GLOBAL_TRACKING_STATE
    video_key = make_video_key(video_path)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        raise OSError(f"Cannot open video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width <= 0 or height <= 0:
        cap.release()
        raise ValueError(f"Invalid video dimensions: {video_path}")
    params = get_adaptive_params(width, height)
    pt_a, pt_b = line_for_video(video_path, width, height)
    reset_tracker_for_new_clip(model)

    counts = {direction: defaultdict(int) for direction in ("entering", "exiting")}
    counted_ids, track_history, last_moved_frame = set(), {}, {}
    track_confidences = defaultdict(list)
    frame_data, all_bbox_areas, all_confidences = [], [], []
    observations, crossings, points = [], [], []
    sample_frame = background_frame = None
    frame_idx = 0
    max_frames = (total_frames if total_frames > 0 else float("inf")) if max_frames is None else max_frames
    try:
        while cap.isOpened() and frame_idx < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if background_frame is None:
                background_frame = frame.copy()
            processed = unsharp_mask(frame) if params["apply_sharpen"] else frame
            # persist=True is valid only for successive frames *within this clip*.
            result = model.track(
                processed, persist=True, tracker=TRACKER_CONFIG_PATH,
                imgsz=params["imgsz"], conf=params["conf"], verbose=False,
                classes=list(VEHICLE_CLASSES)
            )[0]
            annotated = processed.copy() if show_sample else None
            if annotated is not None:
                cv2.line(annotated, pt_a, pt_b, (0, 255, 255), params["line_thick"])
            frame_vehicles = 0
            if result.boxes is not None and result.boxes.id is not None:
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    track_id = int(box.id[0])
                    confidence = float(box.conf[0])
                    x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                    center = ((x1 + x2) // 2, (y1 + y2) // 2)
                    class_name = VEHICLE_CLASSES.get(class_id, "unknown")
                    frame_vehicles += 1
                    all_bbox_areas.append(max(0, x2 - x1) * max(0, y2 - y1))
                    all_confidences.append(confidence)
                    track_confidences[track_id].append(confidence)
                    points.append(center)
                    observations.append({
                        "frame_idx": frame_idx, "track_id": track_id,
                        "vehicle_class": class_name, "confidence": confidence,
                        "cx": center[0], "cy": center[1],
                        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                    })
                    previous = track_history.get(track_id)
                    is_stopped = False
                    if previous is None or math.hypot(center[0] - previous[0], center[1] - previous[1]) > 5:
                        last_moved_frame[track_id] = frame_idx
                    elif fps > 0 and frame_idx - last_moved_frame.get(track_id, frame_idx) > 3 * fps:
                        is_stopped = True
                    if previous is not None and track_id not in counted_ids:
                        if segment_intersection(pt_a, pt_b, previous, center):
                            direction = crossing_direction(pt_a, pt_b, previous, center)
                            counts[direction][class_name] += 1
                            counted_ids.add(track_id)
                            crossings.append({
                                "frame_idx": frame_idx, "track_id": track_id,
                                "vehicle_class": class_name, "direction": direction,
                                "crossing_confidence": confidence,
                                "previous_cx": previous[0], "previous_cy": previous[1],
                                "cx": center[0], "cy": center[1],
                            })
                    # Preserve the last off-line position when a center lands exactly
                    # on the tripwire; count once it actually reaches the other side.
                    if line_side(pt_a, pt_b, center) != 0:
                        track_history[track_id] = center
                    if annotated is not None:
                        color = (0, 0, 255) if is_stopped else (255, 0, 0)
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, params["line_thick"])
                        cv2.putText(annotated, f"{class_name} #{track_id}", (x1, max(15, y1 - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                        if is_stopped:
                            cv2.putText(annotated, "STOPPED VEHICLE", (x1, max(25, y1 - 25)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            frame_data.append({"frame_idx": frame_idx, "vehicles_in_frame": frame_vehicles})
            if annotated is not None and (frame_idx == total_frames // 2 or sample_frame is None):
                sample_frame = annotated.copy()
            frame_idx += 1
    except KeyboardInterrupt:
        print(f"Interrupted at frame {frame_idx}; no partial results saved. Rerun this clip from frame zero.")
        return None, None, None
    finally:
        cap.release()

    if frame_idx == 0:
        raise ValueError(f"No frames read: {video_path}")
    for event in crossings:
        history = track_confidences[event["track_id"]]
        event["mean_track_confidence"] = float(np.mean(history))
        event["track_confidence_history"] = json.dumps(history)
    soft_entering = sum(e["mean_track_confidence"] for e in crossings if e["direction"] == "entering")
    soft_exiting = sum(e["mean_track_confidence"] for e in crossings if e["direction"] == "exiting")
    hard_entering = sum(counts["entering"].values())
    hard_exiting = sum(counts["exiting"].values())
    duration = frame_idx / fps if fps > 0 else 0.0
    densities = [row["vehicles_in_frame"] for row in frame_data]
    safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", video_key)
    log_prefix = os.path.join(RUN_LOG_DIR, safe_key)
    features = {
        "video_path": video_key, "filename": os.path.basename(video_path),
        "camera_id": camera_id_from_path(video_path), "model_name": YOLO_MODEL_NAME,
        "total_frames": frame_idx, "fps": fps, "duration_sec": round(duration, 3),
        "resolution": f"{width}x{height}", "counting_line": f"{pt_a}->{pt_b}",
        "total_unique_vehicles": hard_entering + hard_exiting,
        "entering_count": hard_entering, "exiting_count": hard_exiting,
        "soft_count": round(soft_entering + soft_exiting, 4),
        "soft_entering_count": round(soft_entering, 4),
        "soft_exiting_count": round(soft_exiting, 4),
        "avg_vehicles_per_frame": float(np.mean(densities)),
        "max_vehicles_per_frame": int(max(densities)),
        "flow_rate_per_min": (hard_entering + hard_exiting) * 60 / duration if duration else 0,
        "avg_bbox_area": float(np.mean(all_bbox_areas)) if all_bbox_areas else 0,
        "std_bbox_area": float(np.std(all_bbox_areas)) if all_bbox_areas else 0,
        "avg_confidence": float(np.mean(all_confidences)) if all_confidences else 0,
        "crossing_log": log_prefix + "_crossings.csv",
    }
    for class_name in VEHICLE_CLASSES.values():
        features[f"{class_name}_count"] = counts["entering"][class_name] + counts["exiting"][class_name]
    manifest = {
        "video_path": video_key, "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_weights": YOLO_MODEL_NAME, "tracker_config_path": TRACKER_CONFIG_PATH,
        "tracker_config": custom_config, "ultralytics_version": __import__("ultralytics").__version__,
        "counting_line_pixels": [pt_a, pt_b], "adaptive_parameters": params,
        "frames_processed": frame_idx, "fps": fps, "hard_count": hard_entering + hard_exiting,
        "soft_count_definition": "sum of mean YOLO confidences per crossed track",
        "soft_count": soft_entering + soft_exiting,
        "crossings_file": log_prefix + "_crossings.csv",
        "observations_file": log_prefix + "_observations.csv",
    }
    pd.DataFrame(crossings, columns=[
        "frame_idx", "track_id", "vehicle_class", "direction", "crossing_confidence",
        "previous_cx", "previous_cy", "cx", "cy", "mean_track_confidence",
        "track_confidence_history"
    ]).to_csv(manifest["crossings_file"], index=False)
    pd.DataFrame(observations, columns=[
        "frame_idx", "track_id", "vehicle_class", "confidence", "cx", "cy", "x1", "y1", "x2", "y2"
    ]).to_csv(manifest["observations_file"], index=False)
    with open(log_prefix + "_manifest.json", "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    GLOBAL_TRACKING_STATE = {
        "video_path": video_key, "counts": counts, "frame_data": frame_data,
        "all_confidences": all_confidences, "all_bbox_areas": all_bbox_areas,
        "crossings": crossings, "features": features,
    }
    return features, sample_frame, generate_heatmap(points, width, height, background_frame)

# The single-video journal context is a snapshot, not the mutable last batch clip.
if test_video:
    features, sample, heatmap = process_video_with_tracking(test_video, model, show_sample=True)
    if features is not None:
        JOURNAL_RESULT_CONTEXT = copy.deepcopy(GLOBAL_TRACKING_STATE)
        print(f"Test clip: {features['video_path']}; hard={features['total_unique_vehicles']}; soft={features['soft_count']}")
        from google.colab.patches import cv2_imshow
        if sample is not None:
            cv2_imshow(sample)
        if heatmap is not None:
            cv2_imshow(heatmap)
