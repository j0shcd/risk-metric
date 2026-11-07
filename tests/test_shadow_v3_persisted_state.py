"""Finite independent persisted-state inventory; every case has real API witnesses."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from tests.test_shadow_capture_v3 import Clock,toy_producer
from research import shadow_capture as c,shadow_archive_v3 as a
from research.market_dataset import canonical_bytes


class PersistedStateOracle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.patch=patch.object(c,'datetime',Clock);self.patch.start();Clock.sequence=[]
        reg=a.register({'kind':'operational_witness','decision_days':['2026-11-07','2026-11-08','2026-11-09','2026-11-10'],
                        'entry_observation_buffer_seconds':0},toy_producer,[Path('tests/test_shadow_capture_v3.py')],{'entry_observation_buffer_seconds':0})
        self.archive=self.root/'original';a.initialize(self.archive,reg)
        for day,value in [('2026-11-07',731),('2026-11-08','x'*5000),('2026-11-09',733)]:
            Clock.value=datetime.fromisoformat(day+'T12:00:00+00:00');Clock.sequence=[]
            capture=self.root/day
            raw=canonical_bytes({'closed_at':day+'T00:00:00Z','value':value})
            c.capture_response(capture,{'query_day':day},lambda request:(raw,{'status':200}))
            if day.endswith('07'):a.issue(self.archive,[capture],toy_producer)
            elif day.endswith('08'):
                with self.assertRaises(ValueError):a.issue(self.archive,[capture],toy_producer)
            else:
                Clock.sequence=[Clock.value,KeyboardInterrupt()]
                with self.assertRaises(KeyboardInterrupt):a.issue(self.archive,[capture],toy_producer)
        self.before=a.verify(self.archive)
        self.assertEqual(self.before['observation_count'],1)
        self.assertEqual(self.before['pending_or_failed_days'],['2026-11-08','2026-11-09'])
        self.assertEqual(len(list((self.archive/'captures').iterdir())),3)
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def clone(self,name):
        target=self.root/name;shutil.copytree(self.archive,target);return target
    def write(self,path,raw):path.chmod(0o644);path.write_bytes(raw)
    def capture_dir(self,archive,day):
        return next(p for p in (archive/'captures').iterdir() if json.loads((p/'capture.json').read_bytes())['request']['query_day']==day)
    def reseal_capture(self,directory,kind):
        receipt=json.loads((directory/'capture.json').read_bytes())
        if kind=='raw':
            payload=json.loads((directory/'raw.bin').read_bytes());payload['value']='y'*5000
            raw=canonical_bytes(payload);self.write(directory/'raw.bin',raw);receipt['raw_sha256']=c.sha(raw);receipt['raw_bytes']=len(raw)
        elif kind=='request':
            receipt['request']['extra']='revised';self.write(directory/'request.json',canonical_bytes(receipt['request']))
        else:receipt['response']['extra']='revised'
        receipt['capture_id']=a.digest({k:v for k,v in receipt.items() if k!='capture_id'})
        self.write(directory/'capture.json',canonical_bytes(receipt));directory.rename(directory.parent/receipt['capture_id'])
    def test_finite_file_kind_mutation_and_deletion_matrix(self):
        # This list is deliberately not imported from the archive implementation.
        kinds=['registration','raw','request','capture_receipt','orphan_raw','orphan_request','orphan_receipt',
               'selected_prefix','successful_attempt','failed_attempt','pending_attempt','failure_reason','event','publication']
        for kind in kinds:
            for action in ('mutate','delete'):
                with self.subTest(kind=kind,action=action):
                    archive=self.clone(kind+'-'+action)
                    event=next((archive/'events').iterdir())
                    captures=self.capture_dir(archive,'2026-11-08' if kind.startswith('orphan') else '2026-11-07')
                    path={'registration':archive/'registration.json','raw':captures/'raw.bin','request':captures/'request.json',
                          'capture_receipt':captures/'capture.json','orphan_raw':captures/'raw.bin','orphan_request':captures/'request.json',
                          'orphan_receipt':captures/'capture.json','selected_prefix':event,'successful_attempt':archive/'attempts'/'2026-11-07.json',
                          'failed_attempt':archive/'attempts'/'2026-11-08.json','pending_attempt':archive/'attempts'/'2026-11-09.json',
                          'failure_reason':archive/'attempts'/'2026-11-08.failure.json','event':event,
                          'publication':next((archive/'publications').iterdir())}[kind]
                    self.assertTrue(path.is_file())
                    if action=='delete':path.unlink()
                    elif kind=='selected_prefix':
                        payload=json.loads(path.read_bytes());payload['request']['selected'][0]['prefix']['value']=999
                        self.write(path,canonical_bytes(payload))
                    else:self.write(path,b'{}\n')
                    with self.assertRaises((ValueError,KeyError,FileNotFoundError,TypeError)):
                        a.verify(archive,self.before['head_sha256'])
    def test_semantically_valid_reseals_change_saved_head(self):
        for kind in ('raw','request','receipt','failed_attempt','pending_attempt','failure_reason','publication','registration'):
            with self.subTest(kind=kind):
                archive=self.clone('reseal-'+kind)
                if kind in ('raw','request','receipt'):self.reseal_capture(self.capture_dir(archive,'2026-11-08'),kind)
                else:
                    filename={'failed_attempt':'attempts/2026-11-08.json','pending_attempt':'attempts/2026-11-09.json',
                              'failure_reason':'attempts/2026-11-08.failure.json','registration':'registration.json'}.get(kind)
                    path=archive/filename if filename else next((archive/'publications').iterdir())
                    payload=json.loads(path.read_bytes())
                    if 'attempt' in kind:payload['started_at']=payload['started_at'].replace('12:00:00','11:59:59')
                    elif kind=='failure_reason':payload['error']='changed';payload['error_sha256']=c.sha(b'changed')
                    elif kind=='publication':payload['publication_completed_at']=payload['publication_completed_at'].replace('12:00:00','12:00:01')
                    else:
                        payload['config']['extra']='changed';payload['registration_id']=a.digest({k:v for k,v in payload.items() if k!='registration_id'})
                    self.write(path,canonical_bytes(payload))
                with self.assertRaises(ValueError):a.verify(archive,self.before['head_sha256'])
                if kind!='registration':self.assertNotEqual(a.verify(archive)['head_sha256'],self.before['head_sha256'])
    def test_successful_event_dependency_reseals_change_saved_head(self):
        for kind in ('selected_prefix','successful_attempt','event','raw','request','capture_receipt'):
            with self.subTest(kind=kind):
                archive=self.clone('resealed-success-'+kind)
                path=next((archive/'events').iterdir());event=json.loads(path.read_bytes())
                marker_path=next((archive/'publications').iterdir());marker=json.loads(marker_path.read_bytes())
                if kind=='selected_prefix':
                    item=event['request']['selected'][0];item['prefix']['value']=999;item['prefix_sha256']=a.digest(item['prefix'])
                elif kind=='successful_attempt':
                    attempt=archive/'attempts'/'2026-11-07.json';payload=json.loads(attempt.read_bytes());payload['started_at']=payload['started_at'].replace('12:00:00','11:59:59')
                    self.write(attempt,canonical_bytes(payload));event['request']['attempt_sha256']=c.sha(attempt.read_bytes())
                elif kind=='event':event['request']['features']['witness']=999
                else:
                    before={p.name for p in (archive/'captures').iterdir()}
                    self.reseal_capture(self.capture_dir(archive,'2026-11-07'),'receipt' if kind=='capture_receipt' else kind)
                    after={p.name for p in (archive/'captures').iterdir()}
                    event['request']['capture_ids']=[(after-before).pop()]
                request=event['request']
                produced={'selected':[{k:v for k,v in x.items() if k!='prefix_sha256'} for x in request['selected']],
                          'features':request['features'],'forecasts':[{k:v for k,v in f.items() if k not in ('entry_at','label_end_at','label_available_at')} for f in request['forecasts']]}
                request['producer_output_sha256']=a.digest(produced)
                raw=canonical_bytes(event);event_id=c.sha(raw);new_name='00000001_'+event_id+'.json'
                self.write(path,raw);path.rename(path.parent/new_name)
                marker['event_id']=event_id;self.write(marker_path,canonical_bytes(marker));marker_path.rename(marker_path.parent/(new_name+'.receipt'))
                # Even a self-consistent rewrite must disagree with retained state.
                self.assertEqual(a.verify(archive)['observation_count'],1)
                with self.assertRaisesRegex(ValueError,'trusted head'):a.verify(archive,self.before['head_sha256'])

    def test_original_failed_attempt_erasure_and_valid_next_day(self):
        changed=self.clone('erase-failure')
        for p in (changed/'attempts').glob('2026-11-08*'):p.unlink()
        with self.assertRaisesRegex(ValueError,'trusted head'):a.verify(changed,self.before['head_sha256'])
        Clock.value=datetime(2026,11,10,12,tzinfo=timezone.utc);capture=self.root/'next'
        c.capture_response(capture,{},lambda request:(canonical_bytes({'closed_at':'2026-11-10T00:00:00Z','value':734}),{}))
        event=a.issue(self.archive,[capture],toy_producer)
        after=a.verify(self.archive,event['head_sha256'])
        self.assertEqual(after['observation_count'],2)
        self.assertEqual(after['pending_or_failed_days'],self.before['pending_or_failed_days'])
        self.assertNotEqual(after['event_chain_head_sha256'],self.before['event_chain_head_sha256'])
    def test_lock_exemption_is_explicit_and_missing_lock_fails(self):
        archive=self.clone('lock');self.write(archive/'archive.lock',b'non-scientific lock bytes')
        self.assertEqual(a.verify(archive,self.before['head_sha256'])['head_sha256'],self.before['head_sha256'])
        (archive/'archive.lock').unlink()
        with self.assertRaises(FileNotFoundError):a.verify(archive,self.before['head_sha256'])
