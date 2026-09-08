# PR #7 review and APK release

## Goal
Review `grey7213/homer-android#7` at `8e0a2b2f8b59489763703f0a28848a22b34fe0b7`, repair confirmed regressions, merge the reviewed contribution, and publish an official APK that users can upgrade from inside Homer.

## Scope and acceptance
- Inspect the complete embedded web patch, including its 52 actual files; a successful Android build alone does not establish browser behavior.
- Hide the ordinary community entry points as requested by the contribution. Preserve existing account, conversation, group chat, creator, model administration, and update functionality.
- Keep the native updater already released in 1.15.0. Verify automatic/manual checks, download, integrity/package/signature validation, permission handling and the system installer with the new official release.
- Preserve package `org.nebula.horizon.composeai`, its existing certificate, and user data; increase versionCode above the live 270. Proposed release: 1.15.1 (271).
- Test actual integrated web files at desktop and 390px mobile sizes, Android unit/lint/build/assets, emulator behavior, and an in-place update from 1.15.0.
- Publish source, a signed immutable APK, website release metadata/checksum and GitHub Release; independently verify public downloads and service health.

## Non-goals
Reimplementing the existing updater, enabling new community services, changing credentials or billing, deleting group chats, redesigning unrelated pages, or silently installing APKs.
