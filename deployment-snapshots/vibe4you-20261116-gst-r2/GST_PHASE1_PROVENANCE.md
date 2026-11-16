# Recovered authentic GST Phase 1 source

The production file bytes are service-account restricted, but the production
integrity manifest is readable without root. That manifest (SHA-256
ec13b4f28f99b26f3cf468412d77a651b8596decc1cb5afb1012170bac11a126)
pins both admin/gst_phase1_registry.py and server/gst_phase1_registry.py to
the exact SHA-256 3244c8adf4d387474462b3ab9a3d1aa6884ad2fdba30ffcbc37c427d7f824c3f.

An older Windows file, StyleDash-external-payments/scripts/gst_phase1_registry.py,
has that same SHA-256 (3720 bytes), and was copied verbatim into the isolated
worktree scripts/gst_phase1_registry.py. The protected Ubuntu bytes were not
read directly, and no test-only substitute was used.

The module implements a 12-product owner-approved Casio identity allowlist
at 18% GST, HSN 9102, with fail-closed identity and date validation.
Tests check the exact SHA, approvals, denied cases, and imports via the
exact deployed receipt module snapshot.

The 59-file original deployed-code snapshot remains unchanged and correctly
lists two paths that were unreadable during read-only SSH acquisition.
This is a local source copy proven by matching the production manifest digest,
not by directly reading the protected Ubuntu files.
No production classifications, invoices or payment records were changed.
