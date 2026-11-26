"""Meaningful offline checks for road geometry, incomplete tracks, leakage and resume."""
from pathlib import Path
from copy import deepcopy
import ast
import csv
import json
import sys
import uuid
import shutil
import unittest
from unittest import mock
import types
import importlib.util

import cv2
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'CP-1/Program'))
import junction_counting_v4 as j
import junction_calibration_v4 as ui
import junction_forecasting_v4 as f
import junction_drawing_v4 as drawing


def camera():
    return dict(reviewed=True,reference_size=[80,60],reference_sha256='0'*64,gates=[
        dict(name='A',label='left',a=[.2,.25],b=[.2,.85],inside=[.5,.5]),
        dict(name='B',label='upper',a=[.3,.2],b=[.7,.2],inside=[.5,.5]),
        dict(name='C',label='right',a=[.8,.25],b=[.8,.85],inside=[.5,.5])])


def history_fixture():
    rows=[];labels=[]
    for day in range(20,27):
        for minute in range(12):
            start=pd.Timestamp(f'2025-10-{day} 06:00:00')+pd.Timedelta(minutes=minute)
            key='normanniles2/normanniles2_'+start.strftime('%Y-%m-%d-%H-%M-%S')+'.mp4'
            values={c:float((minute+day)%5+1) for c in f.MEASUREMENTS}
            rows.append(dict(video_path=key,camera_id='normanniles2',duration_sec=59.,
                route_A_B=minute%3,route_A_C_car=minute%2,gate_A_entry_car=2,**values))
            labels.append(dict(videos=key,datetimestamp_start=start,datetimestamp_end=start+pd.Timedelta(seconds=59),
                               congestion_enter_rating=f.CLASSES[minute%4]))
    return pd.DataFrame(rows),pd.DataFrame(labels)


class GeometryTests(unittest.TestCase):
    def counter(self):return j.JourneyCounter(camera(),10,dict(max_motion_per_second=2.))

    def test_two_destinations_from_same_origin(self):
        c=self.counter()
        for frame,p in [(0,(.1,.5)),(3,(.3,.5)),(6,(.5,.4)),(9,(.5,.1))]:c.observe(frame,1,p,'car',.9)
        for frame,p in [(0,(.1,.6)),(3,(.3,.6)),(6,(.6,.6)),(9,(.9,.6))]:c.observe(frame,2,p,'truck',.8)
        routes={(r['origin'],r['destination'],r['vehicle_class']) for r in c.finish() if r['status']=='complete'}
        self.assertEqual(routes,{('A','B','car'),('A','C','truck')})
        self.assertEqual(len(c.events),4)

    def test_finite_gate_and_born_inside_are_not_invented_journeys(self):
        c=self.counter()
        c.observe(0,1,(.1,.95),'car',.9);c.observe(3,1,(.3,.95),'car',.9)
        c.observe(0,2,(.5,.5),'bus',.9);c.observe(3,2,(.9,.5),'bus',.9)
        rows=c.finish()
        self.assertFalse(any(r['status']=='complete' for r in rows))
        self.assertIn('exit_without_entry',{r['reason'] for r in rows})
        self.assertEqual(len(c.events),1)

    def test_gap_and_identity_switch_do_not_bridge_routes(self):
        c=self.counter()
        c.observe(0,1,(.1,.5),'car',.9);c.observe(3,1,(.3,.5),'car',.9)
        c.observe(20,1,(.9,.5),'car',.9)
        c.observe(21,2,(.6,.6),'car',.9);c.observe(24,2,(.9,.6),'car',.9)
        self.assertFalse(any(r['status']=='complete' for r in c.finish()))
        self.assertIn('tracking_gap',{i['flag'] for i in c.issues})

    def test_line_dwell_hysteresis_and_multiple_classes(self):
        c=self.counter();c.observe(0,1,(.1,.5),'truck',.7)
        for frame in range(1,14):c.observe(frame,1,(.2,.5),'car',.9)
        c.observe(14,1,(.3,.5),'car',.9)
        self.assertEqual([(e['gate'],e['event']) for e in c.events],[('A','entry')])
        c.observe(17,1,(.6,.5),'car',.9);c.observe(20,1,(.9,.5),'car',.9)
        self.assertEqual(c.finish()[0]['vehicle_class'],'car')
        self.assertEqual(c.finish()[0]['status'],'complete')

    def test_calibration_is_not_a_default_line(self):
        bad=camera();bad['reviewed']=False
        with self.assertRaises(ValueError):j.validate_camera(bad)
        bad=camera();bad['gates'][0]['inside']=bad['gates'][0]['a']
        with self.assertRaises(ValueError):j.validate_camera(bad)
        bad=camera();bad['gates'][1]['a']=[0,.5];bad['gates'][1]['b']=[1,.5]
        with self.assertRaises(ValueError):j.validate_camera(bad)

    def test_clock_and_colour_checks_flag_candidates_only(self):
        clock=iter(['10:00:20','10:00:21','10:00:17'])
        fake=types.SimpleNamespace(get_tesseract_version=lambda:'test',
            image_to_string=lambda *a,**kw:next(clock))
        with mock.patch.dict(sys.modules,{'pytesseract':fake}):
            quality=j.FrameQuality(10,camera(),dict(j.DEFAULTS))
            quality.check(0,np.full((60,80,3),80,dtype=np.uint8))
            quality.check(10,np.full((60,80,3),130,dtype=np.uint8))
            quality.check(20,np.full((60,80,3),130,dtype=np.uint8))
        self.assertEqual(quality.ocr_matches,3)
        self.assertEqual({r['flag'] for r in quality.flags},
                         {'camera_clock_jump_candidate','colour_brightness_change_candidate'})


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.folder=ROOT/('.junction_test_'+uuid.uuid4().hex)
        self.folder.mkdir()
        assert self.folder.resolve().parent==ROOT.resolve() and self.folder.name.startswith('.junction_test_')

    def tearDown(self):
        assert self.folder.resolve().parent==ROOT.resolve() and self.folder.name.startswith('.junction_test_')
        shutil.rmtree(self.folder)

    def test_inventory_covers_all_four_folders_without_sampling(self):
        for name in j.CAMERAS:
            folder=self.folder/name;folder.mkdir()
            for index in range(25):(folder/f'video_{index}.mp4').write_bytes(b'test')
            nested=folder/'nested';nested.mkdir();(nested/'extra.MP4').write_bytes(b'test')
        other=self.folder/'added';other.mkdir();(other/'not_one_of_the_four_views.mp4').write_bytes(b'test')
        inv=j.inventory(self.folder)
        self.assertEqual(len(inv),104)
        self.assertEqual(set(inv.camera_id),set(j.CAMERAS))
        self.assertTrue(inv.groupby('camera_id').size().eq(26).all())

    def test_pilot_review_is_required_and_bound_to_geometry_and_detector(self):
        calibration=dict(cameras={c:camera() for c in j.CAMERAS})
        with self.assertRaises(ValueError):ui.require_pilot_reviews(self.folder,calibration,'yolo11',{})
        receipts={'yolo11/'+c:dict(counting_signature=ui.counting_signature(camera(),'yolo11',{})) for c in j.CAMERAS}
        j.atomic_json(self.folder/'pilot_reviews.json',receipts)
        ui.require_pilot_reviews(self.folder,calibration,'yolo11',{})
        with self.assertRaises(ValueError):ui.require_pilot_reviews(self.folder,calibration,'yolov8',{})
        changed=deepcopy(calibration);changed['cameras']['normanniles2']['gates'][0]['a'][0]=.21
        with self.assertRaises(ValueError):ui.require_pilot_reviews(self.folder,changed,'yolo11',{})

    def test_video_checkpoint_resume_and_tamper_detection(self):
        base=self.folder/'dataset';(base/'normanniles2').mkdir(parents=True)
        video=base/'normanniles2'/'synthetic.mp4'
        writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),10,(80,60))
        self.assertTrue(writer.isOpened())
        for i in range(30):writer.write(np.full((60,80,3),50+i,dtype=np.uint8))
        writer.release()
        class Array:
            def __init__(self,a):self.a=np.array(a)
            def cpu(self):return self
            def numpy(self):return self.a
        class Boxes(list):id=True
        class Model:
            def __init__(self):self.frame=0
            def track(self,frame,**kwargs):
                x=(.1+.8*self.frame/29)*80;self.frame+=1
                box=types.SimpleNamespace(id=[1],cls=[2],conf=[.9],xyxy=[Array([x-3,18,x+3,30])])
                return [types.SimpleNamespace(boxes=Boxes([box]))]
        videos=pd.DataFrame([dict(video_path='normanniles2/synthetic.mp4',camera_id='normanniles2',size_bytes=video.stat().st_size)])
        calibration=dict(cameras={'normanniles2':camera()})
        run=self.folder/'run';settings=dict(clock_sample_seconds=0)
        features,pending=j.run_batch(base,run,videos,calibration,settings=settings,preview=True,model_factory=lambda _:Model())
        self.assertFalse(pending);self.assertEqual(features.complete_journeys.iloc[0],1)
        self.assertEqual(features.route_A_C_car.iloc[0],1)
        factory=mock.Mock(side_effect=AssertionError('Resume must not load the detector.'))
        again,pending=j.run_batch(base,run,videos,calibration,settings=settings,model_factory=factory)
        factory.assert_not_called();self.assertFalse(pending)
        self.assertEqual(again.complete_journeys.tolist(),features.complete_journeys.tolist())
        bad=deepcopy(calibration);bad['cameras']['normanniles2']['gates'][0]['a'][0]=.21
        with self.assertRaises(ValueError):j.freeze_run(run,videos,bad,'yolo11',settings)
        directory=j.clip_directory(run,videos.video_path.iloc[0]);(directory/'features.json').write_text('{}')
        with self.assertRaises(ValueError):j.verify_checkpoint(directory,json.loads((run/'contract.json').read_text())['signature'])

    def test_manual_counts_reject_blanks_and_partial_clips(self):
        cam=camera();rows={c:0 for c in ['route_'+a+'_'+b+'_'+cls for a in ['A','B','C'] for b in ['A','B','C'] if a!=b for cls in j.CLASSES.values()]}
        features=pd.DataFrame([dict(video_path='normanniles2/a.mp4',camera_id='normanniles2',**rows)])
        calibration=dict(cameras={'normanniles2':cam})
        f.manual_templates(features,calibration,self.folder)
        path=self.folder/'manual_journey_counts.csv'
        with self.assertRaises(ValueError):f.evaluate_manual_counts(features,calibration,path,self.folder/'evaluation')
        annotations=pd.read_csv(path);annotations['ground_truth_count']=0;annotations['annotation_status']='complete'
        annotations.to_csv(path,index=False)
        report=f.evaluate_manual_counts(features,calibration,path,self.folder/'evaluation')
        self.assertEqual(report['cell_mae'],0.)
        annotations=annotations.iloc[:-1];annotations.to_csv(path,index=False)
        with self.assertRaises(ValueError):f.evaluate_manual_counts(features,calibration,path,self.folder/'evaluation')

    def test_mouse_drawing_export_and_import_reference_checks(self):
        original=dict(version=j.VERSION,cameras={})
        for name in j.CAMERAS:
            image=self.folder/(name+'.png')
            self.assertTrue(cv2.imwrite(str(image),np.zeros((60,80,3),dtype=np.uint8)))
            record=camera();record.update(reference_sha256=j.file_hash(image),gates=[],reviewed=False)
            original['cameras'][name]=record
        j.atomic_json(self.folder/'gates.json',original)
        page=drawing.write_drawing_page(self.folder)
        html=page.read_text(encoding='utf-8')
        self.assertEqual(html.count('data:image/png;base64,'),4)
        self.assertNotIn('__PAYLOAD__',html)
        drawn=deepcopy(original)
        for name in j.CAMERAS:drawn['cameras'][name].update(gates=camera()['gates'],reviewed=True)
        drawn['cameras']['normanniles2']['gates'][0]['label']='left <road>'
        saved=drawing.import_drawn_gates(self.folder,json.dumps(drawn).encode())
        self.assertEqual(saved['cameras']['normanniles2']['gates'][0]['label'],'left <road>')
        self.assertEqual(len(list(self.folder.glob('gates_before_drawing_*.json'))),1)
        bad=deepcopy(drawn);bad['cameras']['normanniles1']['reference_sha256']='bad'
        before=(self.folder/'gates.json').read_bytes()
        with self.assertRaises(ValueError):drawing.import_drawn_gates(self.folder,bad)
        self.assertEqual(before,(self.folder/'gates.json').read_bytes())
        bad=deepcopy(drawn);bad['cameras']['normanniles1']['reviewed']=False
        with self.assertRaises(ValueError):drawing.import_drawn_gates(self.folder,bad)
        bad=deepcopy(drawn);bad['cameras']['normanniles1']['gates']=bad['cameras']['normanniles1']['gates'][:2]
        with self.assertRaises(ValueError):drawing.import_drawn_gates(self.folder,bad)
        page=drawing.write_drawing_page(self.folder)
        import re
        payload=re.search(r'id="payload">(.*?)</script>',page.read_text(encoding='utf-8'),re.S)[1]
        self.assertEqual(json.loads(payload)['calibration']['cameras']['normanniles2']['gates'][0]['label'],'left <road>')

    def test_notebook_update_preserves_user_configuration_and_other_outputs(self):
        spec=importlib.util.spec_from_file_location('junction_builder',ROOT/'Scripts/create_junction_v4_notebook.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        nb=json.loads((ROOT/'CP-1/Program/CP1_Junction_Movement_v4.ipynb').read_text(encoding='utf-8'))
        config=''.join(nb['cells'][3]['source']).replace("STAGE='calibrate'","STAGE='pilot'")
        config='\n'.join(line for line in config.splitlines() if not line.startswith('CALIBRATION_METHOD='))+'\n'
        nb['cells'][3]['source']=config.splitlines(keepends=True)
        nb['cells'][6]['outputs']=[dict(output_type='stream',name='stdout',text=['keep this user output'])]
        nb['cells'][6]['execution_count']=9
        output=self.folder/'notebook.ipynb';output.write_text(json.dumps(nb),encoding='utf-8')
        with mock.patch.object(builder,'TARGET',output):builder.main(update_existing=True)
        updated=json.loads(output.read_text(encoding='utf-8'))
        self.assertIn("STAGE='pilot'",''.join(updated['cells'][3]['source']))
        self.assertIn("CALIBRATION_METHOD='draw'",''.join(updated['cells'][3]['source']))
        self.assertEqual(updated['cells'][6],nb['cells'][6])
        self.assertEqual(updated['metadata'],nb['metadata'])
        self.assertFalse(updated['cells'][4]['outputs'])

    def test_history_does_not_use_labels_or_future_features(self):
        features,labels=history_fixture()
        meta,current,history,excluded=f.build_history(features,labels,3)
        changed=labels.copy();changed['congestion_enter_rating']=np.roll(changed.congestion_enter_rating,7)
        m2,c2,h2,_=f.build_history(features,changed,3)
        pd.testing.assert_frame_equal(current,c2);pd.testing.assert_frame_equal(history,h2)
        self.assertNotIn('source_label',current);self.assertNotIn('target_label',history)
        first=meta.iloc[0];changed_features=features.copy()
        changed_features.loc[changed_features.video_path.eq(first.target_video_path),'complete_journeys']=999999
        m3,c3,h3,_=f.build_history(changed_features,labels,3)
        pd.testing.assert_series_equal(history.iloc[0],h3.iloc[0])
        self.assertTrue((meta.source_end<=meta.target_time).all())
        self.assertTrue(meta.history_video_paths.map(lambda s:len(json.loads(s))==3).all())
        broken=features[~features.video_path.eq(json.loads(first.history_video_paths)[0])]
        mb,_,_,_=f.build_history(broken,labels,3)
        self.assertNotIn(first.video_path,set(mb.video_path))

    def test_chronological_selection_export_and_baselines(self):
        features,labels=history_fixture()
        choices=[('logistic_current_balanced','logistic','current','balanced'),
                 ('logistic_history_balanced','logistic','history','balanced'),
                 ('xgb_history_balanced','xgb','history','balanced')]
        output=self.folder/'forecast'
        with mock.patch.object(f,'candidates',return_value=choices):
            metrics=f.evaluate(features,labels,output)
            repeated=f.evaluate(features,labels,output)
            self.assertEqual(metrics.method.tolist(),repeated.method.tolist())
            with self.assertRaises(ValueError):f.evaluate(features,labels,output,history_clips=2)
        selection=json.loads((output/'selected_model.json').read_text())
        self.assertIn(selection['selected_candidate'],{c[0] for c in choices})
        p=pd.read_csv(output/'evaluation_predictions.csv')
        majority=metrics.set_index('method').loc['training_majority']
        self.assertAlmostEqual(majority.accuracy,(p.target_label==p.training_majority).mean())
        pairs=pd.read_csv(output/'selected_pairs.csv')
        train=pairs[pairs.split.eq('train')];test=pairs[pairs.split.eq('test')]
        self.assertLess(pd.to_datetime(train.target_time).max(),pd.to_datetime(test.history_start).min())
        self.assertEqual(selection['evaluation_kind'],'previously_examined_week')

    def test_notebook_embeds_current_modules_and_guards_batch(self):
        nb=json.loads((ROOT/'CP-1/Program/CP1_Junction_Movement_v4.ipynb').read_text(encoding='utf-8'))
        source='\n'.join(''.join(c['source']) for c in nb['cells'])
        self.assertIn("STAGE='calibrate'",source)
        self.assertIn('require_pilot_reviews',source)
        for c in nb['cells']:
            if c['cell_type']=='code':
                tree=ast.parse(''.join(c['source']))
                for node in tree.body:
                    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULE_SOURCES' for t in node.targets):
                        embedded=ast.literal_eval(node.value)
                        for name,text in embedded.items():
                            self.assertEqual(text,(ROOT/'CP-1/Program'/name).read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main(verbosity=2)
