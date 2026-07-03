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
| FC8 | Commit UI replacement and push GitHub | Done | UI replacement commit `4b1cb09` pushed to GitHub after deployment verification |
| FC9 | Refine `/app/` home to match clone search and recommendation layout | Done | Removed the old right-top search input, added clone-style full-width search row and icon tools, split real cards into `官方每周推荐` and `为你推荐`; live cache-buster `20260703-fengyue-home3`; `verify_home_clone_search_browser.py` passed with `topbarInputs=0`, `homeSearchInputs=1`, `featureCards=2`, `recommendCards=10`, no `搜索角色`, no overlap, and zero browser errors |

## Notes

- The clone package provides visual reference only; its static mock data and fake interactions are not imported.
- Existing feature behavior is the source of truth.

## 2026-07-03 Verification Record

- Backup before UI replacement: commit `c747f41`, pushed to `https://github.com/grey7213/AIXingYue.git` on `main`.
- Syntax verification: `node --check` passed for `layout.js`, `chat.js`, `create.js`, `explore.js`, `group-chat.js`, `hub-pages.js`, `login.js`, `me.js`, `my-apps.js`, and `admin-app.js`.
- Browser verification: `output/verify_fengyue_clone_ui_browser.py` captured screenshots under `output/playwright/fengyue-ui-*.png`; live warm theme background was `rgb(243, 237, 227)`; real explore returned 12 role cards; console/page errors were both 0.
- Deployment verification: `ai-fengyue-backend.service` and `nginx` were `active`; local `/health` and public `https://patcher.villainy.top/health` returned `OK`; backend env stayed `CONTENT_MODE=local_only`.

## 2026-07-03 Home Search Refinement Record

- Implemented the screenshot-driven `/app/` home refinement after the user reported the right-top search box conflicted with the role search.
- Changed `frontend/app/index.html` so the old topbar input is gone; search is now a single clone-style `home-search-row` with placeholder `搜索关键词/作者/标签`, search/no-image/theme/filter icon controls, and the existing `searchKeyword -> loadList(true)` behavior.
- Changed `frontend/app/assets/js/explore.js` so the first two real cards render as `官方每周推荐` and the remaining real cards render under `为你推荐`; no mock clone data is imported.
- Changed `frontend/app/assets/css/app.css` to style the new search row, two featured cards, section titles, and responsive mobile layout using the existing warm clone tokens.
- Verification:
  - `node --check` passed for all app JS files.
  - `git diff --check` passed.
  - Deployed with `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`.
  - Independent health checks: `ai-fengyue-backend.service` active, `nginx` active, local `/health` OK, public `/health` OK, and `CONTENT_MODE=local_only`.
  - `D:\Anconda3\python.exe .\output\verify_fengyue_clone_ui_browser.py` returned `console_error_count=0` and `page_error_count=0`.
  - `D:\Anconda3\python.exe .\output\verify_home_clone_search_browser.py` returned `topbarInputs=0`, `homeSearchInputs=1`, placeholder `搜索关键词/作者/标签`, `featureCards=2`, `recommendCards=10`, `hasOldSearchRoleText=false`, `searchOverlapsToolbar=false`, and zero browser errors.
  - Screenshot: `output/playwright/fengyue-home-search-fix.png`.
