"""Verify the shared A/B/C evidence without GPU inference or model deserialization.

This portable review does not claim to verify the omitted raw tracking logs.
Run review_expanded_forecasting_export.py with the original archive for that.
"""
import csv
import hashlib
import io
import json
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean

from review_forecasting_colab_export import CLASSES, read_csv, check_close, review_export
from review_expanded_forecasting_export import metric_values, semantic_hash

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/'CP-1/Forecasting_v3_Results'


def verify_pilot():
    path = ROOT/'CP-1/Journal_Results_Export_v2-20261020T090346Z-1-001.zip'
    with zipfile.ZipFile(path) as archive:
        def read(name):
            text = archive.read('Journal_Results_Export_v2/'+name).decode('utf-8-sig')
            return list(csv.DictReader(io.StringIO(text)))
        original = read('next_segment_holdout_predictions.csv')
        original_metrics = read('next_segment_holdout_metrics.csv')[0]
    other = ROOT/'CP-1/Journal_Results_Export_yolov8_v2'
    rows = read_csv(other/'next_segment_holdout_predictions.csv')
    metrics = read_csv(other/'next_segment_holdout_metrics.csv')[0]
    expected = {r['video_path']:r['next_enter_rating'] for r in original}
    assert len(expected) == len(original) == len(rows) == 32
    assert expected == {r['video_path']:r['next_enter_rating'] for r in rows}
    for name, predictions, recorded in [('YOLO11',original,original_metrics),('YOLOv8',rows,metrics)]:
        result = metric_values([r['next_enter_rating'] for r in predictions],
                               [r['predicted_next_enter_rating'] for r in predictions])
        for key in ['accuracy','macro_f1']:
            check_close(result[key],recorded[key])
        assert result['correct'] == 12
        print(f"Stage A {name}: {result['correct']}/32; macro-F1 {result['macro_f1']:.6f}")


def verify_expanded():
    folder = RESULTS/'Archives/expanded_01/evaluation'
    settings = json.loads((folder/'selected_model.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((folder/'features_used.csv').read_bytes()).hexdigest() == settings['input_sha256']
    features = read_csv(folder/'features_used.csv')
    predictions = read_csv(folder/'evaluation_predictions.csv')
    metrics = read_csv(folder/'evaluation_metrics.csv')
    assert len(features) == len({r['video_path'] for r in features}) == 512
    assert Counter(r['split'] for r in features) == {'train':448,'test':64}
    assert (settings['train_n'],settings['test_n']) == (448,64)
    assert len(settings['feature_columns']) == 34
    assert not {'next_enter_rating','congestion_enter_rating','target_time','split'} & set(settings['feature_columns'])
    assert settings['fresh_independent_dates'] is False
    assert {r['model_name'] for r in features} == {'yolo11l.pt'}
    test = {r['video_path']:r for r in features if r['split']=='test'}
    assert set(test) == {r['video_path'] for r in predictions}
    assert len(predictions) == len(test) == 64
    boundary = datetime(2025,10,25)
    for row in features:
        source, target = map(datetime.fromisoformat,(row['source_time'],row['target_time']))
        assert target > source
        assert (target < boundary) if row['split']=='train' else (source >= boundary)
    assert Counter(r['next_enter_rating'] for r in predictions) == dict(zip(CLASSES,[52,6,5,1]))
    for row in predictions:
        for key in ['next_enter_rating','source_time','target_time']:
            assert row[key] == test[row['video_path']][key]
        assert row['prediction'] == row['selected_model_prediction']
        assert row['persistence_label_baseline_prediction'] == test[row['video_path']]['congestion_enter_rating']
    truth = [r['next_enter_rating'] for r in predictions]
    for row in metrics:
        result = metric_values(truth,[r[row['method']+'_prediction'] for r in predictions])
        for key in ['n','correct','accuracy','balanced_accuracy','macro_f1']:
            check_close(result[key],row[key])
        if row['method'] == 'selected_model':
            matrix = read_csv(folder/'confusion_matrix.csv')
            assert [[int(r[c]) for c in CLASSES] for r in matrix] == result['confusion_matrix']
            print(f"Stage C YOLO11: {result['correct']}/64; macro-F1 {result['macro_f1']:.6f}")
    ranking = read_csv(folder/'validation_ranking.csv')
    folds = read_csv(folder/'validation_folds.csv')
    assert ranking[0]['candidate'] == settings['selected_candidate'] == 'logistic_context'
    for row in ranking:
        scores = [f for f in folds if f['candidate']==row['candidate']]
        assert len(scores) == 3
        for key in ['macro_f1','accuracy']:
            check_close(mean(float(f[key]) for f in scores),row[key])
    assert ranking == sorted(ranking,key=lambda r:(-float(r['macro_f1']),-float(r['accuracy']),r['candidate']))
    plan_file = folder/'run_metadata/selected_pairs.csv'
    plan = read_csv(plan_file)
    contract = json.loads((folder/'run_metadata/checkpoint_contract.json').read_text(encoding='utf-8'))
    config = contract['configuration']
    assert hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest() == contract['signature']
    assert hashlib.sha256(plan_file.read_bytes()).hexdigest() == config['plan_sha256']
    assert semantic_hash(plan) == config['plan_semantic_sha256']
    assert {r['videos'] for r in plan} == {r['video_path'] for r in features}
    labels = {r['videos']:r for r in read_csv(ROOT/'CP-1/Data/Zindi_Labels/Train.csv')}
    for row in plan:
        assert row['congestion_enter_rating'] == labels[row['videos']]['congestion_enter_rating']
        assert row['next_enter_rating'] == labels[row['target_video_path']]['congestion_enter_rating']
    print('Expanded predictions, four methods, class supports, validation ranking and plan hashes agree.')


def main():
    verify_pilot()
    for model in ['yolo11','yolov8']:
        review_export(RESULTS/f'Forecasting_v3_{model}_cached',model)
        print('Stage B verified:',model)
    verify_expanded()
    print('PASS: published evidence verified without retraining or loading fitted models.')


if __name__ == '__main__':
    main()
