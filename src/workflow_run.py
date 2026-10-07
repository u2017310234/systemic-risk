"""Operational Actions entry point: missing data skips, software errors fail."""
from datetime import date,timedelta
import json
import os
from pathlib import Path
from src.config import cfg
from src.pipeline import run_pipeline
from src.operational import DataUnavailable


def write_actions_status(status,reason='',*,ready=False,published=False):
    output=os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output,'a') as file:
            file.write(f'status={status}\nready={str(ready).lower()}\npublished={str(published).lower()}\n')
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as file:
            file.write(f'## Data operation: {status}\n\n')
            file.write(('New data published.' if published else 'No production pointer changed by this step.')+'\n\n')
            if reason:file.write('Reason: '+json.dumps(reason,ensure_ascii=False)+'\n\n')
            if status in ('skipped','unavailable'):
                file.write('Workflow completed normally; current data/acceptance is unavailable. This is not a successful live-data validation.\n')


def execute(target=None):
    target=target or date.today()
    try:
        run_pipeline(target,target-timedelta(days=int(cfg.covar_window*1.5)+30))
    except DataUnavailable as exc:
        result={'status':'skipped','published':False,'reason':str(exc)}
        write_actions_status('skipped',str(exc))
        return result
    except Exception as exc:
        write_actions_status('failed',f'{type(exc).__name__}: {exc}')
        raise
    write_actions_status('published',ready=True,published=True)
    return {'status':'published','published':True}


def main():
    cfg.publication_mode='production'
    result=execute()
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
