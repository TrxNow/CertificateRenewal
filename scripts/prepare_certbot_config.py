"""Rewrite Windows certbot paths in renewal configs for Linux runners."""

from __future__ import annotations

import re
from pathlib import Path


def _normalize_slashes(path: str) -> str:
    return path.replace("\\", "/")


def prepare_config_for_runner(
    config_dir: Path,
    work_dir: Path,
    logs_dir: Path,
) -> None:
    """
    Certbot on Windows stores absolute ``C:\\Certbot\\...`` paths in ``renewal/*.conf``.
    Omarchy/Linux certbot uses repo-local dirs — rewrite those paths before renew.
    """
    config_dir = config_dir.resolve()
    work_dir = work_dir.resolve()
    logs_dir = logs_dir.resolve()
    cfg = _normalize_slashes(str(config_dir))
    work = _normalize_slashes(str(work_dir))
    logs = _normalize_slashes(str(logs_dir))

    renewal_dir = config_dir / "renewal"
    if not renewal_dir.is_dir():
        return

    win_config = re.compile(r"[Cc]:[/\\]Certbot", re.IGNORECASE)
    win_work = re.compile(r"[Cc]:[/\\]Certbot[/\\]lib", re.IGNORECASE)
    win_logs = re.compile(r"[Cc]:[/\\]Certbot[/\\]log", re.IGNORECASE)

    for conf in renewal_dir.glob("*.conf"):
        original = conf.read_text(encoding="utf-8")
        updated = win_config.sub(cfg, original)
        updated = win_work.sub(work, updated)
        updated = win_logs.sub(logs, updated)
        updated = updated.replace("\\", "/")
        if updated != original:
            conf.write_text(updated, encoding="utf-8")
            print(f"  updated paths in {conf.name}")
