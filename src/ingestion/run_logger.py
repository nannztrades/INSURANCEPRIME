
# src/ingestion/run_logger.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any

__all__ = ['RunLogger']

class RunLogger:
    def __init__(self, project_root: Path):
        self.root = Path(project_root)
        self.log_dir = self.root / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.log_dir / 'ingestion.log'
        self.jsonl_path = self.log_dir / 'ingestion.jsonl'

    def _now(self) -> str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def log_csv(self, payload: Dict[str, Any]) -> None:
        keys = ['ts','type','file','rows_parsed','agent_code','agent_name','upload_id',
                'rows_inserted','moved_to','status','error']
        line = {
            'ts': self._now(),
            'type': payload.get('type',''),
            'file': payload.get('file',''),
            'rows_parsed': payload.get('rows_parsed',''),
            'agent_code': payload.get('agent_code',''),
            'agent_name': payload.get('agent_name',''),
            'upload_id': payload.get('upload_id',''),
            'rows_inserted': payload.get('rows_inserted',''),
            'moved_to': payload.get('moved_to',''),
            'status': payload.get('status',''),
            'error': payload.get('error',''),
        }
        write_header = not self.csv_path.exists()
        with self.csv_path.open('a', encoding='utf-8') as f:
            if write_header:
                f.write(','.join(keys) + '\n')
            f.write(','.join(str(line[k]).replace('\n',' ').replace(',',';') for k in keys) + '\n')

    def log_json(self, payload: Dict[str, Any]) -> None:
        import json
        payload_out = dict(payload)
        payload_out['ts'] = self._now()
        with self.jsonl_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(payload_out, ensure_ascii=False) + '\n')
