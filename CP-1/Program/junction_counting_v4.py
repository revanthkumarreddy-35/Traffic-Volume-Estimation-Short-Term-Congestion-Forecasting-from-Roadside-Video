"""Camera-calibrated road-arm events and complete/incomplete vehicle journeys.

No road geometry is inferred from filenames or copied between cameras. Output
counts describe tracked journeys, not ground-truth vehicles. Clips are independent.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import importlib.metadata
import json
import math
import re
import shutil
import time

import cv2
import numpy as np
import pandas as pd

VERSION = 'junction-v4.1'
CAMERAS = tuple('normanniles'+str(i) for i in range(1, 5))
CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
TRACKER = dict(tracker_type='bytetrack', track_high_thresh=.4,
               track_low_thresh=.05, new_track_thresh=.5,
               track_buffer=90, match_thresh=.8, fuse_score=True)
DEFAULTS = dict(imgsz=1280, conf=.05, anchor='bottom_center',
                max_gap_seconds=.5, max_motion_per_second=.8,
                gate_margin=.002, clock_sample_seconds=1.,
                clock_tolerance_seconds=2.5, save_observations=True)
OBS_COLUMNS = ['frame_idx','track_id','vehicle_class','confidence','x1','y1','x2','y2']
EVENT_COLUMNS = ['frame_idx','track_key','gate','event','vehicle_class','confidence','x','y']
JOURNEY_COLUMNS = ['track_key','status','origin','destination','reason','vehicle_class',
                   'first_frame','last_frame','entry_frame','exit_frame','mean_confidence']
QUALITY_COLUMNS = ['frame_idx','playback_seconds','flag','detail']


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    pending = path.with_name(path.name+'.pending')
    pending.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
    pending.replace(path)


def write_csv(path, rows, columns):
    path = Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w = csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


def cross(a,b,p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def intersection(a,b,p,q):
    """Parameter of finite movement p->q intersecting finite gate a->b."""
    r = (q[0]-p[0],q[1]-p[1]); s = (b[0]-a[0],b[1]-a[1])
    den = r[0]*s[1]-r[1]*s[0]
    if abs(den)<1e-12:
        return None
    ap = (a[0]-p[0],a[1]-p[1])
    t = (ap[0]*s[1]-ap[1]*s[0])/den
    u = (ap[0]*r[1]-ap[1]*r[0])/den
    return t if 0<=t<=1 and 0<=u<=1 else None


def validate_camera(camera):
    if not camera.get('reviewed',False):
        raise ValueError('Save reviewed gate positions for this camera first.')
    gates = camera.get('gates',[])
    if not 2<=len(gates)<=6:
        raise ValueError('Define 2-6 road-arm gates (three for a three-arm junction).')
    names = [g['name'] for g in gates]
    if len(set(names))!=len(names) or any(not re.fullmatch('[A-F]',n) for n in names):
        raise ValueError('Use distinct gate IDs A-F; keep their road meanings fixed.')
    for gate in gates:
        for key in ['a','b','inside']:
            point = gate.get(key)
            if not isinstance(point,(tuple,list)) or len(point)!=2 or any(
                    not isinstance(x,(int,float)) or isinstance(x,bool)
                    or not math.isfinite(x) or not 0<=x<=1 for x in point):
                raise ValueError(f"{gate['name']}: {key} must contain two normalized coordinates in [0,1].")
        length = math.dist(gate['a'],gate['b'])
        if length<.02 or abs(cross(gate['a'],gate['b'],gate['inside']))/length<.005:
            raise ValueError('Gate too short or its junction-side point is too close to the line.')
    for i,g in enumerate(gates):
        for other in gates[i+1:]:
            if intersection(g['a'],g['b'],other['a'],other['b']) is not None:
                raise ValueError('Road-arm gates must not intersect one another.')
    size = camera.get('reference_size')
    if not size or len(size)!=2 or min(size)<=0:
        raise ValueError('Missing reference frame size; run the reference-frame cell.')
    roi=camera.get('clock_roi',[.68,0,1,.09])
    if len(roi)!=4 or not (0<=roi[0]<roi[2]<=1 and 0<=roi[1]<roi[3]<=1):
        raise ValueError('clock_roi must be [left, top, right, bottom] within [0,1].')
    return camera


def geometry(calibration, cameras=CAMERAS):
    result = {}
    for name in cameras:
        if name not in calibration.get('cameras',{}):
            raise ValueError('Missing camera calibration: '+name)
        cam = validate_camera(calibration['cameras'][name])
        result[name] = {key:cam[key] for key in ['gates','reference_size','reference_sha256']}
        result[name]['clock_roi']=cam.get('clock_roi',[.68,0,1,.09])
    return result


def inventory(base):
    base = Path(base)
    rows=[]
    for camera in CAMERAS:
        folder=base/camera
        if not folder.is_dir():
            raise FileNotFoundError(f'Camera folder is inaccessible: {folder}')
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.suffix.lower()=='.mp4':
                rows.append(dict(video_path=p.relative_to(base).as_posix(),
                                 camera_id=camera,size_bytes=p.stat().st_size))
    result=pd.DataFrame(rows,columns=['video_path','camera_id','size_bytes'])
    if result.empty or result.video_path.duplicated().any():
        raise ValueError('No videos, or duplicate relative video paths.')
    missing=set(CAMERAS)-set(result.camera_id)
    if missing:
        raise ValueError('No videos found for '+', '.join(sorted(missing)))
    return result.sort_values('video_path').reset_index(drop=True)


def reference_frames(base, videos, folder):
    """Load one actual frame per camera without detector inference."""
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    target=folder/'gates.json'
    calibration=json.loads(target.read_text()) if target.exists() else dict(version=VERSION,cameras={})
    for camera in CAMERAS:
        if camera in calibration['cameras']:
            if not (folder/(camera+'.png')).is_file():
                raise FileNotFoundError('Existing calibration is missing its reference image: '+camera)
            if file_hash(folder/(camera+'.png'))!=calibration['cameras'][camera]['reference_sha256']:
                raise ValueError('Reference image changed; use a new calibration folder: '+camera)
            continue
        choices=videos[videos.camera_id.eq(camera)].video_path.tolist()
        preferred='normanniles2/normanniles2_2025-10-25-16-46-45.mp4'
        choices.sort(key=lambda k:(k!=preferred, not bool(re.search(r'-(?:1[2-6])-\d\d-\d\d\.mp4$',k)),k))
        found=False
        for key in choices[:20]:
            cap=cv2.VideoCapture(str(Path(base)/key))
            try:
                cap.set(cv2.CAP_PROP_POS_MSEC,1000)
                ok,frame=cap.read()
                if not ok: continue
                h,w=frame.shape[:2]
                image=folder/(camera+'.png')
                if not cv2.imwrite(str(image),frame):raise OSError('Could not save '+str(image))
                calibration['cameras'][camera]=dict(reviewed=False,gates=[],
                    reference_video=key,reference_size=[w,h],reference_sha256=file_hash(image),
                    clock_roi=[.68,0,1,.09])
                found=True;break
            finally:cap.release()
        if not found:raise OSError('Could not decode a reference frame for '+camera)
    atomic_json(target,calibration)
    return calibration


@dataclass
class Track:
    key: str
    first: int
    last: int
    previous: tuple
    anchors: dict = field(default_factory=dict)
    votes: Counter = field(default_factory=Counter)
    confidence: float = 0.
    observations: int = 0
    origin: str = ''
    destination: str = ''
    entry: object = None
    exit: object = None
    reason: str = ''
    terminal: bool = False


class JourneyCounter:
    """One observed journey per track segment; never guess missing gate events."""
    def __init__(self,camera,fps,settings=None):
        validate_camera(camera)
        if not math.isfinite(fps) or fps<=0:raise ValueError('A valid frame rate is required.')
        self.gates=camera['gates'];self.fps=fps
        self.settings={**DEFAULTS,**(settings or {})}
        self.tracks={};self.epochs=Counter();self.finished=[];self.events=[];self.issues=[]

    def point(self,box,width,height):
        return ((box['x1']+box['x2'])/(2*width),
                (box['y2'] if self.settings['anchor']=='bottom_center' else (box['y1']+box['y2'])/2)/height)

    def _side(self,gate,point):
        dist=cross(gate['a'],gate['b'],point)/math.dist(gate['a'],gate['b'])
        if abs(dist)<=self.settings['gate_margin']:return 0
        inside=1 if cross(gate['a'],gate['b'],gate['inside'])>0 else -1
        return (1 if dist>0 else -1)*inside

    def observe(self,frame,track_id,point,vehicle_class,confidence):
        if frame<0 or not math.isfinite(confidence) or not 0<=confidence<=1:
            raise ValueError('Invalid frame/confidence observation.')
        if vehicle_class not in CLASSES.values():raise ValueError('Unknown vehicle class.')
        track_id=int(track_id); track=self.tracks.get(track_id)
        if track is not None:
            dt=(frame-track.last)/self.fps
            if dt<=0:raise ValueError('Track observations must be unique and time-ordered.')
            reason='tracking_gap' if dt>self.settings['max_gap_seconds'] else (
                'position_jump' if math.dist(point,track.previous)/dt>
                self.settings['max_motion_per_second'] else '')
            if reason:
                if not track.terminal:track.reason=reason
                self.finished.append(track);del self.tracks[track_id];track=None
                self.issues.append(dict(frame_idx=frame,flag=reason,detail=f'track_id={track_id}'))
        if track is None:
            self.epochs[track_id]+=1
            track=Track(f'{track_id}:{self.epochs[track_id]}',frame,frame,point)
            self.tracks[track_id]=track
        track.votes[vehicle_class]+=1;track.confidence+=confidence;track.observations+=1
        crossings=[]
        for gate in self.gates:
            name=gate['name'];side=self._side(gate,point)
            old=track.anchors.get(name)
            if side and old is not None and old[0]!=side:
                # Hysteresis anchors are checked against the actual finite segment.
                # A track may dwell on the line while continuously observed.
                # Actual observation gaps already split the track above.
                t=intersection(gate['a'],gate['b'],old[1],point)
                if t is not None:crossings.append((t,name,'entry' if side>0 else 'exit'))
            if side:track.anchors[name]=(side,point,frame)
        if len(crossings)>1:
            track.reason='ambiguous_multi_gate_step';track.terminal=True
            self.issues.append(dict(frame_idx=frame,flag=track.reason,detail=track.key))
        elif crossings and not track.terminal:
            _,gate,event=crossings[0]
            self.events.append(dict(frame_idx=frame,track_key=track.key,gate=gate,event=event,
                vehicle_class=vehicle_class,confidence=confidence,x=point[0],y=point[1]))
            if event=='entry':
                if track.origin:
                    track.reason='multiple_entries_without_exit';track.terminal=True
                else:track.origin=gate;track.entry=frame
            else:
                track.destination=gate;track.exit=frame;track.terminal=True
                track.reason=('complete' if track.origin and track.origin!=gate else
                              'same_gate_return' if track.origin else 'exit_without_entry')
        track.last=frame;track.previous=point

    def expire(self,frame):
        for key,track in list(self.tracks.items()):
            if (frame-track.last)/self.fps>self.settings['max_gap_seconds']:
                if not track.terminal:track.reason='tracking_gap' if track.origin else 'no_gate_observed'
                self.finished.append(track);del self.tracks[key]

    def finish(self):
        result=[]
        for t in self.finished+list(self.tracks.values()):
            reason=t.reason or ('entry_without_exit' if t.origin else 'no_gate_observed')
            cls=sorted(t.votes,key=lambda c:(-t.votes[c],c))[0]
            result.append(dict(track_key=t.key,status='complete' if reason=='complete' else 'incomplete',
                origin=t.origin or 'unknown',destination=t.destination or 'unknown',reason=reason,
                vehicle_class=cls,first_frame=t.first,last_frame=t.last,entry_frame=t.entry,
                exit_frame=t.exit,mean_confidence=t.confidence/t.observations))
        return result


class FrameQuality:
    """Candidate flags only: never relabel congestion, remove clips or fabricate frames."""
    def __init__(self,fps,camera,settings):
        self.fps=fps;self.camera=camera;self.settings=settings
        self.previous=None;self.previous_clock=None;self.flags=[];self.ocr_reads=0
        self.ocr_matches=0;self.ocr_error=''
        try:
            import pytesseract
            pytesseract.get_tesseract_version();self.ocr=pytesseract
        except (ImportError,OSError,RuntimeError) as e:
            self.ocr=None;self.ocr_error=str(e)[:200]

    def add(self,frame,flag,detail):
        self.flags.append(dict(frame_idx=frame,playback_seconds=round(frame/self.fps,3),flag=flag,detail=detail))

    def check(self,index,frame):
        interval=self.settings['clock_sample_seconds']
        if interval<=0 or index%max(1,round(self.fps*interval)):return
        tiny=cv2.resize(frame,(80,45));gray=cv2.cvtColor(tiny,cv2.COLOR_BGR2GRAY)
        lab=cv2.cvtColor(tiny,cv2.COLOR_BGR2LAB).astype(float)
        if self.previous is not None:
            oldgray,oldlab=self.previous
            luma=float(abs(gray.mean()-oldgray.mean()))
            chroma=float(np.linalg.norm(lab[:,:,1:].mean((0,1))-oldlab[:,:,1:].mean((0,1))))
            if luma>25 or chroma>12:
                self.add(index,'colour_brightness_change_candidate',f'luma_delta={luma:.2f}; chroma_delta={chroma:.2f}')
        self.previous=(gray,lab)
        if self.ocr is None:return
        h,w=frame.shape[:2];x1,y1,x2,y2=self.camera.get('clock_roi',[.68,0,1,.09])
        crop=frame[round(y1*h):round(y2*h),round(x1*w):round(x2*w)]
        if not crop.size:return
        crop=cv2.cvtColor(cv2.resize(crop,None,fx=3,fy=3),cv2.COLOR_BGR2GRAY)
        self.ocr_reads+=1
        try:
            text=self.ocr.image_to_string(crop,config='--psm 7',timeout=3)
        except (RuntimeError,OSError) as e:
            self.ocr_error=str(e)[:200];return
        matches=re.findall(r'(\d{1,2}):(\d{2}):(\d{2})',text)
        valid=[tuple(map(int,m)) for m in matches if int(m[0])<24 and int(m[1])<60 and int(m[2])<60]
        if not valid:return
        hh,mm,ss=valid[-1];seconds=hh*3600+mm*60+ss;self.ocr_matches+=1
        if self.previous_clock is not None:
            old,old_index=self.previous_clock
            delta=seconds-old
            if old>23*3600 and seconds<3600:delta+=86400
            elapsed=(index-old_index)/self.fps
            if abs(delta-elapsed)>self.settings['clock_tolerance_seconds']:
                self.add(index,'camera_clock_jump_candidate',
                         f'OCR clock_delta={delta}; playback_delta={elapsed:.3f}; raw={text.strip()}')
        self.previous_clock=(seconds,index)


def summarize(counter,journeys,frame_counts,areas,confidence,speeds,frames,fps,width,height):
    complete=[j for j in journeys if j['status']=='complete']
    result=dict(total_frames=frames,fps=fps,duration_sec=frames/fps,
        resolution=f'{width}x{height}',complete_journeys=len(complete),
        incomplete_tracks=len(journeys)-len(complete),observed_tracks=len(journeys),
        gate_entries=sum(e['event']=='entry' for e in counter.events),
        gate_exits=sum(e['event']=='exit' for e in counter.events),
        mean_vehicles=float(np.mean(frame_counts)),max_vehicles=int(max(frame_counts,default=0)),
        density_std=float(np.std(frame_counts)),
        density_trend=float(np.mean(frame_counts[-max(1,frames//3):])-np.mean(frame_counts[:max(1,frames//3)])),
        mean_bbox_area_fraction=float(np.mean(areas)) if areas else 0.,
        bbox_occupancy_proxy=float(sum(areas)/frames),
        mean_confidence=float(np.mean(confidence)) if confidence else 0.,
        motion_median=float(np.median(speeds)) if speeds else 0.,
        motion_p90=float(np.quantile(speeds,.9)) if speeds else 0.,
        slow_fraction=float(np.mean(np.array(speeds)<.005)) if speeds else 0.,
        weighted_complete_journeys=float(sum(j['mean_confidence'] for j in complete)))
    for gate in sorted(g['name'] for g in counter.gates):
        for direction in ['entry','exit']:
            result[f'gate_{gate}_{direction}']=sum(e['gate']==gate and e['event']==direction for e in counter.events)
            for cls in CLASSES.values():
                result[f'gate_{gate}_{direction}_{cls}']=sum(e['gate']==gate and e['event']==direction
                    and e['vehicle_class']==cls for e in counter.events)
    for a in sorted(g['name'] for g in counter.gates):
        for b in sorted(g['name'] for g in counter.gates):
            if a!=b:
                movement=[j for j in complete if j['origin']==a and j['destination']==b]
                result[f'route_{a}_{b}']=len(movement)
                for cls in CLASSES.values():result[f'route_{a}_{b}_{cls}']=sum(j['vehicle_class']==cls for j in movement)
    for cls in CLASSES.values():
        result['journeys_'+cls]=sum(j['vehicle_class']==cls for j in complete)
    return result


def draw_gates(frame,camera):
    out=frame.copy();h,w=frame.shape[:2]
    for gate in camera.get('gates',[]):
        a=tuple(round(v*s) for v,s in zip(gate['a'],(w,h)))
        b=tuple(round(v*s) for v,s in zip(gate['b'],(w,h)))
        inside=tuple(round(v*s) for v,s in zip(gate['inside'],(w,h)))
        middle=tuple(round((x+y)/2) for x,y in zip(a,b))
        cv2.line(out,a,b,(0,255,255),2);cv2.arrowedLine(out,middle,inside,(0,255,0),2)
        cv2.putText(out,gate['name']+' '+gate.get('label',''),a,cv2.FONT_HERSHEY_SIMPLEX,.55,(0,255,255),2)
    return out


def reset_tracker(model):
    for tracker in getattr(getattr(model,'predictor',None),'trackers',[]) or []:tracker.reset()


def process_clip(video,camera,model,output,tracker_path,settings=None,preview=False):
    """Full decode only. Failed or interrupted clips cannot become checkpoints."""
    settings={**DEFAULTS,**(settings or {})};validate_camera(camera)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    cap=cv2.VideoCapture(str(video));writer=None
    if not cap.isOpened():cap.release();raise OSError('Cannot open '+str(video))
    fps=float(cap.get(cv2.CAP_PROP_FPS));expected=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    try:
        if min(width,height)<=0 or fps<=0 or not math.isfinite(fps):raise ValueError('Invalid video metadata.')
        rw,rh=camera['reference_size']
        if abs(width/height-rw/rh)>.01:raise ValueError('Aspect ratio differs from calibrated reference.')
        counter=JourneyCounter(camera,fps,settings);quality=FrameQuality(fps,camera,settings)
        reset_tracker(model)
        if preview:
            writer=cv2.VideoWriter(str(output/'annotated.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
            if not writer.isOpened():raise OSError('Annotated video writer did not open.')
        frames=0;densities=[];areas=[];scores=[];speeds=[];last={}
        obs_file=(output/'observations.csv').open('w',newline='',encoding='utf-8')
        with obs_file:
            obs=csv.DictWriter(obs_file,fieldnames=OBS_COLUMNS);obs.writeheader()
            while True:
                ok,frame=cap.read()
                if not ok:break
                quality.check(frames,frame)
                result=model.track(frame,persist=True,tracker=str(tracker_path),
                    imgsz=settings['imgsz'],conf=settings['conf'],verbose=False,classes=list(CLASSES))[0]
                count=0;annotated=draw_gates(frame,camera) if preview else None
                boxes=getattr(result,'boxes',None)
                if boxes is not None and boxes.id is not None:
                    seen=set()
                    for box in boxes:
                        track_id=int(box.id[0]);cls=CLASSES.get(int(box.cls[0]))
                        if cls is None:continue
                        if track_id in seen:raise ValueError('Duplicate track ID in a frame.')
                        seen.add(track_id)
                        x1,y1,x2,y2=map(float,box.xyxy[0].cpu().numpy());conf=float(box.conf[0])
                        row=dict(frame_idx=frames,track_id=track_id,vehicle_class=cls,
                                 confidence=conf,x1=x1,y1=y1,x2=x2,y2=y2)
                        point=counter.point(row,width,height)
                        if track_id in last:
                            old_frame,old=last[track_id];dt=(frames-old_frame)/fps
                            if 0<dt<=settings['max_gap_seconds']:
                                speed=math.dist(point,old)/dt
                                if speed<=settings['max_motion_per_second']:speeds.append(speed)
                        last[track_id]=(frames,point)
                        counter.observe(frames,track_id,point,cls,conf)
                        if settings['save_observations']:obs.writerow(row)
                        count+=1;areas.append(max(0,x2-x1)*max(0,y2-y1)/(width*height));scores.append(conf)
                        if preview:
                            cv2.rectangle(annotated,(int(x1),int(y1)),(int(x2),int(y2)),(255,160,0),1)
                            cv2.circle(annotated,(round(point[0]*width),round(point[1]*height)),3,(0,0,255),-1)
                            cv2.putText(annotated,f'{cls} #{track_id}',(int(x1),max(15,int(y1)-5)),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,160,0),1)
                counter.expire(frames);densities.append(count)
                if preview:writer.write(annotated)
                frames+=1
        if frames==0:raise OSError('No frames decoded.')
        if expected>0 and frames<expected:
            raise OSError(f'Incomplete decode: {frames}/{expected} frames. Clip not checkpointed.')
        journeys=counter.finish()
        features=summarize(counter,journeys,densities,areas,scores,speeds,frames,fps,width,height)
        for issue in counter.issues:quality.add(issue['frame_idx'],issue['flag'],issue['detail'])
        features.update(quality_flags=len(quality.flags),clock_ocr_reads=quality.ocr_reads,
                        clock_ocr_matches=quality.ocr_matches,
                        clock_check_status='sampled' if quality.ocr_matches else 'not_verified',
                        quality_review_status='candidates_present' if quality.flags else 'no_automatic_candidates')
        write_csv(output/'gate_events.csv',counter.events,EVENT_COLUMNS)
        write_csv(output/'journeys.csv',journeys,JOURNEY_COLUMNS)
        write_csv(output/'quality_flags.csv',quality.flags,QUALITY_COLUMNS)
        write_csv(output/'frame_counts.csv',[dict(frame_idx=i,tracked_vehicles=n) for i,n in enumerate(densities)],
                  ['frame_idx','tracked_vehicles'])
        atomic_json(output/'features.json',features)
        return features,dict(expected_frames=expected,decoded_frames=frames,clock_ocr_error=quality.ocr_error)
    finally:
        cap.release()
        if writer is not None:writer.release()


def clip_directory(run,key):
    parts=Path(key).parts
    if len(parts)<2 or parts[0] not in CAMERAS or '..' in parts or Path(key).is_absolute():
        raise ValueError('Unsafe video key: '+key)
    return Path(run)/'clips'/parts[0]/(Path(key).stem+'_'+digest(key)[:10])


def verify_checkpoint(folder,signature,video=None,expected_weights=None):
    folder=Path(folder);manifest=folder/'manifest.json'
    if not manifest.is_file():raise ValueError('Incomplete checkpoint: '+str(folder))
    data=json.loads(manifest.read_text())
    if data['contract_signature']!=signature:raise ValueError('Checkpoint contract differs.')
    if expected_weights is not None and data.get('detector_weights')!=expected_weights:
        raise ValueError('Checkpoint detector weights differ from the run registry.')
    for name,expected in data['output_sha256'].items():
        if not (folder/name).is_file() or file_hash(folder/name)!=expected:
            raise ValueError('Checkpoint file changed: '+str(folder/name))
    if video is not None and file_hash(video)!=data['source_sha256']:
        raise ValueError('Source video changed: '+str(video))
    return json.loads((folder/'features.json').read_text())


def freeze_run(run,videos,calibration,detector,settings=None):
    run=Path(run);run.mkdir(parents=True,exist_ok=True)
    if detector not in ['yolo11','yolov8']:raise ValueError('Choose yolo11 or yolov8.')
    names=sorted(set(videos.camera_id))
    config=dict(version=VERSION,code_sha256=file_hash(__file__),detector=detector,
                settings={**DEFAULTS,**(settings or {})},tracker=TRACKER,
                geometry=geometry(calibration,names),
                inventory=videos[['video_path','camera_id','size_bytes']].to_dict('records'),
                environment={n:importlib.metadata.version(n) for n in ['ultralytics','opencv-python','numpy','torch']})
    signature=digest(config);path=run/'contract.json'
    if path.exists():
        saved=json.loads(path.read_text())
        if saved.get('signature')!=digest(saved['config']):raise ValueError('Saved contract is damaged.')
        if saved['signature']!=signature:
            changed=[k for k in config if config[k]!=saved['config'].get(k)]
            detail=(' Saved environment: '+str(saved['config'].get('environment'))+
                    '; current environment: '+str(config['environment'])) if 'environment' in changed else ''
            raise ValueError('Cannot resume; changed fields: '+', '.join(changed)+'.'+detail+
                ' Restore the original settings/packages to resume, or use a new EXPERIMENT_NAME for an intentional change. Saved clips are intact.')
    else:atomic_json(path,dict(signature=signature,config=config))
    return signature


def collect_features(run,videos,signature,verify_files=True):
    rows=[];missing=[]
    registry=Path(run)/'model_weights.json'
    expected_weights=json.loads(registry.read_text()) if registry.exists() else None
    for r in videos.itertuples():
        folder=clip_directory(run,r.video_path)
        if not folder.exists():missing.append(r.video_path);continue
        if expected_weights is None:raise ValueError('Missing detector-weights registry for saved checkpoints.')
        feat=verify_checkpoint(folder,signature,expected_weights=expected_weights) if verify_files else json.loads((folder/'features.json').read_text())
        rows.append(dict(video_path=r.video_path,camera_id=r.camera_id,**feat))
    result=pd.DataFrame(rows)
    if not result.empty:
        pending_file=Path(run)/'junction_features.csv.pending'
        result.to_csv(pending_file,index=False)
        pending_file.replace(Path(run)/'junction_features.csv')
    write_csv(Path(run)/'pending_videos.csv',[dict(video_path=k) for k in missing],['video_path'])
    atomic_json(Path(run)/'batch_status.json',dict(planned=len(videos),completed=len(rows),
        pending=len(missing),contract_signature=signature,all_videos_completed=not missing))
    return result,missing


def run_batch(base,run,videos,calibration,detector='yolo11',settings=None,preview=False,model_factory=None):
    """Process all rows in the frozen inventory; restart interrupted clips at zero."""
    import yaml
    settings={**DEFAULTS,**(settings or {})}
    signature=freeze_run(run,videos,calibration,detector,settings)
    run=Path(run);tracker=run/'bytetrack.yaml'
    tracker.write_text(yaml.safe_dump(TRACKER),encoding='utf-8')
    weights='yolo11l.pt' if detector=='yolo11' else 'yolov8l.pt'
    registry=run/'model_weights.json'
    weight_record=json.loads(registry.read_text()) if registry.exists() else None
    failures=[];model=None;started=time.monotonic();completed=0;consecutive_failures=0
    for index,row in enumerate(videos.itertuples(),1):
        source=Path(base)/row.video_path;dest=clip_directory(run,row.video_path)
        if dest.exists():
            if weight_record is None:raise ValueError('Missing detector-weights registry for saved checkpoints.')
            verify_checkpoint(dest,signature,source,weight_record)
            print(f'[{index}/{len(videos)}] Already checkpointed: {row.video_path}');continue
        stage=run/'.pending'/digest(row.video_path)
        if stage.exists():
            if stage.resolve().parent!=(run/'.pending').resolve() or not re.fullmatch('[a-f0-9]{64}',stage.name):
                raise ValueError('Unsafe staging directory.')
            shutil.rmtree(stage)
        stage.mkdir(parents=True,exist_ok=True)
        try:
            if model is None:
                if model_factory is None:
                    from ultralytics import YOLO
                    model=YOLO(weights)
                else:model=model_factory(weights)
                weight_path=Path(getattr(model,'ckpt_path',weights))
                if model_factory is None and not weight_path.is_file():
                    raise FileNotFoundError('Cannot fingerprint detector weights: '+str(weight_path))
                weight_record=dict(filename=weights,sha256=file_hash(weight_path) if weight_path.is_file() else 'test_model_factory')
                registry=run/'model_weights.json'
                if registry.exists() and json.loads(registry.read_text())!=weight_record:
                    raise ValueError('Detector weights changed. Restore the original weights or use a new experiment.')
                atomic_json(registry,weight_record)
            before_hash=file_hash(source)
            clip_started=time.monotonic()
            print(f'[{index}/{len(videos)}] Processing: {row.video_path}')
            features,meta=process_clip(source,calibration['cameras'][row.camera_id],model,
                                      stage,tracker,settings,preview)
            if file_hash(source)!=before_hash:raise ValueError('Source changed while processing.')
            hashes={p.name:file_hash(p) for p in stage.iterdir() if p.is_file()}
            manifest=dict(video_path=row.video_path,model_weights=weights,
                detector_weights=weight_record,
                contract_signature=signature,source_sha256=before_hash,output_sha256=hashes,
                processing_seconds=time.monotonic()-clip_started,
                recorded_utc=datetime.now(timezone.utc).isoformat(),**meta)
            atomic_json(stage/'manifest.json',manifest)
            dest.parent.mkdir(parents=True,exist_ok=True);stage.replace(dest);completed+=1
            consecutive_failures=0
            elapsed=time.monotonic()-started
            print(f"  Complete journeys: {features['complete_journeys']}; incomplete tracks: {features['incomplete_tracks']}; new-clip mean: {elapsed/completed/60:.2f} min")
        except KeyboardInterrupt:
            print('Stopped. Completed clips are saved; this unfinished clip will restart at frame zero.')
            raise
        except Exception as error:
            consecutive_failures+=1
            failures.append(dict(video_path=row.video_path,error=type(error).__name__+': '+str(error)))
            write_csv(run/'processing_failures.csv',failures,['video_path','error'])
            print('  Failed; no completed checkpoint:',error)
            if consecutive_failures>=3:
                raise RuntimeError('Three consecutive clips failed. Resolve the logged error, then resume this experiment.') from error
    write_csv(run/'processing_failures.csv',failures,['video_path','error'])
    features,missing=collect_features(run,videos,signature)
    atomic_json(run/'batch_status.json',dict(planned=len(videos),completed=len(features),
        pending=len(missing),contract_signature=signature,all_videos_completed=not missing))
    return features,missing
