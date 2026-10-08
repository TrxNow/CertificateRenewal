#!/usr/bin/env python3
"""Send certificate reminder or renewal notification email via SMTP."""

from __future__ import annotations

import argparse
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    return value.strip().strip("\"'").strip()


def _smtp_send(msg: EmailMessage) -> None:
    smtp_host = _env("SMTP_HOST")
    smtp_port = int(_env("SMTP_PORT", "587") or "587")
    smtp_user = _env("SMTP_USER")
    smtp_password = _env("SMTP_PASSWORD")
    from_address = _env("SMTP_FROM") or smtp_user
    missing = [
        name
        for name, value in (
            ("SMTP_HOST", smtp_host),
            ("SMTP_USER", smtp_user),
            ("SMTP_PASSWORD", smtp_password),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Email failed: set these in .env (empty values cannot send mail): "
            + ", ".join(missing)
        )
    if not from_address:
        raise SystemExit("Email failed: set SMTP_FROM or SMTP_USER in .env")

    msg["From"] = from_address
    print(f"Sending mail via {smtp_host}:{smtp_port} as {smtp_user}")

    context = ssl.create_default_context()
    if smtp_port == 465:
        server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30, context=context)
    else:
        server = smtplib.SMTP(timeout=30)
        server.connect(smtp_host, smtp_port)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    try:
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            server.close()


def send_reminder_email(
    *,
    to_addresses: Iterable[str],
    client_name: str,
    domain: str,
    days_until_renewal_notice: int,
    renewal_notice_on: str,
    expires_on: str,
) -> None:
    subject = (
        f"[Certificate] {client_name}: renewal notice in {days_until_renewal_notice} day(s)"
    )
    body = f"""Hello,

This is a reminder that the automated certificate renewal notice for {client_name} will be sent in {days_until_renewal_notice} day(s).

Planned renewal notice date (UTC): {renewal_notice_on}
Certificate expiration (UTC): {expires_on}

You will receive a separate email on the planned renewal notice date.

— Certificate Renewal
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)
    _smtp_send(msg)


def send_issued_email(
    *,
    to_addresses: Iterable[str],
    client_name: str,
    domain: str,
    renewal_notice_on: str,
    expires_on: str,
    attachments: Iterable[Path],
    dev_test: bool = False,
) -> None:
    prefix = "[TEST] " if dev_test else ""
    subject = f"{prefix}[Certificate] {client_name}: new certificate issued"
    warning = (
        "THIS IS A TEST MESSAGE. The attached files are a fake self-signed certificate "
        "and should not be installed.\n\n"
        if dev_test
        else ""
    )
    body = f"""Hello,

{warning}Please find the renewed public certificate files attached.

New certificate expiration (UTC): {expires_on}

Attachments:
- fullchain.pem — certificate plus chain (use this file)
- cert.pem — leaf certificate only
- chain.pem — intermediate chain only

The private key is not included.

— Certificate Renewal
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)
    for path in attachments:
        if path.name.lower() == "privkey.pem":
            raise SystemExit("refusing to attach private key")
        filename = path.name
        msg.add_attachment(
            path.read_bytes(),
            maintype="application",
            subtype="x-pem-file",
            filename=filename,
        )
    _smtp_send(msg)


def send_test_email(*, to_addresses: Iterable[str]) -> None:
    subject = "[Certificate] test email"
    body = """Hello,

This is a test from the certificate renewal job. SMTP is working.

You will get reminder and renewal emails only on the scheduled days, and a certificate-attachment email only after certbot issues a new cert.

— Certificate Renewal automation
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)
    _smtp_send(msg)


def send_renewal_email(
    *,
    to_addresses: Iterable[str],
    client_name: str,
    domain: str,
    renewal_notice_on: str,
    expires_on: str,
) -> None:
    subject = f"[Certificate] {client_name}: renewal in progress today"
    body = f"""Hello,

This is the automated renewal notice for {client_name}. Certificate renewal is running today. If a new certificate is issued, you will receive a follow-up email with the public certificate files attached.

Renewal notice date (UTC): {renewal_notice_on}
Certificate expiration (UTC): {expires_on}

— Certificate Renewal
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)
    _smtp_send(msg)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-name")
    parser.add_argument("--domain")
    parser.add_argument("--expires-on")
    parser.add_argument("--renewal-notice-on")
    parser.add_argument("--to", action="append", dest="recipients")
    parser.add_argument(
        "--kind",
        choices=("reminder", "renewal", "issued", "test"),
        required=True,
    )
    parser.add_argument(
        "--days-until-renewal-notice",
        type=int,
        help="Required for reminder emails (7, 3, or 1)",
    )
    parser.add_argument(
        "--attach",
        action="append",
        default=[],
        dest="attachments",
        help="Public certificate PEM to attach (issued emails). Never attach privkey.pem.",
    )
    parser.add_argument(
        "--dev-test",
        action="store_true",
        help="Mark issued email as a fake dev-mode test",
    )
    args = parser.parse_args()
    if not args.recipients:
        raise SystemExit("--to is required")

    if args.kind == "test":
        send_test_email(to_addresses=args.recipients)
        print(f"Sent test email to {', '.join(args.recipients)}")
        return

    missing = [
        name
        for name, value in (
            ("--client-name", args.client_name),
            ("--domain", args.domain),
            ("--expires-on", args.expires_on),
            ("--renewal-notice-on", args.renewal_notice_on),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"{', '.join(missing)} required for {args.kind}")

    if args.kind == "reminder":
        if args.days_until_renewal_notice is None:
            raise SystemExit("--days-until-renewal-notice required for reminder")
        send_reminder_email(
            to_addresses=args.recipients,
            client_name=args.client_name,
            domain=args.domain,
            days_until_renewal_notice=args.days_until_renewal_notice,
            renewal_notice_on=args.renewal_notice_on,
            expires_on=args.expires_on,
        )
        print(
            f"Sent {args.days_until_renewal_notice}-day reminder for {args.domain}"
        )
    elif args.kind == "issued":
        attachments = [Path(p) for p in args.attachments]
        if not attachments:
            raise SystemExit("--attach required for issued email")
        send_issued_email(
            to_addresses=args.recipients,
            client_name=args.client_name,
            domain=args.domain,
            renewal_notice_on=args.renewal_notice_on,
            expires_on=args.expires_on,
            attachments=attachments,
            dev_test=args.dev_test,
        )
        print(f"Sent new certificate for {args.domain} to {', '.join(args.recipients)}")
    else:
        send_renewal_email(
            to_addresses=args.recipients,
            client_name=args.client_name,
            domain=args.domain,
            renewal_notice_on=args.renewal_notice_on,
            expires_on=args.expires_on,
        )
        print(f"Sent renewal notice for {args.domain}")


if __name__ == "__main__":
    main()
