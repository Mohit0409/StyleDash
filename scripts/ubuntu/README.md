# Vibe4You Ubuntu Production Operations

This directory preserves Ubuntu-specific operational scripts separately from the legacy Android/Termux scripts.

## Baseline provenance

backup-styledash-data was copied byte-for-byte from the deployed Ubuntu production host on 2026-10-01 after two fully verified 801-file backups completed successfully to both off-device destinations.

Production path: /opt/vibe4you-production/bin/backup-styledash-data

Baseline SHA-256: 41f64f6144884bc0fe7ba6a72a14d77a6e952bac07bba67eda0457f8b67a809f

Do not overwrite the deployed production copy directly from this repository. Any future deployment must use a reviewed release procedure, a rollback copy, and post-deployment backup verification.

The legacy scripts/termux/backup-styledash-data remains separate because its filesystem paths and runtime assumptions are different.
