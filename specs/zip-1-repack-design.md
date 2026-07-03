# 1.zip CTF Repack Design

## Work Directories

- Raw extraction: `reverse-analysis\zip-1-target\raw`
- Decoded protected APK metadata: `reverse-analysis\zip-1-target\decoded-base`
- Decoded primary target: `reverse-analysis\zip-1-target\decoded-base-1-full`
- Output artifacts: `output\zip-1-repack`

## Target Strategy

The primary target, `org.nebula.horizon.composeai`, is modified at the Android bytecode/resource level.

The injected module is implemented as a new Android Activity:

- `org.nebula.horizon.composeai.ctf.RechargeActivity`
- Stores a local entitlement record in `SharedPreferences`.
- Provides visible trial controls:
  - product id
  - current balance
  - paid access state
  - recharge button
  - reset button
- Uses only platform Android APIs to minimize dependency risk.

The manifest is patched so `RechargeActivity` is exported and reachable via a launcher icon. This keeps the original app entrypoint intact while adding an independently testable paid-access module.

## Build Strategy

- Decode with apktool.
- Compile the injected Java Activity with Android Studio JBR `javac`.
- Convert the injected class jar to dex with Android SDK `d8`.
- Add the injected dex to the rebuilt APK as `classes6.dex`.
- Add manifest entry for the second launcher Activity.
- Rebuild with apktool.
- Align with `zipalign`.
- Sign with a generated debug/repack keystore via `apksigner`.
- Verify with `apksigner verify --print-certs`.

Build uses a short ASCII junction path `E:\a` for apktool/aapt2 because the workspace path contains Chinese characters and the original smali tree contains long Compose-generated filenames.

## Runtime Verification

Use local emulator/ADB:

- Install the repacked APK.
- Launch original `MainActivity`.
- Launch injected `RechargeActivity`.
- Capture screenshots and logcat.
- Tap the recharge button and verify persisted state if possible.
# Server Binding Addendum

## Goal

The recharge-only APK still uses the original remote server nodes for the main app data. The new binding layer changes the APK's built-in node list so Retrofit uses a user-controlled backend.

## Patch Point

- `DefaultServerNodes.smali` contains the static `ServerNode` constructors.
- `ServerNodePreferences` emits `selected_node_url`; when no persisted value exists, it falls back to the default node from `DefaultServerNodes`.
- `DynamicApiServiceManager` rebuilds Retrofit from that emitted URL.

## Implementation

- Patch all original `https://.../` node URL constants to a single target URL, defaulting to `http://10.0.2.2:8000/` for Android emulator access to the host machine.
- Keep `android:usesCleartextTraffic="true"` and existing `networkSecurityConfig`, so HTTP local testing works.
- Preserve the injected `RechargeActivity` and `classes6.dex`.
- Generate a distinct output APK: `ai-fengyue-localserver-signed.apk`.

## Local Backend

- `tools/ai_fengyue_local_server.py` is a stdlib Python HTTP API backed by SQLite.
- It logs every request and implements first-pass compatible responses for auth/profile/points/workspace/list endpoints.
- Unknown endpoints return structured JSON fallback, so request logs reveal the next interface to implement.

## Verification

- Static: `DefaultServerNodes.smali` contains only the configured server URL and no original node domains.
- Package: `apksigner verify --verbose --print-certs` passes and `zipalign -c -p -v 4` passes.
- Runtime: clear app data before testing because an older DataStore value may still contain the previous selected node URL.
