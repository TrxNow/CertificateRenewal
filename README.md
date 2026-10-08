# Certificate Renewal

Runs **`certbot renew` for every client** in `config/clients.yaml` on an **Omarchy** (Arch) host via a daily **cron** job.

**Email sequence** (based on live cert expiry and `renewal_lead_days`, default **30**):

| When | Email |
|------|--------|
| 37 days before expiry (30+7) | Reminder: renewal notice in **7** days |
| 33 days before expiry | Reminder: renewal notice in **3** days |
| 31 days before expiry | Reminder: renewal notice in **1** day |
| 30 days before expiry | **Renewal notice** (automation runs certbot that day) |
| After certbot issues a new cert | **New certificate** email with `fullchain.pem`, `cert.pem`, and `chain.pem` attached (no private key) |

## Setup on Omarchy

From the repo root:

```bash
./scripts/install-omarchy.sh
```

That will:

1. Create `.venv` and install Python deps plus `certbot` with pip (no pacman DBs required)
2. Create `.env` from `.env.example` if missing
3. Enable a systemd user timer at 12:00 daily (`certificate-renewal.timer`)

Then:

1. Edit **`.env`** (`DEV_MODE`, SMTP settings)
2. Edit **`config/recipients.txt`** (one email per line)
3. Import certbot files into `data/letsencrypt/<id>/` (see `data/letsencrypt/README.md`)
4. Test: `./scripts/run-renewal.sh --dev`

Logs go to `logs/renewal-YYYY-MM-DD.log`.

**Dev mode** (`DEV_MODE=true` in `.env`, or `--dev`): `certbot renew --dry-run`, then a **fake test certificate** is emailed so you can verify SMTP and attachments. The subject is marked `[TEST]` — do not send those files to AT&T. Set `DEV_MODE=false` for real renewals.

## Add a client

1. **`config/clients.yaml`**

```yaml
clients:
  - id: att
    name: ATT
    domain: www.example.com
```

2. Add notification addresses to **`config/recipients.txt`** (one email per line).
3. **Import certbot files** into `data/letsencrypt/<id>/` (`id` must match the folder name).

Repeat for each client.

## Manual run

```bash
./scripts/run-renewal.sh          # honors DEV_MODE from .env
./scripts/run-renewal.sh --dev    # force dry-run
```

## Secrets

Put these in **`.env`** on the Omarchy host (not in git):

| Variable | Purpose |
|----------|---------|
| `DEV_MODE` | `true` = `--dry-run`, skip email |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Alert emails |
| `SMTP_FROM` | Optional |
