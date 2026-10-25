# Colab orchestration: labels are matched to video paths, never read from MP4 metadata.
from google.colab import drive
drive.mount('/content/drive')
drive_base = Path(DRIVE_BASE)
if not drive_base.is_dir():
    raise FileNotFoundError('CP-1 Dataset is not accessible. Check the mounted account and My Drive shortcut.')
output_root = drive_base/'Forecasting_v3'/DETECTOR
if RUN_MODE == 'expanded':
    output_root = output_root/EXPERIMENT_NAME
output_root.mkdir(parents=True, exist_ok=True)
features = None

if RUN_MODE == 'expanded':
    import os
    import time
    available = {}
    for camera in ['normanniles1','normanniles2','normanniles3','normanniles4']:
        folder = drive_base/camera
        if not folder.is_dir():
            raise FileNotFoundError('Camera folder is inaccessible: '+str(folder))
        print('Scanning video filenames:', camera, flush=True)
        for directory, _, names in os.walk(folder):
            for name in names:
                if name.lower().endswith('.mp4'):
                    video = Path(directory)/name
                    available[video.relative_to(drive_base).as_posix()] = str(video)
    label_path = drive_base/LABELS_RELATIVE_PATH
    if not label_path.is_file():
        raise FileNotFoundError('Label CSV is missing: '+str(label_path)+'. Copy the project Train.csv here or edit LABELS_RELATIVE_PATH.')
    labels = pd.read_csv(label_path)
    coverage, missing_labels, unlabelled_videos = dataset_label_audit(labels, available)
    timing_issues = label_timing_issues(labels)
    print('Dataset/label match:')
    display(coverage)
    plan = expansion_plan(labels, available, historical,
                          TRAIN_CLIPS_PER_CAMERA_DATE, TEST_CLIPS_PER_CAMERA_DATE)
    sampling_limits = {'train_per_camera_date':TRAIN_CLIPS_PER_CAMERA_DATE,
                       'test_per_camera_date':TEST_CLIPS_PER_CAMERA_DATE}
    plan, previous_contract = resume_saved_plan(plan,labels,available,historical,
                                                output_root,sampling_limits)
    print('Selected clips (training labels do not control sampling):')
    print(plan.groupby(['split','camera_id']).size())
    print('Total selected:',len(plan),'| Train:',int(plan.split.eq('train').sum()),
          '| Evaluation:',int(plan.split.eq('test').sum()))
    coverage.to_csv(output_root/'dataset_inventory.csv', index=False)
    missing_labels.to_csv(output_root/'labelled_videos_missing_from_drive.csv', index=False)
    unlabelled_videos.to_csv(output_root/'videos_without_labels.csv', index=False)
    timing_issues.to_csv(output_root/'invalid_label_timing.csv', index=False)
    print('Invalid label timings excluded from source/target selection:',len(timing_issues))
    preview = output_root/'preflight'
    preview.mkdir(exist_ok=True)
    plan.to_csv(preview/'proposed_pairs.csv', index=False)
    (preview/'SUMMARY.json').write_text(json.dumps({
        'detector':DETECTOR, 'mode':RUN_MODE, 'experiment':EXPERIMENT_NAME,
        'label_rows':len(labels), 'accessible_videos':len(available),
        'matched_videos':int(coverage.matched_videos.sum()),
        'invalid_label_timings':len(timing_issues),
        'train_clips':int(plan.split.eq('train').sum()),
        'evaluation_clips':int(plan.split.eq('test').sum()),
        'new_independent_dates':False}, indent=2))
    RESULT_DIR = output_root/'evaluation'
    EVALUATION_KIND = 'new_clips_on_previously_examined_dates'

    if PLAN_ONLY:
        print('Preflight saved:', preview)
        print('No videos processed. Set PLAN_ONLY=False and run from the top to start extraction.')
    else:
        import subprocess, sys
        saved_version = (previous_contract or {}).get('configuration',{}).get('ultralytics_version')
        requirement = 'ultralytics=='+saved_version if saved_version else 'ultralytics>=8.3.0'
        if saved_version:
            print('Resuming with saved Ultralytics version:',saved_version)
        subprocess.check_call([sys.executable,'-m','pip','install','-q',requirement])
        loaded_ultralytics = sys.modules.get('ultralytics')
        if (saved_version and loaded_ultralytics is not None
                and getattr(loaded_ultralytics,'__version__',saved_version) != saved_version):
            raise RuntimeError('The saved Ultralytics version is installed, but another version is already loaded. Restart the Colab kernel, then Run All with unchanged settings.')
        import cv2, torch, yaml
        from ultralytics import YOLO
        if not torch.cuda.is_available():
            raise RuntimeError('Select a Colab GPU (for example T4), reconnect, and run from the top. The preflight plan is saved.')
        YOLO_MODEL_NAME = 'yolo11l.pt' if DETECTOR == 'yolo11' else 'yolov8l.pt'
        VEHICLE_CLASSES = {2:'car',3:'motorcycle',5:'bus',7:'truck'}
        COUNTING_LINES = {'default':((.05,.5),(.95,.5))}
        custom_config = TRACKER_SETTINGS
        RUN_LOG_DIR = str(output_root/'crossing_logs')
        TRACKER_CONFIG_PATH = str(output_root/'bytetrack.yaml')
        plan_path = output_root/'selected_pairs.csv'
        plan_bytes = plan_path.read_bytes() if previous_contract else plan.to_csv(index=False).encode()
        contract = {'model':YOLO_MODEL_NAME, 'tracker':custom_config, 'lines':COUNTING_LINES,
                    'processor_sha256':hashlib.sha256(PROCESSOR_CODE.encode()).hexdigest(),
                    'plan_sha256':hashlib.sha256(plan_bytes).hexdigest(),
                    'plan_semantic_sha256':plan_fingerprint(plan),
                    'sampling_limits':sampling_limits,
                    'label_csv_sha256':hashlib.sha256(label_path.read_bytes()).hexdigest(),
                    'ultralytics_version':importlib.metadata.version('ultralytics'), 'version':5}
        signature = contract_signature(contract)
        contract_path = output_root/'checkpoint_contract.json'
        checkpoint = output_root/'extracted_features.csv'
        if checkpoint.exists() and not contract_path.exists():
            raise RuntimeError('Checkpoint contract is missing. Use a new EXPERIMENT_NAME.')
        if previous_contract:
            changes = checkpoint_changes(previous_contract,contract)
            if changes:
                (output_root/'checkpoint_mismatch.json').write_text(json.dumps(changes,indent=2))
                print('Changed checkpoint fields:',', '.join(changes))
                for field,values in changes.items():
                    print(field,'| saved:',str(values['saved'])[:100],'| current:',str(values['current'])[:100])
                raise RuntimeError('Resume blocked; changed fields: '+', '.join(changes)+'. Existing checkpoints were not replaced. Details: '+str(output_root/'checkpoint_mismatch.json'))
            if previous_contract['configuration'].get('version') == 4:
                backup = output_root/'checkpoint_contract.v4.json'
                if not backup.exists():
                    backup.write_text(json.dumps(previous_contract,indent=2))
                print('Verified original plan/settings; upgraded resume metadata from v4 to v5.')
        Path(RUN_LOG_DIR).mkdir(exist_ok=True)
        Path(TRACKER_CONFIG_PATH).write_text(yaml.safe_dump(custom_config))
        pending_contract = contract_path.with_suffix('.pending.json')
        pending_contract.write_text(json.dumps({'signature':signature,'configuration':contract},indent=2))
        pending_contract.replace(contract_path)
        if not previous_contract:
            plan_path.write_bytes(plan_bytes)
        cached = pd.read_csv(checkpoint) if checkpoint.exists() else historical.copy()
        if not cached.model_name.eq(YOLO_MODEL_NAME).all():
            raise ValueError('Checkpoint model mismatch')
        cached = cached[cached.video_path.isin(plan.videos)].drop_duplicates('video_path', keep='last')
        rows = cached.to_dict('records')
        done = set(cached.video_path)
        missing = [key for key in plan.videos if key not in done]
        pending = checkpoint.with_suffix('.pending.csv')
        cached.to_csv(pending,index=False)
        pending.replace(checkpoint)
        print('Completed clips reused:',len(done),'| New clips to process:',len(missing),flush=True)

        def make_video_key(path):
            return Path(path).relative_to(drive_base).as_posix()

        exec(PROCESSOR_CODE, globals())
        if missing:
            model = YOLO(YOLO_MODEL_NAME)
            extraction_start = time.perf_counter()
            for index,key in enumerate(missing,1):
                print(f'[{index}/{len(missing)}] Processing {key}',flush=True)
                row,_,_ = process_video_with_tracking(available[key],model)
                if row is None:
                    raise RuntimeError('Interrupted. Run from the top with unchanged settings to resume completed clips.')
                if row['video_path'] != key or row['model_name'] != YOLO_MODEL_NAME:
                    raise ValueError('Extractor returned an unexpected video or model.')
                rows.append(row)
                pd.DataFrame(rows).to_csv(pending,index=False)
                pending.replace(checkpoint)
                elapsed = time.perf_counter()-extraction_start
                eta = elapsed/index*(len(missing)-index)/60
                print(f'Checkpoint saved: {len(rows)}/{len(plan)} clips; estimated remaining {eta:.1f} minutes at current speed.',flush=True)
        features = pd.DataFrame(rows)
        if features.video_path.duplicated().any() or set(features.video_path) != set(plan.videos):
            raise RuntimeError('Every selected clip must finish once before evaluation.')
        metadata = ['videos','source_time','target_time','source_date','split',
                    'next_enter_rating','congestion_enter_rating','horizon_sec',
                    'target_video_path','gap_sec']
        features = features.drop(columns=[c for c in metadata if c in features])
        features = features.merge(plan[metadata],left_on='video_path',right_on='videos',validate='one_to_one')
        if USE_MOTION_FEATURES:
            old_logs = drive_base/('crossing_logs_v2' if DETECTOR=='yolo11' else 'crossing_logs_yolov8_v2')
            features = add_motion(features,[RUN_LOG_DIR,old_logs])
        features.to_csv(output_root/'matched_features.csv',index=False)
else:
    features = historical.copy()
    RESULT_DIR = output_root/'cached_evaluation'
    EVALUATION_KIND = 'reused_historical_holdout'
