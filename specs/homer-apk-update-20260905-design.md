# Integration design

- Source PR head: `508740455ea04296a12a1e72f56041176363fe45`; pinned web base: `b0225ab462945bc3bd9c8537e19e19f932b17a3d`.
- `frontend/` and Homer dialogue bridge patch via `git apply -3`; the initial dry-run merged all files without conflicts.
- `tools/notifications_extension.py` adds a bounded notification table, validation and transactional CRUD; `Handler.route` uses the existing administrator gate. Schema creation must deploy together with the extension module.
- Native updater reuses `/download/release.json` and immutable website APK links; expand release notes metadata without breaking legacy consumers. Android source and prior-art evaluation are documented in the native repository.
- Existing production publisher verifies package, higher versionCode, certificate and downloaded bytes. Retain the prior release, back up changed service/static files and SQLite, and verify services after deployment.
- New static module paths must be in both generated APK assets and signed data patches; advance web-base only after source integration is committed.
