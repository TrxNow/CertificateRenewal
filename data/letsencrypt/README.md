# Certbot data per client

```
data/letsencrypt/<client-id>/
  config/   ← C:\Certbot\ (except lib, log) on Windows
  work/     ← C:\Certbot\lib
  logs/     ← C:\Certbot\log
```

`<client-id>` must match `id` in `config/clients.yaml`.

Import once from the PC where `certbot renew` works, then commit. The workflow updates these folders after each renewal.

**Private keys live here — keep the repo private.**
