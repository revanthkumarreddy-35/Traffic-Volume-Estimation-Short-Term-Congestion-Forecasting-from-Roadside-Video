"""Check leakage boundaries, label-blind sampling and motion calculations."""
from pathlib import Path
import sys
import hashlib
import contextlib
import io
import importlib.metadata
import json
import shutil
import types
import unittest
import uuid
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'CP-1/Program'))
from congestion_forecasting_v3 import (
    read_cached, make_inputs, expansion_plan, motion_features, model_pipeline,
    dataset_label_audit, validate_labels, prepare_pairs,
    plan_fingerprint, contract_signature, checkpoint_changes,
)
import congestion_forecasting_v3 as forecasting


class ForecastingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cached = read_cached(ROOT, 'yolo11')
        cls.labels = pd.read_csv(ROOT/'CP-1/Data/Zindi_Labels/Train.csv')

    def test_human_labels_and_future_metadata_cannot_change_features(self):
        before = make_inputs(self.cached, True)
        changed = self.cached.copy()
        for name in ['next_enter_rating', 'congestion_enter_rating', 'target_time', 'split']:
            changed[name] = 'deliberately corrupted'
        pd.testing.assert_frame_equal(before, make_inputs(changed, True))
        self.assertNotIn('horizon_sec', before)

    def test_plan_excludes_old_test_and_is_label_blind(self):
        available = set(self.labels.videos)
        plan = expansion_plan(self.labels, available, self.cached, 2, 2)
        changed = self.labels.copy()
        changed['congestion_enter_rating'] = np.roll(changed.congestion_enter_rating, 97)
        second = expansion_plan(changed, available, self.cached, 2, 2)
        self.assertEqual(plan.videos.tolist(), second.videos.tolist())
        self.assertFalse(set(plan.loc[plan.split=='test','videos']) & set(self.cached.video_path))
        self.assertTrue((plan.loc[plan.split=='train','target_time'] < pd.Timestamp('2025-10-25')).all())
        for row in self.cached.itertuples():
            nearby = plan[(plan.split=='test') & (plan.camera_id==row.camera_id)]
            for moment in [row.source_time, row.target_time]:
                self.assertTrue(((nearby.source_time-pd.Timestamp(moment)).abs() > pd.Timedelta(minutes=2)).all())
                self.assertTrue(((nearby.target_time-pd.Timestamp(moment)).abs() > pd.Timedelta(minutes=2)).all())

    def test_motion_includes_empty_frames_and_excludes_long_gaps(self):
        rows = pd.DataFrame([
            dict(frame_idx=0,track_id=1,cx=0,cy=0,x1=0,y1=0,x2=10,y2=10),
            dict(frame_idx=1,track_id=1,cx=3,cy=4,x1=0,y1=0,x2=10,y2=10),
            dict(frame_idx=9,track_id=1,cx=99,cy=99,x1=0,y1=0,x2=10,y2=10),
        ])
        result = motion_features(rows, {'fps':10,'total_frames':10,'resolution':'100x100'})
        self.assertAlmostEqual(result['motion_speed_median'], 5/(.1*np.hypot(100,100)))
        self.assertAlmostEqual(result['bbox_occupancy_proxy'], 300/(10*100*100))
        with self.assertRaises(ValueError):
            motion_features(pd.concat([rows,rows]), {'fps':10,'total_frames':10,'resolution':'100x100'})

    def test_new_camera_is_handled_without_fitting_on_test(self):
        train = make_inputs(self.cached.iloc[:16], True)
        test = make_inputs(self.cached.iloc[16:17], True)
        test['camera_id'] = 'unseen_camera'
        pipeline = model_pipeline('logistic', train)
        pipeline.fit(train, np.arange(len(train))%4)
        self.assertEqual(len(pipeline.predict(test)), 1)

    def test_label_coverage_and_conflicts(self):
        labels = self.labels.iloc[:3].copy()
        available = {labels.videos.iloc[0], 'normanniles1/unlabelled.mp4'}
        coverage, missing, unlabelled = dataset_label_audit(labels, available)
        self.assertEqual(coverage.matched_videos.sum(),1)
        self.assertEqual(len(missing),2)
        self.assertEqual(len(unlabelled),1)
        conflict = labels.iloc[[0]].copy()
        conflict['congestion_enter_rating'] = 'heavy delay'
        with self.assertRaisesRegex(ValueError,'conflicting'):
            validate_labels(pd.concat([labels,conflict],ignore_index=True))
        with self.assertRaisesRegex(ValueError,'missing columns'):
            validate_labels(labels.drop(columns='videos'))
        labels.loc[labels.index[1],'datetimestamp_end'] = labels.datetimestamp_start.iloc[1]
        coverage,_,_ = dataset_label_audit(labels,set(labels.videos))
        self.assertEqual(coverage.invalid_timing_labels.sum(),1)
        self.assertTrue(prepare_pairs(labels,set(labels.videos)).empty)

    def test_default_expansion_counts_and_limits(self):
        plan = expansion_plan(self.labels,set(self.labels.videos),self.cached)
        self.assertEqual(plan.split.value_counts().to_dict(),{'train':448,'test':64})
        self.assertEqual(len(set(plan.videos) & set(self.cached.video_path)),48)
        with self.assertRaises(ValueError):
            expansion_plan(self.labels,set(self.labels.videos),self.cached,0,8)

    def test_plan_hash_ignores_serialization_but_detects_label_changes(self):
        plan = expansion_plan(self.labels,set(self.labels.videos),self.cached,1,1)
        decoded = pd.read_csv(io.StringIO(plan.to_csv(index=False))).iloc[::-1].copy()
        decoded['cosmetic_column'] = 'irrelevant'
        self.assertEqual(plan_fingerprint(plan),plan_fingerprint(decoded))
        decoded.loc[decoded.index[0],'next_enter_rating'] = (
            'heavy delay' if decoded.next_enter_rating.iloc[0] != 'heavy delay' else 'light delay')
        self.assertNotEqual(plan_fingerprint(plan),plan_fingerprint(decoded))

    def test_contract_reports_exact_behavior_changes(self):
        original = {'version':4,'model':'yolo11l.pt','lines':{'default':[[0,0],[1,1]]},
                    'plan_sha256':'fixed','processor_sha256':'original'}
        current = {**original,'version':5,'lines':{'default':((0,0),(1,1))},
                   'sampling_limits':{'train':20},'plan_semantic_sha256':'semantic'}
        saved = {'configuration':original,'signature':contract_signature(original)}
        self.assertEqual(checkpoint_changes(saved,current),{})
        current['processor_sha256'] = 'different'
        self.assertEqual(set(checkpoint_changes(saved,current)),{'processor_sha256'})

    def test_expanded_preflight_resume_and_changed_config(self):
        # Dummy MP4 filenames and a stub extractor exercise the notebook workflow.
        # No network requests, GPU, video decoding or model download are performed.
        root = ROOT/('.forecasting_test_'+uuid.uuid4().hex)
        root.mkdir()
        try:
            for i in range(1,5):
                (root/f'normanniles{i}').mkdir()
            labels = self.labels.groupby(['view_label','date'],sort=False).tail(4).copy()
            for key in labels.videos:
                (root/key).touch()
            (root/'CSV').mkdir()
            labels.to_csv(root/'CSV/Train.csv',index=False)
            processor = '''
def process_video_with_tracking(video_path, model):
    key = make_video_key(video_path)
    PROCESS_CALLS.append(key)
    if INTERRUPT_AT and len(PROCESS_CALLS) == INTERRUPT_AT:
        return None, None, None
    row = historical.iloc[0].to_dict()
    row.update(video_path=key, model_name=YOLO_MODEL_NAME)
    return row, None, None
'''
            namespace = dict(vars(forecasting))
            namespace.update(RUN_MODE='expanded',DETECTOR='yolo11',DRIVE_BASE=str(root),
                             LABELS_RELATIVE_PATH='CSV/Train.csv',EXPERIMENT_NAME='test_run',
                             TRAIN_CLIPS_PER_CAMERA_DATE=1,TEST_CLIPS_PER_CAMERA_DATE=1,
                             PLAN_ONLY=True,USE_MOTION_FEATURES=False,historical=self.cached,
                             PROCESSOR_CODE=processor,TRACKER_SETTINGS={},display=lambda table:None,
                             PROCESS_CALLS=[],INTERRUPT_AT=2)
            fake_colab = types.ModuleType('google.colab')
            fake_colab.drive = types.SimpleNamespace(mount=lambda path:None)
            fake_torch = types.ModuleType('torch')
            fake_torch.cuda = types.SimpleNamespace(is_available=lambda:True)
            fake_yolo = types.ModuleType('ultralytics')
            fake_yolo.YOLO = lambda model:object()
            fake_yaml = types.ModuleType('yaml')
            fake_yaml.safe_dump = json.dumps
            source = (ROOT/'CP-1/Program/notebook_sources/forecasting_expanded.py').read_text(encoding='utf-8')
            modules = {'google.colab':fake_colab,'torch':fake_torch,'ultralytics':fake_yolo,
                       'yaml':fake_yaml,'cv2':types.ModuleType('cv2')}
            with mock.patch.dict(sys.modules,modules), mock.patch('subprocess.check_call') as installer, \
                    mock.patch.object(importlib.metadata,'version',return_value='test-version'), \
                    contextlib.redirect_stdout(io.StringIO()):
                exec(source,namespace)
                self.assertIsNone(namespace['features'])
                self.assertTrue((root/'Forecasting_v3/yolo11/test_run/preflight/SUMMARY.json').exists())
                installer.assert_not_called()
                namespace['PLAN_ONLY'] = False
                with self.assertRaisesRegex(RuntimeError,'Interrupted'):
                    exec(source,namespace)
                checkpoint = root/'Forecasting_v3/yolo11/test_run/extracted_features.csv'
                saved = pd.read_csv(checkpoint)
                first_completed = namespace['PROCESS_CALLS'][0]
                self.assertIn(first_completed,set(saved.video_path))
                # Simulate a v4 run whose saved CSV includes an older cosmetic column.
                run_folder = checkpoint.parent
                contract_path = run_folder/'checkpoint_contract.json'
                manifest = json.loads(contract_path.read_text())
                legacy = {k:v for k,v in manifest['configuration'].items()
                          if k not in {'sampling_limits','plan_semantic_sha256'}}
                legacy['version'] = 4
                frozen_path = run_folder/'selected_pairs.csv'
                frozen = pd.read_csv(frozen_path)
                frozen['old_export_metadata'] = 'keep original plan bytes'
                frozen.to_csv(frozen_path,index=False)
                frozen_bytes = frozen_path.read_bytes()
                legacy['plan_sha256'] = hashlib.sha256(frozen_bytes).hexdigest()
                contract_path.write_text(json.dumps({'configuration':legacy,'signature':contract_signature(legacy)}))
                namespace.update(INTERRUPT_AT=0,PROCESS_CALLS=[])
                exec(source,namespace)
                self.assertNotIn(first_completed,namespace['PROCESS_CALLS'])
                self.assertEqual(set(namespace['features'].video_path),set(namespace['plan'].videos))
                self.assertEqual(frozen_path.read_bytes(),frozen_bytes)
                self.assertTrue((run_folder/'checkpoint_contract.v4.json').is_file())
                self.assertEqual(json.loads(contract_path.read_text())['configuration']['version'],5)
                self.assertIn('ultralytics==test-version',installer.call_args.args[0])
                checksum = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
                namespace['TRAIN_CLIPS_PER_CAMERA_DATE'] = 2
                with self.assertRaisesRegex(RuntimeError,'changed'):
                    exec(source,namespace)
                self.assertEqual(hashlib.sha256(checkpoint.read_bytes()).hexdigest(),checksum)
        finally:
            self.assertEqual(root.resolve().parent,ROOT.resolve())
            self.assertTrue(root.name.startswith('.forecasting_test_'))
            shutil.rmtree(root)


if __name__=='__main__': unittest.main()
