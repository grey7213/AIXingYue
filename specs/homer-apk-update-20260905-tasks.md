# Tasks

- [x] Inspect local/remote baseline and confirm contributor CI success.
- [x] Three-way patch dry-run and server integration dry-run succeed.
- [x] Review/integrate contributor code; no blocking defect found. PR #5 merged as `30c9918d63ce67023f5e940281c5eb87fdb6114f`.
- [x] Add update entry and compatible publication metadata/tooling.
- [x] Run notification, conversation, browser and APK regression checks.
- [ ] Back up production, deploy exact verified files, and verify services/API/resources.
- [ ] Publish official signed APK and GitHub Release; verify hashes and upgrade behavior. Existing APK patch key is empty; no live data-patch channel is configured.
- [ ] Commit/push and update navigation/pitfalls with actual results.

## Verified before deployment
- Contributor export tests: 2 passed; notification route/validation/permissions passed; 1440×900 and 390×844 notification/admin/browser regression passed with no console errors or failed requests.
- Conversation/cache/SSE regression passed at both viewports. Native update entry passed 8 combinations of viewport/page/native presence.
- Android: 32 unit tests, lint/build, 111 frontend files / 1117 asset entries, and 6 API 33 instrumentation tests passed.
- Isolated `.updateaudit` application: 10 end-to-end cases passed, including wrong hash/package/signer, truncation, bad origin/service failure, cancellation, permission denial/resume and real Android installation from 269 to 270. Cookie, account, localStorage sentinel and conversation preserved; firstInstallTime unchanged.
- Production preflight: backend and API source match local baseline after newline normalization. Production chat.js was missing the previously committed conversation-switch shell; the integrated file restores it with PR #5's race guards.
- Production backup: `/root/homer-apk-update-20260905-131548`, SQLite 2,561,605,632 bytes, `quick_check=ok`. Backend, release metadata and Nginx config also copied into the private backup directory. Services remained active.
- Release channel fixes: same versionCode with different APK bytes is rejected, immutable filenames cannot be replaced, canonical copy uses atomic rename, and release.json gets no-cache. Snapshot backup filenames include a remote-path hash to avoid collisions between different index.html files.
