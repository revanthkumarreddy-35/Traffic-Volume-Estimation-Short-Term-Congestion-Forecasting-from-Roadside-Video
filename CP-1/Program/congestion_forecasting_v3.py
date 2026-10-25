"""Chronological congestion-model selection, cached features and optional expansion.

Target labels are used only for training/scoring. Prediction inputs never include
current/future human congestion labels. Historical test results are exploratory.
"""
from pathlib import Path
import argparse
import hashlib
import io
import importlib.metadata
import json
import re
import zipfile

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

CLASSES = ['free flowing', 'heavy delay', 'light delay', 'moderate delay']
BASE = ['total_unique_vehicles', 'entering_count', 'exiting_count', 'car_count',
        'truck_count', 'bus_count', 'motorcycle_count', 'avg_vehicles_per_frame',
        'max_vehicles_per_frame', 'flow_rate_per_min', 'avg_bbox_area',
        'std_bbox_area', 'avg_confidence', 'soft_count']
SEED = 42


def validate_labels(labels):
    required = ['videos', 'view_label', 'datetimestamp_start', 'datetimestamp_end',
                'congestion_enter_rating']
    missing = set(required)-set(labels.columns)
    if missing:
        raise ValueError('Label CSV is missing columns: '+', '.join(sorted(missing)))
    if labels[required].isna().any().any():
        raise ValueError('Label CSV contains missing video identifiers, timestamps or congestion labels.')
    t = labels.copy()
    t['videos'] = t.videos.astype(str).str.replace('\\', '/', regex=False).str.strip()
    if t.videos.eq('').any():
        raise ValueError('Label CSV contains an empty video path.')
    if not t.congestion_enter_rating.isin(CLASSES).all():
        raise ValueError('Label CSV contains unknown congestion classes.')
    for column in ['datetimestamp_start', 'datetimestamp_end']:
        if pd.to_datetime(t[column], errors='coerce').isna().any():
            raise ValueError('Label CSV contains invalid '+column)
    unique = t[required].drop_duplicates()
    if unique.videos.duplicated().any():
        raise ValueError('The same video has conflicting labels, camera names or timestamps.')
    return t.drop_duplicates('videos').copy()


def label_timing_issues(labels):
    t = validate_labels(labels)
    bad = pd.to_datetime(t.datetimestamp_end) <= pd.to_datetime(t.datetimestamp_start)
    report = t.loc[bad,['videos','datetimestamp_start','datetimestamp_end']].copy()
    report['reason'] = 'segment end is not after segment start'
    return report


def dataset_label_audit(labels, available):
    """Match labels to accessible paths without requiring attributes in MP4 files."""
    labels = validate_labels(labels)
    labelled = set(labels.videos)
    available = set(available)
    invalid_timing = set(label_timing_issues(labels).videos)
    cameras = ['normanniles'+str(i) for i in range(1,5)]
    rows = []
    for camera in cameras:
        known = {key for key in labelled if key.split('/')[0] == camera}
        found = {key for key in available if key.split('/')[0] == camera}
        rows.append(dict(camera_id=camera, labelled_videos=len(known),
                         accessible_videos=len(found), matched_videos=len(known & found),
                         labelled_but_missing=len(known-found), unlabelled_videos=len(found-known),
                         invalid_timing_labels=len(known & invalid_timing)))
    missing = labels[~labels.videos.isin(available)][['videos','view_label','datetimestamp_start']]
    unlabelled = pd.DataFrame({'video_path':sorted(available-labelled)})
    return pd.DataFrame(rows), missing, unlabelled


def prepare_pairs(labels, available):
    t = validate_labels(labels)
    t['source_time'] = pd.to_datetime(t.datetimestamp_start, errors='coerce')
    t['segment_end'] = pd.to_datetime(t.datetimestamp_end, errors='coerce')
    t['segment_duration'] = (t.segment_end-t.source_time).dt.total_seconds()
    t = t.dropna(subset=['source_time', 'segment_end', 'congestion_enter_rating'])
    t = t.sort_values(['view_label', 'source_time', 'videos']).drop_duplicates('videos')
    grouped = t.groupby('view_label', sort=False)
    t['target_time'] = grouped.source_time.shift(-1)
    t['target_video_path'] = grouped.videos.shift(-1)
    t['next_enter_rating'] = grouped.congestion_enter_rating.shift(-1)
    t['target_duration'] = grouped.segment_duration.shift(-1)
    t['gap_sec'] = (t.target_time - t.segment_end).dt.total_seconds()
    t['horizon_sec'] = (t.target_time - t.source_time).dt.total_seconds()
    t = t[t.videos.isin(available) & t.gap_sec.between(0, 2) & (t.horizon_sec > 0)
          & (t.segment_duration > 0) & (t.target_duration > 0)
          & t.next_enter_rating.isin(CLASSES)].copy()
    t['source_date'] = t.source_time.dt.strftime('%Y-%m-%d')
    t['camera_id'] = t.videos.str.split('/').str[0]
    t = t[t.camera_id.isin(['normanniles'+str(i) for i in range(1, 5)])]
    t['split'] = np.where(t.source_time < pd.Timestamp('2025-10-25'), 'train', 'test')
    # Purge a training target that reaches the test period.
    return t[(t.split != 'train') | (t.target_time < pd.Timestamp('2025-10-25'))]


def expansion_plan(labels, available, historical, per_train_day=20, per_test_day=8):
    """Sample by camera/date, never by the future label; exclude old test neighborhoods."""
    if any(isinstance(n, bool) or not isinstance(n, (int, np.integer)) or n <= 0
           for n in [per_train_day, per_test_day]):
        raise ValueError('Per-camera/date clip limits must be positive integers.')
    t = prepare_pairs(labels, available)
    old_keys = set(historical.video_path)
    old_targets = set(t.loc[t.videos.isin(old_keys),'target_video_path'])
    excluded_keys = old_keys | old_targets
    eligible_test = t.split.eq('test') & ~t.videos.isin(excluded_keys) & ~t.target_video_path.isin(excluded_keys)
    for old in historical.itertuples():
        same_camera = t.camera_id.eq(old.camera_id)
        for time in (pd.Timestamp(old.source_time), pd.Timestamp(old.target_time)):
            near = ((t.source_time-time).abs() <= pd.Timedelta(minutes=2)) | (
                (t.target_time-time).abs() <= pd.Timedelta(minutes=2))
            eligible_test &= ~(same_camera & near)
    chunks = []
    for (_, _, split), group in t.groupby(['camera_id', 'source_date', 'split']):
        if split == 'test': group = group.loc[eligible_test.reindex(group.index)]
        else: group = group[~group.videos.isin(old_keys)]
        n = per_test_day if split == 'test' else per_train_day
        if len(group): chunks.append(group.sample(min(n, len(group)), random_state=SEED))
    # Retain completed training clips to save compute, but never old test clips.
    chunks.append(t[t.videos.isin(historical.loc[historical.split == 'train', 'video_path'])])
    result = pd.concat(chunks).drop_duplicates('videos').sort_values(['source_time', 'camera_id'])
    if not (result.split == 'test').any():
        raise ValueError('No new evaluation clips are available. Keep the cached analysis exploratory.')
    return result.reset_index(drop=True)


def contract_signature(configuration):
    return hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()


def plan_fingerprint(plan):
    """Hash the actual source/target assignments, independently of CSV formatting."""
    columns = ['videos','view_label','target_video_path','source_time','segment_end',
               'target_time','next_enter_rating','congestion_enter_rating','split']
    missing = set(columns)-set(plan)
    if missing or plan.videos.duplicated().any():
        raise ValueError('Saved plan is missing required fields or has duplicate videos.')
    normalized = plan[columns].copy().reset_index(drop=True).sort_values('videos')
    for column in ['source_time','segment_end','target_time']:
        normalized[column] = pd.to_datetime(normalized[column],errors='raise').dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
    if normalized.isna().any().any():
        raise ValueError('Saved plan contains missing assignments.')
    payload = json.dumps(normalized.to_dict('records'),sort_keys=True,separators=(',',':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def resume_saved_plan(proposed, labels, available, historical, folder, sampling_limits):
    """Reuse a verified frozen selection, never replace it with a new random draw."""
    folder = Path(folder)
    contract_path, plan_path = folder/'checkpoint_contract.json', folder/'selected_pairs.csv'
    if not contract_path.exists():
        return proposed, None
    saved = json.loads(contract_path.read_text())
    previous = saved['configuration']
    if saved.get('signature') != contract_signature(previous):
        raise RuntimeError('Saved checkpoint contract failed its integrity check. Files were not replaced.')
    if not plan_path.exists():
        raise RuntimeError('Saved contract has no selected_pairs.csv. Restore that file before resuming.')
    if hashlib.sha256(plan_path.read_bytes()).hexdigest() != previous.get('plan_sha256'):
        raise RuntimeError('The saved selected_pairs.csv changed after checkpoint creation. Restore the original plan; files were not replaced.')
    frozen = pd.read_csv(plan_path)
    if previous.get('sampling_limits') is not None:
        if previous['sampling_limits'] != sampling_limits:
            raise RuntimeError('Sampling limits changed. Restore them or use a new EXPERIMENT_NAME; the checkpoint is unchanged.')
    else:
        # v4 did not record requested limits. Require the same realized group sizes.
        keys = ['split','camera_id','source_date']
        old_sizes = frozen.groupby(keys).size().sort_index()
        new_sizes = proposed.groupby(keys).size().sort_index()
        if not old_sizes.equals(new_sizes):
            raise RuntimeError('Sampling counts or accessible videos changed from the saved v4 plan. Restore the original settings and video availability.')
    valid = prepare_pairs(labels,available).set_index('videos',drop=False)
    missing = set(frozen.videos)-set(valid.index)
    if missing:
        raise RuntimeError(f'{len(missing)} saved clips are inaccessible or no longer form valid labelled pairs. Restore the original videos/labels.')
    if plan_fingerprint(frozen) != plan_fingerprint(valid.loc[frozen.videos]):
        raise RuntimeError('Source/target labels or timestamps changed for saved clips. Restore the original label CSV.')
    old_test = set(historical.loc[historical.split.eq('test'),'video_path'])
    test = frozen[frozen.split.eq('test')]
    if (set(test.videos) | set(test.target_video_path)) & old_test:
        raise RuntimeError('The saved evaluation selection overlaps historical test clips.')
    for column in ['source_time','target_time','segment_end']:
        frozen[column] = pd.to_datetime(frozen[column],errors='raise')
    print('Resuming the verified saved clip plan:',len(frozen),'clips.')
    return frozen, saved


def checkpoint_changes(saved, current):
    """Ignore tuple/list JSON representation; allow only verified v4 metadata migration."""
    previous = json.loads(json.dumps(saved['configuration']))
    current = json.loads(json.dumps(current))
    if previous.get('version') == 4 and current.get('version') == 5:
        keys = set(previous)-{'version'}
    else:
        keys = set(previous) | set(current)
    return {key:{'saved':previous.get(key),'current':current.get(key)}
            for key in sorted(keys) if previous.get(key) != current.get(key)}


def motion_features(observations, row):
    """Image-plane motion proxies; not calibrated road speed or true occupancy."""
    frames = int(row['total_frames'])
    fps = float(row['fps'])
    width, height = map(float, row['resolution'].split('x'))
    if frames <= 0 or fps <= 0: raise ValueError('Invalid video timing')
    o = observations.copy()
    if o.empty:
        return dict(motion_speed_median=0., motion_speed_p90=0., slow_observation_fraction=0.,
                    bbox_occupancy_proxy=0., density_trend=0., density_std=0.)
    numeric = ['frame_idx', 'track_id', 'cx', 'cy', 'x1', 'y1', 'x2', 'y2']
    o[numeric] = o[numeric].apply(pd.to_numeric, errors='raise')
    if o[numeric].isna().any().any(): raise ValueError('Missing tracking observations')
    if not o.frame_idx.between(0, frames-1).all(): raise ValueError('Observation frames exceed clip')
    if o.duplicated(['frame_idx', 'track_id']).any(): raise ValueError('Duplicate track observations')
    o = o.sort_values(['track_id', 'frame_idx'])
    dt = o.groupby('track_id').frame_idx.diff() / fps
    dx = o.groupby('track_id').cx.diff()
    dy = o.groupby('track_id').cy.diff()
    speed = (np.hypot(dx, dy) / (dt * np.hypot(width, height)))[dt.between(1/fps-1e-8, .5)]
    density = np.bincount(o.frame_idx.astype(int), minlength=frames)
    third = max(1, frames // 3)
    areas = (o.x2-o.x1).clip(lower=0) * (o.y2-o.y1).clip(lower=0)
    return dict(motion_speed_median=float(speed.median()) if len(speed) else 0.,
                motion_speed_p90=float(speed.quantile(.9)) if len(speed) else 0.,
                slow_observation_fraction=float((speed < .005).mean()) if len(speed) else 0.,
                bbox_occupancy_proxy=float(areas.sum() / (frames*width*height)),
                density_trend=float(density[-third:].mean()-density[:third].mean()),
                density_std=float(density.std()))


def add_motion(table, log_dirs):
    table = table.copy()
    extracted = []
    for _, row in table.iterrows():
        safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', row.video_path)
        found = next((Path(d)/(safe+'_observations.csv') for d in log_dirs
                      if (Path(d)/(safe+'_observations.csv')).is_file()), None)
        extracted.append(motion_features(pd.read_csv(found), row) if found else {})
    motion = pd.DataFrame(extracted, index=table.index)
    # Only use this feature family when every clip has it, avoiding a run-version
    # missingness signal. Cache-only reruns still work with the original features.
    if motion.empty or motion.isna().any().any():
        print(f'Motion logs available for {sum(bool(r) for r in extracted)}/{len(table)} clips; motion family omitted.')
        return table
    return pd.concat([table, motion], axis=1)


def make_inputs(table, enhanced):
    x = table[BASE].apply(pd.to_numeric, errors='raise').copy()
    if enhanced:
        dimensions = table.resolution.str.split('x', expand=True).astype(float)
        area = dimensions[0]*dimensions[1]
        total = x.total_unique_vehicles.clip(lower=1)
        for name in ['entering_count', 'exiting_count', 'car_count', 'truck_count', 'bus_count', 'motorcycle_count']:
            x[name+'_share'] = x[name]/total
        x['bbox_area_fraction'] = x.avg_bbox_area / area
        x['bbox_std_fraction'] = x.std_bbox_area / area
        x['density_to_crossings'] = x.avg_vehicles_per_frame / total
        x['soft_hard_ratio'] = x.soft_count / total
        x['density_peak_ratio'] = x.max_vehicles_per_frame / x.avg_vehicles_per_frame.clip(lower=.1)
        time = pd.to_datetime(table.source_time)
        hour = time.dt.hour + time.dt.minute/60
        x['hour_sin'], x['hour_cos'] = np.sin(2*np.pi*hour/24), np.cos(2*np.pi*hour/24)
        # Camera identity is available at deployment; human congestion is not.
        x['camera_id'] = table.camera_id.astype(str)
        for col in table.columns:
            if col in ['motion_speed_median', 'motion_speed_p90', 'slow_observation_fraction',
                       'bbox_occupancy_proxy', 'density_trend', 'density_std']:
                x[col] = pd.to_numeric(table[col], errors='raise')
    return x.replace([np.inf, -np.inf], np.nan)


def candidates():
    # Fixed before looking at the audit set. The original model is a candidate,
    # so validation can reject the proposed changes rather than forcing them.
    return [('original_xgb', False), ('regularized_xgb', False),
            ('regularized_xgb', True), ('shallow_xgb', True),
            ('random_forest', True), ('logistic', True)]


def model_pipeline(name, x):
    cats = [c for c in x if not pd.api.types.is_numeric_dtype(x[c])]
    nums = [c for c in x if c not in cats]
    preprocess = ColumnTransformer([
        ('numeric', Pipeline([('fill', SimpleImputer(strategy='median', keep_empty_features=True)),
                              ('scale', StandardScaler())]), nums),
        ('camera', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cats),
    ])
    shared = dict(objective='multi:softprob', eval_metric='mlogloss', tree_method='hist',
                  random_state=SEED, n_jobs=2)
    if name == 'original_xgb':
        model = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=.08,
                              subsample=.9, colsample_bytree=.9, **shared)
    elif name == 'regularized_xgb':
        model = XGBClassifier(n_estimators=150, max_depth=2, learning_rate=.04,
                              min_child_weight=3, reg_lambda=10, reg_alpha=.5,
                              subsample=.85, colsample_bytree=.85, **shared)
    elif name == 'shallow_xgb':
        model = XGBClassifier(n_estimators=100, max_depth=1, learning_rate=.05,
                              min_child_weight=2, reg_lambda=10, **shared)
    elif name == 'random_forest':
        model = RandomForestClassifier(n_estimators=250, max_depth=5, min_samples_leaf=3,
                                        max_features=.7, n_jobs=1, random_state=SEED)
    elif name == 'logistic':
        model = LogisticRegression(C=.3, max_iter=1500, random_state=SEED)
    else: raise ValueError(name)
    return Pipeline([('preprocess', preprocess), ('model', model)])


def fit_model(model, x, y, name):
    weights = np.ones(len(y)) if name == 'original_xgb' else compute_sample_weight('balanced', y)
    return model.fit(x, y, model__sample_weight=weights)


def evaluate_pipeline(table, output, evaluation_kind='reused_historical_holdout'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    t = table.sort_values(['source_time', 'video_path']).reset_index(drop=True)
    if t.video_path.duplicated().any(): raise ValueError('Duplicate clips')
    if t.model_name.nunique() != 1: raise ValueError('Do not mix detectors in one feature table')
    if not t.next_enter_rating.isin(CLASSES).all(): raise ValueError('Unknown target class')
    t['source_time'] = pd.to_datetime(t.source_time)
    t['target_time'] = pd.to_datetime(t.target_time)
    t['source_date'] = t.source_time.dt.strftime('%Y-%m-%d')
    t['split'] = np.where(t.source_time < pd.Timestamp('2025-10-25'), 'train', 'test')
    if not (t.target_time > t.source_time).all(): raise ValueError('Target must be in the future')
    train = t[t.split == 'train'].copy()
    test = t[t.split == 'test'].copy()
    if len(train) < 20 or len(test) < 8: raise ValueError('Insufficient training or evaluation clips')
    if train.target_time.max() >= test.source_time.min(): raise ValueError('Train target overlaps evaluation period')
    y = train.next_enter_rating.map({c:i for i,c in enumerate(CLASSES)}).to_numpy()
    distribution = pd.crosstab(t['split'], t.next_enter_rating).reindex(
        index=['train','test'], columns=CLASSES, fill_value=0)
    distribution.to_csv(output/'split_class_distribution.csv')
    folds = []
    for day in ['2025-10-22', '2025-10-23', '2025-10-24']:
        boundary = pd.Timestamp(day)
        fit = np.flatnonzero((train.source_time < boundary) & (train.target_time < boundary))
        valid = np.flatnonzero(train.source_date == day)
        if len(fit) >= 12 and len(valid) >= 4 and set(y[fit]) == set(range(4)):
            folds.append((day, fit, valid))
    if len(folds) < 2: raise ValueError('Need two chronological validation folds with all training classes')
    logs, configs = [], {}
    for name, enhanced in candidates():
        key = name + ('_context' if enhanced else '_base')
        x = make_inputs(train, enhanced)
        configs[key] = (name, enhanced)
        for day, fit, valid in folds:
            model = fit_model(model_pipeline(name, x), x.iloc[fit], y[fit], name)
            pred = model.predict(x.iloc[valid])
            logs.append(dict(candidate=key, validation_date=day, train_n=len(fit), validation_n=len(valid),
                             accuracy=accuracy_score(y[valid], pred),
                             macro_f1=f1_score(y[valid], pred, labels=range(4), average='macro', zero_division=0)))
    folds_table = pd.DataFrame(logs)
    folds_table.to_csv(output/'validation_folds.csv', index=False)
    ranking = folds_table.groupby('candidate')[['macro_f1', 'accuracy']].mean().reset_index().sort_values(
        ['macro_f1', 'accuracy', 'candidate'], ascending=[False, False, True])
    ranking.to_csv(output/'validation_ranking.csv', index=False)
    chosen = ranking.iloc[0].candidate
    name, enhanced = configs[chosen]
    x = make_inputs(train, enhanced)
    trained = fit_model(model_pipeline(name, x), x, y, name)
    selection = {'selected_candidate': chosen, 'selection_metric': 'mean chronological validation macro-F1',
                 'detector_model': t.model_name.iloc[0],
                 'feature_columns': list(x), 'train_n': len(train), 'test_n': len(test),
                 'seed': SEED, 'evaluation_kind': evaluation_kind,
                 'packages': {p: importlib.metadata.version(p) for p in ['scikit-learn','xgboost','pandas','numpy']},
                 'input_sha256': hashlib.sha256(t.to_csv(index=False).encode()).hexdigest(),
                 'fresh_independent_dates': False,
                 'note': 'The dates 25-26 October were previously examined. New clips improve evaluation coverage, but are not new independent dates.'}
    # Save the frozen selection before any evaluation predictions or metrics.
    (output/'selected_model.json').write_text(json.dumps(selection, indent=2), encoding='utf-8')
    joblib.dump(trained, output/'selected_model.joblib')
    joblib.dump({'classes': CLASSES, 'enhanced': enhanced, 'features': list(x)}, output/'feature_schema.joblib')
    truth = test.next_enter_rating.map({c:i for i,c in enumerate(CLASSES)}).to_numpy()
    pred = trained.predict(make_inputs(test, enhanced))
    original = fit_model(model_pipeline('original_xgb', make_inputs(train, False)), make_inputs(train, False), y, 'original_xgb')
    guesses = {'selected_model': pred, 'original_settings_recomputed': original.predict(make_inputs(test, False)),
               'majority': np.full(len(test), np.bincount(y).argmax()),
               'persistence_label_baseline': test.congestion_enter_rating.map({c:i for i,c in enumerate(CLASSES)}).to_numpy()}
    metrics = []
    for label, guess in guesses.items():
        metrics.append(dict(method=label, n=len(test), correct=int((truth == guess).sum()),
                            accuracy=accuracy_score(truth, guess),
                            balanced_accuracy=balanced_accuracy_score(truth, guess),
                            macro_f1=f1_score(truth, guess, labels=range(4), average='macro', zero_division=0)))
    metrics = pd.DataFrame(metrics)
    metrics.to_csv(output/'evaluation_metrics.csv', index=False)
    result = test[['video_path','source_time','target_time','next_enter_rating']].copy()
    result['prediction'] = [CLASSES[int(i)] for i in pred]
    for method, guess in guesses.items():
        result[method+'_prediction'] = [CLASSES[int(i)] for i in guess]
    result.to_csv(output/'evaluation_predictions.csv', index=False)
    pd.DataFrame(confusion_matrix(truth, pred, labels=range(4)), index=CLASSES, columns=CLASSES).to_csv(output/'confusion_matrix.csv')
    pd.DataFrame(classification_report(truth, pred, labels=range(4), target_names=CLASSES,
                                       output_dict=True, zero_division=0)).T.to_csv(output/'classification_report.csv')
    t.to_csv(output/'features_used.csv', index=False)
    report = ('# Forecasting v3 experiment\n\nSelected using training-date validation only: '+chosen+
              '\n\nEvaluation type: '+evaluation_kind+'\n\n'+metrics.to_string(index=False)+
              '\n\nThese are congestion-classification metrics. Detection/counting accuracy remains unmeasured. '
              'The original-settings baseline is refitted under the current software, sorted row order and preprocessing; '
              'it is not a bit-for-bit replay of the archived 37.5% run. '
              'Historical test performance is exploratory after previous inspection. Do not claim independent confirmation '
              'without new dates/cameras. Context features contain no human congestion labels. Motion is an image-plane proxy.\n')
    (output/'REPORT.md').write_text(report, encoding='utf-8')
    print(ranking.to_string(index=False))
    print('\nSelected:', chosen)
    print(metrics.to_string(index=False))
    return selection, metrics


def read_cached(root, model):
    root = Path(root)
    if model == 'yolov8':
        return pd.read_csv(root/'CP-1/Journal_Results_Export_yolov8_v2/next_segment_features.csv')
    with zipfile.ZipFile(root/'CP-1/Journal_Results_Export_v2-20261020T090346Z-1-001.zip') as archive:
        return pd.read_csv(io.BytesIO(archive.read('Journal_Results_Export_v2/next_segment_features.csv')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', choices=['yolo11','yolov8'], default='yolo11')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    evaluate_pipeline(read_cached(root, args.model), root/'CP-1/Forecasting_v3_Results/Local_Runs'/args.model)
