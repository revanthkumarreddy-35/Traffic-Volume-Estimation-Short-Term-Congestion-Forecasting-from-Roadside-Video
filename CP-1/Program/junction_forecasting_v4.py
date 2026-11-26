"""Forecast congestion from calibrated journeys and past contiguous source clips."""
from pathlib import Path
import json
import re
import hashlib
import importlib.metadata

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
import joblib

from junction_counting_v4 import atomic_json, digest, file_hash, write_csv

CLASSES=['free flowing','heavy delay','light delay','moderate delay']
MEASUREMENTS=['complete_journeys','incomplete_tracks','observed_tracks','gate_entries','gate_exits',
    'mean_vehicles','max_vehicles','density_std','density_trend','mean_bbox_area_fraction',
    'bbox_occupancy_proxy','mean_confidence','motion_median','motion_p90','slow_fraction',
    'weighted_complete_journeys']


def validate_labels(labels):
    required=['videos','datetimestamp_start','datetimestamp_end','congestion_enter_rating']
    if set(required)-set(labels):raise ValueError('Label CSV is missing '+str(set(required)-set(labels)))
    t=labels[required].copy()
    if t.isna().any().any():raise ValueError('Missing label/path/timestamp.')
    t['videos']=t.videos.astype(str).str.replace('\\','/',regex=False).str.strip()
    if not t.congestion_enter_rating.isin(CLASSES).all():raise ValueError('Unknown congestion label.')
    for c in ['datetimestamp_start','datetimestamp_end']:
        t[c]=pd.to_datetime(t[c],errors='raise')
    t=t.drop_duplicates()
    if t.videos.duplicated().any():raise ValueError('Conflicting labels/timestamps for the same video.')
    if t.videos.eq('').any():raise ValueError('Empty video path.')
    return t


def build_history(features,labels,history_clips=3):
    """All candidates use the same eligible cohort. Missing history is never padded."""
    if isinstance(history_clips,bool) or not isinstance(history_clips,int) or history_clips<1:
        raise ValueError('history_clips must be a positive integer.')
    if features.video_path.duplicated().any():raise ValueError('Duplicate source features.')
    labels=validate_labels(labels)
    table=features.copy()
    # Only measured, explicit features are permitted; human labels never enter X.
    numeric=MEASUREMENTS+sorted(c for c in table if re.fullmatch(
        r'(?:gate_[A-F]_(?:entry|exit)(?:_(?:car|motorcycle|bus|truck))?|route_[A-F]_[A-F](?:_(?:car|motorcycle|bus|truck))?|journeys_(?:car|motorcycle|bus|truck))',c))
    if set(MEASUREMENTS)-set(table):raise ValueError('Missing required junction measurements.')
    table[numeric]=table[numeric].apply(pd.to_numeric,errors='raise').fillna(0)
    table=table.merge(labels,on=None,left_on='video_path',right_on='videos',how='left',validate='one_to_one')
    labelled=table.datetimestamp_start.notna()
    parsed=table.video_path.str.extract(r'_(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\.mp4$')[0]
    fallback=pd.to_datetime(parsed,format='%Y-%m-%d-%H-%M-%S',errors='coerce')
    table['source_time']=table.datetimestamp_start.fillna(fallback)
    table['segment_end']=table.datetimestamp_end.fillna(table.source_time+pd.to_timedelta(table.duration_sec,unit='s'))
    table=table.dropna(subset=['source_time','segment_end']).sort_values(['camera_id','source_time','video_path']).reset_index(drop=True)
    invalid=table.segment_end<=table.source_time
    table=table[~invalid].copy().reset_index(drop=True)
    if table.duplicated(['camera_id','source_time']).any():raise ValueError('Ambiguous duplicate camera timestamps.')
    by_camera=labels.assign(camera_id=labels.videos.str.split('/').str[0]).sort_values(['camera_id','datetimestamp_start'])
    by_camera=by_camera[by_camera.datetimestamp_end>by_camera.datetimestamp_start].copy()
    g=by_camera.groupby('camera_id')
    by_camera['target_video_path']=g.videos.shift(-1)
    by_camera['target_time']=g.datetimestamp_start.shift(-1)
    by_camera['target_label']=g.congestion_enter_rating.shift(-1)
    by_camera['gap_seconds']=(by_camera.target_time-by_camera.datetimestamp_end).dt.total_seconds()
    pairs=by_camera[by_camera.gap_seconds.between(0,2)].set_index('videos')
    lookup=set(features.video_path)
    x_current=[];x_history=[];metadata=[];excluded=[]
    for camera,group in table.groupby('camera_id',sort=False):
        group=group.reset_index(drop=True)
        for i,row in group.iterrows():
            if row.video_path not in pairs.index:
                excluded.append(dict(video_path=row.video_path,reason='no_valid_labelled_next_segment'));continue
            p=pairs.loc[row.video_path]
            if p.target_video_path not in lookup:
                excluded.append(dict(video_path=row.video_path,reason='target_video_not_processed'));continue
            if i<history_clips-1:
                excluded.append(dict(video_path=row.video_path,reason='insufficient_prior_history'));continue
            window=group.iloc[i-history_clips+1:i+1]
            gaps=(window.source_time.iloc[1:].reset_index(drop=True)-window.segment_end.iloc[:-1].reset_index(drop=True)).dt.total_seconds()
            if not gaps.between(0,2).all():
                excluded.append(dict(video_path=row.video_path,reason='history_is_not_contiguous'));continue
            if window.segment_end.max()>p.target_time:
                raise ValueError('Source/history frames extend into the prediction target.')
            current={c:float(row[c]) for c in numeric}
            hour=row.source_time.hour+row.source_time.minute/60
            current.update(camera_id=camera,hour_sin=np.sin(2*np.pi*hour/24),hour_cos=np.cos(2*np.pi*hour/24))
            hist=current.copy()
            for lag in range(1,history_clips):
                earlier=window.iloc[-lag-1]
                for c in numeric:hist[f'lag{lag}_{c}']=float(earlier[c])
            for c in numeric:
                hist['past_mean_'+c]=float(window[c].mean())
                hist['past_change_'+c]=float(window[c].iloc[-1]-window[c].iloc[0])
            x_current.append(current);x_history.append(hist)
            metadata.append(dict(video_path=row.video_path,camera_id=camera,source_time=row.source_time,
                source_end=row.segment_end,history_start=window.source_time.iloc[0],
                history_video_paths=json.dumps(window.video_path.tolist()),target_video_path=p.target_video_path,
                target_time=p.target_time,target_label=p.target_label,
                source_label=row.congestion_enter_rating))
    return pd.DataFrame(metadata),pd.DataFrame(x_current),pd.DataFrame(x_history),pd.DataFrame(excluded)


def model_pipeline(kind,x):
    cats=['camera_id'];nums=[c for c in x if c not in cats]
    prep=ColumnTransformer([
        ('numeric',Pipeline([('fill',SimpleImputer(strategy='median',keep_empty_features=True)),('scale',StandardScaler())]),nums),
        ('camera',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats)])
    if kind=='logistic':model=LogisticRegression(C=.3,max_iter=2000,random_state=42)
    elif kind=='forest':model=RandomForestClassifier(n_estimators=250,max_depth=6,min_samples_leaf=3,max_features=.7,n_jobs=2,random_state=42)
    elif kind=='xgb':model=XGBClassifier(n_estimators=150,max_depth=2,learning_rate=.04,min_child_weight=3,
        reg_lambda=10,reg_alpha=.5,subsample=.85,colsample_bytree=.85,
        objective='multi:softprob',num_class=4,eval_metric='mlogloss',tree_method='hist',n_jobs=2,random_state=42)
    else:raise ValueError(kind)
    return Pipeline([('prep',prep),('model',model)])


def candidates():
    return [(kind+'_'+family+suffix,kind,family,weight)
        for family in ['current','history']
        for kind,suffix,weight in [('logistic','_balanced','balanced'),('logistic','_unweighted',None),
                                  ('xgb','_balanced','balanced'),('forest','_balanced','balanced')]]


def scores(truth,pred):
    return dict(n=len(truth),correct=int(np.sum(truth==pred)),accuracy=float(accuracy_score(truth,pred)),
        balanced_accuracy=float(balanced_accuracy_score(truth,pred)),
        macro_f1=float(f1_score(truth,pred,labels=range(4),average='macro',zero_division=0)))


def evaluate(features,labels,output,test_start='2025-10-25',test_end='2025-10-27',history_clips=3):
    output=Path(output)
    meta,current,history,excluded=build_history(features,labels,history_clips)
    if meta.empty:raise ValueError('No eligible contiguous histories; finish feature processing first.')
    start=pd.Timestamp(test_start);end=pd.Timestamp(test_end)
    train=(meta.source_time<start)&(meta.target_time<start)
    test=(meta.history_start>=start)&(meta.source_time>=start)&(meta.source_time<end)&(meta.target_time<end)
    if not train.any() or not test.any():raise ValueError('No eligible chronological train/test split.')
    # Purge all target/test-frame overlap, not just duplicate source paths.
    train_paths=set(meta.loc[train,'video_path'])|set(meta.loc[train,'target_video_path'])
    test_paths=set(meta.loc[test,'video_path'])|set(meta.loc[test,'target_video_path'])
    if train_paths&test_paths:raise ValueError('Train/test source or target overlap.')
    config=dict(code_sha256=file_hash(__file__),test_start=str(start),test_end=str(end),history_clips=history_clips,
        features_sha256=hashlib.sha256(features.to_csv(index=False).encode()).hexdigest(),
        labels_sha256=hashlib.sha256(labels.to_csv(index=False).encode()).hexdigest(),candidates=candidates(),
        environment={n:importlib.metadata.version(n) for n in ['scikit-learn','xgboost','numpy','pandas']})
    signature=digest(config)
    output.mkdir(parents=True,exist_ok=True)
    contract=output/'evaluation_contract.json'
    if contract.exists():
        old=json.loads(contract.read_text())
        if old['signature']!=signature:raise ValueError('Evaluation inputs/settings changed; use a new EVALUATION_NAME.')
        if (output/'evaluation_complete.json').exists():
            finished=json.loads((output/'evaluation_complete.json').read_text())
            for name,expected in finished['sha256'].items():
                if not (output/name).is_file() or file_hash(output/name)!=expected:
                    raise ValueError('Completed evaluation artifact changed: '+name)
            return pd.read_csv(output/'evaluation_metrics.csv')
    else:atomic_json(contract,dict(signature=signature,config=config))
    excluded.to_csv(output/'excluded_pairs.csv',index=False)
    meta.assign(split=np.where(train,'train',np.where(test,'test','unused'))).to_csv(output/'selected_pairs.csv',index=False)
    x={'current':current,'history':history};y=meta.target_label.map({c:i for i,c in enumerate(CLASSES)}).to_numpy()
    if set(y[train])!=set(range(4)):raise ValueError('Training must contain all four classes.')
    folds=[]
    days=sorted(meta.loc[train,'source_time'].dt.normalize().unique())
    for day in days[2:]:
        day=pd.Timestamp(day)
        fit=np.flatnonzero(train&(meta.target_time<day)&(meta.source_time<day))
        valid=np.flatnonzero(train&(meta.history_start>=day)&(meta.source_time.dt.normalize()==day))
        if len(fit) and len(valid) and set(y[fit])==set(range(4)):folds.append((day,fit,valid))
    if len(folds)<2:raise ValueError('Need at least two usable chronological validation folds.')
    records=[]
    for name,kind,family,weight in candidates():
        for day,fit,valid in folds:
            model=model_pipeline(kind,x[family]);weights=compute_sample_weight(weight,y[fit]) if weight else np.ones(len(fit))
            model.fit(x[family].iloc[fit],y[fit],model__sample_weight=weights)
            pred=model.predict(x[family].iloc[valid]);records.append(dict(candidate=name,validation_date=str(day),**scores(y[valid],pred)))
    validation=pd.DataFrame(records);validation.to_csv(output/'validation_folds.csv',index=False)
    ranking=validation.groupby('candidate',as_index=False)[['macro_f1','accuracy']].mean().sort_values(
        ['macro_f1','accuracy','candidate'],ascending=[False,False,True])
    ranking.to_csv(output/'validation_ranking.csv',index=False)
    name=ranking.iloc[0].candidate
    selected=next(c for c in candidates() if c[0]==name)
    family_winners={}
    for family in ['current','history']:
        names={c[0] for c in candidates() if c[2]==family}
        family_winners[family]=next(c for c in candidates() if c[0]==ranking[ranking.candidate.isin(names)].iloc[0].candidate)
    selection=dict(selected_candidate=name,selection_metric='chronological training-date validation macro-F1',
        contract_signature=signature,evaluation_kind='previously_examined_week' if start<pd.Timestamp('2025-10-27') else 'new_dates_require_provenance_review',
        feature_names=x[selected[2]].columns.tolist(),family_winners={family:spec[0] for family,spec in family_winners.items()},
        train_n=int(train.sum()),test_n=int(test.sum()))
    atomic_json(output/'selected_model.json',selection)  # Before any test scoring.
    fit=np.flatnonzero(train);test_idx=np.flatnonzero(test)
    chosen=model_pipeline(selected[1],x[selected[2]])
    weights=compute_sample_weight(selected[3],y[fit]) if selected[3] else np.ones(len(fit))
    chosen.fit(x[selected[2]].iloc[fit],y[fit],model__sample_weight=weights)
    predictions={'selected_model':chosen.predict(x[selected[2]].iloc[test_idx])}
    # Frozen per-family winners give a same-test current/history ablation.
    for family in ['current','history']:
        winner=family_winners[family]
        model=model_pipeline(winner[1],x[family]);w=compute_sample_weight(winner[3],y[fit]) if winner[3] else np.ones(len(fit))
        model.fit(x[family].iloc[fit],y[fit],model__sample_weight=w)
        predictions[family+'_validation_winner']=model.predict(x[family].iloc[test_idx])
    predictions['training_majority']=np.full(len(test_idx),np.bincount(y[fit],minlength=4).argmax())
    predictions['human_source_label_persistence']=meta.loc[test,'source_label'].map({c:i for i,c in enumerate(CLASSES)}).to_numpy()
    if pd.isna(predictions['human_source_label_persistence']).any():raise ValueError('Missing source labels for reference baseline.')
    truth=y[test_idx];metrics=pd.DataFrame([dict(method=n,**scores(truth,p)) for n,p in predictions.items()])
    metrics.to_csv(output/'evaluation_metrics.csv',index=False)
    export=meta.loc[test].copy()
    for n,p in predictions.items():export[n]=[CLASSES[int(k)] for k in p]
    export.to_csv(output/'evaluation_predictions.csv',index=False)
    matrix=pd.DataFrame(confusion_matrix(truth,predictions['selected_model'],labels=range(4)),index=CLASSES,columns=CLASSES)
    matrix.to_csv(output/'confusion_matrix.csv')
    pd.DataFrame(classification_report(truth,predictions['selected_model'],labels=range(4),target_names=CLASSES,
        output_dict=True,zero_division=0)).T.to_csv(output/'classification_report.csv')
    distribution=pd.DataFrame({'class':CLASSES,'train':[int(sum(y[fit]==i)) for i in range(4)],
                               'test':[int(sum(truth==i)) for i in range(4)]})
    distribution.to_csv(output/'split_class_distribution.csv',index=False)
    joblib.dump(chosen,output/'selected_model.joblib')
    (output/'REPORT.md').write_text('# Junction forecasting experiment\n\n'
        f'Selected using training-date validation: `{name}`.\n\n'
        f'Evaluation provenance: `{selection["evaluation_kind"]}`. The default October 2025 week was examined before.\n\n'
        'Current and history candidates use the same eligible source/target pairs and test sample. '
        'Quality flags are retained for review; no test clips are removed based on their errors. '
        'Persistence copies a human-provided current label and is a reference baseline, not an input available to the predictor. '
        'Scores assess next-segment congestion, not vehicle-counting accuracy.\n\n'+metrics.to_string(index=False)+'\n',encoding='utf-8')
    atomic_json(output/'evaluation_complete.json',dict(contract_signature=signature,
        sha256={p.name:file_hash(p) for p in output.iterdir() if p.is_file() and p.name not in
                {'evaluation_complete.json','confusion_matrix.png'}}))
    return metrics


def manual_templates(features,calibration,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    routes=[];gates=[]
    for r in features.itertuples():
        names=sorted(g['name'] for g in calibration['cameras'][r.camera_id]['gates'])
        for a in names:
            for cls in ['car','motorcycle','bus','truck']:
                for direction in ['entry','exit']:
                    gates.append(dict(video_path=r.video_path,gate=a,event=direction,vehicle_class=cls,
                                      ground_truth_count='',annotation_status='pending'))
                for b in names:
                    if a!=b:routes.append(dict(video_path=r.video_path,origin=a,destination=b,vehicle_class=cls,
                                               ground_truth_count='',annotation_status='pending'))
    for name,rows in [('manual_journey_counts.csv',routes),('manual_gate_counts.csv',gates)]:
        path=output/name
        if not path.exists() and rows:write_csv(path,rows,list(rows[0]))


def evaluate_manual_counts(features,calibration,annotation_file,output,kind='journeys'):
    """Reject partial annotations. Compare only fully annotated full clips."""
    t=pd.read_csv(annotation_file,keep_default_na=False)
    keys=['video_path','origin','destination','vehicle_class'] if kind=='journeys' else ['video_path','gate','event','vehicle_class']
    if set(keys+['ground_truth_count','annotation_status'])-set(t):raise ValueError('Missing annotation columns.')
    if t.empty or t.duplicated(keys).any():raise ValueError('Empty or duplicate annotations.')
    if not t.annotation_status.eq('complete').all():raise ValueError('All submitted rows must be marked complete; pending/uncertain counts cannot be scored.')
    counts=pd.to_numeric(t.ground_truth_count,errors='raise')
    if counts.isna().any() or ((counts<0)|(counts%1!=0)).any():raise ValueError('Enter a nonnegative integer for every count, including zero.')
    lookup=features.set_index('video_path');rows=[]
    for video,group in t.groupby('video_path'):
        if video not in lookup.index:raise ValueError('No processed feature row for '+video)
        row=lookup.loc[video];names=sorted(g['name'] for g in calibration['cameras'][row.camera_id]['gates'])
        classes=['car','motorcycle','bus','truck']
        expected={(a,b,c) for a in names for b in names if a!=b for c in classes} if kind=='journeys' else {
            (a,d,c) for a in names for d in ['entry','exit'] for c in classes}
        actual=set(map(tuple,group[keys[1:]].to_numpy()))
        if actual!=expected:raise ValueError('Annotate every permitted route/gate and class, including zeros, for '+video)
        for _,r in group.iterrows():
            if kind=='journeys':
                col=f'route_{r.origin}_{r.destination}_{r.vehicle_class}'
                details=dict(origin=r.origin,destination=r.destination)
            elif kind=='gates':
                col=f'gate_{r.gate}_{r.event}_{r.vehicle_class}';details=dict(gate=r.gate,event=r.event)
            else:raise ValueError('kind must be journeys or gates.')
            rows.append(dict(video_path=video,**details,vehicle_class=r.vehicle_class,
                             predicted=int(row[col]),ground_truth=int(r.ground_truth_count)))
    result=pd.DataFrame(rows);error=result.predicted-result.ground_truth
    totals=result.groupby('video_path')[['predicted','ground_truth']].sum();te=totals.predicted-totals.ground_truth
    report=dict(annotation_kind=kind,annotated_clips=len(totals),cell_mae=float(abs(error).mean()),
                cell_rmse=float(np.sqrt((error**2).mean())),
                clip_total_mae=float(abs(te).mean()),clip_total_rmse=float(np.sqrt((te**2).mean())))
    output=Path(output);output.mkdir(parents=True,exist_ok=True);result.to_csv(output/'manual_comparison.csv',index=False)
    atomic_json(output/'manual_metrics.json',report)
    return report
