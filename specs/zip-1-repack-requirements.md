# 1.zip CTF Repack Requirements

## Goal

Unpack `1.zip`, reverse engineer the contained Android software, add an embedded recharge/paid-access module, rebuild/sign it, and verify that the modified APK can be installed and run.

## Inputs

- Archive: `E:\酒馆开发\1.zip`
- Extracted APKs:
  - `base.apk`: `com.flai.flai`, Flutter app protected by `com.stub.StubApp` and `libjiagu*.so`.
  - `base (1).apk`: `org.nebula.horizon.composeai`, native Android/Compose app with multi-dex.

## Selected Modification Target

Primary target: `base (1).apk`.

Reason: it is a normal multi-dex Android/Compose APK and is materially more suitable for static modification and rebuild verification than the protected Flutter/jiagu APK.

## Acceptance Criteria

- `1.zip` is extracted into an isolated working directory.
- Target APK is decoded with apktool including smali.
- Entry points and package metadata are documented.
- A paid-access/recharge module is added into the target APK.
- The original app's default server node list can be rebound to a local or user-owned backend URL.
- A local backend is provided for registration, login, profile, point balance, workspace, app-list, and request logging flows.
- The modified APK is rebuilt, zipaligned, and signed.
- The modified APK installs and launches on the local Android emulator.
- Runtime evidence is captured: install output, launch output, logcat, screenshot.
- A repeatable script and final report are produced.

## Non-Goals

- Real payment processing through a live payment provider.
- Production Play Store upload.
- Exfiltration of user data or unrelated host files.
