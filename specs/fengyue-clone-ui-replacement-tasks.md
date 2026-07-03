# Fengyue Clone UI Replacement Tasks

Updated: 2026-07-03

| ID | Task | Status | Verification |
|----|------|--------|--------------|
| FC1 | Back up current project to GitHub before UI work | Done | Commit `c747f41`, pushed to `https://github.com/grey7213/AIXingYue.git` on `main` |
| FC2 | Inspect clone archive and current frontend architecture | Done | `fengyue-clone.zip` extracted to `output/ui-clone-source/fengyue-clone/`; CSS and key HTML pages reviewed |
| FC3 | Add replacement requirements/design/tasks SPEC | Done | This SPEC set |
| FC4 | Apply clone visual system to app CSS and shared shell | Done | `node --check` passed for touched app JS; screenshots `output/playwright/fengyue-ui-app-home.png`, `fengyue-ui-chat.png`, `fengyue-ui-create.png` |
| FC5 | Apply clone visual system to public/dashboard/admin shared CSS | Done | Screenshots `output/playwright/fengyue-ui-home.png`, `fengyue-ui-dashboard.png`, `fengyue-ui-admin.png` |
| FC6 | Verify representative pages online | Done | `D:\Anconda3\python.exe .\output\verify_fengyue_clone_ui_browser.py` returned `console_error_count=0`, `page_error_count=0`; verified `/`, `/app/`, login, detail, chat, create, rewards, me, group chat, dashboard, admin, and mobile `/app/` |
| FC7 | Deploy frontend/backend-only update | Done | `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`; service and Nginx active, public `/health` OK, `CONTENT_MODE=local_only`, live HTML references `20260703-fengyue-ui2` |
| FC8 | Commit UI replacement and push GitHub | Done | Commit `3cf17d4` prepared after deployment verification; pushed to GitHub after amend |

## Notes

- The clone package provides visual reference only; its static mock data and fake interactions are not imported.
- Existing feature behavior is the source of truth.

## 2026-07-03 Verification Record

- Backup before UI replacement: commit `c747f41`, pushed to `https://github.com/grey7213/AIXingYue.git` on `main`.
- Syntax verification: `node --check` passed for `layout.js`, `chat.js`, `create.js`, `explore.js`, `group-chat.js`, `hub-pages.js`, `login.js`, `me.js`, `my-apps.js`, and `admin-app.js`.
- Browser verification: `output/verify_fengyue_clone_ui_browser.py` captured screenshots under `output/playwright/fengyue-ui-*.png`; live warm theme background was `rgb(243, 237, 227)`; real explore returned 12 role cards; console/page errors were both 0.
- Deployment verification: `ai-fengyue-backend.service` and `nginx` were `active`; local `/health` and public `https://patcher.villainy.top/health` returned `OK`; backend env stayed `CONTENT_MODE=local_only`.
