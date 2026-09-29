#!/usr/bin/env python3
"""For each client: renewal reminder emails, renewal notice, then certbot renew."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cert_utils import (
    days_until_expiry,
    days_until_renewal_notice,
    fetch_cert_dates,
    renewal_notice_date,
)
from prepare_certbot_config import prepare_config_for_runner

REMINDER_DAYS_BEFORE_RENEWAL_NOTICE = (7, 3, 1)
DEFAULT_RENEWAL_LEAD_DAYS = 30
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
LE_ROOT = Path(os.environ.get("LETSENCRYPT_ROOT", REPO_ROOT / "data" / "letsencrypt"))


def load_config(path: Path) -> tuple[list[dict], int]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    lead = int(data.get("renewal_lead_days", DEFAULT_RENEWAL_LEAD_DAYS))
    return data.get("clients") or [], lead


def client_lead_days(client: dict, default_lead: int) -> int:
    return int(client.get("renewal_lead_days", default_lead))


def client_dirs(client_id: str) -> tuple[Path, Path, Path]:
    base = LE_ROOT / client_id
    config = base / "config"
    work = base / "work"
    logs = base / "logs"
    for d in (config, work, logs):
        d.mkdir(parents=True, exist_ok=True)
    return config, work, logs


def run_email(
    client: dict,
    *,
    kind: str,
    expires_on: str,
    renewal_notice_on: str,
    days_until_notice: int | None = None,
) -> None:
    recipients = client.get("notify_emails") or []
    if not recipients:
        return
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "send_notification.py"),
        "--kind",
        kind,
        "--client-name",
        client.get("name") or client["id"],
        "--domain",
        client["domain"],
        "--expires-on",
        expires_on,
        "--renewal-notice-on",
        renewal_notice_on,
    ]
    if kind == "reminder":
        cmd.extend(["--days-until-renewal-notice", str(days_until_notice)])
    for addr in recipients:
        cmd.extend(["--to", addr])
    subprocess.run(cmd, check=True, env=os.environ)


def truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def in_dev_mode(*, cli_flag: bool = False) -> bool:
    return cli_flag or truthy_env("DEV_MODE")


def certbot_renew(client_id: str, *, dry_run: bool) -> None:
    config, work, logs = client_dirs(client_id)
    prepare_config_for_runner(config, work, logs)
    renewal_dir = config / "renewal"
    if not renewal_dir.is_dir() or not any(renewal_dir.glob("*.conf")):
        print(f"  WARN: no renewal/*.conf under {config} - certbot has nothing to renew")
    cmd = [
        "certbot",
        "renew",
        "--non-interactive",
        "--config-dir",
        str(config),
        "--work-dir",
        str(work),
        "--logs-dir",
        str(logs),
    ]
    if dry_run:
        cmd.append("--dry-run")
    print(f"  {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "clients.yaml")
    parser.add_argument("--dry-run", action="store_true", help="certbot renew --dry-run; skip email")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Dev mode: certbot renew --dry-run; skip email (also set DEV_MODE=true)",
    )
    args = parser.parse_args()

    dry_run = args.dry_run or in_dev_mode(cli_flag=args.dev)
    if dry_run:
        reason = "DEV_MODE" if in_dev_mode(cli_flag=args.dev) else "--dry-run"
        print(f"{reason}: certbot renew will use --dry-run (no emails)")

    if not args.config.is_file():
        raise SystemExit(f"Missing {args.config}")

    clients, default_lead = load_config(args.config)
    if not clients:
        raise SystemExit("No clients in config/clients.yaml")

    errors = 0
    for client in clients:
        cid = client["id"]
        domain = client["domain"]
        lead = client_lead_days(client, default_lead)
        print(f"\n=== {cid} ({domain}) ===")

        try:
            _, not_after = fetch_cert_dates(domain)
            expires_on = fmt_dt(not_after)
            notice_dt = renewal_notice_date(not_after, lead)
            renewal_notice_on = fmt_dt(notice_dt)
            until_expiry = days_until_expiry(not_after)
            until_notice = days_until_renewal_notice(not_after, lead)
            print(
                f"  cert expires in {until_expiry} day(s); "
                f"renewal notice in {until_notice} day(s) ({renewal_notice_on})"
            )
        except Exception as exc:
            print(f"  WARN: could not read live cert: {exc}")
            until_notice = None

        if not dry_run and until_notice is not None:
            try:
                if until_notice in REMINDER_DAYS_BEFORE_RENEWAL_NOTICE:
                    print(f"  sending {until_notice}-day reminder (before renewal notice)")
                    run_email(
                        client,
                        kind="reminder",
                        expires_on=expires_on,
                        renewal_notice_on=renewal_notice_on,
                        days_until_notice=until_notice,
                    )
                elif until_notice == 0:
                    print("  sending renewal notice email")
                    run_email(
                        client,
                        kind="renewal",
                        expires_on=expires_on,
                        renewal_notice_on=renewal_notice_on,
                    )
            except subprocess.CalledProcessError:
                errors += 1

        try:
            certbot_renew(cid, dry_run=dry_run)
        except subprocess.CalledProcessError:
            print("  ERROR: certbot failed")
            errors += 1

    if errors:
        raise SystemExit(errors)


if __name__ == "__main__":
    main()
