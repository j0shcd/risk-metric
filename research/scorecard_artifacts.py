"""Exclusive, hash-bound local research receipts. No implicit repair or deletion."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from .market_dataset import canonical_bytes


def safe_path(path: Path) -> Path:
    path = path.absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("research paths cannot contain symlinks")
    return path


def publish(path: Path, payload: bytes) -> None:
    path = safe_path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".scorecard-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink()


def write_packet(path: Path, files: dict[str, bytes], bound_existing: tuple[str, ...] = ()) -> None:
    """Caller owns an existing, newly reserved directory. COMPLETE is last."""
    path = safe_path(path)
    if (set(files).intersection(bound_existing) or
            any(Path(name).name != name or name in {"receipt.json", "COMPLETE"} for name in (*files, *bound_existing))):
        raise ValueError("invalid owned file name")
    payloads = {**files, "COMPLETE": b"All receipt-listed files were published.\n"}
    hashes = {name: hashlib.sha256(safe_path(path / name).read_bytes()).hexdigest() for name in bound_existing}
    publish(path / "receipt.json", canonical_bytes({"files": {
        **hashes, **{name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()}}}))
    for name, payload in payloads.items():
        publish(path / name, payload)


def verify_packet(path: Path) -> dict:
    path = safe_path(path)
    if not (path / "COMPLETE").is_file():
        raise ValueError("incomplete research receipt")
    receipt = json.loads((path / "receipt.json").read_bytes())
    if "COMPLETE" not in receipt.get("files", {}):
        raise ValueError("receipt does not bind completion")
    for name, expected in receipt["files"].items():
        if Path(name).name != name:
            raise ValueError("unsafe receipt file")
        file = safe_path(path / name)
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError(f"corrupt research receipt: {name}")
    return receipt
