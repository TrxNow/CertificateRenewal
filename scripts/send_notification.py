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


def _smtp_send(msg: EmailMessage) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    from_address = os.environ.get("SMTP_FROM", smtp_user)
    msg["From"] = from_address

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        if smtp_port == 587:
            server.starttls(context=context)
            server.ehlo()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


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

Domain: {domain}
Planned renewal notice date (UTC): {renewal_notice_on}
Certificate expiration (UTC): {expires_on}

You will receive a separate renewal email on the planned renewal notice date when the automation runs certbot renew.

— Certificate Renewal automation
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
) -> None:
    subject = f"[Certificate] {client_name}: new certificate issued"
    body = f"""Hello,

The Let's Encrypt certificate for {client_name} ({domain}) was renewed. The public certificate files are attached so they can be sent to AT&T.

Domain: {domain}
Renewal notice date (UTC): {renewal_notice_on}
New certificate expiration (UTC): {expires_on}

Attached:
- fullchain.pem — certificate plus chain (send this to AT&T)
- cert.pem — leaf certificate only
- chain.pem — intermediate chain only

The private key is not attached. Do not email the private key.

— Certificate Renewal automation
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)
    for path in attachments:
        if path.name.lower() == "privkey.pem":
            raise SystemExit("refusing to attach private key")
        filename = f"{path.parent.name}-{path.name}"
        msg.add_attachment(
            path.read_bytes(),
            maintype="application",
            subtype="x-pem-file",
            filename=filename,
        )
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

This is the automated renewal notice for {client_name}. The certificate renewal job is running certbot renew today. If a new certificate is issued, you will receive a follow-up email with the public certificate files attached to send to AT&T.

Domain: {domain}
Renewal notice date (UTC): {renewal_notice_on}
Certificate expiration (UTC): {expires_on}

— Certificate Renewal automation
"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(body)
    _smtp_send(msg)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--expires-on", required=True)
    parser.add_argument("--renewal-notice-on", required=True)
    parser.add_argument("--to", action="append", required=True, dest="recipients")
    parser.add_argument(
        "--kind",
        choices=("reminder", "renewal", "issued"),
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
    args = parser.parse_args()

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
