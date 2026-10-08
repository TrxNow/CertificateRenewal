"""TLS certificate expiry helpers."""

from __future__ import annotations

import socket
import ssl
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Tuple


def _parse_asn1_time(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%d%H%M%SZ").replace(tzinfo=timezone.utc)
    return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def fetch_cert_dates(domain: str, timeout: float = 15.0) -> Tuple[datetime, datetime]:
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=timeout) as raw:
        with context.wrap_socket(raw, server_hostname=domain) as tls:
            cert = tls.getpeercert()
    if not cert:
        raise RuntimeError(f"No certificate returned for {domain}")
    not_before = _parse_asn1_time(cert["notBefore"])
    not_after = _parse_asn1_time(cert["notAfter"])
    return not_before, not_after


def pem_cert_dates(path: Path) -> Tuple[datetime, datetime]:
    """Read notBefore/notAfter from a local PEM certificate via openssl."""

    def _field(flag: str) -> datetime:
        out = subprocess.check_output(
            ["openssl", "x509", "-in", str(path), "-noout", flag],
            text=True,
        )
        value = out.split("=", 1)[1].strip()
        return _parse_asn1_time(value)

    return _field("-startdate"), _field("-enddate")


def days_until_expiry(not_after: datetime, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if not_after.tzinfo is None:
        not_after = not_after.replace(tzinfo=timezone.utc)
    return (not_after.date() - now.date()).days


def renewal_notice_date(not_after: datetime, lead_days: int) -> datetime:
    """Calendar day the renewal notice email is sent (lead_days before cert expiry)."""
    if not_after.tzinfo is None:
        not_after = not_after.replace(tzinfo=timezone.utc)
    return not_after - timedelta(days=lead_days)


def days_until_renewal_notice(
    not_after: datetime, lead_days: int, now: datetime | None = None
) -> int:
    notice = renewal_notice_date(not_after, lead_days)
    now = now or datetime.now(timezone.utc)
    if notice.tzinfo is None:
        notice = notice.replace(tzinfo=timezone.utc)
    return (notice.date() - now.date()).days
