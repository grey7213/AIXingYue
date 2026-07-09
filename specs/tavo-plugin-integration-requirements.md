# Tavo Plugin Integration Requirements

## Goal

Add Tavo `.tpg` plugin package import and management to AI星月 Web/admin.

## Scope

- Admin can upload `.tpg` or `.zip` plugin packages.
- Backend validates package structure and root `manifest.json`.
- Backend stores the original package and parsed manifest/contributions.
- Admin can list, inspect, enable/disable, and delete imported plugins.
- Web runtime can read enabled plugin contributions through a safe endpoint.

## Safety Boundary

- Do not execute plugin `actions.js` on the public site.
- Do not expose account tokens, main DOM, localStorage, backend admin APIs, or arbitrary file/network access to plugin code.
- HTML fragments are treated as data only and must still render through the existing sandbox/advanced-rendering path.
- MCP is not enabled server-side unless a real local Tavo MCP endpoint and token are provided and an explicit safe use case exists.

## Acceptance

- Valid `.tpg` with `manifest.json` imports successfully.
- Invalid zip, missing manifest, unsafe paths, or missing required manifest fields are rejected.
- Admin page shows plugin metadata, features, enabled status, and raw manifest.
- Enabled plugins appear in `/console/api/web/tavo-plugins/runtime-contributions`; disabled plugins do not.
- Python and frontend syntax checks pass.
