# Tasks

- [x] Inspect project instructions, live PR/checks, current release and clean workspaces.
- [x] Fetch PR, create isolated native/web worktrees and apply the patch against current main.
- [x] Review all 52 embedded files; reproduce and repair material regressions.
- [x] Verify browser behavior at desktop/mobile widths and existing conversation flows.
- [x] Prepare 1.15.1 (271), pass unit/lint/build/assets and signing checks.
- [x] Validate updater scenarios and actual official APK upgrade preserving data.
- [x] Update/review PR head, wait for successful CI, merge and push verified source/baseline.
- [x] Back up targeted production files, deploy and publish website plus GitHub APK release.
- [x] Independently verify public artifacts, update flow and health; record final evidence.

## Initial findings
- PR description says only community entrances are hidden, while the embedded patch also deletes group chat, replaces shared dialogs/selects, changes model management and adds chat appearance/tools. All require review before merge.
- In-app APK updating already exists in official 1.15.0; this release must prove that path still works, rather than add a second updater.

Evidence belongs under `output/pr7-release-20260908/` and is not committed as generated files.

## Completed result
- Corrected PR head `5ccbd82` passed build 34215115916; PR #7 merged as `3d54e8d`. Web source `b794ecc` and web-base `798eeac1209d` are pushed. Main and baseline CI passed (34216004973 / 34216845029).
- Preserved group chat and personal tags; repaired stale-account private-card caches, dark confirmation contrast (heading 1.05 -> 13.91), administrator-only community preview and appearance drafts across conversation changes. New social moderation remains disabled because this PR has no corresponding backend.
- 9 focused browser cases, 8 update-entry combinations and existing cache/SSE regressions passed. Real local backend/SillyTavern at 1440/390px passed generation, hide/collapse persistence, cloud role preservation, selection cancellation and switching protection during an in-flight save.
- Debug/release each passed 32 unit tests; lint and builds passed. APK contains 127 frontend files / 1133 indexed assets. API 33 passed 6 cache/patch tests and 4 real Android Back scenarios.
- 10 updater cases passed, including bad hash, truncation, wrong origin/package/signer, cancellation, permission decline/resume, system installation and preservation of cookie/account/local conversation.
- Official **1.15.1 (271)**: 42,315,512 bytes; SHA-256 `f34a4807f2b1b37e8c97eace2a6079e5449d2cf17738ef90eff6e90d5c178154`; existing package/certificate, v2/v3 and zipalign passed.
- Website: https://patcher.villainy.top/download/homer-android-1.15.1-271-release.apk ; GitHub: https://github.com/grey7213/homer-android-apk/releases/tag/release-1.15.1-271 . Both full website download URLs, GitHub asset digest and checksum match. Feed remains no-cache; public copy is v1.15.1.
- The already installed official 1.15.0 automatically detected 1.15.1 and used the real production download and Android installer to upgrade. Installed APK hash matches, firstInstallTime `2026-09-01 08:36:29` is unchanged, and a subsequent manual check reports the latest version. No official-app uninstall or adb sideload was used for that upgrade.
- Existing production files received root-only backups before 61 targeted uploads; all 61 final hashes independently match. Release metadata restore point: `/root/homer-apk-release-backup-20260908-105424/`. Backend/dialogue/Nginx active, backend NRestarts=0, public health OK, login 1440/390 has no errors/overflow, retired source page remains 404.
- The original publisher's public-read step hit a transient proxy TLS EOF after its remote writes finished; independent direct HTTPS verification subsequently passed. No production model requests, fixture posts or payment operations were made.

Remaining boundary: versions before 1.15.0 without an updater need one manual installation. This release preserves the native update path for subsequent releases; Android always requires the user's installation confirmation.

Final evidence: 58 screenshots/reports/logs were copied into `output/pr7-release-20260908/` and verified with `evidence-sha256.json`. Task-owned audit apps, port forwards and isolated services were removed/stopped; the emulator retains the upgraded official 1.15.1 and was shut down after verification.
