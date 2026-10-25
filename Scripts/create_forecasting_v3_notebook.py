"""Build a self-contained Colab notebook for CPU reuse or expanded extraction."""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / 'CP-1/Program'
sys.path.insert(0, str(PROGRAM))
from congestion_forecasting_v3 import read_cached

EXPANDED = (PROGRAM/'notebook_sources/forecasting_expanded.py').read_text(encoding='utf-8')

SAVE_COMPLETED = '''
# Run only this cell to save an already completed run from this Colab runtime.
from pathlib import Path
from google.colab import drive
import shutil
import csv
import json

drive.mount('/content/drive')
save_base = Path(globals().get('DRIVE_BASE', '/content/drive/MyDrive/CP-1 Dataset'))
if not save_base.is_dir():
    raise FileNotFoundError('CP-1 Dataset is not accessible. Check the mounted account and My Drive shortcut.')
save_detector = globals().get('DETECTOR', 'yolo11')
save_mode = globals().get('RUN_MODE', 'cached')
if save_detector not in {'yolo11', 'yolov8'} or save_mode not in {'cached', 'expanded'}:
    raise ValueError('Check DETECTOR and RUN_MODE before saving.')
save_root = save_base/'Forecasting_v3'/save_detector
if save_mode == 'expanded':
    if globals().get('PLAN_ONLY', False):
        raise RuntimeError('Preflight only: set PLAN_ONLY=False and run from the top before saving evaluation results.')
    save_root = save_root/globals().get('EXPERIMENT_NAME','expanded_01')
evaluation_name = 'cached_evaluation' if save_mode == 'cached' else 'evaluation'
saved_results = save_root/evaluation_name
runtime_results = Path('/content/Forecasting_v3')/save_detector/evaluation_name
current_results = Path(globals().get('RESULT_DIR', runtime_results))
source_results = next((p for p in [current_results, runtime_results, saved_results]
                       if (p/'evaluation_metrics.csv').is_file()), None)
if source_results is None:
    raise FileNotFoundError('Completed results are unavailable in this runtime. Rerun the evaluation/export cell.')
with (source_results/'features_used.csv').open(newline='') as saved_table:
    saved_models = {row['model_name'] for row in csv.DictReader(saved_table)}
expected_model = 'yolov8l.pt' if save_detector == 'yolov8' else 'yolo11l.pt'
saved_selection = json.loads((source_results/'selected_model.json').read_text())
expected_kind = 'reused_historical_holdout' if save_mode == 'cached' else 'new_clips_on_previously_examined_dates'
if saved_models != {expected_model} or saved_selection['evaluation_kind'] != expected_kind:
    raise ValueError('Completed results do not match the selected detector/mode. Run the configuration and processing cells in order.')
save_root.mkdir(parents=True, exist_ok=True)
if source_results.resolve() != saved_results.resolve():
    shutil.copytree(source_results, saved_results, dirs_exist_ok=True)
archive = shutil.make_archive(str(save_root/f'Forecasting_v3_{save_detector}_{save_mode}'),
                              'zip', saved_results)
RESULT_DIR = saved_results
print('Results folder:', saved_results)
print('Results archive:', archive)
print('Open Google Drive > My Drive > CP-1 Dataset > Forecasting_v3 > '+save_detector)
'''


def configuration_text(run_mode='cached', detector='yolo11'):
    return f'''# Change only this cell to configure the experiment.
RUN_MODE = {run_mode!r}  # 'expanded': larger GPU run; 'cached': the original 80 clips.
DETECTOR = {detector!r}  # 'yolo11' or 'yolov8'
DRIVE_BASE = '/content/drive/MyDrive/CP-1 Dataset'
LABELS_RELATIVE_PATH = 'CSV/Train.csv'
EXPERIMENT_NAME = 'expanded_01'  # Use the same name/settings to resume.
TRAIN_CLIPS_PER_CAMERA_DATE = 20
TEST_CLIPS_PER_CAMERA_DATE = 8
PLAN_ONLY = False  # True: audit filenames/labels and save a plan without GPU extraction.
USE_MOTION_FEATURES = True  # Used only when logs cover every selected clip.
assert RUN_MODE in {{'cached','expanded'}} and DETECTOR in {{'yolo11','yolov8'}}
assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', EXPERIMENT_NAME), 'Use a simple experiment folder name.'
'''


def finish_text():
    source = '''
selection, metrics = evaluate_pipeline(features, RESULT_DIR, EVALUATION_KIND)
display(metrics)
print('Class distribution (compare with majority and persistence on this same sample):')
display(pd.read_csv(RESULT_DIR/'split_class_distribution.csv'))
import matplotlib.pyplot as plt
matrix = pd.read_csv(RESULT_DIR/'confusion_matrix.csv', index_col=0)
fig, ax = plt.subplots(figsize=(8,6))
im = ax.imshow(matrix.values, cmap='Blues')
for i in range(4):
    for j in range(4):
        r,g,b,_ = im.cmap(im.norm(matrix.iloc[i,j]))
        color = 'black' if .2126*r+.7152*g+.0722*b>.5 else 'white'
        ax.text(j,i,str(matrix.iloc[i,j]),ha='center',va='center',color=color,fontsize=14)
ax.set_xticks(range(4),CLASSES,rotation=25,ha='right')
ax.set_yticks(range(4),CLASSES)
ax.set_xlabel('Predicted future class'); ax.set_ylabel('True future class')
ax.set_title(DETECTOR+' features: '+selection['selected_candidate'])
fig.tight_layout(); fig.savefig(RESULT_DIR/'confusion_matrix.png',dpi=300); plt.show()
import shutil
if RUN_MODE == 'expanded':
    metadata_folder = RESULT_DIR/'run_metadata'
    metadata_folder.mkdir(exist_ok=True)
    for name in ['dataset_inventory.csv','labelled_videos_missing_from_drive.csv',
                 'videos_without_labels.csv','invalid_label_timing.csv',
                 'selected_pairs.csv','checkpoint_contract.json']:
        shutil.copy2(output_root/name,metadata_folder/name)
archive = shutil.make_archive(str(RESULT_DIR.parent/('Forecasting_v3_'+DETECTOR+'_'+RUN_MODE)), 'zip', RESULT_DIR)
print('Results archive:',archive)
print('These recording dates were previously examined; independent confirmation on new dates is still required.')
print('Google Drive results folder:',RESULT_DIR.parent)
'''
    from textwrap import indent
    return ("if RUN_MODE == 'expanded' and PLAN_ONLY:\n"
            "    print('Preflight finished; no forecasting evaluation was run.')\nelse:\n"+
            indent(source.strip(),'    ')+'\n')


def save_completed_text():
    from textwrap import indent
    return ("if RUN_MODE == 'expanded' and PLAN_ONLY:\n"
            "    print('Preflight reports are already saved. No evaluation ZIP is needed yet.')\nelse:\n"+
            indent(SAVE_COMPLETED.strip(),'    ')+'\n')

def cell(text, kind='code'):
    result = {'cell_type':kind,'metadata':{},'source':text.strip().splitlines(keepends=True)}
    # splitlines without trailing newline at each joined boundary is intentional:
    # strings retain their own newlines, with final line left unterminated.
    if kind=='code': result.update(outputs=[], execution_count=None)
    return result


def data_cell_text(cached, tracker, processor):
    """Keep CSV rows on separate source lines; configuration selects the model."""
    lines = ['# Saved feature data: do not edit. Change DETECTOR in the configuration cell.',
             'CACHED_FEATURES = {']
    for name, text in cached.items():
        lines.append(f'    {name!r}: (')
        lines.extend('        '+repr(row) for row in text.splitlines(keepends=True))
        lines.append('    ),')
    lines.extend(['}', f'TRACKER_SETTINGS = {tracker!r}', f'PROCESSOR_CODE = {processor!r}',
                  'historical = pd.read_csv(io.StringIO(CACHED_FEATURES[DETECTOR]))',
                  'expected_model = "yolov8l.pt" if DETECTOR == "yolov8" else "yolo11l.pt"',
                  'if not historical.model_name.eq(expected_model).all():',
                  '    raise ValueError("Cached feature model does not match DETECTOR.")',
                  'print("Detector:", DETECTOR, "| Loaded completed clips:", len(historical))'])
    return '\n'.join(lines)


def main():
    module = (PROGRAM/'congestion_forecasting_v3.py').read_text(encoding='utf-8').split("if __name__ == '__main__':")[0]
    processor = (PROGRAM/'notebook_sources/cell_5.py').read_text(encoding='utf-8').split('# The single-video journal context')[0]
    processor = processor.replace('    for event in crossings:',
        '    if total_frames > 0 and frame_idx != total_frames:\n'
        '        raise ValueError(f"Incomplete clip: {frame_idx}/{total_frames} frames")\n'
        '    for event in crossings:', 1)
    nb11 = json.loads((PROGRAM/'CP1_Vehicle_Counter_yolov11.ipynb').read_text(encoding='utf-8'))
    config_ast = ast.parse(''.join(nb11['cells'][4]['source']))
    tracker = next(ast.literal_eval(n.value) for n in config_ast.body if isinstance(n,ast.Assign)
                   and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='custom_config')
    cached = {name:read_cached(ROOT,name).to_csv(index=False) for name in ['yolo11','yolov8']}
    intro = '''# CP-1: improved congestion forecasting (v3)

Start with `RUN_MODE = "cached"`: uses embedded completed YOLO features, needs
no video processing or GPU. Mount Drive to save results in `CP-1 Dataset`.
Select either detector in configuration.
Model choice uses chronological validation on 20–24 October only, then evaluates
once on the historical 32 clips. Those test results are exploratory because they
were already examined. Results may improve or decrease; the procedure never
chooses a model using test accuracy.

For more training data, change `RUN_MODE` to `"expanded"`, use a T4 GPU and run
from the top. Defaults select up to 400 additional training clips plus completed
training clips, and up to 64 new evaluation clips, depending on Drive availability.
Selection is by camera/date, without balancing on future labels. This changes
class prevalence: compare the v3 baselines on this same new set, not just the old
37.5% number. Old test clips and nearby clips are excluded from the new audit.
New independent dates/cameras are still needed for a stronger final test.

Both modes save reports, charts, models and ZIPs to
`CP-1 Dataset/Forecasting_v3/<detector>/`. Expanded mode resumes completed clips.
Keep its model/settings/sample size unchanged while resuming. Motion features
are enabled only if saved observation logs cover every selected clip. Motion
speed is normalized image displacement, not road speed. Empty frames count in
density and occupancy summaries. Human source/future labels never enter model
features; source labels are used only by the reported persistence baseline.

Run cells in order; the export cell creates a ZIP for review. The final save cell
can also copy a previously completed runtime result into the same Drive folder
without retraining. No paper results are
automatically replaced. Validation practice follows scikit-learn guidance:
https://scikit-learn.org/stable/common_pitfalls.html#data-leakage
'''
    config = configuration_text()
    data = data_cell_text(cached, tracker, processor)
    finish = finish_text()
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
              'colab':{'name':'CP1_Congestion_Improved.ipynb'}},
              'cells':[cell(intro,'markdown'),cell('!pip install -q "scikit-learn>=1.4" "xgboost>=2.0" pandas numpy matplotlib joblib'),
                       cell(module),cell(config),cell(data),cell(EXPANDED),cell(finish),cell(save_completed_text())]}
    for i,c in enumerate(notebook['cells']):
        if c['cell_type']=='code':
            code=''.join(line for line in c['source'] if not line.lstrip().startswith('!'))
            ast.parse(code,filename=f'cell_{i}')
    target=PROGRAM/'CP1_Congestion_Improved.ipynb'
    if target.exists():
        old=json.loads(target.read_text(encoding='utf-8'))
        if any(c.get('outputs') for c in old['cells']): raise RuntimeError('Refusing to clear executed notebook outputs')
    target.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print('Created:',target)


if __name__=='__main__': main()
