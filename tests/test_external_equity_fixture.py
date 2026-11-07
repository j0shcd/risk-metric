"""Invented tiny provider-shaped fixtures; no real provider data redistributed."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import pandas as pd

from research import external_equity_fixture as f

HEADER = b'Invented test header\n,Mkt-RF,SMB,HML,RF\n'
MONTHS = b'202211,10.00,1.00,-2.00,2.00\n202212,-5.00,0.00,3.00,1.00\n202301,4.00,-1.00,0.00,0.50\n'
FOOTER = b'\n Annual Factors: January-December\n,Mkt-RF,SMB,HML,RF\n2022,999.00,999.00,999.00,999.00\n'

def zipped(raw=HEADER+MONTHS+FOOTER, name=f.MEMBER):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(name,raw)
    return buffer.getvalue()


class FrenchMonthlyFixtureTests(unittest.TestCase):
    def test_percent_market_total_return_and_index_scale_invariance(self):
        frame,coverage=f.parse_monthly(HEADER+MONTHS+FOOTER)
        self.assertEqual(frame.index.strftime('%Y-%m-%d').tolist(),['2022-11-30','2022-12-31','2023-01-31'])
        self.assertEqual(coverage['annual_rows_excluded'],1)
        np.testing.assert_allclose(frame['market_total_return'],[.12,-.04,.045],rtol=0,atol=1e-16)
        expected=np.cumprod([1.12,.96,1.045])
        np.testing.assert_allclose(frame['market_total_return_index'],expected,rtol=1e-15)
        for scale in (.001,1,1000):
            levels=np.r_[scale,frame['market_total_return_index'].to_numpy()*scale]
            np.testing.assert_allclose(levels[1:]/levels[:-1]-1,frame['market_total_return'],rtol=0,atol=3e-16)
        np.testing.assert_allclose(frame['smb_return'],[.01,0,-.01])
        self.assertEqual(frame.index.name,'Date')

    def test_invalid_values_dates_and_schema_fail_closed(self):
        for value in ('NaN','inf','-inf','-99.99','-999','1e3','10%','', '1'*400):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):f.parse_monthly(HEADER+f'202211,{value},1,2,0\n'.encode())
        for bad in (b'202211,-100,0,0,0\n',b'202211,-101,0,0,0\n',
                    b'202213,1,2,3,0\n',b'202211,1,2,3,0\n2022,1,2,3,0\n',b'2022-11,1,2,3,0\n',b'202211,1,2,3\n',
                    b'202211,1,2,3,0,5\n',b'202211,1,2,3,0\n202211,1,2,3,0\n',
                    b'202211,1,2,3,0\n202301,1,2,3,0\n',
                    b'202212,1,2,3,0\n202211,1,2,3,0\n',
                    b'202211,1,2,3,0\n\n202212,1,2,3,0\n'):
            with self.subTest(row=bad):
                with self.assertRaises(ValueError):f.parse_monthly(HEADER+bad)
        with self.assertRaises(ValueError):f.parse_monthly(b'not a monthly table')
        with self.assertRaises(ValueError):f.parse_monthly(HEADER+MONTHS+HEADER)
        with self.assertRaises(ValueError):f.parse_monthly(b'x'*(f.MAX_MEMBER_BYTES+1))

    def test_zip_is_bounded_and_never_extracts(self):
        expected=HEADER+MONTHS+FOOTER
        raw,metadata=f.read_member(zipped())
        self.assertEqual(raw,expected);self.assertEqual(metadata['sha256'],f.sha(expected))
        for name in ('../'+f.MEMBER,'/tmp/'+f.MEMBER,'folder/'+f.MEMBER,'wrong.csv'):
            with self.assertRaises(ValueError):f.read_member(zipped(name=name))
        with self.assertRaises(ValueError):f.read_member(b'x'*(f.MAX_DOWNLOAD_BYTES+1))
        with self.assertRaises(ValueError):f.read_member(zipped(b'x'*(f.MAX_MEMBER_BYTES+1)))
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as z:
            z.writestr(f.MEMBER,expected);z.writestr('other.csv',expected)
        with self.assertRaises(ValueError):f.read_member(buffer.getvalue())
        with self.assertRaises(zipfile.BadZipFile):f.read_member(b'not a zip')

    def test_private_acquisition_crops_future_and_never_overwrites(self):
        payload=zipped();retrieval={'requested_url':f.URL,'sha256':f.sha(payload),'retrieved_at_utc':'2000-01-01T00:00:00+00:00'}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();private=root/'data/external_private';destination=private/'invented'
            manifest=root/'metadata.json'
            with patch.object(f,'PRIVATE_ROOT',private),patch.object(f,'download',return_value=(payload,retrieval)) as get:
                metadata=f.acquire(destination,manifest)
                self.assertEqual(metadata,json.loads(manifest.read_bytes()))
                self.assertEqual(metadata['fixture']['rows'],2)
                self.assertEqual(metadata['fixture']['excluded_after_cutoff'],1)
                self.assertEqual(metadata['fixture']['last_month'],'2022-12-31')
                self.assertEqual((destination/'source.zip').read_bytes(),payload)
                numeric=(destination/'monthly_through_2022.csv').read_bytes()
                self.assertEqual(metadata['fixture']['sha256'],f.sha(numeric))
                frame=pd.read_csv(io.BytesIO(numeric))
                self.assertEqual(frame['Date'].tolist(),['2022-11-30','2022-12-31'])
                self.assertFalse((destination/'source.zip').stat().st_mode & 0o222)
                with self.assertRaises(FileExistsError):f.acquire(destination,manifest)
                self.assertEqual(get.call_count,1)
                with self.assertRaises(ValueError):f.acquire(root/'public-data',root/'other.json')
                with self.assertRaises(ValueError):f.acquire(private/'..'/'escaped',root/'other.json')
                self.assertEqual(get.call_count,1)
                (root/'link').symlink_to(private,target_is_directory=True)
                with self.assertRaises(ValueError):f.acquire(root/'link'/'oops',root/'other.json')

    def test_existing_raw_can_resume_without_network_but_not_change(self):
        payload=zipped()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();private=root/'data/external_private';captured=private/'captured'
            captured.mkdir(parents=True)
            (captured/'source.zip').write_bytes(payload)
            (captured/'retrieval.json').write_text(json.dumps({'sha256':f.sha(payload),'requested_url':f.URL}))
            with patch.object(f,'PRIVATE_ROOT',private),patch.object(f,'download',side_effect=AssertionError('no refetch')):
                result=f.derive(captured,root/'manifest.json')
                self.assertEqual(result['fixture']['rows'],2)
                with self.assertRaises(FileExistsError):f.derive(captured,root/'new.json')
                (captured/'monthly_through_2022.csv').unlink()
                (captured/'source.zip').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'retrieval identity'):f.derive(captured,root/'new.json')

    def test_fetch_bound_and_https_verification_without_network(self):
        class Response:
            status=200
            headers={'Content-Length':str(f.MAX_DOWNLOAD_BYTES+1)}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def geturl(self):return f.URL
            def read(self,n):raise AssertionError('oversized response must not be read')
        class Opener:
            def open(self,request,timeout):
                self.request=request;return Response()
        with patch.object(f.urllib.request,'build_opener',return_value=Opener()) as opener:
            with self.assertRaisesRegex(ValueError,'Content-Length'):f.download()
            handlers=opener.call_args.args
            self.assertIsInstance(handlers[0],f._NoRedirects)
            self.assertTrue(handlers[1]._context.check_hostname)
            self.assertEqual(handlers[1]._context.verify_mode,f.ssl.CERT_REQUIRED)
        with self.assertRaises(ValueError):f._NoRedirects().redirect_request(None,None,302,'',{},'http://elsewhere')


if __name__=='__main__':unittest.main()
