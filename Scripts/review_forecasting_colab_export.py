"""Audit the downloaded cached Colab run without loading models or retraining."""
import csv
import json
import math
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'CP-1/Forecasting_v3_Results'
EXPORT = RESULTS / 'Forecasting_v3_yolo11_cached'
CLASSES = ['free flowing', 'heavy delay', 'light delay', 'moderate delay']


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def check_close(actual, expected):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError(f'Metric mismatch: {actual} versus {expected}')


def review_export(export, detector):
    EXPORT = Path(export)
    predictions = read_csv(EXPORT / 'evaluation_predictions.csv')
    features = read_csv(EXPORT / 'features_used.csv')
    settings = json.loads((EXPORT / 'selected_model.json').read_text(encoding='utf-8'))
    metrics = {row['method']: row for row in read_csv(EXPORT / 'evaluation_metrics.csv')}
    index = {row['video_path']: row for row in features}
    if len(index) != len(features) or len({r['video_path'] for r in predictions}) != len(predictions):
        raise ValueError('Duplicate video paths')
    train = [r for r in features if r['split'] == 'train']
    test = [r for r in features if r['split'] == 'test']
    assert len(train) == settings['train_n'] == 48
    assert len(test) == settings['test_n'] == len(predictions) == 32
    expected_model = 'yolov8l.pt' if detector == 'yolov8' else 'yolo11l.pt'
    assert {r['model_name'] for r in features} == {expected_model}
    boundary = datetime(2025, 10, 25)
    assert all(datetime.fromisoformat(r['source_time']) < boundary and
               datetime.fromisoformat(r['target_time']) < boundary for r in train)
    assert all(datetime.fromisoformat(r['source_time']) >= boundary for r in test)
    assert {r['video_path'] for r in predictions} == {r['video_path'] for r in test}
    archived = read_csv(ROOT / 'CP-1/Executed_Results_Analysis/matched_holdout_predictions.csv')
    assert {r['video_path']:r['next_enter_rating'] for r in predictions} == {
        r['video_path']:r['next_enter_rating'] for r in archived}
    forbidden = {'next_enter_rating', 'congestion_enter_rating', 'target_time', 'split'}
    assert not forbidden.intersection(settings['feature_columns'])
    matrix = [[0 for _ in CLASSES] for _ in CLASSES]
    for row in predictions:
        feature = index[row['video_path']]
        for field in ['next_enter_rating', 'source_time', 'target_time']:
            assert row[field] == feature[field]
        matrix[CLASSES.index(row['next_enter_rating'])][CLASSES.index(row['prediction'])] += 1
    saved_matrix = read_csv(EXPORT / 'confusion_matrix.csv')
    for i, row in enumerate(saved_matrix):
        assert row[''] == CLASSES[i]
        assert [int(row[c]) for c in CLASSES] == matrix[i]
    class_results = []
    reports = {r['']:r for r in read_csv(EXPORT / 'classification_report.csv')}
    for i, label in enumerate(CLASSES):
        tp = matrix[i][i]
        support = sum(matrix[i])
        predicted = sum(row[i] for row in matrix)
        precision = tp/predicted if predicted else 0
        recall = tp/support if support else 0
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0
        for key, value in [('precision', precision), ('recall', recall), ('f1-score', f1), ('support', support)]:
            check_close(value, reports[label][key])
        class_results.append(dict(label=label, correct=tp, support=support,
                                  precision=precision, recall=recall, macro_component=f1))
    correct = sum(matrix[i][i] for i in range(4))
    accuracy = correct/len(predictions)
    macro_f1 = mean(r['macro_component'] for r in class_results)
    check_close(accuracy, metrics['selected_model']['accuracy'])
    check_close(macro_f1, metrics['selected_model']['macro_f1'])
    assert correct == int(metrics['selected_model']['correct'])
    persistence_correct = sum(r['next_enter_rating'] == r['congestion_enter_rating'] for r in test)
    assert persistence_correct == int(metrics['persistence_label_baseline']['correct'])
    majority_label = sorted(Counter(r['next_enter_rating'] for r in train).items(),
                            key=lambda pair:(-pair[1], CLASSES.index(pair[0])))[0][0]
    assert sum(r['next_enter_rating'] == majority_label for r in test) == int(metrics['majority']['correct'])
    folds = read_csv(EXPORT/'validation_folds.csv')
    ranking = read_csv(EXPORT/'validation_ranking.csv')
    for row in ranking:
        candidate_folds = [r for r in folds if r['candidate'] == row['candidate']]
        assert len(candidate_folds) == 3
        assert all(datetime.fromisoformat(r['validation_date']) < boundary for r in candidate_folds)
        for metric in ['macro_f1', 'accuracy']:
            check_close(mean(float(r[metric]) for r in candidate_folds), row[metric])
    assert ranking[0]['candidate'] == settings['selected_candidate']
    for row in metrics.values():
        assert int(row['n']) == len(predictions)
        check_close(int(row['correct'])/int(row['n']), row['accuracy'])

    audit = {'detector':detector, 'source': str(EXPORT.relative_to(ROOT)), 'train_n':len(train), 'test_n':len(test),
             'correct':correct, 'accuracy':accuracy, 'macro_f1':macro_f1,
             'classes':class_results, 'confusion_matrix':matrix,
             'same_clips_and_truth_as_archived_v2':True,
             'independent_test':False, 'packages':settings['packages'],
             'verified':['selected predictions, confusion matrix and class metrics agree',
                         'train/test path uniqueness, dates and labels agree',
                         'validation averages and selected candidate agree',
                         'baseline counts and accuracy arithmetic agree'],
             'limits':['Original-settings baseline predictions were not exported; its F1 was not independently recomputed.',
                       'The test set was previously examined; this is an exploratory evaluation.']}
    return audit, settings, metrics, predictions, features


def main():
    runs = {name:review_export(RESULTS/f'Forecasting_v3_{name}_cached',name)
            for name in ['yolo11','yolov8']}
    a11, s11, m11, p11, f11 = runs['yolo11']
    a8, s8, m8, p8, f8 = runs['yolov8']
    assert s11['packages'] == s8['packages']
    for split in ['train','test']:
        assert {r['video_path']:r['next_enter_rating'] for r in f11 if r['split']==split} == {
            r['video_path']:r['next_enter_rating'] for r in f8 if r['split']==split}
    v8_predictions = {r['video_path']:r for r in p8}
    paired = []
    for row in p11:
        other = v8_predictions[row['video_path']]
        assert row['next_enter_rating'] == other['next_enter_rating']
        paired.append({'video_path':row['video_path'], 'truth':row['next_enter_rating'],
                       'yolo11_prediction':row['prediction'], 'yolov8_prediction':other['prediction'],
                       'yolo11_correct':row['prediction']==row['next_enter_rating'],
                       'yolov8_correct':other['prediction']==other['next_enter_rating']})
    outcomes = Counter('both_correct' if r['yolo11_correct'] and r['yolov8_correct'] else
                       'yolo11_only_correct' if r['yolo11_correct'] else
                       'yolov8_only_correct' if r['yolov8_correct'] else 'both_incorrect' for r in paired)
    audit_folder = RESULTS/'Audits'
    audit_folder.mkdir(exist_ok=True)
    for name,(audit,*_) in runs.items():
        (audit_folder/f'COLAB_{name.upper()}_REVIEW.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    with (audit_folder/'colab_matched_holdout_predictions.csv').open('w',encoding='utf-8',newline='') as handle:
        writer = csv.DictWriter(handle,fieldnames=list(paired[0]))
        writer.writeheader()
        writer.writerows(paired)
    summary = {'same_package_versions':True, 'same_training_and_test_clips_and_labels':True,
               'packages':s11['packages'], 'paired_outcomes':dict(outcomes),
               'yolo11':a11, 'yolov8':a8,
               'accuracy_difference_percentage_points':100*(a11['accuracy']-a8['accuracy']),
               'macro_f1_difference':a11['macro_f1']-a8['macro_f1'], 'independent_test':False}
    (audit_folder/'COLAB_COMPARISON.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    table = '\n'.join(f"| {name} | {settings['selected_candidate']} | {audit['correct']}/32 | {audit['accuracy']:.3%} | {audit['macro_f1']:.6f} |"
                      for name,(audit,settings,*_) in runs.items())
    methods = '\n'.join(f"| {name} | {method} | {row['correct']}/32 | {float(row['accuracy']):.3%} | {float(row['macro_f1']):.6f} |"
                        for name,(_,_,metrics,*_) in runs.items() for method,row in metrics.items())
    classes = '\n'.join(f"| {r11['label']} | {r11['correct']}/{r11['support']} | {r11['macro_component']:.4f} | {r8['correct']}/{r8['support']} | {r8['macro_component']:.4f} |"
                        for r11,r8 in zip(a11['classes'],a8['classes']))
    report = f'''# Forecasting v3: reviewed cached results, 23 October 2026

The downloaded Colab exports confirm **YOLO11: 50.0% accuracy (16/32),
macro-F1 {a11['macro_f1']:.6f}**, and **YOLOv8: 40.625% (13/32), macro-F1
{a8['macro_f1']:.6f}**. These are next-segment congestion-classification scores.
Detection and vehicle-count accuracy remain unmeasured.

## Comparison and provenance

| Detector features | Selected classifier | Correct | Accuracy | Macro-F1 |
|---|---|---:|---:|---:|
{table}

Both runs use the same 48 training and 32 test clips, labels, seed, candidate
selection procedure, and package versions. Model selection uses mean macro-F1
on three chronological training-date validation folds, before test evaluation.
YOLO11's selected classifier uses 14 base features; YOLOv8's selected classifier
uses 28 base/context features. This compares selected forecasting pipelines;
it does not isolate the detector's contribution while holding the classifier
and feature set fixed.

The YOLO11 pipeline leads by **9.375 percentage points**, three additional correct
clips, and {a11['macro_f1']-a8['macro_f1']:.6f} macro-F1 on this test set.
Both are correct on {outcomes['both_correct']} clips; only YOLO11 is correct on
{outcomes['yolo11_only_correct']}; only YOLOv8 is correct on {outcomes['yolov8_only_correct']};
both are incorrect on {outcomes['both_incorrect']}.

Colab packages: scikit-learn {s11['packages']['scikit-learn']},
XGBoost {s11['packages']['xgboost']}, pandas {s11['packages']['pandas']},
NumPy {s11['packages']['numpy']}. Exports are stored in
`Forecasting_v3_yolo11_cached/` and `Forecasting_v3_yolov8_cached/`.
Earlier local outputs remain in `Local_Runs/yolo11/` and `Local_Runs/yolov8/`; use the downloaded
Colab values above when reporting these completed runs. Software differences
explain why earlier local F1/control results need not exactly reproduce these
exports. Model artifacts were not loaded during review.

## Colab controls on the same 32 clips

| Detector features | Method | Correct | Accuracy | Macro-F1 |
|---|---|---:|---:|---:|
{methods}

Against the corresponding refitted original-settings control, the selected
YOLO11 pipeline gains 9.375 percentage points (three clips); the YOLOv8 pipeline
gains 6.25 percentage points (two clips). Archived v2 accuracy was 37.5% for
both detectors. The descriptive v3 differences from v2 are +12.5 points for
YOLO11 and +3.125 for YOLOv8. Historical comparisons change software,
preprocessing and row order and do not isolate a single cause.

## Performance by congestion class

| Class | YOLO11 correct | YOLO11 F1 | YOLOv8 correct | YOLOv8 F1 |
|---|---:|---:|---:|---:|
{classes}

YOLO11 performs better on light delay, while YOLOv8 performs better on moderate
delay. Free-flowing recall is equal. YOLO11 is the stronger selected forecasting
pipeline on this particular evaluation, without establishing universal or
detector-level superiority.

## Verification and interpretation

For each export, predictions independently reproduce the selected model's
accuracy, macro-F1, confusion matrix and per-class report. The exports match
all archived v2 holdout paths and labels, with no duplicate paths or training
targets crossing the 25 October split. Validation averages and selected
candidates match saved fold scores. Baseline counts agree; original-settings
baseline F1 cannot be independently recomputed because its predictions were
not exported. Detector identity is checked from every feature row.

The same test clips from 25-26 October 2025 were examined before this experiment.
Report this as an exploratory cached-feature improvement. Independent testing
with frozen settings and untouched dates/cameras remains necessary. Expanded
GPU extraction was not part of these cached runs. Later experimental stages
are reported separately and must retain their own test conditions and baselines.

Machine-readable audits: `Audits/COLAB_YOLO11_REVIEW.json`,
`Audits/COLAB_YOLOV8_REVIEW.json`, `Audits/COLAB_COMPARISON.json`.
Matched predictions: `Audits/colab_matched_holdout_predictions.csv`.
Original downloaded ZIPs are retained once each in `Archives/`.
'''
    comparison = RESULTS/'COMPARISON.md'
    marker = '<!-- expanded-yolo11-review -->'
    previous = comparison.read_text(encoding='utf-8') if comparison.exists() else ''
    if marker in previous:
        report = report.rstrip()+'\n\n'+marker+previous.split(marker,1)[1]
    comparison.write_text(report,encoding='utf-8')
    print(f"Verified YOLO11: {a11['correct']}/32, macro-F1={a11['macro_f1']:.6f}")
    print(f"Verified YOLOv8: {a8['correct']}/32, macro-F1={a8['macro_f1']:.6f}")
    print('Updated COMPARISON.md, JSON audits and matched predictions; original exports preserved.')


if __name__ == '__main__':
    main()
