# Fengyue Clone UI Replacement Requirements

Updated: 2026-07-03

## Goal

Use the visual style from `fengyue-clone.zip` as the new Web UI for the current AI星月 / AI风月 site while keeping the existing backend, routes, auth, role cards, chat, credits, admin, and SillyTavern-compatible behavior unchanged.

## Source UI

- Archive: `fengyue-clone.zip`
- Extracted reference: `output/ui-clone-source/fengyue-clone/`
- Main visual traits:
  - Warm paper background, white panels, soft orange accent.
  - Left sidebar with compact nav, user block, secondary links, and utility buttons.
  - Top search/filter row and dense two-column/card-grid browsing.
  - Rounded white role cards with 4:3 covers, concise metadata, tags, and subtle shadows.
  - Full-screen chat with simple white header/tool rows, left conversation list, message bubbles, and rounded input.
  - Auth/recharge/create/detail pages using simple form panels and warm accent buttons.

## Scope

- Replace the visual layer for:
  - Public home page `/`.
  - Web app shell under `/app/`.
  - App pages including explore, detail, chat, create/edit, my roles, profile, rewards, logs, favorites, histories, group chat, image chat, and info.
  - Dashboard and admin console base styling so they no longer look like the old purple star theme.
- Keep all existing routes, API calls, Alpine components, cache keys, localStorage keys, and backend response shapes.
- Keep existing logo files and app branding unless a page needs text-only clone-style branding.
- Preserve Tavo / advanced HTML rendering sandbox security exactly: no same-origin iframe, no parent DOM/token access, no external network from card HTML.

## Non-Goals

- Do not import clone static sample data.
- Do not replace real role lists with hardcoded clone cards.
- Do not rebuild or modify the APK.
- Do not re-enable ordinary-user BYOK/API-key UI.
- Do not change `CONTENT_MODE=local_only`.
- Do not change pricing, credits, registration, or admin permissions.

## Acceptance Criteria

- The live site visually uses the warm clone UI style instead of the old purple/glow style.
- Existing functional smoke paths still work:
  - Login/register form can render and submit.
  - Explore loads real local role cards.
  - Character detail links into chat.
  - Chat retains streaming, model selector, memory panel, advanced render settings, Tavo iframe, quick replies, swipe/regenerate controls, and message actions.
  - Create/edit keeps Prompt Manager, world book, import/export, quick replies, regex, and site model picker.
  - Rewards/deposit retains balance, packages, daily reward, Afdian jump, and redeem-code entry.
  - Admin retains role-card list/edit/bulk edit, model presets, site settings, redeem codes, and stats.
- Browser verification reports zero new console/page errors on representative pages.
- Deployment verifies `ai-fengyue-backend.service`, `nginx`, public `/health`, and `CONTENT_MODE=local_only`.
- A post-replacement Git commit is pushed after verification. The pre-change backup remains at commit `c747f41`.
