"""Private official French monthly-factor fixture; no scoring or daily adapter.

The reconstructed market series is broad-US research-market total return, not
S&P 500, a tradable index, or a verified historical publication vintage. Current
French files use the CIZ methodology and can revise history. Retrieval timestamps
and HTTP Last-Modified are not observation publication timestamps. Redistribution
permission is unresolved: raw ZIP/member bytes and derived numeric rows stay in
the ignored data/external_private directory. Only metadata may be committed.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import ssl
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

URL = 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip'
MEMBER = 'F-F_Research_Data_Factors.csv'
MAX_DOWNLOAD_BYTES = 1024 * 1024
MAX_MEMBER_BYTES = 2 * 1024 * 1024
CUTOFF = '2022-12-31'
PRIVATE_ROOT = Path(__file__).resolve().parents[1] / 'data/external_private'
FACTOR_COLUMNS = ('Mkt-RF', 'SMB', 'HML', 'RF')
OUTPUT_COLUMNS = ('market_excess_return', 'smb_return', 'hml_return', 'risk_free_return')
NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)')
SENTINELS = {-99.99, -999.0}


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def _utc():
    return datetime.now(timezone.utc).isoformat()


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirects are not permitted for the fixed official download')


def download():
    """Fetch only the fixed HTTPS URL with normal certificate verification."""
    started = _utc(); deadline = time.monotonic() + 60
    opener = urllib.request.build_opener(_NoRedirects(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(URL, headers={'Accept-Encoding': 'identity',
                                                  'User-Agent': 'risk-metric-monthly-research-fixture/1'})
    with opener.open(request, timeout=20) as response:
        if response.status != 200 or response.geturl() != URL:
            raise ValueError('unexpected response status or URL')
        headers = dict(response.headers.items())
        length = response.headers.get('Content-Length')
        if length is not None and (int(length) < 0 or int(length) > MAX_DOWNLOAD_BYTES):
            raise ValueError('download Content-Length exceeds bound')
        chunks = []; size = 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError('download exceeded 60-second read budget')
            chunk = response.read(min(65536, MAX_DOWNLOAD_BYTES + 1 - size))
            if not chunk: break
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES: raise ValueError('download exceeds byte bound')
            chunks.append(chunk)
    payload = b''.join(chunks)
    return payload, {'requested_url': URL, 'resolved_url': URL, 'started_at_utc': started,
                     'retrieved_at_utc': _utc(), 'status': 200, 'headers': headers,
                     'tls_certificate_verification': True, 'redirects_permitted': False,
                     'bytes': len(payload), 'sha256': sha(payload)}


def read_member(payload):
    """Bound ZIP work and read one expected member in memory; never extract paths."""
    if not payload or len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError('ZIP size outside bound')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        if len(members) != 1:
            raise ValueError('require exactly one monthly-factor CSV member')
        member = members[0]
        if member.filename.lower() != MEMBER.lower() or member.is_dir():
            raise ValueError('unexpected ZIP member name')
        if (member.flag_bits & 1 or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                or member.file_size > MAX_MEMBER_BYTES or member.compress_size > MAX_DOWNLOAD_BYTES):
            raise ValueError('unsupported or oversized ZIP member')
        with archive.open(member) as stream:
            raw = stream.read(MAX_MEMBER_BYTES + 1)
        if len(raw) > MAX_MEMBER_BYTES or len(raw) != member.file_size:
            raise ValueError('decompressed member size mismatch')
        return raw, {'name': member.filename, 'bytes': len(raw), 'sha256': sha(raw),
                     'compressed_bytes': member.compress_size, 'zip_crc32': f'{member.CRC:08x}'}


def parse_monthly(raw):
    """Read the one monthly table, interpret provider values strictly as percent.

    Annual four-digit rows after the monthly table are excluded, never combined
    with monthly observations. Missing rows/values are errors, not imputed.
    The compounded index is 1 immediately before the first observed month;
    therefore its first published value is 1 + that month's total return.
    """
    if len(raw) > MAX_MEMBER_BYTES: raise ValueError('text exceeds member byte bound')
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    dates = []; values = []; started = False; ended = False; annual = False; annual_count = 0
    for row in rows:
        row = [cell.strip() for cell in row]
        if row == ['', *FACTOR_COLUMNS]:
            if started:
                if annual: continue
                raise ValueError('duplicate monthly header')
            started = True; continue
        if not started: continue
        if not row or not any(row):
            if dates: ended = True
            continue
        token = row[0]
        if re.fullmatch(r'\d{6}', token):
            if ended: raise ValueError('monthly rows resume after table ended')
            if len(row) != 5 or any(not NUMBER.fullmatch(cell) for cell in row[1:]):
                raise ValueError('monthly row requires exactly four finite percent numbers')
            numeric = np.array([float(cell) for cell in row[1:]], dtype=float)
            if not np.isfinite(numeric).all() or any(value in SENTINELS for value in numeric):
                raise ValueError('nonfinite or missing-value sentinel in monthly data')
            date = pd.to_datetime(token, format='%Y%m', errors='raise') + pd.offsets.MonthEnd(0)
            dates.append(date); values.append(numeric / 100.)
        elif dates and annual and re.fullmatch(r'\d{4}', token):
            annual_count += 1
        elif dates and token.lower().startswith('annual factors:'):
            ended = True; annual = True
        elif not ended:
            raise ValueError('malformed monthly date or row')
    if not dates: raise ValueError('monthly table missing or empty')
    index = pd.DatetimeIndex(dates, name='Date')
    if index.has_duplicates or not index.is_monotonic_increasing:
        raise ValueError('monthly dates must be unique and ordered')
    if not index.equals(pd.date_range(index[0], index[-1], freq='ME', name='Date')):
        raise ValueError('monthly observations contain gaps')
    frame = pd.DataFrame(values, index=index, columns=OUTPUT_COLUMNS)
    frame['market_total_return'] = frame['market_excess_return'] + frame['risk_free_return']
    if (frame['market_total_return'] <= -1).any():
        raise ValueError('market total return must be greater than -1')
    with np.errstate(over='raise', invalid='raise'):
        frame['market_total_return_index'] = np.exp(np.log1p(frame['market_total_return']).cumsum())
    if not np.isfinite(frame.to_numpy()).all() or (frame['market_total_return_index'] <= 0).any():
        raise ValueError('nonfinite or nonpositive compounded market index')
    vintage = re.search(r'created using the (\d{6}) CRSP database', raw.decode('utf-8-sig'))
    return frame, {'monthly_rows': len(frame), 'annual_rows_excluded': annual_count,
                   'provider_database_vintage': vintage.group(1) if vintage else None,
                   'first_month': index[0].date().isoformat(), 'last_month': index[-1].date().isoformat()}


def _safe(path):
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)): raise ValueError('symlink output path forbidden')
    return path.resolve()


def private_child(path, root):
    """Canonical private sink; reject symlinks and root/escape aliases before I/O.

    Cooperative local boundary, not protection against concurrent filesystem
    replacement. Public manifests contain identities/counts, never numeric rows.
    """
    path, root = _safe(Path(path)), _safe(Path(root))
    if not path.is_relative_to(root) or path == root:
        raise ValueError('numeric outputs require a child of the private directory')
    return path


def _write_once(path, payload):
    with path.open('xb') as stream: stream.write(payload)
    path.chmod(0o444)


def acquire(private_dir, manifest_path):
    """One exclusive acquisition, private raw/derived bytes, public metadata only."""
    private_dir, manifest_path = private_child(private_dir, PRIVATE_ROOT), _safe(Path(manifest_path))
    if private_dir.exists() or manifest_path.exists(): raise FileExistsError('acquisition paths must be new')
    payload, retrieval = download()
    private_dir.mkdir(parents=True, exist_ok=False)
    _write_once(private_dir / 'source.zip', payload)
    _write_once(private_dir / 'retrieval.json', _json_bytes(retrieval))
    return derive(private_dir, manifest_path)


def derive(private_dir, manifest_path):
    """Derive once from captured bytes, without redownloading or modifying raw data."""
    private_dir, manifest_path = private_child(private_dir, PRIVATE_ROOT), _safe(Path(manifest_path))
    if manifest_path.exists() or (private_dir / 'monthly_through_2022.csv').exists():
        raise FileExistsError('derived acquisition outputs must be new')
    for name in ('source.zip', 'retrieval.json', 'monthly_source.csv'):
        _safe(private_dir / name)
    with (private_dir / 'source.zip').open('rb') as stream:
        payload = stream.read(MAX_DOWNLOAD_BYTES + 1)
    retrieval = json.loads((private_dir / 'retrieval.json').read_bytes())
    if retrieval['sha256'] != sha(payload) or retrieval['requested_url'] != URL:
        raise ValueError('captured raw bytes differ from retrieval identity')
    raw, member = read_member(payload)
    raw_path = private_dir / 'monthly_source.csv'
    if raw_path.exists():
        if raw_path.read_bytes() != raw: raise ValueError('captured member differs from ZIP')
    else:
        _write_once(raw_path, raw)
    frame, coverage = parse_monthly(raw)
    cropped = frame.loc[:CUTOFF].copy()
    if cropped.empty: raise ValueError('no observations through the development cutoff')
    numeric = cropped.to_csv(float_format='%.17g', date_format='%Y-%m-%d', lineterminator='\n').encode()
    _write_once(private_dir / 'monthly_through_2022.csv', numeric)
    metadata = {
        'schema': 'private-french-monthly-research-market-v1', 'retrieval': retrieval, 'zip_member': member,
        'producer_sha256': sha(Path(__file__).read_bytes()), 'raw_coverage': coverage,
        'fixture': {'path': str((private_dir / 'monthly_through_2022.csv').relative_to(PRIVATE_ROOT.parent.parent)),
                    'bytes': len(numeric), 'sha256': sha(numeric), 'rows': len(cropped),
                    'first_month': cropped.index[0].date().isoformat(), 'last_month': cropped.index[-1].date().isoformat(),
                    'cutoff': CUTOFF, 'excluded_after_cutoff': len(frame)-len(cropped),
                    'columns': list(cropped.columns), 'numeric_units': 'decimal monthly simple returns; compounded index dimensionless',
                    'market_total_return': '(provider Mkt-RF percent + provider RF percent)/100',
                    'index_base': '1 immediately before first observed month; scale-invariant return reconstruction'},
        'classification': 'broad-US research-market total return; not S&P500 or a tradable index',
        'methodology': 'Current CIZ-format provider history; revised historical returns, not point-in-time vintages.',
        'availability': 'Month-end is an observation anchor, not a verified publication or execution timestamp.',
        'licence': 'Redistribution not cleared; raw and derived numeric provider data remain ignored/private.',
        'scope': 'Monthly-observation falsification fixture only; no daily drawdown, model fit or scoring performed.',
        'validation': 'Strict percent conversion; finite values; no sentinels; market return>-1; unique consecutive months.',
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_once(manifest_path, _json_bytes(metadata))
    return metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--from-existing', action='store_true', help='derive from captured private bytes without network')
    args = parser.parse_args(argv)
    result = (derive if args.from_existing else acquire)(args.private_dir, args.manifest)
    print(json.dumps({'status': 'private_monthly_fixture_only', 'fixture': result['fixture'],
                      'manifest': str(args.manifest)}, sort_keys=True))


if __name__ == '__main__': main()
