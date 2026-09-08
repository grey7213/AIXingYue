# Integration design

## Verified baseline
- Web/backend main: `80ce932`; Android main: `149e0e9`.
- PR head: `8e0a2b2`; CI build 34133712641 succeeded, but the branch is behind main. Review uses a local merge with current main.
- PR contains two tracked files, one of which expands to 52 web/runtime files (2066 additions, 1192 deletions). The patch is based on `736853e86477` and applies cleanly to current web main.
- Live HTTPS feed on 2026-09-08 returns 1.15.0 (270), JSON with `Cache-Control: no-cache`; existing signing fingerprint ends in `d93f320`.

## Existing implementation and prior art
Reuse the repository's `ApkRelease`, `ApkUpdateManager`, `ApkUpdateController` and AndroidX FileProvider implementation from merged PR #6. Its design was based on Android platform installation APIs and the AppUpdater/XUpdate comparison recorded in `E:/homer-android/specs/in-app-update-20260905/design.md`. Current GitHub source and live release feed were checked in this task. No new updater framework is needed.

## Boundaries
- Worktrees: `E:/homer-web-pr7-20260908` for web integration; `E:/homer-pr7-20260908` for Android/PR integration. Original workspaces remain recoverable.
- Keep contributor patch provenance. Fix confirmed regressions in integrated files, export a corrected patch against its pinned web baseline, and update the contributor PR before merging if maintainers can edit it.
- Public APK uses current verified web assets and current native source. Patch-slot metadata is invalidated on APK version changes; user databases/preferences are retained.
- Targeted production files are backed up before replacement. APK publishing uses the established `publish_homer_apk.py`, preserving immutable version files and atomic canonical replacement.
- Device/browsers use local fixtures for feature writes; public verification uses read-only endpoints. No production test posts, model charges or credential changes.

## Checks
Review group-chat removals, chat actions, confirmation/cancellation, account-scoped storage, admin pricing fields, CSS contrast, update entry points and community preview gating. Record each reproduced failure and its repair before publication.

## Confirmed repair scope
- Browser probes reproduced private-card cache writes under a stale account in My Apps and Workshop. Preserve cached first paint, but establish the authenticated profile before refreshing private data and discard responses after an account change.
- The shared confirmation dialog has dark-theme heading contrast 1.05:1. Inherit the application's semantic foreground/background colors.
- Close an appearance draft when its owner/conversation changes; do not retain a save action for the old scope.
- Restore removed group chat APIs/pages/navigation and the personal tag editor. Keep other reviewed UI changes.
- Community preview must pass the existing administrator endpoint before page initialization. The new social backend is absent from this PR/current backend, so do not expose its moderation tab as a working feature.
- Android Back must dismiss the new web dialogs before navigating. Reuse the contributor's overlay handler and bridge only the fixed, same-origin dialogue iframe.
- Existing message-header/avatar visibility is also hidden in current main's final CSS rules, so do not reinterpret older AGENTS history as a requested visual change.
