# Certbot data per client

```
data/letsencrypt/<client-id>/
  config/   ← /etc/letsencrypt on Linux, or C:\Certbot\ (except lib, log) on Windows
  work/     ← /var/lib/letsencrypt, or C:\Certbot\lib
  logs/     ← /var/log/letsencrypt, or C:\Certbot\log
```

`<client-id>` must match `id` in `config/clients.yaml`.

Import once from the machine where `certbot renew` already works. The Omarchy cron job updates these folders after each renewal.

If the files came from Windows, `scripts/renew_all.py` rewrites `C:\Certbot\...` paths before calling certbot.

**Private keys live here — keep the repo private.**
