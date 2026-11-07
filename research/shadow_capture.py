"""Owned bounded current-vintage capture; no built-in networking or CLI imports.

The callback performs acquisition. Runtime receipt proves observed-by time under
an honest local clock/process, not first publication or external authentication.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from .scorecard_artifacts import publish
from .market_dataset import canonical_bytes

MAX_RESPONSE_BYTES=8*1024*1024
MAX_CAPTURE_BYTES=128*1024*1024
MAX_METADATA_BYTES=32*1024


class CaptureFailure(Exception):
    """Collector failure carrying bounded partial bytes/metadata for audit only."""
    def __init__(self,message,raw_bytes=b'',response_metadata=None):
        super().__init__(message);self.raw_bytes=raw_bytes;self.response_metadata=response_metadata or {}


def now():return datetime.now(timezone.utc)
def stamp(t):return t.isoformat(timespec='microseconds').replace('+00:00','Z')
def time(value):
    if not isinstance(value,str):raise ValueError('explicit UTC timestamp required')
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None or t.utcoffset().total_seconds()!=0:raise ValueError('UTC timestamp required')
    return t

def sha(raw):return hashlib.sha256(raw).hexdigest()
def safe(path):
    path=Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('unsafe path')
    return path

def read(path,limit):
    with safe(path).open('rb') as stream:raw=stream.read(limit+1)
    if len(raw)>limit:raise ValueError('byte limit')
    return raw

def frozen_write(path,raw):
    publish(safe(path),raw);Path(path).chmod(0o444)


def capture_response(directory,request,fetch):
    """fetch(request copy) -> (bytes, response metadata). Never import a provider."""
    directory=safe(directory);request_raw=canonical_bytes(request)
    if len(request_raw)>MAX_METADATA_BYTES or not isinstance(request,dict):raise ValueError('request metadata limit/shape')
    directory.mkdir(parents=True,exist_ok=False)
    started=now();frozen_write(directory/'request.json',request_raw)
    try:
        raw,response=fetch(json.loads(request_raw));completed=now()
        if completed<started:raise ValueError('capture clock reversal')
        if not isinstance(raw,bytes) or len(raw)>MAX_RESPONSE_BYTES:raise ValueError('response byte limit/type')
        metadata=canonical_bytes(response)
        if not isinstance(response,dict) or len(metadata)>MAX_METADATA_BYTES:raise ValueError('response metadata limit/shape')
        frozen_write(directory/'raw.bin',raw)
        receipt={'schema':'owned-current-vintage-v1','availability':'observed_current_vintage','published_at':None,
                 'started_at':stamp(started),'completed_at':stamp(completed),'request':json.loads(request_raw),
                 'response':response,'raw_sha256':sha(raw),'raw_bytes':len(raw)}
        receipt['capture_id']=sha(canonical_bytes(receipt))
        frozen_write(directory/'capture.json',canonical_bytes(receipt))
        return receipt
    except Exception as error:
        failure={'status':'failed_capture','error':str(error),'started_at':stamp(started),'failed_at':stamp(now()),
                 'request_sha256':sha(request_raw)}
        if isinstance(error,CaptureFailure):
            partial=error.raw_bytes;metadata=canonical_bytes(error.response_metadata)
            if isinstance(partial,bytes) and len(partial)<=MAX_RESPONSE_BYTES and len(metadata)<=MAX_METADATA_BYTES:
                frozen_write(directory/'partial.bin',partial)
                failure.update(partial_sha256=sha(partial),response_metadata=error.response_metadata)
            else:failure['partial_payload']='rejected_over_limit_or_wrong_type'
        frozen_write(directory/'failure.json',canonical_bytes(failure));raise


def verify_capture(directory):
    directory=safe(directory)
    if {p.name for p in directory.iterdir()}!={'request.json','raw.bin','capture.json'}:raise ValueError('incomplete/unexpected capture files')
    raw=read(directory/'raw.bin',MAX_RESPONSE_BYTES);receipt=json.loads(read(directory/'capture.json',2*MAX_METADATA_BYTES))
    if set(receipt)!={'schema','availability','published_at','started_at','completed_at','request','response','raw_sha256','raw_bytes','capture_id'}:raise ValueError('capture schema')
    if (receipt['schema']!='owned-current-vintage-v1' or receipt['availability']!='observed_current_vintage'
            or receipt['published_at'] is not None or receipt['raw_sha256']!=sha(raw) or receipt['raw_bytes']!=len(raw)
            or receipt['capture_id']!=sha(canonical_bytes({k:v for k,v in receipt.items() if k!='capture_id'}))
            or read(directory/'request.json',MAX_METADATA_BYTES)!=canonical_bytes(receipt['request'])
            or time(receipt['completed_at'])<time(receipt['started_at'])):raise ValueError('capture identity/chronology mismatch')
    return raw,receipt
