"""Public resolution and replay boundary: models share one realized target."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import unittest
from tests import test_shadow_capture_v3 as support
from research import shadow_archive_v3 as a,shadow_capture as c
from research.market_dataset import canonical_bytes


class SharedOutcomeTests(unittest.TestCase):
    setUp=support.ContractTests.setUp
    tearDown=support.ContractTests.tearDown
    capture=support.ContractTests.capture
    archive=support.ContractTests.archive

    def prepare(self):
        archive=self.archive(config={'models':['empirical','generative']})
        issued=a.issue(archive,[self.capture()],support.toy_producer)
        observation=next((archive/'events').iterdir()).read_bytes()
        support.Clock.value=datetime(2027,11,9,12,tzinfo=support.UTC)
        capture=self.capture('outcome','2027-11-08T00:00:00Z')
        return archive,issued['event_id'],capture,observation

    def test_public_rejects_each_conflict_and_accepts_equal_other_model(self):
        archive,observation,capture,original=self.prepare();closed='2027-11-08T00:00:00Z'
        # Start with the second model, so the invariant cannot depend on model order.
        a.resolve(archive,observation,'generative','terminal_log_return',12,.2,capture,closed)
        other=self.capture('other','2027-11-08T00:00:00Z',value=999)
        for outcome,source,close in ((.3,capture,closed),(.2,other,closed),(.2,capture,'2027-11-08T01:00:00Z')):
            with self.subTest(outcome=outcome,source=source.name,close=close),self.assertRaisesRegex(ValueError,'conflicting shared'):
                a.resolve(archive,observation,'empirical','terminal_log_return',12,outcome,source,close)
            self.assertEqual(a.verify(archive)['resolution_count'],1)
        result=a.resolve(archive,observation,'empirical','terminal_log_return',12,.2,capture,closed)
        self.assertEqual(a.verify(archive,result['head_sha256'])['resolution_count'],2)
        self.assertEqual(sorted((archive/'events').iterdir())[0].read_bytes(),original)

    def test_different_horizon_is_independent(self):
        archive,observation,capture,_=self.prepare()
        a.resolve(archive,observation,'empirical','terminal_log_return',12,.2,capture,'2027-11-08T00:00:00Z')
        support.Clock.value=datetime(2028,11,9,12,tzinfo=support.UTC)
        later=self.capture('later','2028-11-08T00:00:00Z')
        for model in ('empirical','generative'):
            a.resolve(archive,observation,model,'terminal_log_return',24,.9,later,'2028-11-08T00:00:00Z')
        self.assertEqual(a.verify(archive)['resolution_count'],3)

    def test_resealed_persisted_conflicts_fail_without_external_head(self):
        archive,observation,capture,_=self.prepare();closed='2027-11-08T00:00:00Z'
        for model in ('empirical','generative'):
            a.resolve(archive,observation,model,'terminal_log_return',12,.2,capture,closed)
        other=self.capture('other',closed,value=999)
        with self.assertRaises(ValueError):a.resolve(archive,observation,'unknown','terminal_log_return',12,.2,other,closed)
        other_id=c.verify_capture(other)[1]['capture_id']
        for field,value in [('outcome',.3),('capture_id',other_id),('closed_at','2027-11-08T01:00:00Z')]:
            with self.subTest(field=field):
                changed=self.root/('rewrite-'+field);shutil.copytree(archive,changed)
                path=sorted((changed/'events').iterdir())[-1];old_name=path.name
                event=json.loads(path.read_bytes());event['request'][field]=value
                raw=canonical_bytes(event);identity=c.sha(raw);name=f"{event['sequence']:08d}_{identity}.json"
                path.chmod(0o644);path.write_bytes(raw);path.rename(path.parent/name)
                marker=changed/'publications'/(old_name+'.receipt');data=json.loads(marker.read_bytes());data['event_id']=identity
                marker.chmod(0o644);marker.write_bytes(canonical_bytes(data));marker.rename(marker.parent/(name+'.receipt'))
                with self.assertRaisesRegex(ValueError,'conflicting shared'):a.verify(changed)
