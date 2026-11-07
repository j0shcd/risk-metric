"""Independent source/sink chronology oracle; synthetic responses only."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import ast
import inspect
import os
import stat
import json
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from research import shadow_capture as c,shadow_archive_v3 as a

UTC=timezone.utc

def toy_producer(raw,config,day):
    payload=json.loads(raw[0]);mode=config.get('mode')
    if mode=='interrupt':raise KeyboardInterrupt
    if mode=='failure':raise ValueError(config.get('error','synthetic failure'))
    if mode=='mutate':config['changed']=True
    n=config.get('atoms',3)
    forecasts=[{'model':model,'interpretation':'issued_cdf' if model=='empirical' else 'iid_predictive_law_draws',
                'target':'terminal_log_return','horizon_months':h,'atoms':np.linspace(-1,1,n).tolist(),'weights':[1/n]*n}
               for model in config.get('models',['empirical']) for h in (12,24)]
    return {'selected':[{'capture_index':0,'closed_at':payload['closed_at'],'prefix':payload}],
            'features':{'witness':float(payload['value'])},'forecasts':forecasts}

class Clock(datetime):
    value=datetime(2026,11,7,12,tzinfo=UTC)
    sequence=[]
    @classmethod
    def now(cls,tz):
        if cls.sequence:
            value=cls.sequence.pop(0)
            if isinstance(value,BaseException):raise value
            cls.value=value
        return cls.value

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        Clock.value=datetime(2026,11,7,12,tzinfo=UTC);Clock.sequence=[]
        self.patch=patch.object(c,'datetime',Clock);self.patch.start()
    def tearDown(self):self.patch.stop();self.tmp.cleanup()
    def capture(self,name='capture',close='2026-11-07T00:00:00Z',value=731):
        p=self.root/name;payload=json.dumps({'closed_at':close,'value':value}).encode()
        c.capture_response(p,{'query_day':'2026-11-07'},lambda r:(payload,{'status':200}))
        return p
    def archive(self,config=None,kind='operational_witness',days=None,name='archive'):
        reg=a.register({'kind':kind,'decision_days':days or ['2026-11-07'],'entry_observation_buffer_seconds':(config or {}).get('entry_observation_buffer_seconds',0)},toy_producer,[Path(__file__)],{'entry_observation_buffer_seconds':0,**(config or {})})
        p=self.root/name;a.initialize(p,reg);return p
    def test_actual_callback_owned_bytes_and_stale_eligible(self):
        capture=self.capture(close='2026-11-01T00:00:00Z');archive=self.archive()
        event=a.issue(archive,[capture],toy_producer)
        result=a.verify(archive,event['head_sha256']);self.assertEqual(result['observation_count'],1)
        record=json.loads(next((archive/'events').iterdir()).read_bytes())
        self.assertEqual(record['request']['features']['witness'],731)
        self.assertTrue(event['classification']['prospective_eligibility'])
        self.assertEqual(record['classification']['classification'],'provisional_requires_publication_receipt')
        self.assertIn('older_source_as_of',record['classification']['quality_flags'])
        self.assertEqual(record['request']['forecasts'][0]['entry_at'],'2026-11-08T00:00:00.000000Z')
        with self.assertRaisesRegex(ValueError,'attempted'):a.issue(archive,[capture],toy_producer)
        capture.joinpath('raw.bin').chmod(0o644);capture.joinpath('raw.bin').write_bytes(b'changed external copy')
        self.assertEqual(a.verify(archive)['observation_count'],1)
    def test_chronology_matrix(self):
        for mode in ('futurebar','captureafter','reversal','midnight','commitentry','wrongday'):
            with self.subTest(mode=mode):
                Clock.value=datetime(2026,11,7,12,tzinfo=UTC);Clock.sequence=[]
                capture=self.capture(mode,close='2026-11-08T00:00:00Z' if mode=='futurebar' else '2026-11-07T00:00:00Z')
                archive=self.archive(name='archive-'+mode)
                start=Clock.value
                if mode=='captureafter':Clock.value=start-timedelta(seconds=1)
                if mode=='reversal':Clock.sequence=[start,start-timedelta(seconds=1)]
                if mode=='midnight':Clock.sequence=[start,datetime(2026,11,8,tzinfo=UTC)]
                if mode=='commitentry':Clock.sequence=[start,start,datetime(2026,11,8,tzinfo=UTC)]
                if mode=='wrongday':Clock.value=start+timedelta(days=1)
                with self.assertRaises(ValueError):a.issue(archive,[capture],toy_producer)
                self.assertEqual(len(list((archive/'events').iterdir())),0)
    def test_formal_cohort_and_v2_reject(self):
        with self.assertRaisesRegex(ValueError,'month ends'):self.archive(kind='formal_monthly')
        archive=self.archive(kind='formal_monthly',days=['2026-11-30'])
        with self.assertRaisesRegex(ValueError,'cohort'):a.issue(archive,[self.capture()],toy_producer)
        reg=json.loads((archive/'registration.json').read_bytes());reg['schema']='research-shadow-archive-v2';reg['registration_id']=a.digest({k:v for k,v in reg.items() if k!='registration_id'})
        with self.assertRaisesRegex(ValueError,'v3'):a.initialize(self.root/'v2',reg)
    def test_tamper_matrix(self):
        for mode in ('raw','unknown','prefix','runtime','config','helper'):
            Clock.value=datetime(2026,11,7,12,tzinfo=UTC)
            capture=self.capture('capture-'+mode);archive=self.archive(name='archive-'+mode)
            if mode in ('raw','unknown'):
                file=capture/('raw.bin' if mode=='raw' else 'capture.json');file.chmod(0o644)
                if mode=='raw':file.write_bytes(b'poison')
                else:
                    receipt=json.loads(file.read_bytes());receipt['availability']='unknown_vintage';receipt['capture_id']=a.digest({k:v for k,v in receipt.items() if k!='capture_id'});file.write_bytes(canonical(receipt))
                with self.assertRaises(ValueError):a.issue(archive,[capture],toy_producer)
            elif mode=='config':
                other=self.archive(config={'mode':'mutate'},name='mutator')
                with self.assertRaisesRegex(ValueError,'changed'):a.issue(other,[capture],toy_producer)
            elif mode in ('runtime','helper'):
                target=patch.object(a.platform,'python_version',return_value='changed') if mode=='runtime' else patch.object(a,'finite',lambda x:None)
                with target,self.assertRaisesRegex(ValueError,'drift'):a.issue(archive,[capture],toy_producer)
            else:
                a.issue(archive,[capture],toy_producer);file=next((archive/'events').iterdir());event=json.loads(file.read_bytes());event['request']['selected'][0]['prefix']['value']=999
                file.chmod(0o644);file.write_bytes(canonical(event))
                with self.assertRaises(ValueError):a.verify(archive)
    def test_failure_interruption_and_concurrency(self):
        capture=self.capture()
        for mode in ('failure','interrupt'):
            archive=self.archive(config={'mode':mode},name=mode)
            with self.assertRaises(ValueError if mode=='failure' else KeyboardInterrupt):a.issue(archive,[capture],toy_producer)
            self.assertEqual(a.verify(archive)['pending_or_failed_days'],['2026-11-07'])
            with self.assertRaisesRegex(ValueError,'attempted'):a.issue(archive,[capture],toy_producer)
        archive=self.archive()
        def call():
            try:a.issue(archive,[capture],toy_producer);return 'success'
            except ValueError:return 'rejected'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:call(),range(2)))
        self.assertEqual(sorted(results),['rejected','success'])
    def test_capture_limits_paths_and_clock(self):
        with self.assertRaises(ValueError):c.capture_response(self.root/'..'/'escape',{},lambda r:(b'',{}))
        (self.root/'link').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError):c.capture_response(self.root/'link'/'escape',{},lambda r:(b'',{}))
        with patch.object(c,'MAX_RESPONSE_BYTES',2),self.assertRaisesRegex(ValueError,'byte limit'):c.capture_response(self.root/'large',{},lambda r:(b'123',{}))
        Clock.sequence=[Clock.value,Clock.value-timedelta(seconds=1)]
        with self.assertRaisesRegex(ValueError,'reversal'):c.capture_response(self.root/'clock',{},lambda r:(b'',{}))
    def test_caps_and_head(self):
        capture=self.capture();archive=self.archive();a.issue(archive,[capture],toy_producer)
        with self.assertRaisesRegex(ValueError,'head'):a.verify(archive,'0'*64)
        with patch.object(a,'MAX_EVENT_BYTES',100),self.assertRaises(ValueError):a.verify(archive)
        with patch.object(a,'MAX_ARCHIVE_BYTES',100),self.assertRaises(ValueError):a.verify(archive)
        with patch.object(a,'MAX_EVENTS',0),self.assertRaises(ValueError):a.verify(archive)
        with patch.object(c,'MAX_CAPTURE_BYTES',1),self.assertRaises(ValueError):a.verify(archive)
    def test_resolution_is_model_aware(self):
        capture=self.capture();archive=self.archive(config={'models':['empirical','generative']});issued=a.issue(archive,[capture],toy_producer)
        Clock.value=datetime(2027,11,9,12,tzinfo=UTC);resolved=self.capture('outcome','2027-11-08T00:00:00Z')
        for model in ('empirical','generative'):a.resolve(archive,issued['event_id'],model,'terminal_log_return',12,.2,resolved,'2027-11-08T00:00:00Z')
        self.assertEqual(a.verify(archive)['resolution_count'],2)
        with self.assertRaisesRegex(ValueError,'duplicate'):a.resolve(archive,issued['event_id'],'empirical','terminal_log_return',12,.2,resolved,'2027-11-08T00:00:00Z')
    def test_postpublication_boundary_and_interruption(self):
        for mode in ('atentry','clockroll','interruption'):
            Clock.value=datetime(2026,11,7,12,tzinfo=UTC);Clock.sequence=[]
            capture=self.capture('c-'+mode);archive=self.archive(name='a-'+mode)
            start=Clock.value
            if mode=='atentry':Clock.sequence=[start,start,start,datetime(2026,11,8,tzinfo=UTC)]
            elif mode=='clockroll':Clock.sequence=[start,start,start,start-timedelta(seconds=1)]
            if mode!='interruption':
                with self.assertRaisesRegex(ValueError,'publication'):a.issue(archive,[capture],toy_producer)
            else:
                Clock.sequence=[start,start,start,KeyboardInterrupt()]
                with self.assertRaises(KeyboardInterrupt):a.issue(archive,[capture],toy_producer)
            self.assertEqual(len(list((archive/'events').iterdir())),1)
            with self.assertRaises((ValueError,FileNotFoundError)):a.verify(archive)

    def test_partial_failure_and_forecast_domains(self):
        def failed(request):raise c.CaptureFailure('page2 failed',b'page1',{'completed_pages':1})
        with self.assertRaises(c.CaptureFailure):c.capture_response(self.root/'partial',{},failed)
        self.assertEqual((self.root/'partial'/'partial.bin').read_bytes(),b'page1')
        with self.assertRaises(ValueError):c.verify_capture(self.root/'partial')
        base={'model':'x','interpretation':'issued_cdf','target':'terminal_log_return','horizon_months':12,'atoms':[0.],'weights':[1.],
              'entry_at':'2026-11-08T00:00:00Z','label_end_at':'2027-11-08T00:00:00Z','label_available_at':'2027-11-09T00:00:00Z'}
        for changes in ({'weights':[.9]},{'atoms':[float('nan')]},{'target':'peak_drawdown_log_loss','atoms':[-1.]},{'horizon_months':True},{'interpretation':'unknown'}):
            with self.assertRaises(ValueError):a._forecast_shape([{**base,**changes}])
        with self.assertRaises(ValueError):a._forecast_shape([base,base])

    def test_parent_omission_capture_interruption_and_append_caps(self):
        first=self.capture('first');second=self.capture('second',value=732)
        archive=self.archive(name='omitted')
        with self.assertRaisesRegex(ValueError,'parent inventory'):a.issue(archive,[first,second],toy_producer)
        def interrupted(request):raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):c.capture_response(self.root/'interrupted',{},interrupted)
        with self.assertRaises(ValueError):c.verify_capture(self.root/'interrupted')
        for mode in ('event','archive','count','capture'):
            archive=self.archive(name='cap-'+mode)
            target={'event':(a,'MAX_EVENT_BYTES',20000),'archive':(a,'MAX_ARCHIVE_BYTES',1),'count':(a,'MAX_EVENTS',0),'capture':(c,'MAX_CAPTURE_BYTES',1)}[mode]
            # Event cap requires realistically larger atoms; registration still fits.
            if mode=='event':archive=self.archive(config={'atoms':8192},name='large-event')
            with patch.object(target[0],target[1],target[2]),self.assertRaises(ValueError):a.issue(archive,[first],toy_producer)
            self.assertEqual(len(list((archive/'events').iterdir())),0)

    def test_buffered_publication_cutoff_keeps_label_anchors(self):
        capture=self.capture()
        archive=self.archive(config={'entry_observation_buffer_seconds':7200})
        start=datetime(2026,11,7,21,59,59,tzinfo=UTC);Clock.sequence=[start,start,start,start]
        result=a.issue(archive,[capture],toy_producer)
        event=json.loads(next((archive/'events').iterdir()).read_bytes())
        self.assertEqual(event['request']['forecasts'][0]['entry_at'],'2026-11-08T00:00:00.000000Z')
        a.verify(archive,result['head_sha256'])
        archive=self.archive(config={'entry_observation_buffer_seconds':7200},name='at-buffer')
        Clock.sequence=[start,start,start,datetime(2026,11,7,22,tzinfo=UTC)]
        with self.assertRaisesRegex(ValueError,'publication'):a.issue(archive,[capture],toy_producer)
        with self.assertRaisesRegex(ValueError,'publication'):a.verify(archive)

    def test_repeated_days_preserve_loaded_code_identity(self):
        days=['2026-11-07','2026-11-08']
        archive=self.archive(days=days)
        for index,day in enumerate(days):
            Clock.value=datetime.fromisoformat(day+'T12:00:00+00:00')
            capture=self.capture('repeat-'+day,close=day+'T00:00:00Z',value=index)
            a.issue(archive,[capture],toy_producer)
        self.assertEqual(a.verify(archive)['observation_count'],2)

    def test_trusted_head_binds_publication_upper_bound(self):
        archive=self.archive();result=a.issue(archive,[self.capture()],toy_producer)
        marker=next((archive/'publications').iterdir());value=json.loads(marker.read_bytes())
        value['publication_completed_at']='2026-11-07T12:00:01.000000Z'
        marker.chmod(0o644);marker.write_bytes(canonical(value))
        with self.assertRaisesRegex(ValueError,'head'):a.verify(archive,result['head_sha256'])

    def test_resealed_registration_semantics_and_defaults(self):
        archive=self.archive();original=json.loads((archive/'registration.json').read_bytes())
        for mode in ('formal','calendar','limits'):
            reg=json.loads(json.dumps(original))
            if mode=='formal':reg['cohort']['kind']='formal_monthly'
            elif mode=='calendar':reg['calendar']['anchors']='same day entry'
            else:reg['limits']['events']=99999
            reg['registration_id']=a.digest({k:v for k,v in reg.items() if k!='registration_id'})
            with self.assertRaises(ValueError):a.initialize(self.root/('bad-'+mode),reg)
        capture=self.capture()
        original_defaults=toy_producer.__kwdefaults__
        try:
            toy_producer.__kwdefaults__={'unused':.99}
            with self.assertRaisesRegex(ValueError,'drift'):a.issue(archive,[capture],toy_producer)
        finally:toy_producer.__kwdefaults__=original_defaults

    def test_directory_durability_before_publication_witness(self):
        original=os.fsync;calls=[]
        def observe(fd):
            calls.append('directory' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'file')
            return original(fd)
        with patch.object(c.os,'fsync',observe):c.frozen_write(self.root/'durable',b'sentinel')
        self.assertGreaterEqual(calls.count('file'),2)
        self.assertEqual(calls[-1],'directory')
        archive=self.archive();capture=self.capture()
        events_inode=(archive/'events').stat().st_ino
        def fail_event_directory(fd):
            info=os.fstat(fd)
            if stat.S_ISDIR(info.st_mode) and info.st_ino==events_inode:raise OSError('directory durability failure')
            return original(fd)
        with patch.object(c.os,'fsync',fail_event_directory),self.assertRaises(OSError):a.issue(archive,[capture],toy_producer)
        self.assertEqual(len(list((archive/'events').iterdir())),1)
        self.assertEqual(list((archive/'publications').iterdir()),[])
        with self.assertRaises(FileNotFoundError):a.verify(archive)

    def test_long_error_does_not_poison_later_cohort_day(self):
        archive=self.archive(days=['2026-11-07','2026-11-08'])
        capture=self.capture(value='x'*5000)
        with self.assertRaises(ValueError):a.issue(archive,[capture],toy_producer)
        failure=archive/'attempts'/'2026-11-07.failure.json'
        self.assertLess(failure.stat().st_size,4096)
        self.assertEqual(a.verify(archive)['pending_or_failed_days'],['2026-11-07'])
        Clock.value=datetime(2026,11,8,12,tzinfo=UTC)
        a.issue(archive,[self.capture('good','2026-11-08T00:00:00Z')],toy_producer)
        self.assertEqual(a.verify(archive)['observation_count'],1)

    def test_failure_message_unicode_byte_oracle(self):
        for i,message in enumerate(['x'*5000,'🚀'*5000,'\ud800'*5000]):
            with self.subTest(i=i):
                evidence=c.failure_evidence(ValueError(message))
                self.assertLess(len(canonical(evidence)),3500)
                self.assertEqual(evidence['error_sha256'],c.sha(canonical(message)))
                archive=self.archive(config={'mode':'failure','error':message},name='unicode-'+str(i))
                with self.assertRaises(ValueError):a.issue(archive,[self.capture('unicode-capture-'+str(i))],toy_producer)
                self.assertLess((archive/'attempts'/'2026-11-07.failure.json').stat().st_size,4096)
                self.assertEqual(a.verify(archive)['pending_or_failed_days'],['2026-11-07'])
                def fail(request):raise c.CaptureFailure(message,b'partial',{})
                directory=self.root/('unicode-partial-'+str(i))
                with self.assertRaises(c.CaptureFailure):c.capture_response(directory,{},fail)
                failure=json.loads((directory/'failure.json').read_bytes())
                self.assertEqual(failure['error_sha256'],c.sha(canonical(message)))

    def test_write_sink_inventory(self):
        expected={c:{'new_directory','frozen_write','capture_response'},a:{'initialize','_own_capture','_append','issue'}}
        for module,sinks in expected.items():
            actual=set()
            for node in ast.parse(inspect.getsource(module)).body:
                if isinstance(node,ast.FunctionDef):
                    if any(isinstance(x,ast.Call) and getattr(x.func,'id',getattr(x.func,'attr','')) in ('publish','frozen_write','new_directory','mkdir') for x in ast.walk(node)):actual.add(node.name)
            self.assertEqual(actual,sinks)

def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
