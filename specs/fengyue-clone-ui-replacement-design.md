# Fengyue Clone UI Replacement Design

Updated: 2026-07-03

## Strategy

Migrate the reference UI as a visual system, not as a page replacement. The clone archive is a static prototype with mock data and mock JavaScript, while the current site has richer real features. The safest implementation is:

1. Keep current HTML routes and Alpine controllers.
2. Add clone-style design tokens and component overrides to the existing CSS.
3. Adjust the shared shell renderer in `frontend/app/assets/js/layout.js` to expose clone-like sidebar utility links and theme controls.
4. Update page cache-busters and remove avoidable external Alpine CDN references where local Alpine already exists.
5. Keep page-specific JS untouched unless required by markup compatibility.

## CSS Layers

- `frontend/app/assets/css/app.css`
  - Primary app shell and page component overrides.
  - Warm tokens mapped onto existing `xy-*` and `app-*` variables.
  - Overrides for cards, toolbar, segmented controls, chat, create editor, detail, list/form panels, bottom nav, and responsive behavior.
- `frontend/assets/css/custom.css`
  - Public home, dashboard, admin, and shared `xy-*` components.
  - Warm tokens mapped onto old `xy-*` helpers so Tailwind-heavy pages inherit the new look.

## Route Mapping

- Clone `index.html` -> existing `/app/index.html` and `/app/explore.html` visual style only.
- Clone `detail.html` -> existing `/app/character.html` component styling.
- Clone `chat.html` -> existing `/app/chat.html` visual styling while preserving current chat controls and sandbox renderer.
- Clone `create.html` -> existing `/app/create.html` editor styling while preserving advanced fields.
- Clone `login.html/register.html` -> existing `/app/login.html` and dashboard auth panels.
- Clone `recharge.html/checkin.html/gift.html` -> existing `/app/rewards.html` and `/dashboard.html` credits/deposit styling.

## Data And State

- Real role data still comes from `/go/api/explore/search`.
- Details still come from `/console/api/apps/{id}`.
- Chat still uses `/console/api/web/chat/stream` and related conversation/message/memory APIs.
- Credits still use `/console/api/user/credits`, `/console/api/web/deposit-meta`, `/console/api/web/rewards/daily`, and `/console/api/web/redeem-code`.
- Admin data still uses existing `/admin/api/*`.

## Verification Plan

- Syntax:
  - `node --check` for touched JS.
  - `D:\Anconda3\python.exe -m py_compile` for deploy/verification helper scripts if edited.
- Browser:
  - Local or live screenshots for `/`, `/app/`, `/app/login.html`, `/app/character.html`, `/app/chat.html`, `/app/create.html`, `/app/rewards.html`, `/app/me.html`, and `/admin.html`.
  - Check console/page errors.
- Deployment:
  - `D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`
  - SSH health/service check and public `/health`.

## Risk Controls

- Prefer CSS overrides instead of HTML rewrites.
- Do not touch backend unless UI verification reveals a real API compatibility issue.
- Do not remove Tavo sandbox restrictions or CSP.
- Keep all temporary screenshots under `output/playwright/`.
