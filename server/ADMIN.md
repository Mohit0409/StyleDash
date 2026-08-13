# StyleDash local administrator service

The administrator service is a separate Python listener bound only to
`127.0.0.1:8081`. It is not part of the customer Vite build, is not routed by
ngrok, and uses separate `admin_users`, `admin_sessions`, challenge, recovery,
and audit tables. Customer cookies cannot authenticate it.

## First administrator — manual stop

No default administrator is created. From an SSH session on the phone, run:

```bash
~/bin/styledash-create-admin
```

The command asks interactively for the username and password, prints the TOTP
setup URI only in that local terminal, requires a valid authenticator code
before committing, then prints one-use recovery codes once. Never paste the
password, setup URI, TOTP secret, or recovery codes into chat or a shell
command.

## Access from the existing Windows laptop

Keep this SSH process running:

```powershell
ssh -i C:\Users\91896\.ssh\codex_styledash_termux -p 8022 -L 8081:127.0.0.1:8081 u0_a324@192.168.1.7
```

Then open `http://127.0.0.1:8081/` on the laptop. The service deliberately uses
a non-`Secure` admin cookie because this endpoint is plain HTTP localhost. The
cookie is still `HttpOnly`, `SameSite=Strict`, path-scoped, short-lived, stored
hashed in SQLite, protected by separate CSRF, and usable only through the
loopback listener/SSH tunnel. Do not create an ngrok or Cloudflare route to
port 8081.

## Backups and maintenance

Run an online SQLite backup, payment-state copy, integrity verification, and
14-copy retention:

```bash
~/bin/backup-styledash-data
```

Backups are private under `~/.local/share/styledash/backups/` and deliberately
exclude `secrets.env`. To copy a selected backup over encrypted SSH transport
to a protected, non-cloud-synced laptop folder:

```powershell
scp -i C:\Users\91896\.ssh\codex_styledash_termux -P 8022 -r u0_a324@192.168.1.7:/data/data/com.termux/files/home/.local/share/styledash/backups/TIMESTAMP C:\StyleDash-Private-Backups\
```

Losing `styledash.db` loses account/session/profile/vendor/admin/audit data.
Losing the payment JSON loses payment reconciliation and authoritative stock.
Losing `STYLEDASH_TOTP_ENCRYPTION_KEY` makes existing encrypted administrator
TOTP secrets unusable and invalidates CSRF derivation; it is not included in
data backups, so keep a separate protected recovery copy.

Customer self-service password-reset email is not enabled because no approved
SMTP/provider configuration exists. This remains a launch limitation requiring
a documented support decision; do not return reset tokens to browsers.
