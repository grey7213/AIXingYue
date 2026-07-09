# Tavo Plugin Integration Design

## Backend

- New SQLite table `tavo_plugins`.
- Package files saved under `MEDIA_DIR/tavo-plugins/packages/<sha>.tpg`.
- `manifest.json` fields are normalized into summary columns and JSON payload columns.
- Admin APIs:
  - `GET /admin/api/tavo-plugins`
  - `POST /admin/api/tavo-plugins/import`
  - `POST /admin/api/tavo-plugins/{id}/toggle`
  - `POST /admin/api/tavo-plugins/{id}/delete`
- User/Web API:
  - `GET /console/api/web/tavo-plugins/runtime-contributions`

## Validation

- Accept only zip-formatted `.tpg` or `.zip` packages.
- Reject absolute paths, `..`, empty path segments, and backslashes.
- Limit package size, file count, and total uncompressed size.
- Require manifest object with `id`, `name`, and `version`.
- Preserve unknown manifest fields for forward compatibility.

## Frontend

- Add an admin tab "Tavo 插件".
- Use file input to read `.tpg/.zip` as data URL.
- Show plugin list, feature badges, enabled toggle, raw manifest preview, and delete action.

## MCP Decision

The public website should not become a remote-control bridge for a user's local Tavo instance. MCP stays out of the production server for now because it needs local Tavo foreground/small-window runtime plus Bearer token and exposes high-risk write tools. The reusable piece we can safely carry over is plugin package validation/storage and selected runtime contribution metadata.
