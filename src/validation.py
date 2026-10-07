"""CLI: uncertainty from supplied paired returns or out-of-time score evaluation.

No historical data or event labels are invented. Forecast evaluation requires
one outcome per entity/forecast date and explicit known-at/outcome dates.
"""
import argparse
import json
import math
from pathlib import Path
import pandas as pd
from src.analysis import bootstrap_uncertainty


def evaluate_predictions(records, cutoff):
    frame = pd.DataFrame(records)
    needed = {'entity','forecast_date','known_at','outcome_date','score','outcome'}
    if not needed<=set(frame): raise ValueError('Missing columns: '+str(sorted(needed-set(frame))))
    for col in ('forecast_date','known_at','outcome_date'):
        frame[col] = pd.to_datetime(frame[col],errors='raise',utc=True)
    if frame.duplicated(['entity','forecast_date']).any(): raise ValueError('Duplicate forecasts')
    if (frame.known_at>frame.forecast_date).any() or (frame.outcome_date<=frame.forecast_date).any():
        raise ValueError('Look-ahead or non-forward outcome')
    frame['score'] = pd.to_numeric(frame.score,errors='raise')
    if not frame.score.between(0,1).all() or not frame.outcome.isin([0,1]).all():
        raise ValueError('Evaluation requires probabilities and binary outcomes')
    point = pd.to_datetime(cutoff, utc=True)
    if pd.isna(point) or frame[['forecast_date','known_at','outcome_date']].isna().any().any():
        raise ValueError('Missing dates are not valid evidence')
    # Training labels must have matured by the split; overlapping unresolved labels excluded.
    train = frame[(frame.forecast_date<point)&(frame.outcome_date<point)]
    test = frame[frame.forecast_date>=point]
    if train.empty or test.empty: raise ValueError('Need mature training labels and out-of-time test rows')
    baseline = float(train.outcome.mean())
    return {'method':'chronological_holdout_with_mature_training_labels','cutoff':cutoff,
            'train_count':len(train),'test_count':len(test),
            'test_brier':float(((test.score-test.outcome)**2).mean()),
            'training_base_rate':baseline,'baseline_test_brier':float(((baseline-test.outcome)**2).mean()),
            'limitations':['Caller must document model training cutoff, label definition and sample selection.',
                           'Does not prove source vintages or eliminate survivor bias. No model is trained here.']}


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['uncertainty','evaluate'])
    p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--cutoff')
    args=p.parse_args();frame=pd.read_csv(args.input)
    if args.mode=='uncertainty':
        frame=frame.set_index(pd.to_datetime(frame['date'],errors='raise'))
        report=bootstrap_uncertainty(frame['bank_return'],frame['index_return'])
    else:
        if not args.cutoff:p.error('--cutoff required for evaluate')
        report=evaluate_predictions(frame.to_dict('records'),args.cutoff)
    Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False))

if __name__=='__main__':main()
