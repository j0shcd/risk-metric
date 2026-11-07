"""Execute reviewed indicator transforms on exactly the immutable bytes attested.

No paths are accepted. This prevents hash-then-reopen races at central admission;
producer purity and code/configuration identity remain separately reviewed.
This is not a Python sandbox and changes no forecast-scoring protocol.
"""
import hashlib
import io
import pandas as pd

MAX_INPUT_BYTES = 16 * 1024 * 1024


def derive(raw, expected_sha256, transform):
    if type(raw) is not bytes or len(raw) > MAX_INPUT_BYTES:
        raise ValueError('bounded immutable input bytes required')
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError('owned input identity mismatch')
    frame = pd.read_csv(io.BytesIO(raw))
    rows = len(frame)
    result = transform(frame)
    return result, {'input_sha256': digest, 'input_bytes': len(raw), 'input_rows': rows}
