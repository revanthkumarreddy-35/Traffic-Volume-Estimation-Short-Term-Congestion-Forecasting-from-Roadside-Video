"""Build the self-contained all-camera calibration/pilot/batch/evaluation notebook."""
from pathlib import Path
import ast
import json
import argparse
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
PROGRAM=ROOT/'CP-1/Program'
TARGET=PROGRAM/'CP1_Junction_Movement_v4.ipynb'


def cell(kind,text):
    base=dict(cell_type=kind,metadata={},source=text.strip().splitlines(keepends=True))
    if kind=='code':base.update(execution_count=None,outputs=[])
    return base


def main(update_existing=False):
    old=json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else None
    if old and not update_existing and any(c.get('outputs') or c.get('execution_count') is not None for c in old['cells']):
        raise FileExistsError('Executed notebook: use --update-existing to preserve its configuration and unrelated outputs.')
    if old and update_existing and TARGET.resolve().parent==PROGRAM.resolve():
        backup_folder=ROOT/'Local_Only/Executed_Notebooks'
        backup_folder.mkdir(parents=True,exist_ok=True)
        backup=backup_folder/('junction_before_mouse_drawing_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.ipynb')
        backup.write_bytes(TARGET.read_bytes())
    modules={name:(PROGRAM/name).read_text(encoding='utf-8') for name in [
        'junction_counting_v4.py','junction_calibration_v4.py','junction_forecasting_v4.py','junction_drawing_v4.py']}
    embed='''# These embedded sources make this notebook independent of your local checkout.
from pathlib import Path
import sys, importlib
from google.colab import drive
drive.mount('/content/drive')
PROGRAM_FOLDER=Path('/content/junction_v4_code')
PROGRAM_FOLDER.mkdir(exist_ok=True)
MODULE_SOURCES = '''+repr(modules)+'''
for filename,source in MODULE_SOURCES.items():
    (PROGRAM_FOLDER/filename).write_text(source,encoding='utf-8')
sys.path.insert(0,str(PROGRAM_FOLDER))
for module_name in ['junction_counting_v4','junction_calibration_v4','junction_forecasting_v4','junction_drawing_v4']:
    sys.modules.pop(module_name,None)
import junction_counting_v4 as junction
import junction_calibration_v4 as calibration_tools
import junction_forecasting_v4 as forecasting
import junction_drawing_v4 as drawing_tools
import pandas as pd
import json
from IPython.display import display
'''
    cells=[cell('markdown','''# CP-1: road-arm movements for all four camera folders

This is a new experiment. The old notebooks, cached features and paper scores are retained.

1. Run all cells with `STAGE='calibrate'`. Download the generated `Draw_Camera_Gates.html` from Drive, open it in your browser, and draw each gate with the mouse. Click two endpoints (or drag a line), then click its junction side. Save each camera, download `gates_drawn.json`, then import it using the notebook's upload control. No coordinate sliders are needed.
2. Set `STAGE='pilot'`, run the configuration cell and the cells below it. Inspect the annotated pilot videos in Drive, then record your geometry/direction review with the displayed button. The default pilot covers all four cameras, including the three previously clear camera-2 clips.
3. Set `STAGE='batch'` and rerun configuration and the cells below it. Every MP4 under **normanniles1, normanniles2, normanniles3 and normanniles4** is included, including videos without congestion labels. There is no per-day sample limit. Extra folders such as `added` are outside these four views.
4. After completion, use `STAGE='evaluate'` to train/compare classifiers on clips with valid labels and three contiguous source clips of history. Default test dates were examined before; this remains exploratory.

All files are saved under **My Drive / CP-1 Dataset / Junction_v4**. Gates need actual road calibration; the notebook does not invent positions for unseen cameras. It requires annotated-pilot review for each camera before the full batch. A pilot is a geometry check, not a measurement of counting accuracy. Complete route counts require both gates within one clip; partial tracks are exported separately. Counts from overlapping camera views are not deduplicated across cameras.
'''),cell('code','''# Cell 1 — install before importing the project modules. Use a Colab GPU runtime for inference.
import sys, subprocess, shutil, importlib.metadata
subprocess.check_call([sys.executable,'-m','pip','install','-q',
    'ultralytics==8.4.184','numpy==2.1.3','pandas==2.2.3','scikit-learn==1.6.1',
    'xgboost==3.4.1','opencv-python==4.11.0.86','ipywidgets','pytesseract','matplotlib'])
for name in ['numpy','pandas','sklearn']:
    installed=importlib.metadata.version('scikit-learn' if name=='sklearn' else name)
    if name in sys.modules and getattr(sys.modules[name],'__version__',installed)!=installed:
        raise RuntimeError('A loaded library was changed. Restart the Colab kernel and run from Cell 1.')
if shutil.which('tesseract') is None:
    try:
        subprocess.run(['apt-get','update','-qq'],check=True)
        subprocess.run(['apt-get','install','-y','-qq','tesseract-ocr'],check=True)
    except (OSError,subprocess.CalledProcessError):
        print('Clock OCR unavailable. Counts can run, but camera-clock continuity will be marked unverified.')
'''),cell('code',embed),cell('code','''# Cell 3 — configuration. Keep names/settings unchanged when resuming.
DRIVE_BASE=Path('/content/drive/MyDrive/CP-1 Dataset')
STAGE='calibrate'  # calibrate, pilot, batch, evaluate, export
CALIBRATION_METHOD='draw'  # draw: mouse drawing in a browser; sliders: previous coordinate editor
DETECTOR='yolo11'  # yolo11 or yolov8; each has independent outputs and pilot reviews
EXPERIMENT_NAME='junction_01'
CALIBRATION_NAME='camera_gates_01'
EVALUATION_NAME='historical_week_01'
PILOT_CAMERAS=list(junction.CAMERAS)  # Can use ['normanniles2'] for an initial camera-2-only pilot.
PILOT_CLIPS_PER_CAMERA=3
HISTORY_CLIPS=3
TEST_START='2025-10-25'
TEST_END_EXCLUSIVE='2025-10-27'
LABELS_PATH=DRIVE_BASE/'CSV'/'Train.csv'
SETTINGS=dict(junction.DEFAULTS)
# OCR is sampled once per second; its flags require review and never exclude a clip automatically.
# Set clock_sample_seconds=0 to disable both sampled image/clock checks before starting a NEW experiment.
assert STAGE in {'calibrate','pilot','batch','evaluate','export'}
if STAGE in {'pilot','batch'}:
    import torch
    if not torch.cuda.is_available():raise RuntimeError('Select a Colab GPU runtime before pilot/batch inference.')
    print('GPU:',torch.cuda.get_device_name(0))
for name in [EXPERIMENT_NAME,CALIBRATION_NAME,EVALUATION_NAME]:
    if not junction.re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',name):raise ValueError('Use simple folder names.')
CALIBRATION_FOLDER=DRIVE_BASE/'Junction_v4'/'calibration'/CALIBRATION_NAME
RUN_FOLDER=DRIVE_BASE/'Junction_v4'/DETECTOR/EXPERIMENT_NAME
RUN_FOLDER.mkdir(parents=True,exist_ok=True)
'''),cell('code','''# Cell 4 — inventory all videos in the four camera folders, then get actual reference frames.
VIDEOS=junction.inventory(DRIVE_BASE)
display(VIDEOS.groupby('camera_id').agg(videos=('video_path','size'),bytes=('size_bytes','sum')))
print('Total planned videos:',len(VIDEOS))
print('Calibration folder:',CALIBRATION_FOLDER)
print('Result folder:',RUN_FOLDER)
CALIBRATION=junction.reference_frames(DRIVE_BASE,VIDEOS,CALIBRATION_FOLDER)
if STAGE=='calibrate':
    if CALIBRATION_METHOD=='draw':
        drawing_page=drawing_tools.write_drawing_page(CALIBRATION_FOLDER)
        print('Download this HTML from Google Drive and open it in Chrome/Edge:',drawing_page)
        print('Draw gates with the mouse; download gates_drawn.json, then import it below.')
        drawing_tools.drawing_import_widget(CALIBRATION_FOLDER)
    elif CALIBRATION_METHOD=='sliders':
        calibration_tools.gate_editor(CALIBRATION_FOLDER)
    else:raise ValueError('CALIBRATION_METHOD must be draw or sliders.')
else:
    CALIBRATION=json.loads((CALIBRATION_FOLDER/'gates.json').read_text())
    needed=PILOT_CAMERAS if STAGE=='pilot' else junction.CAMERAS
    junction.geometry(CALIBRATION,needed)
'''),cell('markdown','''### Gate placement and manual counting

Name the visible road arms A/B/C (e.g. left, upper, right for camera 2). Move each gate's endpoints **across that road arm**, spanning its entry and exit traffic, without intersecting the other gates. Put the green-arrow `inside` point on the junction side. The algorithm uses the **bottom centre of each predicted vehicle box**; the pilot marks it with a red dot. Confirm that real inbound vehicles produce `entry` and outbound vehicles produce `exit` at the correct gate.

With the mouse drawing page: choose camera and gate; click endpoint 1, click endpoint 2, click toward the junction. Alternatively drag the yellow line, release, then click toward the junction. Use Undo or Redraw to fix a gate. Click Save this camera after all A/B/C gates are drawn. The page embeds the real reference images and works offline; return the downloaded JSON through the notebook's import control.

The existing camera-1 glitches and camera-2 colour shift remain review observations, not reasons to selectively discard misclassified clips. Review flags and labelled/correctly classified clips as well. A colour change alone does not make a manual count invalid.
'''),cell('code','''# Cell 6 — short annotated pilot and manual-annotation templates; no full batch here.
if STAGE=='pilot':
    PILOT_VIDEOS=calibration_tools.pilot_inventory(VIDEOS,PILOT_CAMERAS,PILOT_CLIPS_PER_CAMERA)
    pilot_id=junction.digest(dict(videos=PILOT_VIDEOS.video_path.tolist(),
        geometry=junction.geometry(CALIBRATION,PILOT_CAMERAS),settings=SETTINGS,
        code=junction.file_hash(junction.__file__)))[:12]
    PILOT_FOLDER=RUN_FOLDER/'pilots'/pilot_id
    PILOT_FEATURES,PILOT_PENDING=junction.run_batch(DRIVE_BASE,PILOT_FOLDER,PILOT_VIDEOS,
        CALIBRATION,DETECTOR,SETTINGS,preview=True)
    if PILOT_PENDING:raise RuntimeError('Some pilot clips failed. Resolve processing_failures.csv and resume.')
    forecasting.manual_templates(PILOT_FEATURES,CALIBRATION,PILOT_FOLDER/'manual_annotations')
    display(PILOT_FEATURES[['video_path','gate_entries','gate_exits','complete_journeys','incomplete_tracks','quality_flags']])
    print('Open each annotated.mp4 under:',PILOT_FOLDER/'clips')
    manifests=[json.loads((junction.clip_directory(PILOT_FOLDER,r.video_path)/'manifest.json').read_text())
               for r in PILOT_VIDEOS.itertuples()]
    seconds=[m['processing_seconds'] for m in manifests]
    estimate=sum(seconds)/len(seconds)*len(VIDEOS)/3600
    print(f'Rough full-run estimate from this pilot: {estimate:.1f} GPU/runtime hours; I/O and scene load can change it.')
    calibration_tools.pilot_review_button(CALIBRATION_FOLDER,PILOT_FOLDER,PILOT_VIDEOS,DETECTOR,SETTINGS)
else:
    print('Pilot runs only with STAGE="pilot". Save calibrated gates first.')
'''),cell('code','''# Cell 7 — full inventory, no sampling. Completed clips resume; interrupted clips restart at zero.
if STAGE=='batch':
    calibration_tools.require_pilot_reviews(CALIBRATION_FOLDER,CALIBRATION,DETECTOR,SETTINGS)
    FEATURES,PENDING=junction.run_batch(DRIVE_BASE,RUN_FOLDER,VIDEOS,CALIBRATION,DETECTOR,SETTINGS)
    print('Completed:',len(FEATURES),'Pending/failed:',len(PENDING))
    if PENDING:
        print('Inspect processing_failures.csv. No failed or partial clip is treated as a completed count.')
else:
    print('All-video processing runs only with STAGE="batch".')
'''),cell('code','''# Cell 8 — labelled next-segment forecasting, after all planned clips complete.
if STAGE=='evaluate':
    contract_path=RUN_FOLDER/'contract.json'
    if not contract_path.is_file():raise FileNotFoundError('Run the batch stage first.')
    contract=json.loads(contract_path.read_text())
    # Recheck current configuration/inventory before trusting the completed index.
    signature=junction.freeze_run(RUN_FOLDER,VIDEOS,CALIBRATION,DETECTOR,SETTINGS)
    FEATURES,PENDING=junction.collect_features(RUN_FOLDER,VIDEOS,signature)
    if PENDING:raise RuntimeError(f'{len(PENDING)} videos are incomplete; resolve the saved failures and resume batch first.')
    if not LABELS_PATH.is_file():raise FileNotFoundError('Set LABELS_PATH to the supplied congestion-label CSV.')
    LABELS=pd.read_csv(LABELS_PATH)
    EVALUATION_FOLDER=RUN_FOLDER/'evaluations'/EVALUATION_NAME
    METRICS=forecasting.evaluate(FEATURES,LABELS,EVALUATION_FOLDER,TEST_START,TEST_END_EXCLUSIVE,HISTORY_CLIPS)
    display(METRICS)
    display(pd.read_csv(EVALUATION_FOLDER/'split_class_distribution.csv'))
    import matplotlib.pyplot as plt
    matrix=pd.read_csv(EVALUATION_FOLDER/'confusion_matrix.csv',index_col=0)
    fig,ax=plt.subplots(figsize=(8,6));im=ax.imshow(matrix.values,cmap='Blues')
    for i in range(4):
        for j in range(4):
            r,g,b,_=im.cmap(im.norm(matrix.iloc[i,j]));colour='black' if .2126*r+.7152*g+.0722*b>.5 else 'white'
            ax.text(j,i,str(matrix.iloc[i,j]),ha='center',va='center',color=colour,fontsize=14)
    ax.set_xticks(range(4),forecasting.CLASSES,rotation=25,ha='right');ax.set_yticks(range(4),forecasting.CLASSES)
    ax.set_xlabel('Predicted future class');ax.set_ylabel('Supplied future class')
    fig.tight_layout();fig.savefig(EVALUATION_FOLDER/'confusion_matrix.png',dpi=250);plt.show()
    print('Default dates were previously examined. No independent confirmation or counting accuracy is implied.')
else:
    print('Forecasting runs only with STAGE="evaluate". Unlabelled videos contribute counts/history but cannot be scored targets.')
'''),cell('code','''# Cell 9 — save a compact results ZIP to Drive; large per-frame logs stay in their clip folders.
if STAGE=='export' and (RUN_FOLDER/'contract.json').is_file():
    signature=junction.freeze_run(RUN_FOLDER,VIDEOS,CALIBRATION,DETECTOR,SETTINGS)
    FEATURES,PENDING=junction.collect_features(RUN_FOLDER,VIDEOS,signature)
    print('Export coverage — completed:',len(FEATURES),'pending:',len(PENDING))
if STAGE in {'batch','evaluate','export'} and (RUN_FOLDER/'junction_features.csv').is_file():
    archive=calibration_tools.export_bundle(RUN_FOLDER,CALIBRATION_FOLDER,PROGRAM_FOLDER)
    print('Results archive:',archive)
    print('Download it using Google Drive in your browser; this works with VS Code Colab.')
else:
    print('No full-run results archive yet. Pilot outputs are already saved in Drive.')
'''),cell('markdown','''### Manual counting evaluation (after gate calibration)

The pilot creates `manual_journey_counts.csv` and `manual_gate_counts.csv`. Keep these separate from old single-tripwire annotations. For journeys, count a physical vehicle only when both its entry and departure gates are visible within the clip; record incomplete/ambiguous journeys separately. For gate counts, record each entry/exit event by class. Enter zeros explicitly and set every scored row's `annotation_status` to `complete` only after reviewing the full clip. Templates initially contain blanks, not invented zeros.

After completing a copy of a template, run in an extra cell:

```python
report=forecasting.evaluate_manual_counts(
    PILOT_FEATURES,CALIBRATION,
    PILOT_FOLDER/'manual_annotations'/'manual_journey_counts.csv',
    PILOT_FOLDER/'manual_evaluation',kind='journeys')
print(report)
```

Use `kind='gates'` with `manual_gate_counts.csv` for gate-event errors. This measures counting on the annotated clips only; a pilot selected during development is not an independent final counting test. Freeze gates, features and validation choices before testing on new labelled recording dates. For a detector comparison, repeat with `DETECTOR='yolov8'`, the same gates, inventory, history and test protocol. Its pilot review and outputs are separate.
''')]
    for c in cells:
        if c['cell_type']=='code':ast.parse(''.join(c['source']))
    result=dict(cells=cells,metadata=dict(kernelspec=dict(display_name='Python 3',language='python',name='python3'),
        language_info=dict(name='python'),colab=dict(provenance=[])),nbformat=4,nbformat_minor=5)
    for i,c in enumerate(cells):c['id']=f'junction-v4-{i:02d}'
    if old and update_existing:
        if len(old['cells'])!=len(cells) or any(c.get('id')!=n['id'] for c,n in zip(old['cells'],cells)):
            raise ValueError('Notebook structure differs; not replacing user cells.')
        # These are the only cells affected by the new drawing interface.
        for index in [0,2,4,5]:
            old['cells'][index]['source']=cells[index]['source']
            if old['cells'][index]['cell_type']=='code':
                old['cells'][index]['outputs']=[];old['cells'][index]['execution_count']=None
        config=''.join(old['cells'][3]['source'])
        if not any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CALIBRATION_METHOD' for t in n.targets)
                   for n in ast.parse(config).body):
            config="CALIBRATION_METHOD='draw'  # Mouse drawing; use 'sliders' for the previous editor.\n"+config
            old['cells'][3]['source']=config.splitlines(keepends=True)
            old['cells'][3]['execution_count']=None;old['cells'][3]['outputs']=[]
        result=old
    TARGET.write_text(json.dumps(result,indent=1,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Created',TARGET,'with',len(cells),'cells.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--update-existing',action='store_true')
    args=parser.parse_args();main(args.update_existing)
