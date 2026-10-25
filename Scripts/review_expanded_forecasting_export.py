"""Verify the supplied expanded run without retraining or loading model artifacts."""
import csv
import hashlib
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from statistics import mean

from review_forecasting_colab_export import CLASSES, read_csv, check_close

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/'CP-1/Forecasting_v3_Results'
RUN = RESULTS/'Archives/expanded_01'
EVALUATION = RUN/'evaluation'
ANALYSIS = RESULTS/'Expanded_Analysis/yolo11/expanded_01'


def metric_values(truth, predicted):
    matrix = [[0]*4 for _ in CLASSES]
    for actual, guess in zip(truth,predicted):
        matrix[CLASSES.index(actual)][CLASSES.index(guess)] += 1
    per_class = []
    for i,label in enumerate(CLASSES):
        tp, support, assigned = matrix[i][i],sum(matrix[i]),sum(row[i] for row in matrix)
        precision = tp/assigned if assigned else 0
        recall = tp/support if support else 0
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0
        per_class.append(dict(label=label,correct=tp,support=support,
                              precision=precision,recall=recall,f1=f1))
    correct = sum(matrix[i][i] for i in range(4))
    return dict(n=len(truth),correct=correct,accuracy=correct/len(truth),
                balanced_accuracy=mean(r['recall'] for r in per_class if r['support']),
                macro_f1=mean(r['f1'] for r in per_class),
                classes=per_class,confusion_matrix=matrix)


def semantic_hash(plan):
    fields = ['videos','view_label','target_video_path','source_time','segment_end',
              'target_time','next_enter_rating','congestion_enter_rating','split']
    records = []
    for row in sorted(plan,key=lambda row:row['videos']):
        normalized = {key:row[key] for key in fields}
        for key in ['source_time','segment_end','target_time']:
            normalized[key] = datetime.fromisoformat(normalized[key]).strftime('%Y-%m-%dT%H:%M:%S.%f')
        records.append(normalized)
    return hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def main():
    archive_path = RUN/'Forecasting_v3_yolo11_expanded.zip'
    with zipfile.ZipFile(archive_path) as archive:
        members = [name for name in archive.namelist() if not name.endswith('/')]
        for name in members:
            relative = PurePosixPath(name)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert archive.read(name) == (EVALUATION/name).read_bytes(),name

    features = read_csv(EVALUATION/'features_used.csv')
    predictions = read_csv(EVALUATION/'evaluation_predictions.csv')
    settings = json.loads((EVALUATION/'selected_model.json').read_text())
    plan = read_csv(RUN/'selected_pairs.csv')
    contract = json.loads((RUN/'checkpoint_contract.json').read_text())
    configuration = contract['configuration']
    assert contract['signature'] == hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()
    assert configuration['plan_sha256'] == hashlib.sha256((RUN/'selected_pairs.csv').read_bytes()).hexdigest()
    assert configuration['plan_semantic_sha256'] == semantic_hash(plan)
    assert settings['input_sha256'] == hashlib.sha256((EVALUATION/'features_used.csv').read_bytes()).hexdigest()
    assert {r['model_name'] for r in features} == {configuration['model']} == {'yolo11l.pt'}
    indexed = {r['video_path']:r for r in features}
    planned = {r['videos']:r for r in plan}
    assert len(indexed) == len(features) and len(planned) == len(plan)
    assert set(indexed) == set(planned)
    train = [r for r in features if r['split']=='train']
    test = [r for r in features if r['split']=='test']
    assert len(train) == settings['train_n'] and len(test) == settings['test_n']
    assert len(predictions) == len({r['video_path'] for r in predictions}) == len(test)
    assert {r['video_path'] for r in predictions} == {r['video_path'] for r in test}
    boundary = datetime(2025,10,25)
    assert all(datetime.fromisoformat(r['source_time']) < boundary and
               datetime.fromisoformat(r['target_time']) < boundary for r in train)
    assert all(datetime.fromisoformat(r['source_time']) >= boundary for r in test)

    labels = read_csv(ROOT/'CP-1/Data/Zindi_Labels/Train.csv')
    label_index = {r['videos']:r for r in labels}
    by_camera = defaultdict(list)
    for row in labels:
        by_camera[row['view_label']].append(row)
    next_video = {}
    for rows in by_camera.values():
        rows.sort(key=lambda row:(row['datetimestamp_start'],row['videos']))
        next_video.update({left['videos']:right['videos'] for left,right in zip(rows,rows[1:])})
    for row in features:
        source, target = label_index[row['video_path']],label_index[row['target_video_path']]
        assert next_video[source['videos']] == target['videos']
        assert row['congestion_enter_rating'] == source['congestion_enter_rating']
        assert row['next_enter_rating'] == target['congestion_enter_rating']
        assert datetime.fromisoformat(row['source_time']) == datetime.fromisoformat(source['datetimestamp_start'])
        assert datetime.fromisoformat(row['target_time']) == datetime.fromisoformat(target['datetimestamp_start'])
        assert 0 <= float(row['gap_sec']) <= 2
        assert datetime.fromisoformat(source['datetimestamp_end']) > datetime.fromisoformat(source['datetimestamp_start'])
        assert datetime.fromisoformat(target['datetimestamp_end']) > datetime.fromisoformat(target['datetimestamp_start'])
        for key in ['split','next_enter_rating','congestion_enter_rating','target_video_path']:
            assert row[key] == planned[row['video_path']][key]
    forbidden = {'congestion_enter_rating','next_enter_rating','target_time','split','target_video_path'}
    assert not forbidden.intersection(settings['feature_columns'])
    # Context shares/cyclic times are derived inputs, not raw features_used columns.
    sys.path.insert(0,str(ROOT/'CP-1/Program'))
    import pandas as pd
    from congestion_forecasting_v3 import make_inputs
    inputs = make_inputs(pd.DataFrame(features),settings['selected_candidate'].endswith('_context'))
    assert list(inputs) == settings['feature_columns']
    assert not inputs.isna().any().any()
    assert all(math.isfinite(float(value)) for column in inputs if column != 'camera_id'
               for value in inputs[column])

    metrics = {r['method']:r for r in read_csv(EVALUATION/'evaluation_metrics.csv')}
    verified = {}
    truth = [r['next_enter_rating'] for r in predictions]
    majority = Counter(r['next_enter_rating'] for r in train).most_common(1)[0][0]
    for row in predictions:
        assert row['next_enter_rating'] == indexed[row['video_path']]['next_enter_rating']
        assert row['prediction'] == row['selected_model_prediction']
        assert row['majority_prediction'] == majority
        assert row['persistence_label_baseline_prediction'] == indexed[row['video_path']]['congestion_enter_rating']
    for method,report in metrics.items():
        result = metric_values(truth,[r[method+'_prediction'] for r in predictions])
        for key in ['n','correct','accuracy','balanced_accuracy','macro_f1']:
            check_close(result[key],report[key])
        verified[method] = result
    selected = verified['selected_model']
    matrix = read_csv(EVALUATION/'confusion_matrix.csv')
    assert [[int(row[c]) for c in CLASSES] for row in matrix] == selected['confusion_matrix']
    class_report = {r['']:r for r in read_csv(EVALUATION/'classification_report.csv')}
    for row in selected['classes']:
        for key,column in [('precision','precision'),('recall','recall'),('f1','f1-score'),('support','support')]:
            check_close(row[key],class_report[row['label']][column])
    for row in read_csv(EVALUATION/'split_class_distribution.csv'):
        actual = Counter(r['next_enter_rating'] for r in features if r['split']==row['split'])
        assert all(actual[c] == int(row[c]) for c in CLASSES)

    folds = read_csv(EVALUATION/'validation_folds.csv')
    ranking = read_csv(EVALUATION/'validation_ranking.csv')
    for row in ranking:
        matching = [r for r in folds if r['candidate']==row['candidate']]
        assert len(matching) == 3
        for key in ['macro_f1','accuracy']:
            check_close(mean(float(r[key]) for r in matching),row[key])
        for fold in matching:
            day = datetime.fromisoformat(fold['validation_date'])
            assert day < boundary
            assert int(fold['train_n']) == sum(datetime.fromisoformat(r['source_time']) < day and
                datetime.fromisoformat(r['target_time']) < day for r in train)
            assert int(fold['validation_n']) == sum(r['source_date']==fold['validation_date'] for r in train)
    assert ranking[0]['candidate'] == settings['selected_candidate']
    assert ranking[0]['candidate'] == sorted(ranking,key=lambda r:(-float(r['macro_f1']),-float(r['accuracy']),r['candidate']))[0]['candidate']

    historical = read_csv(RESULTS/'Forecasting_v3_yolo11_cached/features_used.csv')
    old_keys = {r['video_path'] for r in historical}
    assert not ({r['video_path'] for r in test}|{r['target_video_path'] for r in test}) & old_keys
    near_old = 0
    for row in test:
        for old in historical:
            if row['camera_id'] != old['camera_id']:
                continue
            if any(abs(datetime.fromisoformat(row[new])-datetime.fromisoformat(old[prior])) <= timedelta(minutes=2)
                   for new in ['source_time','target_time'] for prior in ['source_time','target_time']):
                near_old += 1
    new_keys = set(indexed)-old_keys
    versions = Counter()
    for key in new_keys:
        safe = re.sub(r'[^A-Za-z0-9_.-]+','_',key)
        manifest = json.loads((RUN/'crossing_logs'/f'{safe}_manifest.json').read_text())
        events = read_csv(RUN/'crossing_logs'/f'{safe}_crossings.csv')
        row = indexed[key]
        assert manifest['video_path'] == key and manifest['model_weights'] == 'yolo11l.pt'
        assert int(manifest['frames_processed']) == int(row['total_frames'])
        assert int(manifest['hard_count']) == len(events) == int(row['total_unique_vehicles'])
        assert sum(e['direction']=='entering' for e in events) == int(row['entering_count'])
        assert sum(e['direction']=='exiting' for e in events) == int(row['exiting_count'])
        assert math.isclose(sum(float(e['mean_track_confidence']) for e in events),float(row['soft_count']),abs_tol=1e-3)
        assert (RUN/'crossing_logs'/f'{safe}_observations.csv').is_file()
        versions[manifest['ultralytics_version']] += 1
    assert set(versions) == {configuration['ultralytics_version']}
    inventory = read_csv(RUN/'dataset_inventory.csv')
    inventory_totals = {key:sum(int(r[key]) for r in inventory) for key in inventory[0] if key != 'camera_id'}
    assert len(read_csv(RUN/'labelled_videos_missing_from_drive.csv')) == inventory_totals['labelled_but_missing']
    assert len(read_csv(RUN/'videos_without_labels.csv')) == inventory_totals['unlabelled_videos']
    assert len(read_csv(RUN/'invalid_label_timing.csv')) == inventory_totals['invalid_timing_labels']

    audit = {'review_date':'2026-10-25','source':str(RUN.relative_to(ROOT)),
             'train_n':len(train),'test_n':len(test),'selected_candidate':settings['selected_candidate'],
             'feature_n':len(settings['feature_columns']),'methods':verified,
             'training_class_counts':dict(Counter(r['next_enter_rating'] for r in train)),
             'test_class_counts':dict(Counter(truth)),'inventory_totals':inventory_totals,
             'new_clip_logs_verified':len(new_keys),'reused_historical_training_clips':len(set(indexed)&old_keys),
             'logged_ultralytics_versions':dict(versions),'new_test_overlaps_old_sources':False,
             'near_historical_source_or_target_pairs':near_old,'fresh_independent_dates':False,
             'zip_and_extracted_files_agree':True,'input_and_contract_hashes_agree':True,
             'all_method_metrics_independently_recomputed':True,
             'conclusion':'Selected model improves macro-F1 over these baselines but loses on accuracy; this does not establish an overall forecasting improvement or detector superiority.'}
    ANALYSIS.mkdir(parents=True,exist_ok=True)
    (ANALYSIS/'AUDIT.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    methods = '\n'.join(f"| {name} | {r['correct']}/{r['n']} | {r['accuracy']:.3%} | {r['balanced_accuracy']:.3%} | {r['macro_f1']:.6f} |"
                        for name,r in verified.items())
    classes = '\n'.join(f"| {r['label']} | {r['support']} | {r['correct']} | {r['recall']:.1%} | {r['f1']:.4f} |"
                        for r in selected['classes'])
    report = f'''# Expanded YOLO11 forecasting review — 25 October 2026

The completed run used **448 training and 64 evaluation clips**, retaining 48
historical training features and processing 464 new clips. The validation-selected
classifier is **logistic regression with context/motion features**, not XGBoost.
Its 34 inputs are extracted from pretrained YOLO11l detections/tracks plus context.

## Verified results

| Method | Correct | Accuracy | Balanced accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
{methods}

The selected pipeline has **71.875% accuracy** and **0.428289 macro-F1**. Always
predicting free-flowing traffic scores 81.25% accuracy because 52/64 evaluation
clips are free flowing. Persistence scores 79.6875%. Therefore the selected
pipeline does not beat these baselines on accuracy. Its macro-F1 exceeds majority
by {selected['macro_f1']-verified['majority']['macro_f1']:.6f}, and persistence by
only {selected['macro_f1']-verified['persistence_label_baseline']['macro_f1']:.6f}.
Balanced accuracy measures mean class recall and is also above the baselines.
These metrics describe different trade-offs; they do not establish an overall win.

## Class-level performance

| Class | Test clips | Correct | Recall | F1 |
|---|---:|---:|---:|---:|
{classes}

There is only one moderate-delay test clip; the model misclassified it. Scores
for that class are particularly uncertain. The old balanced test had eight clips
per class. The 50% cached score and this 71.875% score use different samples and
class proportions, so their difference is not a controlled accuracy improvement.
There is no matching expanded YOLOv8 result yet; cached YOLOv8 is not a fair
comparison against this expanded YOLO11 pipeline.

## Dataset availability and quality

The Drive inventory contains {inventory_totals['accessible_videos']:,} accessible
videos across four camera folders and matches {inventory_totals['matched_videos']:,}
of the 16,076 labelled paths. There are {inventory_totals['labelled_but_missing']}
labelled paths missing from Drive, {inventory_totals['unlabelled_videos']:,} videos
without matching rows in Train.csv, and 20 invalid label timing records. Their
lists are retained with the run. Unlabelled videos do not support scored
congestion evaluation without reference labels.

## Audit

The ZIP matches its extracted evaluation files. Input-feature and checkpoint
hashes agree. All four methods' saved predictions independently reproduce their
accuracy, balanced accuracy and macro-F1. The confusion matrix, class reports,
class counts, validation fold sizes/averages and validation winner agree.
Source/target labels and timestamps match the original Train.csv and contiguous
segment pairing. No human congestion labels or future timestamps are input features.

The new 64-clip test shares no source/target video with historical source clips;
{near_old} source/target pairs are within two minutes of a historical source or
target time. Training targets precede the evaluation period. The 464 newly
processed clips' manifests and crossing logs agree with frame/count summaries;
observation-log files exist and all manifests record Ultralytics
{configuration['ultralytics_version']}. These are consistency checks, not measured
vehicle-detection or counting accuracy. No joblib artifact was loaded or retrained.

All evaluation dates remain 25–26 October 2025, from the previously examined
recording week. This is broader coverage, not confirmation on new independent
dates. Keep settings frozen and assess additional untouched labelled traffic
before a stronger generalization claim. Integration of these results into the
paper is recorded separately in `PAPER_INTEGRATION.json` alongside this report.

Raw run: `Archives/expanded_01/`; machine-readable review: `AUDIT.json` alongside
this report. The original downloaded ZIP and logs are preserved in place.
'''
    (ANALYSIS/'REPORT.md').write_text(report,encoding='utf-8')
    comparison = RESULTS/'COMPARISON.md'
    marker = '<!-- expanded-yolo11-review -->'
    cached = comparison.read_text(encoding='utf-8').split(marker)[0].rstrip()
    addition = f'''\n\n{marker}
## Expanded YOLO11 run reviewed on 25 October 2026

The new experiment used 448 training and 64 evaluation clips and selected
`logistic_context` using training-date validation. This is a different sample
from the cached comparison above, with 52/64 free-flowing clips.

| Method | Correct | Accuracy | Balanced accuracy | Macro-F1 |
|---|---:|---:|---:|---:|
{methods}

The selected model's 71.875% accuracy is below majority (81.25%) and persistence
(79.6875%). It has higher macro-F1 and balanced accuracy, with only a small
macro-F1 lead over persistence. Do not describe the increase from the old 50%
as a controlled improvement: sample/class proportions changed. No matched
expanded YOLOv8 run has been supplied. Detection/counting accuracy is unmeasured.

Full [expanded review](Expanded_Analysis/yolo11/expanded_01/REPORT.md) and
[machine-readable audit](Expanded_Analysis/yolo11/expanded_01/AUDIT.json).
The cached results above remain valid for their original 32-clip comparison.
'''
    comparison.write_text(cached+addition,encoding='utf-8')
    print('Expanded export verified:',len(train),'train /',len(test),'test;',len(new_keys),'new clip logs checked.')
    print('Selected model:',settings['selected_candidate'])
    print('Accuracy:',selected['accuracy'],'Macro-F1:',selected['macro_f1'])
    print('Majority accuracy:',verified['majority']['accuracy'],'Persistence accuracy:',verified['persistence_label_baseline']['accuracy'])
    print('Report:',ANALYSIS/'REPORT.md')


if __name__ == '__main__':
    main()
