from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

import pandas as pd

from .schemas import EvaluationManifest, EvaluationTestResult, EvaluationWarning, json_safe


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    status TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    seed INTEGER NOT NULL,
    git_commit TEXT
);

CREATE TABLE IF NOT EXISTS data_fingerprints (
    run_id TEXT NOT NULL,
    name TEXT NOT NULL,
    rows INTEGER NOT NULL,
    columns INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (run_id, name)
);

CREATE TABLE IF NOT EXISTS test_results (
    run_id TEXT NOT NULL,
    test_id TEXT NOT NULL,
    family TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    artifacts_json TEXT NOT NULL,
    PRIMARY KEY (run_id, test_id)
);

CREATE TABLE IF NOT EXISTS warnings (
    run_id TEXT NOT NULL,
    test_id TEXT,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    blocks_dashboard INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    run_id TEXT NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL
);
"""


class EvaluationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_dir = root / "runs"
        self.db_path = root / "evaluation.sqlite"

    def initialize(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def write_json(self, run_id: str, relative_path: str, payload: object) -> str:
        path = self.run_dir(run_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(json_safe(payload), sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return str(path.relative_to(self.root))

    def write_jsonl(self, run_id: str, relative_path: str, rows: Iterable[object]) -> str:
        path = self.run_dir(run_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(json_safe(row), sort_keys=True, separators=(",", ":")) for row in rows]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return str(path.relative_to(self.root))

    def write_text(self, run_id: str, relative_path: str, content: str) -> str:
        path = self.run_dir(run_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path.relative_to(self.root))

    def write_frame(self, run_id: str, relative_path: str, frame: pd.DataFrame) -> str:
        path = self.run_dir(run_id) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=True)
        return str(path.relative_to(self.root))

    def record_manifest(self, manifest: EvaluationManifest) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs
                (run_id, profile, generated_at, status, config_hash, seed, git_commit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    manifest.run_id,
                    manifest.profile,
                    manifest.generated_at,
                    manifest.status,
                    manifest.config_hash,
                    int(manifest.seed),
                    manifest.git_commit,
                ),
            )
            conn.execute("DELETE FROM data_fingerprints WHERE run_id = ?", (manifest.run_id,))
            conn.execute("DELETE FROM test_results WHERE run_id = ?", (manifest.run_id,))
            conn.execute("DELETE FROM warnings WHERE run_id = ?", (manifest.run_id,))
            conn.execute("DELETE FROM artifacts WHERE run_id = ?", (manifest.run_id,))

            for item in manifest.data_fingerprints:
                conn.execute(
                    """
                    INSERT INTO data_fingerprints
                    (run_id, name, rows, columns, start_date, end_date, sha256)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.run_id,
                        item.name,
                        int(item.rows),
                        int(item.columns),
                        item.start_date,
                        item.end_date,
                        item.sha256,
                    ),
                )

            for result in manifest.tests:
                conn.execute(
                    """
                    INSERT INTO test_results
                    (run_id, test_id, family, status, severity, summary, metrics_json, artifacts_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest.run_id,
                        result.test_id,
                        result.family,
                        result.status,
                        result.severity,
                        result.summary,
                        json.dumps(json_safe(result.metrics), sort_keys=True),
                        json.dumps(json_safe(result.artifacts), sort_keys=True),
                    ),
                )

            for warning in manifest.warnings:
                self._insert_warning(conn, manifest.run_id, warning)

            for artifact in manifest.artifacts:
                conn.execute(
                    "INSERT INTO artifacts (run_id, path, kind) VALUES (?, ?, ?)",
                    (manifest.run_id, artifact, Path(artifact).suffix.lstrip(".") or "file"),
                )

    def _insert_warning(self, conn: sqlite3.Connection, run_id: str, warning: EvaluationWarning) -> None:
        conn.execute(
            """
            INSERT INTO warnings (run_id, test_id, code, severity, message, blocks_dashboard)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                warning.test_id,
                warning.code,
                warning.severity,
                warning.message,
                1 if warning.blocks_dashboard else 0,
            ),
        )
