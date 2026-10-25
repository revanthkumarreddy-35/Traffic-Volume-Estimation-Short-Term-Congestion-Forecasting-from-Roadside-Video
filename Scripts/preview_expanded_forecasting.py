"""Create a label-only preview; actual Drive availability is checked in Colab."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'CP-1/Program'))
import pandas as pd
from congestion_forecasting_v3 import read_cached, expansion_plan, label_timing_issues


def main():
    labels = pd.read_csv(ROOT/'CP-1/Data/Zindi_Labels/Train.csv')
    historical = read_cached(ROOT,'yolo11')
    plan = expansion_plan(labels,set(labels.videos),historical)
    folder = ROOT/'CP-1/Forecasting_v3_Results/Expanded_Plan_Preview'
    folder.mkdir(exist_ok=True)
    plan.to_csv(folder/'label_only_selected_pairs.csv',index=False)
    issues = label_timing_issues(labels)
    issues.to_csv(folder/'invalid_label_timing.csv',index=False)
    summary = {'preview_only':True,'drive_availability_verified':False,'label_rows':len(labels),
               'invalid_label_timings':len(issues),'selected_train':int(plan.split.eq('train').sum()),
               'selected_test':int(plan.split.eq('test').sum()),
               'completed_training_clips_reused':len(set(plan.videos)&set(historical.video_path)),
               'new_clips_requiring_extraction':len(set(plan.videos)-set(historical.video_path)),
               'date_range':[str(plan.source_time.min()),str(plan.source_time.max())],
               'new_independent_dates':False}
    (folder/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    (folder/'README.md').write_text('''# Expanded experiment: label-only preview

This plan assumes every video listed in the local Train.csv is accessible.
It is not a completed experiment or a verified Drive inventory. The notebook
rebuilds the plan from actual accessible filenames and checks the saved
configuration before resuming. No new accuracy scores are available yet.

Default: 448 training clips, 64 evaluation clips; 48 completed training features
are reused, leaving 464 clips for GPU extraction if all listed videos exist.
Twenty invalid label timing records are excluded from source/target pairing.
The previous test sources/targets and nearby source/target times are excluded.
All dates are from the previously examined recording week.
''',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
