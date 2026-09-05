# Tasks

- [x] Inspect local/remote baseline and confirm contributor CI success.
- [x] Three-way patch dry-run and server integration dry-run succeed.
- [x] Review/integrate contributor code; no blocking defect found. PR #5 merged as `30c9918d63ce67023f5e940281c5eb87fdb6114f`.
- [x] Add update entry and compatible publication metadata/tooling.
- [x] Run notification, conversation, browser and APK regression checks.
- [x] Back up production, deploy exact verified files, and verify services/API/resources.
- [x] Publish official signed APK and GitHub Release; verify hashes and upgrade behavior. Existing APK patch key is empty; no live data-patch channel is configured.
- [x] Commit/push implementation and update navigation/pitfalls with actual results.

## Verified before deployment
- Contributor export tests: 2 passed; notification route/validation/permissions passed; 1440×900 and 390×844 notification/admin/browser regression passed with no console errors or failed requests.
- Conversation/cache/SSE regression passed at both viewports. Native update entry passed 8 combinations of viewport/page/native presence.
- Android: 32 unit tests, lint/build, 111 frontend files / 1117 asset entries, and 6 API 33 instrumentation tests passed.
- Isolated `.updateaudit` application: 10 end-to-end cases passed, including wrong hash/package/signer, truncation, bad origin/service failure, cancellation, permission denial/resume and real Android installation from 269 to 270. Cookie, account, localStorage sentinel and conversation preserved; firstInstallTime unchanged.
- Production preflight: backend and API source match local baseline after newline normalization. Production chat.js was missing the previously committed conversation-switch shell; the integrated file restores it with PR #5's race guards.
- Production backup: `/root/homer-apk-update-20260905-131548`, SQLite 2,561,605,632 bytes, `quick_check=ok`. Backend, release metadata and Nginx config also copied into the private backup directory. Services remained active.
- Release channel fixes: same versionCode with different APK bytes is rejected, immutable filenames cannot be replaced, canonical copy uses atomic rename, and release.json gets no-cache. Snapshot backup filenames include a remote-path hash to avoid collisions between different index.html files.

## Published result
- Native implementation: `grey7213/homer-android` main `d54f65c0bd5550c8d709ec04d43dfa3610968d2f` (PR #6), with PR #5 retained as `30c9918d63ce67023f5e940281c5eb87fdb6114f`. Both PR build checks and the implementation's main build passed.
- Web/backend implementation: `520897d865db`; pinned web snapshot: `736853e86477` (fast-forward publication, previous snapshot retained).
- Version: **1.15.0 (270)**, package `org.nebula.horizon.composeai`, 42,264,908 bytes.
- SHA-256: `b572854e05c3fbbf6022e0f67904b71ba4eefc840896a7e8ab780244b634de17`.
- Website: https://patcher.villainy.top/download/ai-xingyue-latest.apk ; immutable: `/download/homer-android-1.15.0-270-release.apk`. Both complete public downloads matched the signed local artifact.
- GitHub: https://github.com/grey7213/homer-android-apk/releases/tag/release-1.15.0-270 ; public/latest/stable verified, APK digest and checksum attachment match.
- 45 production files uploaded and individually hash-verified; backend `NRestarts=0`, backend/dialogue/Nginx active, internal/public health OK, notification table empty and anonymous writes denied. No public test announcement created.
- Production login pages at 1440/390 had no console/page/HTTP errors. New entry/module hashes match local; public site copy is v1.15.0; release.json is JSON/no-cache; retired open-source page remains 404.
- Official existing APK 269 → signed 270 installed without uninstall: `firstInstallTime=2026-09-01 08:36:29` unchanged, cold Activity launch 1013 ms (not full dialogue-ready time), no fatal exception. Its actual native update action against production displayed “当前版本 1.15.0 / 已是最新版本”.
- Isolated emulator applications and port forwards were removed after testing. Production database was never used for fixture accounts or notices. Conversation browser tests used isolated API/runtime fixtures; no paid production model generation was performed.
- Local evidence and APK: `output/apk-update-20260905/final-release-verification.json`, `official-upgrade-result.json`, `device-update-results.json`, and `output/homer-release/homer-1.15.0-270-release-signed.apk`.
- Existing versions need one manual installation of 1.15.0 to gain the native updater; later official website releases are discoverable and installable inside the app with Android confirmation.
