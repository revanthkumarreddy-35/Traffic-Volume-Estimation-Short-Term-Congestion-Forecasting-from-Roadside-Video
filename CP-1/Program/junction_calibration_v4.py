"""Standard ipywidgets calibration controls, usable with VS Code/Colab notebooks."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.metadata
import json
import zipfile

import cv2
import numpy as np
import pandas as pd

import junction_counting_v4 as core


def gate_editor(folder):
    import ipywidgets as w
    import matplotlib.pyplot as plt
    from IPython.display import display,clear_output
    folder=Path(folder);path=folder/'gates.json'
    calibration=json.loads(path.read_text())
    camera=w.Dropdown(options=core.CAMERAS,description='Camera:')
    gate=w.Dropdown(options=['A','B','C'],description='Road gate:')
    label=w.Text(description='Road name:',placeholder='e.g. left / upper / right')
    names=['a_x','a_y','b_x','b_y','inside_x','inside_y']
    sliders={n:w.IntSlider(description=n,min=0,max=100,value=0,continuous_update=False,
                           layout=w.Layout(width='430px')) for n in names}
    status=w.Output();plot=w.Output();draft={};loading=[False]
    store=w.Button(description='Store this road gate',button_style='info',layout=w.Layout(width='210px'))
    save=w.Button(description='Save reviewed camera gates',button_style='success',layout=w.Layout(width='260px'))

    def candidate():
        rw,rh=calibration['cameras'][camera.value]['reference_size']
        return dict(name=gate.value,label=label.value.strip(),
            a=[sliders['a_x'].value/rw,sliders['a_y'].value/rh],
            b=[sliders['b_x'].value/rw,sliders['b_y'].value/rh],
            inside=[sliders['inside_x'].value/rw,sliders['inside_y'].value/rh])

    def render(*args):
        if loading[0]:return
        image=cv2.imread(str(folder/(camera.value+'.png')))
        if image is None:raise FileNotFoundError('Reference image is missing.')
        display_camera={**calibration['cameras'][camera.value],
                        'gates':[g for n,g in draft.items() if n!=gate.value]+[candidate()]}
        shown=core.draw_gates(image,display_camera)
        with plot:
            clear_output(wait=True)
            fig,ax=plt.subplots(figsize=(12,6.75))
            ax.imshow(cv2.cvtColor(shown,cv2.COLOR_BGR2RGB))
            h,width=image.shape[:2]
            ax.set_xticks(range(0,width+1,max(1,width//10)));ax.set_yticks(range(0,h+1,max(1,h//10)))
            ax.grid(alpha=.35);ax.set_title(camera.value+' — yellow gate, green arrow toward junction')
            plt.show();plt.close(fig)

    def load_gate(*args):
        loading[0]=True
        size=calibration['cameras'][camera.value]['reference_size']
        g=draft.get(gate.value,dict(label='',a=[0,0],b=[0,0],inside=[0,0]))
        label.value=g.get('label','')
        vals=[*g['a'],*g['b'],*g['inside']]
        for i,(name,value) in enumerate(zip(names,vals)):
            sliders[name].max=size[i%2];sliders[name].value=round(value*size[i%2])
        loading[0]=False;render()

    def load_camera(*args):
        draft.clear();draft.update({g['name']:g for g in calibration['cameras'][camera.value]['gates']})
        load_gate()

    def store_gate(button):
        g=candidate()
        with status:
            clear_output()
            if core.math.dist(g['a'],g['b'])<.02:
                print('Move the two endpoints so the gate spans the road.');return
            if abs(core.cross(g['a'],g['b'],g['inside']))/core.math.dist(g['a'],g['b'])<.005:
                print('Move the inside point onto the junction side of the gate.');return
            draft[gate.value]=g
            print('Stored gate',gate.value,'for',camera.value,'in the editor. Store all road gates, then save this camera.')
        render()

    def save_camera(button):
        with status:
            clear_output()
            try:
                if set(draft)!={'A','B','C'}:
                    raise ValueError('Store all three road gates A, B and C before saving this three-arm camera.')
                record={**calibration['cameras'][camera.value],
                        'gates':[draft[n] for n in sorted(draft)],'reviewed':True}
                core.validate_camera(record)
                reference=folder/(camera.value+'.png')
                if core.file_hash(reference)!=record['reference_sha256']:
                    raise ValueError('Reference image changed. Create a new calibration folder.')
                calibration['cameras'][camera.value]=record
                core.atomic_json(path,calibration)
                print('Saved',camera.value,'to',path)
                print('A/B/C are road-arm identifiers. Place gates across each road arm, not across the grass.')
            except (ValueError,KeyError) as e:print('Not saved:',e)

    camera.observe(load_camera,names='value');gate.observe(load_gate,names='value')
    for slider in sliders.values():slider.observe(render,names='value')
    label.observe(render,names='value');store.on_click(store_gate);save.on_click(save_camera)
    display(w.VBox([w.HTML('<b>For each road: move endpoints a/b across its traffic lanes. '
        'Put the inside point toward the junction. Store A, B, C, then save the camera. '
        'The red dots on pilot videos mark vehicle bottom-centres used for crossings.</b>'),
        w.HBox([camera,gate]),label,
        w.HBox([w.VBox([sliders[n] for n in names[:3]]),w.VBox([sliders[n] for n in names[3:]])]),
        w.HBox([store,save]),status,plot]))
    load_camera()


def pilot_inventory(videos,cameras=core.CAMERAS,per_camera=3):
    if per_camera<1:raise ValueError('Pilot clips per camera must be positive.')
    preferred=['normanniles2/normanniles2_2025-10-25-16-46-45.mp4',
               'normanniles2/normanniles2_2025-10-25-17-33-45.mp4',
               'normanniles2/normanniles2_2025-10-26-13-10-45.mp4']
    rank={key:i for i,key in enumerate(preferred)};selected=[]
    for camera in cameras:
        group=videos[videos.camera_id.eq(camera)].copy()
        if group.empty:raise ValueError('No videos for '+camera)
        group['_rank']=group.video_path.map(rank).fillna(100)
        preferred_group=group[group._rank<100].sort_values('_rank').head(per_camera)
        rest=group[group._rank.eq(100)].sort_values('video_path')
        n=min(per_camera-len(preferred_group),len(rest))
        spread=rest.iloc[np.linspace(0,len(rest)-1,n,dtype=int)] if n else rest.iloc[:0]
        group=pd.concat([preferred_group,spread]).drop(columns='_rank')
        selected.append(group)
    return pd.concat(selected).sort_values('video_path').reset_index(drop=True)


def counting_signature(camera,detector,settings):
    record={k:camera[k] for k in ['gates','reference_size','reference_sha256']}
    record['clock_roi']=camera.get('clock_roi',[.68,0,1,.09])
    return core.digest(dict(camera=record,detector=detector,settings={**core.DEFAULTS,**settings},
        tracker=core.TRACKER,code_sha256=core.file_hash(core.__file__),
        environment={n:importlib.metadata.version(n) for n in ['ultralytics','opencv-python','numpy','torch']}))


def pilot_review_button(calibration_folder,pilot_run,pilot_videos,detector,settings):
    import ipywidgets as w
    from IPython.display import display,clear_output
    calibration_folder=Path(calibration_folder);pilot_run=Path(pilot_run)
    calibration=json.loads((calibration_folder/'gates.json').read_text())
    contract=json.loads((pilot_run/'contract.json').read_text())
    cameras=sorted(set(pilot_videos.camera_id))
    if core.geometry(calibration,cameras)!=contract['config']['geometry']:
        raise ValueError('Gates changed since these pilot videos were processed. Run a new pilot.')
    for r in pilot_videos.itertuples():
        core.verify_checkpoint(core.clip_directory(pilot_run,r.video_path),contract['signature'])
        if not (core.clip_directory(pilot_run,r.video_path)/'annotated.mp4').is_file():
            raise ValueError('Missing annotated pilot video.')
    out=w.Output()
    button=w.Button(description='I reviewed pilot gates and directions',button_style='success',layout=w.Layout(width='350px'))
    def save(button):
        path=calibration_folder/'pilot_reviews.json'
        saved=json.loads(path.read_text()) if path.exists() else {}
        # Reload so changing a gate after inference cannot approve stale previews.
        now=json.loads((calibration_folder/'gates.json').read_text())
        with out:
            clear_output()
            for camera in cameras:
                if core.geometry(now,[camera])!=core.geometry(calibration,[camera]):
                    print('Gates changed since these pilot previews. Run a new pilot.');return
                saved[detector+'/'+camera]=dict(counting_signature=counting_signature(now['cameras'][camera],detector,settings),
                    pilot_contract_signature=contract['signature'],
                    reviewed_utc=datetime.now(timezone.utc).isoformat(),
                    video_paths=pilot_videos.loc[pilot_videos.camera_id.eq(camera),'video_path'].tolist())
            core.atomic_json(path,saved)
            print('Saved pilot geometry/direction review. Manual counting accuracy remains unmeasured until annotations are entered.')
    button.on_click(save)
    display(w.HTML('Open the annotated pilot videos in Drive and inspect each gate, arrow and route. '
        'This button records your visual geometry review; it does not certify counting accuracy.'),button,out)


def require_pilot_reviews(folder,calibration,detector,settings):
    path=Path(folder)/'pilot_reviews.json'
    reviews=json.loads(path.read_text()) if path.exists() else {}
    missing=[c for c in core.CAMERAS if reviews.get(detector+'/'+c,{}).get('counting_signature')!=
             counting_signature(calibration['cameras'][c],detector,settings)]
    if missing:raise ValueError('Run and visually review annotated pilot videos for: '+', '.join(missing))


def export_bundle(run,calibration_folder,program_folder):
    run=Path(run);calibration_folder=Path(calibration_folder);program_folder=Path(program_folder)
    files={}
    for name in ['contract.json','model_weights.json','junction_features.csv','pending_videos.csv','processing_failures.csv','batch_status.json']:
        p=run/name
        if p.is_file():files[name]=p
    if 'junction_features.csv' not in files:raise ValueError('No completed feature export yet.')
    for name in ['gates.json','pilot_reviews.json']:
        p=calibration_folder/name
        if p.is_file():files['calibration/'+name]=p
    for camera in core.CAMERAS:
        p=calibration_folder/(camera+'.png')
        if p.is_file():files['calibration/'+p.name]=p
    for name in ['junction_counting_v4.py','junction_calibration_v4.py','junction_forecasting_v4.py','junction_drawing_v4.py']:
        p=program_folder/name
        if p.is_file():files['code/'+name]=p
    for folder in ['evaluations','manual_evaluation']:
        if (run/folder).exists():
            for p in (run/folder).rglob('*'):
                if p.is_file():files[p.relative_to(run).as_posix()]=p
    if (run/'pilots').exists():
        for pilot in (run/'pilots').iterdir():
            if not pilot.is_dir():continue
            for name in ['contract.json','junction_features.csv']:
                p=pilot/name
                if p.is_file():files[p.relative_to(run).as_posix()]=p
            for folder in ['manual_evaluation','manual_annotations']:
                for p in (pilot/folder).rglob('*'):
                    if p.is_file():files[p.relative_to(run).as_posix()]=p
    manifest={name:core.file_hash(p) for name,p in files.items()}
    target=run/'Junction_v4_Results.zip';pending=target.with_suffix('.zip.pending')
    with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,p in files.items():z.write(p,name)
        z.writestr('FILE_SHA256.json',json.dumps(manifest,indent=2))
        z.writestr('READ_ME.txt','Predicted junction movements and optional forecasting outputs. '
            'No counting accuracy is established without completed manual annotations. '
            'Per-frame observations, quality flags, gate events, journeys and annotated pilot videos remain in the Drive run folders. '
            'Complete journeys require both gates within a single clip. Counts are per camera; '
            'overlapping views are not deduplicated across cameras. OCR/colour flags are candidates for review, not confirmed corruption.\n')
    with zipfile.ZipFile(pending) as z:
        if z.testzip() is not None:raise OSError('Archive integrity check failed.')
    pending.replace(target)
    return target
