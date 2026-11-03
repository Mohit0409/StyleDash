# Vibe4You staging isolation preflight

This is a **read-only, offline configuration check**, not a deployment command or runtime security certification.

The check accepts a JSON snapshot containing *sanitized* systemd service properties and an allowlist of non-secret staging mode flags. It does not connect to the server, execute systemctl, inspect customer data, access credentials or install a service override.

Example usage:

    python qa/staging_isolation_gate.py --snapshot safe_snapshot.json

Only include the following snapshot fields:

- staging: ActiveState, User, ProtectSystem, NoNewPrivileges, PrivateTmp, ProtectHome, ReadWritePaths, InaccessiblePaths.
- production: User.
- settings: RAZORPAY_MODE, STYLEDASH_ORDERING_ENABLED, STYLEDASH_NTFY_ENABLED, STYLEDASH_NTFY_BACKGROUND, STYLEDASH_ENABLE_TEST_PRODUCT.
- paths: existence boolean and the isolated scope for STYLEDASH_DATABASE_PATH, STYLEDASH_DATA_DIR, STYLEDASH_CATALOG_PATH and STYLEDASH_SETTINGS_PATH. Never paste secret values or credentials into snapshots.

The preflight requires staging to be active, using strict system protection, no new privileges, private temp files, protected home directories, staging-only writable paths and staging-scoped data paths. It also requires test payments, disabled ordering and notification side effects, and explicit InaccessiblePaths for production data, backup, application and configuration directories.

These four directories are protected:

    /var/lib/vibe4you-production
    /var/backups/vibe4you-production
    /opt/vibe4you-production
    /etc/vibe4you-production

The current 3 November 2026 staging configuration was validated offline and **failed** the check only because InaccessiblePaths was empty. A locally **simulated**, unapplied staging-only InaccessiblePaths override passed this configuration-level check. Neither result proves actual mount namespace isolation or protects against the remaining shared Linux UID/process access.

**Release blockers outside this preflight:** staging-only root-authorized drop-in/restart and rollback, runtime verification that protected production directories cannot be read from staging, a separate staging system user/group and permission audit, real authentication/payment/GST tests and production-equivalent fixtures.

Do not treat a green result as permission to deploy production code. The override and deployment still require owner approval and a guarded release procedure.
