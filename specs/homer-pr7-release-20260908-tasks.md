# Tasks

- [x] Inspect project instructions, live PR/checks, current release and clean workspaces.
- [x] Fetch PR, create isolated native/web worktrees and apply the patch against current main.
- [ ] Review all 52 embedded files; reproduce and repair material regressions.
- [ ] Verify browser behavior at desktop/mobile widths and existing conversation flows.
- [ ] Prepare 1.15.1 (271), pass unit/lint/build/assets and signing checks.
- [ ] Validate updater scenarios and actual official APK upgrade preserving data.
- [ ] Update/review PR head, wait for successful CI, merge and push verified source/baseline.
- [ ] Back up targeted production files, deploy and publish website plus GitHub APK release.
- [ ] Independently verify public artifacts, update flow and health; record final evidence.

## Initial findings
- PR description says only community entrances are hidden, while the embedded patch also deletes group chat, replaces shared dialogs/selects, changes model management and adds chat appearance/tools. All require review before merge.
- In-app APK updating already exists in official 1.15.0; this release must prove that path still works, rather than add a second updater.

Evidence belongs under `output/pr7-release-20260908/` and is not committed as generated files.
