"""
logger.py
Persists all monitor snapshots to SQLite.
One database per session, stored in logs/ directory.
"""

import sqlite3
import time
import os
import json
from datetime import datetime
from typing import List, Optional

from ..monitor.session import CombinedSnapshot

LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")


def ensure_logs_dir():
    os.makedirs(LOGS_DIR, exist_ok=True)


class SessionLogger:
    def __init__(self, session_name: Optional[str] = None):
        ensure_logs_dir()
        if session_name is None:
            session_name = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        self.session_name = session_name
        self.db_path = os.path.join(LOGS_DIR, f"{session_name}.sqlite")
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        c = self._conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                lr_running INTEGER,
                -- Process
                lr_pid INTEGER,
                lr_cpu_pct REAL,
                lr_ram_rss_mb REAL,
                lr_ram_pct REAL,
                lr_threads INTEGER,
                lr_open_files INTEGER,
                -- System
                sys_cpu_pct REAL,
                sys_ram_used_mb REAL,
                sys_ram_pct REAL,
                sys_swap_used_mb REAL,
                sys_swap_pct REAL,
                -- Disk
                disk_read_bps REAL,
                disk_write_bps REAL,
                disk_usage_pct REAL,
                disk_free_gb REAL,
                -- Thermal
                thermal_pressure TEXT,
                cpu_temp_c REAL,
                gpu_temp_c REAL,
                cpu_power_w REAL,
                throttling INTEGER,
                -- GPU
                active_gpu TEXT,
                gpu_util_pct REAL
            );

            CREATE TABLE IF NOT EXISTS session_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        c.execute(
            "INSERT OR REPLACE INTO session_meta VALUES (?, ?)",
            ("start_time", str(time.time()))
        )
        self._conn.commit()

    def log(self, snap: CombinedSnapshot):
        p = snap.process
        s = snap.system
        d = snap.disk
        t = snap.thermal
        g = snap.gpu

        self._conn.execute("""
            INSERT INTO snapshots VALUES (
                NULL, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?
            )
        """, (
            snap.timestamp, int(snap.lr_running),
            p.pid if p else None,
            p.cpu_percent if p else None,
            p.memory_rss_mb if p else None,
            p.memory_percent if p else None,
            p.num_threads if p else None,
            p.num_open_files if p else None,
            s.cpu_percent_total, s.memory_used_mb, s.memory_percent,
            s.swap_used_mb, s.swap_percent,
            d.read_bytes_per_sec, d.write_bytes_per_sec,
            d.disk_usage_percent, d.disk_free_gb,
            t.thermal_pressure, t.cpu_die_temp_c, t.gpu_temp_c,
            t.cpu_power_watts, int(t.throttling_detected),
            g.active_gpu, g.gpu_utilization_percent,
        ))
        self._conn.commit()

    def close(self):
        self._conn.execute(
            "INSERT OR REPLACE INTO session_meta VALUES (?, ?)",
            ("end_time", str(time.time()))
        )
        self._conn.commit()
        self._conn.close()

    def get_all(self) -> List[dict]:
        c = self._conn.cursor()
        c.execute("SELECT * FROM snapshots ORDER BY timestamp")
        cols = [desc[0] for desc in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
