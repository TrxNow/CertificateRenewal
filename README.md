# Certificate Renewal

Runs **`certbot renew` for every client** in `config/clients.yaml` and stores certbot data in git.

**Email sequence** (based on live cert expiry and `renewal_lead_days`, default **30**):

| When | Email |
|------|--------|
| 37 days before expiry (30+7) | Reminder: renewal notice in **7** days |
| 33 days before expiry | Reminder: renewal notice in **3** days |
| 31 days before expiry | Reminder: renewal notice in **1** day |
| 30 days before expiry | **Renewal notice** (automation runs certbot that day) |

## Add a client

1. **`config/clients.yaml`**

```yaml
clients:
  - id: att
    name: ATT
    domain: www.example.com
    notify_emails:
      - you@example.com
```

2. **Import certbot files** from your PC into `data/letsencrypt/<id>/` (see `data/letsencrypt/README.md`). On Windows, copy `C:\Certbot` → `config/`, `C:\Certbot\lib` → `work/`, `C:\Certbot\log` → `logs/`.

3. Commit and push.

Repeat for each client (`id` must match the folder name under `data/letsencrypt/`).

## What runs in GitHub Actions

Daily (12:00 UTC):

1. For **each** client → check live `domain` expiry → email if **7, 3, or 1** days left.
2. For **each** client → `certbot renew` (Let's Encrypt only issues when renewal is due; otherwise certbot exits successfully).
3. Commit any changes under `data/letsencrypt/`.

**Manual:** Actions → **Certificate renewal** → Run workflow. Enable **dry_run** for `certbot renew --dry-run` on all clients (no email, no commit).

## Secrets

| Secret | Purpose |
|--------|---------|
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | Alert emails |
| `SMTP_FROM` | Optional |
