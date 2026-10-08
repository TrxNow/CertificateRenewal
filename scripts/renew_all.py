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
    pem_cert_dates,
    renewal_notice_date,
)
from prepare_certbot_config import prepare_config_for_runner

REMINDER_DAYS_BEFORE_RENEWAL_NOTICE = (7, 3, 1)
DEFAULT_RENEWAL_LEAD_DAYS = 30
PUBLIC_CERT_NAMES = ("fullchain.pem", "cert.pem", "chain.pem")
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
LE_ROOT = Path(os.environ.get("LETSENCRYPT_ROOT", REPO_ROOT / "data" / "letsencrypt"))
DEFAULT_RECIPIENTS_FILE = REPO_ROOT / "config" / "recipients.txt"


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


def load_recipients(path: Path) -> list[str]:
    if not path.is_file():
        return []
    recipients: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        recipients.append(line)
    return recipients


def public_cert_files(config_dir: Path) -> list[Path]:
    live = config_dir / "live"
    if not live.is_dir():
        return []
    found: list[Path] = []
    for lineage in sorted(p for p in live.iterdir() if p.is_dir()):
        if lineage.name.startswith("."):
            continue
        for name in PUBLIC_CERT_NAMES:
            path = lineage / name
            if path.is_file():
                found.append(path)
    return found


def run_email(
    client: dict,
    *,
    kind: str,
    expires_on: str,
    renewal_notice_on: str,
    recipients: list[str],
    days_until_notice: int | None = None,
    attachments: list[Path] | None = None,
) -> None:
    if not recipients:
        print("  WARN: no recipients in config/recipients.txt - skipping email")
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
    for path in attachments or []:
        cmd.extend(["--attach", str(path)])
    for addr in recipients:
        cmd.extend(["--to", addr])
    subprocess.run(cmd, check=True, env=os.environ)


def truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def in_dev_mode(*, cli_flag: bool = False) -> bool:
    return cli_flag or truthy_env("DEV_MODE")


def certbot_bin() -> str:
    override = os.environ.get("CERTBOT", "").strip()
    if override:
        return override
    venv_certbot = REPO_ROOT / ".venv" / "bin" / "certbot"
    if venv_certbot.is_file():
        return str(venv_certbot)
    return "certbot"


def certbot_renew(client_id: str, *, dry_run: bool) -> list[Path]:
    """Run certbot renew. Return public cert files that were newly issued."""
    config, work, logs = client_dirs(client_id)
    prepare_config_for_runner(config, work, logs)
    renewal_dir = config / "renewal"
    if not renewal_dir.is_dir() or not any(renewal_dir.glob("*.conf")):
        print(f"  WARN: no renewal/*.conf under {config} - certbot has nothing to renew")
    before = {path.resolve(): path.resolve().read_bytes() for path in public_cert_files(config)}
    cmd = [
        certbot_bin(),
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
    if dry_run:
        return []
    changed: list[Path] = []
    for path in public_cert_files(config):
        data = path.resolve().read_bytes()
        if before.get(path.resolve()) != data:
            changed.append(path)
    return changed


def fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "clients.yaml")
    parser.add_argument(
        "--recipients",
        type=Path,
        default=DEFAULT_RECIPIENTS_FILE,
        help="Text file with one email address per line",
    )
    parser.add_argument("--dry-run", action="store_true", help="certbot renew --dry-run; skip email")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Dev mode: certbot renew --dry-run; skip email (also set DEV_MODE=true)",
    )
    parser.add_argument(
        "--send-test-email",
        action="store_true",
        help="Send a test email to config/recipients.txt and exit (ignores --dev)",
    )
    args = parser.parse_args()

    if args.send_test_email:
        recipients = load_recipients(args.recipients)
        if not recipients:
            raise SystemExit(f"No recipients in {args.recipients}")
        run_email(
            {"id": "test", "name": "test", "domain": "test"},
            kind="test",
            expires_on="n/a",
            renewal_notice_on="n/a",
            recipients=recipients,
        )
        return

    dry_run = args.dry_run or in_dev_mode(cli_flag=args.dev)
    if dry_run:
        reason = "DEV_MODE" if in_dev_mode(cli_flag=args.dev) else "--dry-run"
        print(f"{reason}: certbot renew will use --dry-run (no emails)")

    if not args.config.is_file():
        raise SystemExit(f"Missing {args.config}")

    clients, default_lead = load_config(args.config)
    if not clients:
        raise SystemExit("No clients in config/clients.yaml")

    recipients = load_recipients(args.recipients)
    if not dry_run and not recipients:
        print(f"WARN: no recipients found in {args.recipients}")

    errors = 0
    for client in clients:
        cid = client["id"]
        domain = client["domain"]
        lead = client_lead_days(client, default_lead)
        expires_on = ""
        renewal_notice_on = ""
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
                        recipients=recipients,
                        days_until_notice=until_notice,
                    )
                elif until_notice == 0:
                    print("  sending renewal notice email")
                    run_email(
                        client,
                        kind="renewal",
                        expires_on=expires_on,
                        renewal_notice_on=renewal_notice_on,
                        recipients=recipients,
                    )
            except subprocess.CalledProcessError:
                errors += 1

        issued_files: list[Path] = []
        try:
            issued_files = certbot_renew(cid, dry_run=dry_run)
        except subprocess.CalledProcessError:
            print("  ERROR: certbot failed")
            errors += 1
            continue

        if dry_run:
            continue
        if not issued_files:
            print("  no new certificate issued")
            continue

        cert_pem = next((p for p in issued_files if p.name == "cert.pem"), None)
        if cert_pem:
            try:
                _, not_after = pem_cert_dates(cert_pem)
                expires_on = fmt_dt(not_after)
            except Exception as exc:
                print(f"  WARN: could not read new cert dates: {exc}")

        print("  sending new certificate email (public PEMs attached)")
        try:
            run_email(
                client,
                kind="issued",
                expires_on=expires_on or "unknown",
                renewal_notice_on=renewal_notice_on or "unknown",
                recipients=recipients,
                attachments=issued_files,
            )
        except subprocess.CalledProcessError:
            errors += 1

    if errors:
        raise SystemExit(errors)


if __name__ == "__main__":
    main()
