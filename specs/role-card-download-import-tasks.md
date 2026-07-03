# 角色卡下载包导入任务

Updated: 2026-07-01

## Requirements

- Source archive: `E:\xd高级动效\角色卡下载.zip`.
- Import every usable SillyTavern/Character Card role card from the archive.
- Do not filter by topic, theme, or content category.
- Preserve role-card extensions, especially Regex and TavernHelper script/rendering metadata.
- Exclude files that are empty shells, script/config/workflow-only payloads, or PNG/JSON files without recognizable role-card metadata.
- Do not destructively modify the original ZIP archive.

## Design

- Build a local import bundle under `output\role-card-download-import\`.
- Parse `.png` Character Card metadata from `tEXt`/`iTXt`/`zTXt` chunks and parse `.json` cards with existing backend card decoders.
- Convert parsed cards through `tools\ai_fengyue_local_server.py` helpers so the import matches the live platform schema.
- Promote `extensions.regex_scripts` and `extensions.TavernHelper_scripts` into top-level `extra_settings.regex_scripts` while keeping the original `extensions`.
- Generate compressed cover images under `output\role-card-download-import\covers\` for usable PNG cards.
- Import records into live SQLite as public official/admin cards with a new batch marker, after a DB backup.

## Tasks

| ID | Task | Status | Verification |
|----|------|--------|--------------|
| RCD1 | Inspect archive format, encryption, candidate counts | Done | ZIP is AES encrypted; password `123` works. Found 3,304 `.png/.json` candidates: 3,093 PNG and 211 JSON. |
| RCD2 | Generate local import bundle and summary | Done | `output\role-card-download-import\import-summary.json`: 2,695 parsed metadata cards, 2,137 usable role cards, 558 empty shells/config-only skipped, 609 no metadata, 970 with promoted regex, 2,027 covers. |
| RCD3 | Upload bundle/covers and import into live DB with backup | Done | Uploaded 319MB bundle and 98MB cover archive to `/tmp`; extracted 2,027 `admin-rcdownload-*.jpg` covers. Remote import backup `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3.bak-role-card-download-20260701-140213`; inserted 2,137, updated 0, skipped 0; admin total 2,255. |
| RCD4 | Verify counts, regex preservation, sample detail, cover, chat, service health | Done | Remote verification returned `expected_found=2137`, `public_found=2137`, `regex_nonempty=970`, `extensions_nonempty=2119`, `world_nonempty=2036`, `empty_imported=0`; sample `admin-rcdownload-d00016f575bee6ca42e1` detail OK, cover HTTP 200, streaming chat `message_end=true`, 24 deltas, points `5000 -> 4950`, cleanup 0. Backend and Nginx active; local/public `/health` OK; `CONTENT_MODE=local_only`; explore total 2,255 with lightweight payload. |
| RCD5 | Record final result in specs/current state | Done | Updated `specs\sillytavern-parity-tasks.md` and `C:\Users\86180\.codex\skills\ai-xingyue-apk-ops\references\current-state.md`. |
