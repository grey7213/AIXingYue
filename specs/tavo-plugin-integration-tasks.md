# Tavo Plugin Integration Tasks

| ID | Task | Status | Verification |
|----|------|--------|--------------|
| TP1 | Write requirements/design/tasks SPEC | Done | This file plus requirements/design docs |
| TP2 | Add backend `.tpg` package validation and storage | Done | `D:\Anconda3\python.exe .\output\verify_tavo_plugin_local.py` returned `imported/runtime_fragment/invalid_rejected/deleted=true` |
| TP3 | Add admin and runtime plugin APIs | Done | Local Store verification covered import/list/toggle/runtime/delete |
| TP4 | Add admin UI for upload/manage/enable/delete | Done | `node --check` passed; browser verification imported and enabled `Codex Browser Plugin`, console error count 0, screenshot `output/playwright/admin-tavo-plugin-local.png`; deployed admin cache-buster `20260710-tavo-plugin` verified online |
| TP5 | Verify and document MCP decision | Done | Real 7347 endpoint absent; no production MCP bridge. Only safe plugin import/runtime contribution subset added |

## 2026-07-10 Verification

- Local syntax: `D:\Anconda3\python.exe -m py_compile` for backend and verification scripts passed.
- Frontend syntax: `node --check` for `admin-app.js`, `api.js`, `app-core.js`, and `chat.js` passed.
- Local backend: `output\verify_tavo_plugin_local.py` returned `imported=true`, `runtime_fragment=true`, `invalid_rejected=true`, and `deleted=true`.
- Local browser: `output\verify_tavo_plugin_browser.py` rendered the admin Tavo plugin tab, imported and enabled a test `.tpg`, captured `output\playwright\admin-tavo-plugin-local.png`, and saw `console_error_count=0`.
- Live deploy: `deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` succeeded; backend and Nginx are active, public `/health` returns `OK`, and `CONTENT_MODE=local_only`.
- Live API: `output\verify_tavo_plugin_remote.py` returned `admin_cache_buster=true`, `chat_cache_buster=true`, `imported=true`, `enabled=true`, `runtime_fragment=true`, and `deleted=true`.
