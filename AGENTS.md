# Project Working Notes

## Scope

- Web 平台当前正式品牌为“惑梦（Homer）”；积分展示名为“惑梦币”。历史文件名、服务名、数据库名、接口路径和 APK 标识仍保留旧技术命名以保证兼容，除非用户另行要求迁移。

- Current workspace contains Android APK reverse engineering artifacts for a CTF sandbox target.
- Primary APKs:
  - `base.apk`: `com.flai.flai`, Flutter app protected by `com.stub.StubApp` and `libjiagu*.so`.
  - `base (1).apk`: `org.nebula.horizon.composeai`, native Android/Compose app.

## Tooling

- Local apktool wrapper: `tools\apktool\apktool.bat` verified as apktool `3.0.2`.
- Android Studio E-drive copy is available at `E:\Android\AndroidStudio`; launch with `E:\Android\start-android-studio-e.ps1` so SDK/AVD/Gradle/JAVA environment variables point to E-drive paths.
- E-drive Android paths configured at user environment level:
  - `ANDROID_HOME` / `ANDROID_SDK_ROOT`: `E:\Android\Sdk`
  - `ANDROID_AVD_HOME`: `E:\Android\Avd`
  - `GRADLE_USER_HOME`: `E:\Android\Gradle`
  - `JAVA_HOME`: `E:\Android\AndroidStudio\jbr`
- The E-drive Android Studio copy uses `E:\Android\StudioData` for IDE config/system/plugin/log paths via `E:\Android\AndroidStudio\bin\idea.properties`.
- Android SDK tools found at `C:\Users\86180\AppData\Local\Android\Sdk`:
  - `platform-tools\adb.exe`
  - `build-tools\33.0.2\apksigner.bat`
  - `build-tools\33.0.2\zipalign.exe`
- The old `C:\Users\86180\AppData\Local\Android\Sdk` and `C:\Users\86180\.android\avd` directories were deleted on 2026-06-14 to free C-drive space.
- Current default PATH Java may still be Java 8 in old shells. Use `E:\Android\AndroidStudio\jbr\bin` first on PATH, or launch a new shell after the user-level `JAVA_HOME` update, before running JADX/Gradle.

## Verification Constraints

- `adb devices -l` started adb but listed no connected devices during the 2026-06-14 check.
- Without a connected rooted device/emulator, runtime root/admin control, runtime anti-tamper bypass, install, launch, and Play/App Store style runtime validation can only be prepared as scripts, not proven on-device.

## Codebase Map

- `reverse-analysis/base-apk/unpacked/`: decoded FLAI APK.
- `reverse-analysis/base-apk/unpacked/smali/com/stub/StubApp.smali`: protected Application stub.
- `reverse-analysis/base-apk/unpacked/assets/libjiagu*.so`: protected loader/native hardening libraries.
- `reverse-analysis/base-apk/unpacked/assets/.jgapp`: jiagu marker asset.
- `reverse-analysis/base-apk/unpacked/lib/*/libapp.so`: Flutter/Dart AOT business logic.
- `reverse-analysis/base-1-apk/unpacked/`: decoded Compose APK.
- `specs/`: project requirements, design, and task tracking.
- `tools/ai_fengyue_local_server.py`: AI星月 Web/backend implementation, including `site_settings` admin/public APIs, rewards, credits, role cards, chat, and admin operations.
- `frontend/assets/js/site-settings.js`: public homepage hydrator for admin-managed site copy and links.
- `frontend/app/assets/js/layout.js`: shared Web App shell navigation and admin-managed announcement injection.
- `frontend/admin.html` + `frontend/assets/js/admin-app.js`: admin console, including user/admin authorization, data charts, model presets, role cards, redeem codes, and site operations settings.
- Role cards use `local_apps.id` as the internal primary key referenced by conversations, favorites, likes, comments, group chats, memories, and logs. Public short card numbers such as `0001` live in `local_apps.display_id`; do not rewrite primary IDs to short numbers.

## Artifact Hygiene

- Do not put temporary verification screenshots, one-off data files, browser traces, or throwaway scripts in the project root.
- Put test screenshots under `output/playwright/` or a task-specific `output/<task>/` directory.
- Put one-off verification/import/prune scripts under `output/` if they are short-lived, or `tools/` only when they become reusable project tooling.
- After a task is verified, archive useful temporary artifacts under `output/root-artifact-archive-*` or delete disposable files; keep the project root limited to source APKs, source zips, docs, and stable project files.

## Git Backup Policy

- Every important implementation change, feature change, deployment-affecting fix, or project rule update must be committed to git after verification.
- Push completed commits to `origin/main` when network/auth is available so GitHub remains the recoverable backup.
- Keep commits focused and descriptive; do not include temporary screenshots, one-off scripts, traces, secrets, local tokens, or generated junk unless they are intentionally reusable project artifacts.
- Before committing, check `git status --short` and avoid staging unrelated user changes.

## Reusable Pitfalls

- Symptom: 标签优化 ZIP 的 `tag-overrides.filled.csv` 仍是上一轮结果，直接运行旧回填工具会漏掉文件名中新增的 1767 张标签，并把 318 张 `CLEAR` 卡继续保留。
  Cause: 第三方本轮主要通过 `cards/<display_id>__<标签表达式>[√/✗].json` 改名，未同步更新 filled CSV；同时角色表没有外键，直接删除 CLEAR 卡会让历史会话失联。
  Fix: 2026-07-13 使用 `tools/sync_role_card_filename_tags.py` 校验 Manifest/卡 SHA 后从文件名解析优化标签；CLEAR 卡先审计引用，306 张无功能引用卡物理删除，12 张关联会话的卡保留原 ID 并设为私有隐藏。
  Verify: 8318 张标签更新；公开官方空标签为 0；conversations/messages/favorites 等业务表行数前后不变；live/backup `quick_check=ok`，backend/Nginx active，内外 `/health` OK。

- Symptom: `aifadian_redeem_ops.py generate --count 500` 输出却只有每套餐 200 个。
  Cause: 卡密生成接口/工具将单批数量限制为 200。
  Fix: 大批量补货按多批生成，例如 500 使用 `200 + 200 + 100`，上传前合并并校验行数与唯一数。
  Verify: 2026-07-12 为 7 个套餐各生成 500 个唯一卡密并上传，全部商品保存返回“更新成功”。

- Symptom: Web 聊天角色朗读依赖浏览器默认语音，不同设备音色、可用性和效果不一致。
  Cause: Web Speech API 的语音库由设备和浏览器提供，站点无法稳定控制音色，也无法保证移动端可用。
  Fix: 2026-07-12 改用服务端 `edge-tts`，前端通过鉴权接口合成自己会话中的 assistant 消息并播放 MP3；提供 12 种普通话、粤语和台湾音色，并按文本、音色、语速、音调缓存结果。
  Verify: 线上接口返回 12 种音色和 `audio/mpeg`；同一消息首次合成 `cached=false`、音频 655920 bytes，第二次 `cached=true`。

- Symptom: Tavo Lorebook JSON 导入后世界书为空，或“反扒卡”可被投稿者编辑删除。
  Cause: Tavo v2 文件的 `entries` 可能是对象字典而非数组；旧规范化仅接受列表，且角色世界书原本完全由卡片自身控制。
  Fix: 2026-07-12 增加站点必需世界书 `tavo-anti-scrape-v2`，从 `/opt/ai-fengyue-backend/data/tavo_anti_scrape_worldbook.json` 加载对象字典，创建/导入/编辑/运行时均强制去重并置于 `world_info[0]`，priority=10000、order=-10000；生成时完整放在系统提示最前。
  Verify: 线上迁移报告 `total=8791, first_entry=8791, duplicates=0`；运行时验证 `future_first=tavo-anti-scrape-v2`、`prompt_first=true`、完整尾标存在。

- Symptom: 注册验证码偶发“发送失败”、收不到，且角色卡批量导入时集中出现 `database is locked`。
  Cause: 验证码原先与约 1.3GB 角色内容共用主 SQLite；长写事务会在邮件提交前锁死验证码创建，重复发送还会生成新码导致迟到邮件的旧码失效。
  Fix: 2026-07-11 将验证码和投递状态迁移到独立 `verification_mail.sqlite3`（WAL + busy timeout），10 分钟内复用活动验证码并设置 60 秒投递冷却，验证时兼容旧主库验证码。
  Verify: 本地主库 `BEGIN IMMEDIATE` 锁定期间独立库仍完成创建/复用/核销；线上服务和 Nginx active，内外 `/health` 为 OK，注册邮件接口返回 `status=accepted` 与 `retry_after=60`。

- Symptom: JADX command fails with `UnsupportedClassVersionError ... class file version 55.0`.
  Cause: PATH resolves to `C:\Program Files\Java\jdk1.8.0_112\bin\java.exe`, but JADX 1.5.5 needs Java 11+.
  Fix: Run JADX with `E:\Android\AndroidStudio\jbr\bin` first on PATH or set `JAVA_HOME=E:\Android\AndroidStudio\jbr` before invoking `tools\jadx\bin\jadx.bat`.
  Verify: `java -version` reports OpenJDK 21 from Android Studio JBR and `tools\jadx\bin\jadx.bat --version` prints `1.5.5`.

- Symptom: Runtime control/root checks cannot produce a decisive result.
  Cause: `adb devices -l` shows no connected Android device/emulator.
  Fix: Connect an authorized rooted device/emulator, then rerun `tools\ctf-apk-control-audit.ps1 -Apk base.apk -PackageName com.flai.flai -LaunchActivity com.flai.flai.MainActivity -Install`.
  Verify: Script reports `adb.root.available`, installs the rebuilt APK, starts the launch Activity, and captures logcat evidence.

- Symptom: Python package install or script dependency check fails even though Python exists.
  Cause: `python` on PATH may resolve to an MSYS Python without `pip`; the working interpreter with pip is `D:\Anconda3\python.exe`.
  Fix: Run APK audit automation with `D:\Anconda3\python.exe` and install dependencies through that interpreter.
  Verify: `D:\Anconda3\python.exe -m pip show frida-tools objection capstone` returns package metadata, and `D:\Anconda3\python.exe -m py_compile .\tools\ctf_breach_pipeline.py` succeeds.

- Symptom: `adb root` fails on the auto-created Pixel 6 API 33 emulator.
  Cause: Current emulator image is `sdk_gphone64_x86_64` Google Play USER build; it reports `adbd cannot run as root in production builds`, `disable-verity` reports USER build, and `su` is missing.
  Fix: Use a rooted/userdebug emulator image or an authorized rooted ARM/ARM64 physical device for runtime tamper and Frida-server validation.
  Verify: `adb shell id` or `adb shell su -c id` reports `uid=0`.

- Symptom: Installing `base.apk` or `mutated-signed.apk` on the current emulator fails with `INSTALL_FAILED_NO_MATCHING_ABIS`.
  Cause: The APK contains ARM native libraries (`arm64-v8a`, `armeabi-v7a`), while the auto-created emulator ABI is `x86_64`.
  Fix: Test on an ARM/ARM64 Android device or an emulator/runtime with compatible native bridge support.
  Verify: `adb shell getprop ro.product.cpu.abi` is compatible with `lib/<abi>/*.so`, then rerun `D:\Anconda3\python.exe .\tools\ctf_breach_pipeline.py --apk .\base.apk --package com.flai.flai --activity com.flai.flai.MainActivity`.

- Symptom: Deleting `C:\Users\86180\AppData\Local\Android\Sdk` leaves `platform-tools\adb.exe` and DLLs with `Access to the path ... is denied`.
  Cause: A running `adb` process is locking files inside the SDK directory.
  Fix: Stop the matching `adb` process first, then delete the SDK directory.
  Verify: `Test-Path C:\Users\86180\AppData\Local\Android\Sdk` and `Test-Path C:\Users\86180\.android\avd` both return `False`.

- Symptom: `winget install --location E:\Android\AndroidStudio` still installs Android Studio under `C:\Program Files\Android\Android Studio`.
  Cause: The Android Studio installer ignores winget's requested location for this package.
  Fix: Keep the registered install or copy the installed IDE directory to `E:\Android\AndroidStudio`; launch the E-drive copy with `E:\Android\start-android-studio-e.ps1`. Do not rely on moving `Program Files` directly, which can hit file-permission failures.
  Verify: `Get-Process studio64` shows `E:\Android\AndroidStudio\bin\studio64.exe`, and `E:\Android\AndroidStudio\jbr\bin\java.exe -version` reports OpenJDK 21.

- Symptom: `apktool b` fails under `E:\酒馆开发` with aapt2 reporting a garbled path such as `E:\�ƹݿ���...res` or long smali copy failures.
  Cause: aapt2/subprocess path handling and Windows path length limits are brittle with Chinese workspace paths plus long Compose-generated smali filenames.
  Fix: Build through a short ASCII junction, currently `E:\a` pointing to `reverse-analysis\zip-1-target\decoded-base-1-full`; keep temporary outputs under `E:\z1`.
  Verify: `D:\Anconda3\python.exe .\tools\zip1_repack_pipeline.py` reaches `Built apk into: E:\z1\ai-fengyue-repacked-unsigned.apk`.

- Symptom: `d8.bat` cannot be found when auto-selecting newest build-tools.
  Cause: `E:\android\Sdk\build-tools\37.0.0` exists but lacks `d8.bat`; `36.1.0` is the latest complete directory with `zipalign.exe`, `apksigner.bat`, and `d8.bat`.
  Fix: Select build-tools only if all required tools exist.
  Verify: `tools\zip1_repack_pipeline.py` logs `build_tools=E:\android\Sdk\build-tools\36.1.0` and produces `classes6.dex`.

- Symptom: Server-bound AI风月 APK logs `CLEARTEXT communication to 10.0.2.2 not permitted by network security policy`.
  Cause: `network_security_config.xml` allows only the original cleartext hosts; `usesCleartextTraffic=true` alone is not enough when the XML config is present.
  Fix: Patch `res\xml\network_security_config.xml` to include `10.0.2.2`, `127.0.0.1`, `localhost`, and the configured HTTP backend host.
  Verify: `adb logcat` no longer reports the cleartext-policy error for `http://10.0.2.2:8000/health`.

- Symptom: Local backend receives `/health` with 200, but AI风月 still enters maintenance mode after `NodeTestService` reports `unexpected end of stream`.
  Cause: The app's splash flow gates on `NodeTestService.testSingleNodeLatency`; local stdlib HTTP health responses can still fail OkHttp's node-test read path.
  Fix: For local-server APK builds, patch `NodeTestService.testSingleNodeLatency` to return boxed `Long(1)` while leaving Retrofit business API base URL bound to the configured backend.
  Verify: `adb logcat` shows `BaseUrl changed to: http://10.0.2.2:8000/`, `上次选中节点可用`, and `选择了最优节点: 主节点`.

- Symptom: AI风月 backend appears to support email-code registration, but login can still create a user directly.
  Cause: The local backend's first login implementation used `upsert_user` for unknown emails, bypassing the intended registration verification boundary.
  Fix: `tools\ai_fengyue_local_server.py` login now requires an existing user and matching password; only `console/api/register` can create users after `verify_email_code`.
  Verify: `D:\Anconda3\python.exe .\tools\verify_ai_fengyue_villainy.py` reports login-before-register failure, wrong-code registration failure, correct-code registration success, wrong-password failure, and correct-password success.

- Symptom: Rebuilding AI风月 with a new `--server-url` fails with `server node patch did not find any original or target URLs`.
  Cause: The apktool decode directory may already contain a previously patched backend URL such as `http://10.0.2.2:8000/`, so the original upstream domains are no longer present.
  Fix: `tools\zip1_repack_pipeline.py` tracks known patched backend URLs and can replace those with the new target, e.g. `https://villainy.top/`.
  Verify: The Villain Y build logs `patched server nodes to https://villainy.top/; replacements=18; target_occurrences=18`, and static checks report `villainy=18`, `local=0`, `original_aiporn=0`.

- Symptom: `https://patcher.villainy.top/health` returns Nginx `410 Gone` even after writing the AI星月 patcher site.
  Cause: An older `/etc/nginx/sites-enabled/patcher.conf` also owned `server_name patcher.villainy.top` and was selected before the new backend config.
  Fix: Disable the old symlink and use `/etc/nginx/sites-available/ai-fengyue-patcher.conf` as the only enabled `patcher.villainy.top` site, with 80 redirecting to 443 and 443 proxying `/health`, `/console/`, and `/go/` to `127.0.0.1:8008`.
  Verify: `curl -k https://patcher.villainy.top/health` returns `OK`, and `nginx -T` shows only `ai-fengyue-patcher.conf` for that server name.

- Symptom: The injected recharge page says success but backend points do not change.
  Cause: The first recharge module only wrote `SharedPreferences` and never called a backend billing/points endpoint.
  Fix: `RechargeActivity` now posts to `https://patcher.villainy.top/console/api/ctf/recharge` with the registered user's `local.` token; the backend inserts a `recharge_orders` row and updates `users.points`.
  Verify: `D:\Anconda3\python.exe .\tools\verify_ai_fengyue_villainy.py` reports `server recharge` success and remote SQLite shows a `recharge_orders` entry with user points increased to `1100`.

- Symptom: Full sub2api backup script can fail with `tar: ... pg_wal/... file changed as we read it`.
  Cause: The backup includes live PostgreSQL WAL files under `/opt/sub2api-deploy/postgres_data` while the database is running.
  Fix: For small patcher-only changes, additionally create targeted snapshots of Nginx configs, `/opt/ai-fengyue-backend`, and the systemd unit before editing; keep using the full backup for migration-grade captures when it succeeds.
  Verify: Manual snapshots exist as `/etc/nginx/sites-available/*.bak-*`, `/etc/systemd/system/ai-fengyue-backend.service.bak-*`, and `/opt/ai-fengyue-backend.bak-*.tgz`.

- Symptom: `scp` upload of `E:\...\ai-xingyue-patcher-signed.apk` fails with `Could not resolve hostname e`.
  Cause: Git/MSYS `scp` parses the Windows drive-letter colon as a remote-host separator.
  Fix: Explicitly call `C:\Windows\System32\OpenSSH\scp.exe` when uploading Windows absolute paths to the server.
  Verify: Upload to `/tmp/ai-xingyue-latest.apk.upload` succeeds, then the server file at `/var/www/ai-fengyue-frontend/download/ai-xingyue-latest.apk` hashes to `fa998f9cfbd5c1b36553bf8196f888855be45d2199f9cb9791d9f49394a80072`.

- Symptom: Remote backend deploy script runs but `systemctl`/`sleep`/`curl` fail with `\r`-tainted unit names or `invalid option`.
  Cause: A CRLF-local helper script was piped into Linux `bash`, so command arguments inherited trailing carriage returns.
  Fix: Keep remote deploy helpers LF-only or use inline single-quoted SSH commands; verify the live file hash and `grep` the remote script before assuming the replacement succeeded.
  Verify: `sha256sum /opt/ai-fengyue-backend/ai_fengyue_local_server.py` matches the uploaded helper and `systemctl is-active ai-fengyue-backend.service` returns `active`.

- Symptom: AI星月 APK grows larger and visible content/resources drift away from the AI风月 APK after icon/cover/welcome replacement.
  Cause: The full AI星月 branding pass replaced content assets such as `res/drawable/logo.png`, `res/drawable/base_logo.webp`, launcher icons, and `res/drawable-*/welcome.webp`.
  Fix: For "same content and same usable functions as AI风月" builds, use `D:\Anconda3\python.exe .\tools\zip1_repack_pipeline.py --functional-parity --server-url https://patcher.villainy.top/` from a clean or already clean decode tree; this keeps original content assets and only applies server/recharge compatibility plus minimal app-name branding.
  Verify: `output\zip-1-repack\ai-xingyue-parity-signed.apk` verifies with apksigner/zipalign; static APK entry sizes for `logo.png`, `base_logo.webp`, and all `welcome.webp` densities match `ai-fengyue-villainy-signed.apk`; public checksum is `a6e76e1a7eb4bd188e3d1bd0e31a8c59323b4947581f1e9e1c925f862404eefc`.

- Symptom: User requires AI星月 to keep the previous APK icon/logo and welcome page while still loading AI风月 data from `patcher.villainy.top`.
  Cause: `--functional-parity` intentionally restores AI风月 content resources, which conflicts with the later AI星月 resource-preservation requirement.
  Fix: Use `D:\Anconda3\python.exe .\tools\zip1_repack_pipeline.py --server-url https://patcher.villainy.top/ --xingyue-assets`; this preserves AI星月 logo/icon/welcome assets while binding API traffic to the patcher backend.
  Verify: Public checksum is `63efb415bb3046dc1d0984a1cba4c643fefcd12db103d124ba2ad0abf4845e56`; static APK entries include AI星月 `res/drawable/logo.png`, `res/drawable/base_logo.webp`, and `res/drawable-*/welcome.webp`; emulator login reaches patcher APIs.

- Symptom: After login, logcat reports `MineViewModel: getAppSiteList请求异常: Required value 'list' missing at $.data`.
  Cause: The Compose client Moshi model for `/console/api/app_site/list` requires `data.list`; backend fallback/proxy data only had `installed_apps`, `apps`, and `items`.
  Fix: `tools\ai_fengyue_local_server.py` normalizes `/console/api/app_site/list` responses so `data.list` always exists.
  Verify: `curl -k https://patcher.villainy.top/console/api/app_site/list?lang=zh-Hans` returns `data.list`; emulator logcat after login has no `JsonDataException` or `Required value` entries.

- Symptom: Personal center or side drawer shows `Expected BEGIN_ARRAY but was BEGIN_OBJECT at path $.data`.
  Cause: Some empty backend fallbacks returned `data:{}` while the APK model expects `data` to be a JSON array for `/console/api/account/referral-info`, `/console/api/v1/activities/gift-packs`, and `/console/api/emojis`.
  Fix: `tools\ai_fengyue_local_server.py` returns or normalizes those endpoints to `data: []` when no records exist.
  Verify: `curl -k` for those three endpoints reports `data` as a list; emulator logcat `ai-xingyue-profile-after-array-fixes-logcat.txt` has no `Expected BEGIN_ARRAY`, `JsonDataException`, or `Required value`.

- Symptom: `--force-decode` fails deleting `decoded-base-1-full` with `WinError 3` on a very long Compose smali filename.
  Cause: Windows path length handling breaks on nested generated smali paths under the Chinese workspace.
  Fix: `tools\zip1_repack_pipeline.py` uses a guarded `remove_work_tree()` with a Windows long-path prefix and refuses to delete outside `reverse-analysis\zip-1-target`.
  Verify: A clean decode followed by `--functional-parity --server-url https://patcher.villainy.top/` completed and produced `ai-xingyue-parity-signed.apk`.

- Symptom: AI星月探索页 shows `暂无数据`, and 我的 page stays on `加载中`.
  Cause: The APK requests many `go/api/explore/search` query shapes that were not present in `content_cache`, and local `go/*` profile responses used `code:0` plus too few profile alias fields. Missing static avatar also caused image decode failures.
  Fix: `tools\ai_fengyue_local_server.py` now returns `go_response` with code `100000`, adds `nickname`/`user_name`/`username`/`display_name` aliases, serves a real default avatar, returns `personal-profile`, and falls back to the first non-empty cached explore payload for unmatched explore queries.
  Verify: Emulator screenshot `output\zip-1-repack\ai-xingyue-20260618-after-backend-fix-start.png` shows loaded role cards; `output\zip-1-repack\ai-xingyue-20260618-after-backend-fix-mine.png` shows `本地测试用户`; curl confirms profile/explore `code=100000`, avatar `Content-Type: image/png`, and logcat has no `JsonDataException`, `Required value`, `数据加载失败`, or upstream domain leakage.

- Symptom: AI星月个人中心修改用户名后 APK 提示报错或保存后不刷新昵称.
  Cause: The APK posts username edits to `POST /console/api/account/name`, but the local backend only implemented gender/profile reads and did not persist name edits.
  Fix: `tools\ai_fengyue_local_server.py` implements `console/api/account/name` and `go/api/account/name`, accepts `name`/`nickname`/`user_name`/`username`/`display_name`, updates `users.name`, and returns full profile aliases.
  Verify: `python -m py_compile tools\ai_fengyue_local_server.py`; public curl POST to `/console/api/account/name?lang=zh-Hans` returns the new `name`, and subsequent `/go/api/account/profile` reads it back.

- Symptom: `curl.exe` API verification from PowerShell returns unexpected backend validation errors such as `invalid email` even for a valid JSON body.
  Cause: Double-quoted JSON with escaped quotes/backslashes can be rewritten by PowerShell before it reaches `curl.exe`.
  Fix: Use Python/urllib or requests for structured API probes, or use single-quoted JSON with `--data-raw` when calling `curl.exe` from PowerShell.
  Verify: `curl.exe -k -sS -H 'Content-Type: application/json' --data-raw '{\"email\":\"codexwebverify178177@test.com\",\"lang\":\"en\"}' https://patcher.villainy.top/console/api/register/email` returns `result=success`.

- Symptom: `/console/api/web/chat` returns `app_id and content are required` when testing Web chat.
  Cause: The Web chat backend expects the request field `content`; using `message` is only a test-script mistake. The shipped `frontend/app/assets/js/chat.js` sends `content`.
  Fix: Send `{"app_id":"...","content":"..."}` to `/console/api/web/chat`.
  Verify: 2026-06-18 one-time user flow created a user role, sent chat with `content`, received a reply, read 2 conversation messages, then deleted the role.

- Symptom: Admin API verification using `local@ctf.test` and `local123456` fails with `invalid email or password`.
  Cause: The live admin email remains `local@ctf.test`, but its password has changed from the original default.
  Fix: Do not reset or assume the password. For non-mutating admin API verification, read the admin user's id from the remote SQLite DB and generate a temporary `local.` bearer token matching `token_for()` in `tools\ai_fengyue_local_server.py`.
  Verify: 2026-06-18 generated token for the `local@ctf.test` user id; `/admin/api/whoami`, `/admin/api/llm-settings`, and `/admin/api/apps?source=upstream&page=1&page_size=1` succeeded while unauthenticated `/admin/api/llm-settings` returned `403`.

- Symptom: `sync_upstream_content.py` long multi-page retry over SSH times out locally and no `--report` JSON appears.
  Cause: The report is written only at normal script exit; an interactive SSH timeout can terminate the remote process before report writing.
  Fix: For quick status checks after upstream rate limiting, run a one-page low-frequency retry first: `--start-page 14 --pages 1 --timeout 30 --retries 1 --retry-sleep 20 --force --no-detail --report ...`.
  Verify: 2026-06-18 single-page retry wrote `/opt/ai-fengyue-backend/data/sync-upstream-report.json` showing page 14 failed with non-JSON response and `total_upstream_in_db=449`.

- Symptom: AI星月 Web `my-apps.html` browser console reports `Cannot read properties of null (reading 'name')` and similar errors after opening pages.
  Cause: Alpine `x-show="editing"` hides the edit modal but still evaluates nested `x-model="editing.*"` bindings while `editing` is `null`.
  Fix: Wrap the edit modal in `<template x-if="editing">` so nested bindings are mounted only after an edit object exists.
  Verify: After redeploying on 2026-06-18, `agent-browser errors --clear` followed by visits to `/app/my-apps.html`, `/app/me.html`, `/app/character.html`, `/app/chat.html`, and `/app/create.html` produced no new browser errors.

- Symptom: 注册验证码接口提示已发送，但普通邮箱收不到验证码。
  Cause: 当前 Resend SMTP 使用 `onboarding@resend.dev` 测试发件人，只允许投递到 Resend 账号自己的邮箱 `yjy112508@gmail.com`；`patcher.villainy.top` 发件域尚未在 Resend 验证，使用 `noreply@patcher.villainy.top` 会被 Resend 550 拒绝。
  Fix: 2026-06-22 已将线上 `ALLOW_EMAIL_SEND_FAILURE=false`，让发送失败明确返回错误；要恢复任意邮箱注册，需在 Resend 验证 `patcher.villainy.top` 发件域，或提供一个可向外部邮箱投递的 SMTP。
  Verify: `yjy112508@gmail.com` 验证码发送返回 success；测试外部邮箱返回 `email send failed`；`ai-fengyue-backend.service` 与 `nginx` 均 active，`/health` 返回 OK。

- Symptom: 从首页点“先看看 App”注册/登录后可能落到旧入口 `/app/explore.html`。
  Cause: 首页按钮已带 `next=/app/`，但 `frontend/app/assets/js/login.js` 的无 `next` 兜底仍默认 `/app/explore.html`。
  Fix: 2026-06-22 已把登录页已登录直跳和登录/注册成功后的默认跳转统一改为 `/app/`，并部署到线上。
  Verify: 线上首页按钮为 `/app/login.html?next=%2Fapp%2F`；`https://patcher.villainy.top/app/assets/js/login.js` 中两个默认 `next` 均为 `/app/`；`/app/` 返回 HTTP 200。

- Symptom: 用户可以反复点击每日签到并无限增加积分。
  Cause: 旧接口 `/console/api/ctf/dailyapppoints` 每次请求都直接 `add_points`；新奖励接口也只用 `user_events.payload_json like date` 做弱检查，缺少数据库唯一约束。
  Fix: 2026-06-26 新增 `daily_reward_claims(user_id, claim_date)` 主键表和 `Store.claim_daily_reward()`，旧接口与 `/console/api/web/rewards/daily` 统一调用；前端根据 `points_added=0` 显示“今日已经签到过了”。
  Verify: 线上临时用户从 `1000` 积分开始，第一次签到 `points_added=10` 余额 `1010`，第二次旧接口和第三次新接口均 `points_added=0` 且余额保持 `1010`；`ai-fengyue-backend.service` 与 `nginx` active，`/health` OK。

- Symptom: AI星月 Web 聊天缺少 SillyTavern 式流式输出体验。
  Cause: `/console/api/web/chat` 原本只支持阻塞返回完整回复，前端再做本地 typewriter 动画。
  Fix: 2026-06-26 新增 `/console/api/web/chat/stream` SSE 端点，前端 `app-core.js` 增加 `sendChatStream()`，`chat.js` 优先使用 `start`/`delta`/`message_end` 增量更新 assistant 气泡。
  Verify: 线上临时流式请求返回 `event: start`、3 个 `event: delta` 和 `event: message_end`；线上 `chat.js` 已包含 `sendChatStream` 和 `response_mode: 'streaming'`。

- Symptom: 角色卡选择管理员模型预设后，真实模型请求可能把预设 ID 当作模型名发送。
  Cause: 用户角色卡的 `llm_model` 字段保存的是模型预设 ID，例如 `default`，旧 `call_user_llm()` 优先使用该字段作为 OpenAI `model`。
  Fix: 2026-06-26 `build_user_llm_request()` 会在 `llm_model` 等于有效预设 ID 时使用预设中的真实 `model`，并且 `/console/api/web/chat/stream` 对用户/管理员角色卡发送 OpenAI-compatible `stream:true` 请求，逐块透传上游 `delta.content`。
  Verify: 本地假上游收到 `stream=true`、`model=gpt-real`；线上临时假上游收到 `stream=true`、`model=gpt-stream-real`，前端 SSE 有 3 个 `delta`，最终 assistant 消息保存为完整 `真流式`。

- Symptom: Prompt Manager 的 `system_before` 线上验证失败，但代码里前置注入逻辑存在。
  Cause: 验证脚本没有先保存 persona，却断言 `{{user}}` 会替换成 `Codex Prompt`；实际默认用户宏会是 `你`。
  Fix: 2026-06-26 远程验证脚本先调用 `/console/api/web/persona` 保存测试 persona，再创建角色并检查 `system_before/system_after/post_history`。
  Verify: `python3 /tmp/verify_prompt_manager_remote.py` 返回 `system_has_before=true`、`system_has_after=true`、`post_has_block=true`、`upstream_stream_true=true`、`stream_has_end=true`。

- Symptom: 高级世界书中 `probability: 0` 的条目仍被注入。
  Cause: 选择逻辑使用 `entry.get("probability") or 100`，把合法的 `0` 当成空值回退到 100。
  Fix: 2026-06-26 改为只在字段为 `None` 时默认 100；导出 Character Book 时同样保留 0。
  Verify: 本地和远程 `verify_advanced_world_info.py` 均返回 `probability_zero_excluded=true`，同时优先级、二级关键词、depth 插入和递归扫描通过。

- Symptom: SillyTavern PNG 角色卡导入失败，前端只接受 `.json` 且后端只解析 JSON 对象。
  Cause: 创建页导入逻辑使用 `file.text()` + `JSON.parse()`，后端 `/console/api/web/cards/import` 没有读取 PNG `chara` metadata。
  Fix: 2026-06-26 前端允许 `.png` 并上传 data URL；后端解析 PNG `tEXt/iTXt/zTXt` 中的 `chara/character/ccv2/ccv3/card/metadata`，并新增 `/console/api/web/my-apps/{id}/export-png` 导出带 `chara` metadata 的 PNG。
  Verify: 线上 `verify_card_png_api_remote.py` 返回 `imported=true`、`extensions_preserved=true`、`world_secondary=true`、`world_probability_zero=true`、`export_png=true`，测试角色和用户已清理。

- Symptom: AI星月 Web 相比 SillyTavern 缺少多角色群聊。
  Cause: 原有聊天只建模为单个 `conversation.app_id` 和普通 `messages`，无法表达群成员、发言顺序和每条消息的角色发言人。
  Fix: 2026-06-26 新增 `group_chats`、`group_members`、`group_messages`，新增 `/console/api/web/group-chats*` API 和 `/app/group-chat.html`。群聊回复复用单聊 LLM/Persona/世界书/Prompt Manager 链路，并用 `active_index` 轮转下一位角色。
  Verify: 线上 `verify_group_chat_remote.py` 返回 `created_members=2`、`has_role_a=true`、`has_role_b=true`、`deleted=true`；`output/playwright/group-chat-st6.png` 显示群聊页面正常渲染。

- Symptom: 用户角色卡无法使用自己的 API Key，所有模型都只能走站长后台配置。
  Cause: 旧模型预设只有管理员 `api_settings`，角色卡 `llm_model` 只能引用站点 preset ID。
  Fix: 2026-06-26 新增 `user_model_presets` 和 `/console/api/web/user-model-presets`，前端“我的”页可保存用户 BYOK 连接器；角色 `llm_model=user:<preset_id>` 时聊天按当前用户读取自己的 Key，不写入角色卡、不回显明文 Key。
  Verify: 线上 `verify_user_byok_remote.py` 返回 `api_key_redacted=true`、`upstream_model=gpt-user-real`、`upstream_auth_user_key=true`、`reply=BYOK OK`；`output/playwright/me-byok-st7.png` 显示 UI 正常。

- Symptom: OpenAI-compatible 阻塞响应已请求成功，但聊天仍回退到模板回复。
  Cause: `extract_upstream_chat_answer()` 只解析 `reply/content/data` 等字段，未解析标准 `choices[0].message.content`。
  Fix: 2026-06-26 补齐 OpenAI Chat Completions 阻塞响应解析。
  Verify: BYOK 远程 E2E 的假上游返回 `{"choices":[{"message":{"content":"BYOK OK"}}]}`，最终聊天回复为 `BYOK OK`。

- Symptom: 用户前台看不到“我的”入口，无法找到自带 Key / 我的模型连接器配置。
  Cause: 桌面侧边栏 `frontend/app/assets/js/layout.js` 没有 `me` 导航项，只有移动底部导航有“我的”；左下角用户卡也不是链接。
  Fix: 2026-06-26 已在桌面 `NAV_ITEMS` 添加“我的”并把左下角用户卡改为 `/app/me.html` 链接。
  Verify: Playwright 打开线上 `/app/workshop.html` 看到侧边栏“我的”，用户卡 `href=/app/me.html`；打开 `/app/me.html` 能看到“我的模型连接器”，截图 `output/playwright/workshop-me-nav-fix.png`、`output/playwright/me-model-connector-entry.png`。

- Symptom: 点击“添加 Anthropic/Claude”后，组件数据里 `provider=anthropic` 且协议/Base URL/模型正确，但供应商下拉视觉上仍显示 `OpenAI Compatible`。
  Cause: `me.html` 的 provider `<select>` 选项由嵌套 `x-for` 渲染，初次插入用户模型对象时浏览器 select 显示没有跟上 Alpine 的 `x-model` 数据。
  Fix: 2026-06-26 在 provider `<select>` 加 `x-effect="$el.value = p.provider || 'custom-openai'"`，并在 option 上加 `:selected="tpl.id === p.provider"`。
  Verify: Playwright 登录临时用户打开线上 `/app/me.html`，点击“添加 Anthropic/Claude”后 `selectValues[0].value=anthropic`、`selectValues[1].value=anthropic`，无 console error，截图 `output/playwright/me-provider-protocol.png`。

- Symptom: 新增后台数据总览图表后，`/admin/api/stats` 请求连接被关闭，服务端日志出现 `OSError: [Errno 22] Invalid argument`。
  Cause: `daily_count_series()` 把毫秒时间戳直接传给 `time.gmtime()`；Python `time.gmtime()` 需要秒级时间戳。
  Fix: 2026-06-26 将 `time.gmtime(start_ms + offset_ms)` 改为 `time.gmtime((start_ms + offset_ms) / 1000)`。
  Verify: `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过；`D:\Anconda3\python.exe .\output\verify_admin_ops_local.py` 返回 `stats_charts=true`；线上远程验证返回 `charts_daily_users=true` 和 `charts_daily_requests=true`。

- Symptom: Playwright 打开线上 `/app/` 做运营配置截图验证时，`page.goto(..., wait_until="networkidle")` 超时。
  Cause: Web App 页面会持续请求或等待慢资源，`networkidle` 对这类页面过严，容易把已渲染页面误判为失败。
  Fix: 2026-06-26 将 `output\verify_site_settings_browser.py` 页面跳转改为 `wait_until="domcontentloaded"`，再等待目标文案/选择器出现并用页面文本断言验证真实渲染。
  Verify: `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回 `console_error_count=0`、`page_error_count=0`，并生成登录页、App 公告、奖励页、用户中心、我的页、工坊、图片聊天、信息中心和后台截图。

- Symptom: 运营配置浏览器验证中，“我的”页模型连接器占位文案断言失败，但页面无 console/page error。
  Cause: BYOK 模型连接器输入框是动态字段，只有点击“添加 OpenAI/OpenRouter/Anthropic”后才挂载到 DOM；直接读取页面初始 placeholders 会漏掉这些字段。
  Fix: 2026-06-26 `output\verify_site_settings_browser.py` 先点击“运营添加 Claude”，再检查模型显示名、Base URL、模型名和 API Key 等占位文案。
  Verify: 浏览器验证返回 `me_copy_ok=true`、`admin_values_ok=true`、`console_error_count=0`、`page_error_count=0`。

- Symptom: 多个 App 页面浏览器验证出现 `Unexpected token '}'`，但 `node --check frontend\app\assets\js\layout.js` 通过。
  Cause: `layout.js` 生成的 HTML 中，`x-text="user?.name || ${JSON.stringify(text)}"` 把 JSON 双引号直接放进双引号属性，浏览器解析后 Alpine 表达式被截断；这是 HTML 属性转义问题，不是 JS 模块语法问题。
  Fix: 对插入属性的 JS 字符串表达式再做 HTML 转义，例如 `escapeHtml(jsString(value))`。
  Verify: 重新部署后 `D:\Anconda3\python.exe .\output\verify_site_settings_browser.py` 返回 `console_error_count=0`、`page_error_count=0`。

- Symptom: 运营配置里把聊天空态连接词设为带尾随空格的 `去 `，本地验证只返回 `去` 或自定义值尾部空格消失。
  Cause: `tools\ai_fengyue_local_server.py` 的 `clean_text()` 会对所有站点配置文本做 `.strip()`，前后空格不会被持久保留。
  Fix: 不依赖配置值保存首尾空格；把中文连接词配置为不带空格的纯文本，HTML 中用普通空白或独立元素负责视觉间距。
  Verify: `D:\Anconda3\python.exe .\output\verify_site_settings_local.py` 返回 `chat_no_conversations_prefix=本地去`；线上恢复后公开配置返回 `no_conversations_prefix=去`。

- Symptom: Web “我的”页或侧栏头像加载 `https://patcher.villainy.top/media-cache/profile/default-avatar.png` 报 404，浏览器 console 出现 `Failed to load resource`。
  Cause: `profile_json()` 默认返回 `/media-cache/profile/default-avatar.png`，但线上后端默认只查 `DEFAULT_STATE_DIR/static/default_avatar.png`，该文件不存在；实际默认头像随前端部署在 `/var/www/ai-fengyue-frontend/assets/img/apk/default_avatar.png`。
  Fix: `tools\ai_fengyue_local_server.py` 的默认头像 handler 增加本地前端资源和线上前端资源 fallback，保持默认头像 URL 稳定。
  Verify: `curl.exe -k -sS -o NUL -w "avatar_http=%{http_code} content_type=%{content_type} size=%{size_download}\n" https://patcher.villainy.top/media-cache/profile/default-avatar.png` 返回 `avatar_http=200 content_type=image/png`；Playwright 打开 `/app/me.html` 无头像 404 error。

- Symptom: SillyTavern/Tavo 角色卡正则把开场或状态替换成大段 HTML/CSS/JS 后，AI星月聊天要么只显示源码，要么存在把 `<script>` 插进主聊天 DOM 的风险。
  Cause: 旧 `/app/chat.html` 渲染层只支持 `<StatusBlock>` 格式化，其他内容全部作为文本；Tavo 类卡片需要脚本执行，但主 DOM 执行会暴露账号 token、localStorage 和平台 API。
  Fix: `frontend\app\assets\js\chat.js` 检测 fenced/raw 高级 HTML 后只放进 `iframe srcdoc`，iframe 仅 `sandbox="allow-scripts"` 且不加 `allow-same-origin`；`srcdoc` 强制 CSP 禁止 connect/frame/object/form/external script，并清理外部资源属性。长消息折叠，消息接口用 `limit/before` 分页加载更早消息。
  Verify: `D:\Anconda3\python.exe .\output\verify_tavo_sandbox_browser.py` 返回 `mainScriptCount=0`、`sandboxHasSameOrigin=false`、`srcdocHasCsp=true`、`parentCanReadFrame=false`、`console_error_count=0`；`D:\Anconda3\python.exe .\output\verify_message_pagination_local.py` 验证最新窗口和更早窗口分页正确。

- Symptom: 搬 Tavo 高级渲染时，想让角色卡脚本像 SillyTavern 插件一样直接操作页面。
  Cause: TavoJS/角色卡脚本若进入主 DOM 或 same-origin iframe，会读取 `localStorage`、账号 token、同源 API 和主页面 DOM，风险不可接受。
  Fix: `frontend\app\assets\js\chat.js` 只在无 `allow-same-origin` 的 sandbox iframe 中提供受限 `window.TavoJS/window.tavo` 兼容桥；默认 TavoJS 需要点击确认，禁用 JS 时使用 `sandbox=""` 与 `script-src 'none'`，Code Block 模式只允许 fenced 高级代码块执行脚本。
  Verify: 2026-07-02 本地和线上 `D:\Anconda3\python.exe .\output\verify_tavo_advanced_render_browser.py` 返回 `default_confirm_paused=true`、`tavo_bridge_ok=true`、`sandbox_has_same_origin=false`、`parent_can_read_frame=false`、`raw_script_ran=false`、`fenced_script_ran=true`、`formula_inline=true`、console/page error 为 0。

- Symptom: HTML 代码注入器/高级渲染开关已开启，但片段以 `<style>` 或 `<script>` 开头时没有实际视觉效果，脚本里查找 `.mes_text`、`#chat` 等 SillyTavern 消息目标为空。
  Cause: `DOMParser.parseFromString(..., 'text/html')` 会把片段开头的 `<style>/<script>` 移到 iframe `<head>`，脚本早于 body 和兼容目标执行；部分输出还会使用 ` ```html injector ` 这类带说明 code fence 或未闭合最终 fence。
  Fix: `frontend\app\assets\js\chat.js` 对非完整 HTML 片段把 parsed head 内容放回 iframe body 兼容容器，容器提供 `#chat`、`.mes`、`.mes_text`、`.message-content`、`.tavo-content`；HTML fence 语言取首个 token，最后一个未闭合 fence 也解析；脚本仍只在无 `allow-same-origin` 的 sandbox iframe 中运行。
  Verify: 2026-07-02 本地和线上 `D:\Anconda3\python.exe .\output\verify_tavo_advanced_render_browser.py` 返回 `injector_ran=true`、`injector_text_has_result=true`、`unclosed_fence_ran=true`、`event_only_ran=true`，同时 `sandbox_has_same_origin=false`、`parent_can_read_frame=false`、`main_script_count=0`；线上 `verify_tavo_sandbox_browser.py` 回归通过。

- Symptom: Tavo/ST 开场视觉页显示源码、空白，或首屏出现但点击章节/按钮没有效果。
  Cause: 开场问候曾不执行角色 Regex；旧导入卡可能把 `# 游玩说明...` 视觉前言放进 `creator_notes`、只把 `P1` 留在 `opening_statement`；大段 HTML Regex 顶层副本可能被截断但 `extensions.regex_scripts` 保留完整替换；Python `re.sub` 不兼容 SillyTavern/JS 的 `$1/$&/$<name>` 替换；iframe sandbox 中卡片脚本直接访问 `window.top`、`parent.SillyTavern`、`localStorage/sessionStorage` 或世界书函数会失败。
  Fix: `tools\ai_fengyue_local_server.py` 恢复视觉前言、开场问候执行 Prompt Template 后再执行 Regex、从顶层和 `extensions` 合并读取 regex 并优先使用更长替换、`REGEX_REPLACE_MAX_CHARS=240000`、函数式展开 JS 风格替换；`frontend\app\assets\js\chat.js` 在无 same-origin iframe 中提供 `__xySTTop`、`SillyTavern.getContext()`、本地 storage shim、世界书 no-op helpers，并重写卡内脚本/事件属性。
  Verify: 2026-07-03 目标卡 `admin-rczip-9721d5969c2effd819af` 远程 API 返回 `first_has_hero=true`、`first_has_script=true`、`swipe_count=13`、`has_p6/h8/u6=true`；线上 `D:\Anconda3\python.exe .\output\verify_tavern_opening_render_live.py` 返回 `hero_text=晚上好，欢迎回来`、菜单 labels 齐全、`modal_opened=true`、`sandbox_has_same_origin=false`、console/page error 为 0。

- Symptom: 从 PowerShell 执行 `ssh "... python3 - <<'PY' ..."` 一类内联远程 Python 检查时，本地 PowerShell 把远程脚本里的 `*` 等字符当作本地命令解析，导致命令还没到服务器就失败。
  Cause: PowerShell 与远程 shell 双层转义叠加，bash heredoc/多行 Python 不适合直接塞进本地命令字符串。
  Fix: 把远程检查写成临时 `.py` 文件，用 Windows OpenSSH `scp.exe` 上传到 `/tmp/` 后再 `ssh "python3 /tmp/script.py"` 执行。
  Verify: `check_chat_credits_remote_cleanup.py` 上传执行成功，返回 `{"remote_test_users": 0, "remote_test_apps": 0}`。

- Symptom: 后台 `/admin.html` 角色卡 Tab 点开后很久没有可勾选角色，浏览器验证会等不到可见行。
  Cause: `/admin/api/apps` 曾默认返回 30 张完整角色卡，包含大世界书、正则和扩展字段；导入 2000+ 张官方卡后，首屏列表请求过重。
  Fix: 管理端列表请求 `lightweight=1`，后端用 `local_app_to_list_card()` 返回轻量卡；点击编辑时再走 `GET /admin/api/apps/{id}` 拉完整详情。
  Verify: `D:\Anconda3\python.exe .\output\verify_admin_bulk_edit_browser.py` 15 秒内完成，批量编辑弹窗可见，console/page error 为 0。

- Symptom: Rewards/Deposit 页面看起来仍是默认兜底文案，只显示 `1 CNY = 1000 星月币` 而不显示套餐和订阅卡片。
  Cause: 浏览器验收脚本没有在页面初始化前写入 `ai_xingyue_token`，或先打开其他 App 页面后异步请求清理了 localStorage，导致 Rewards 按未登录状态渲染。
  Fix: Playwright 验收用 context `add_init_script` 立即执行 localStorage 写入，或直接打开目标受保护页面后再刷新初始化；不要把未登录兜底页面当成套餐渲染失败。
  Verify: `D:\Anconda3\python.exe .\output\verify_billing_logo_browser.py` 返回 `rewards_rate_ok=true`、`packages_ok=true`、`subscriptions_ok=true`、`mobile_subscriptions_ok=true`、`admin_subscription_editor_ok=true`。

- Symptom: 计费配置仍出现 `1 CNY ≈ 10000 星月币` 或 `20 CNY -> 220000` 一类旧套餐。
  Cause: 旧 `site_settings.deposit` 运营配置覆盖了代码默认值，会让 `50` 积分只卖 `0.005 CNY`，低于当前 `0.022 CNY/次` 模型成本。
  Fix: 充值口径保持 `1 CNY = 1000 星月币，50 星月币约等于 1 次角色回复`；积分包为 `10->10000`、`20->22000`、`50->57500`、`100->120000`；订阅只做月度额度包 `19.9->22000`、`39.9->50000`、`79.9->110000`，不承诺无限用。
  Verify: 线上 `/console/api/web/deposit-meta` 返回新 rate/packages/subscriptions，`output\verify_billing_logo_browser.py` 前台/后台截图验证通过。

- Symptom: 用户看不到 Codex 打开的第三方后台浏览器，无法扫码、登录或手动确认。
  Cause: `agent-browser`/Playwright 自动化会话可能是独立浏览器上下文或 headless/headed daemon，不等于用户桌面前台可见的 Chrome 窗口。
  Fix: 涉及爱发电、微信、支付、登录、扫码、后台商品配置等需要用户参与的第三方页面时，优先用 Windows 前台可见浏览器打开，例如 `Start-Process chrome.exe <url>`；不要默认使用 headless。只有纯页面验证/截图才使用 headless。
  Verify: 用户能在桌面看到浏览器窗口并自行登录/确认后，再继续自动化或手动指导。

- Symptom: CelestiAI OpenAI-compatible API 直连或后台聊天走兜底回复，直连返回 Cloudflare 1010 `browser_signature_banned`。
  Cause: CelestiAI 会拦截默认 Python/urllib User-Agent 的请求；AI星月后端上游 LLM 调用也使用 urllib。
  Fix: `tools\ai_fengyue_local_server.py` 给上游 OpenAI/Anthropic-compatible LLM 请求补充浏览器式 `User-Agent`、`Origin`、`Referer` 请求头；不要把模型 API Key 写入本地文档或日志。
  Verify: 2026-06-29 直连 `gemini-2.5-pro-cli` 成功；线上 `/console/api/web/chat/stream` 对 `Blacksouls` 返回 9 个 delta、`message_end=true`，积分 `5000 -> 4950`，公开 `/console/api/web/model-presets` 不包含 API Key。

- Symptom: SillyTavern 角色卡导入后，卡片自带的正则渲染/替换没有在聊天中生效。
  Cause: 部分卡把正则放在 `extensions.regex_scripts` 或 `TavernHelper_scripts`，而 AI星月聊天执行链路读取的是顶层 `extra_settings.regex_scripts`，且字段需要规范为 `find/replace/flags/enabled`。
  Fix: 导入时保留原始 `extensions`，同时把 `findRegex/replaceString/scriptName/disabled` 转换并提升到顶层 `regex_scripts`；不要把只有脚本/工作流但没有角色设定、开场、世界书或问候语的文件当作角色卡导入。
  Verify: 2026-06-29 全量可用卡导入后，118 张官方卡中 59 张有非空顶层 regex；样本新卡 `admin-rczip-all-6545f4abddf781438e0c` 有 10 条 regex，线上流式聊天成功并扣费正常。

- Symptom: 聊天回复里 `<StatusBlock>` 原样挤在正文中，且角色卡输出混入日文/英文对话。
  Cause: `/app/chat.html` 旧气泡用 `x-text` 纯文本显示，无法把状态块格式化；后端组装 system prompt 时没有硬性要求最终回复统一简体中文。
  Fix: `frontend/app/assets/js/chat.js` 使用安全转义后的 `x-html` 渲染消息，把 `<StatusBlock>` 转成中文状态卡片并把 `H对象` 等字段规范为中文；`tools/ai_fengyue_local_server.py` 在角色 system prompt 追加“最终回复统一使用简体中文”和中文状态字段规则。
  Verify: `node --check frontend\app\assets\js\chat.js`、`python -m py_compile tools\ai_fengyue_local_server.py` 通过；线上 `chat.js?v=20260629-format` 已部署；`output\playwright\chat-statusblock-format.png` 显示状态卡片，浏览器验证返回 `hasStatusCard=true`、`hasRawTag=false`。

- Symptom: `/app/` 首页首屏角色加载很慢，公网 `/go/api/explore/search` 甚至可能几十秒才返回。
  Cause: 探索列表接口不能返回完整角色卡详情；完整载荷会把 opening messages、world books、regex scripts、extensions 等详情字段塞进每张列表卡，20 张卡可膨胀到数 MB。首页还曾依赖 Tailwind/jsdelivr 外部 CDN，放大首屏等待。
  Fix: 首页列表必须使用 `Store.list_local_apps(..., lightweight=True)` 和 `local_app_to_list_card()`，详情页/聊天页才用 `local_app_to_card()`；`/app/index.html` 保持本地 Alpine、无 Tailwind/jsdelivr、预加载默认第一页和模块依赖；`api.exploreSearch()` 对公开探索接口保持 `auth:false` 以复用 fetch preload。
  Verify: 2026-06-29 线上 `/app/` 浏览器验证 `first_card_ms=1795`、探索 payload 约 `10.9KB`、`first_has_heavy_fields=false`、`console_error_count=0`、`page_error_count=0`；服务/Nginx active，`/health` OK，`CONTENT_MODE=local_only`。

- Symptom: 聊天回复开始时出现“上面空白 assistant 气泡 + 下面单独加载气泡”，或者角色卡输出 `<battle_status_panel>`、`<protagonist>`、`<opponent>` 等 raw XML 标签，用户看起来像乱码。
  Cause: `sendMessage()` 已经插入流式 assistant 占位消息，但 `chat.html` 还用 `x-if="replying"` 额外渲染加载气泡；状态渲染器只识别 `<StatusBlock>`，没有识别角色卡常见的 XML 状态面板。
  Fix: 删除独立 `replying` 加载气泡；用 `rowClass()`/`bubbleClass()` 给流式 assistant 占位消息直接加 `is-loading`；回复生成中隐藏消息操作条；把 `<battle_status_panel>` 和 `*_status_panel` 块解析为 `structured-status-card` 中文状态卡。
  Verify: 2026-06-29 线上 `D:\Anconda3\python.exe .\output\verify_chat_panel_fix_browser.py` 返回 `assistantBubbles=1`、`loadingBubbles=1`、`visibleActions=0`、`panelCount=1`、`rawTagVisible=false`、浏览器错误为 0；截图 `output\playwright\chat-panel-fix-live.png`。

- Symptom: 某些 SillyTavern 角色卡进入聊天后，首条 assistant 消息把 `## U1/U2/U3/U4` 或 `## P1/P2/...` 多个开头全部显示在一起。
  Cause: 卡片把多个编号开场打包在 `first_mes/opening_statement` 里，而不是规范写入 `alternate_greetings`；旧导入和开新对话逻辑只把整段 first_mes 当普通开场。
  Fix: `tools\ai_fengyue_local_server.py` 使用 `split_silly_first_mes_greetings()` 将 packed first_mes 拆为首开场 + `alternate_greetings`，`chat_greetings_from_card()` 在新对话启动时也动态拆存量卡并写入 assistant message `swipes`。存量线上卡修复前先用 SQLite backup API 备份。
  Verify: 2026-06-29 最终线上备份 `/opt/ai-fengyue-backend/data/ai_fengyue.sqlite3.bak-silly-openings-20260629-154616`；存量修复扫描 117 张有开场卡并修复 packed-opening 卡字段，补强后扫描 10 条旧会话首条 assistant 消息并更新 2 条为 12 个 swipe；`/tmp/verify_silly_opening_split_remote.py` 返回 `swipe_count=4`、`first_has_u2=false`、`next_swipe_has_u2=true`、临时数据清理为 0。

- Symptom: Prompt Template `<% if %>` / `<%- expr %>` 被跳过，或变量名为 `items` 时模板循环/变量保存异常。
  Cause: 模板 AST 白名单把内部生成的 `__out.append()` 代码也当用户代码二次校验，且 `TemplateDict` 的属性访问会和 Python `dict.items()` 等方法名冲突。
  Fix: 只对白名单用户表达式/语句做 AST 校验，内部拼接代码由编译器生成；`TemplateDict` 读键优先，但内部反序列化/遍历使用 `dict.items()`、`dict.values()`、`dict.get()` 避免方法名冲突。
  Verify: 2026-07-01 `D:\Anconda3\python.exe output\verify_tavern_template_local.py` 返回 `template_payload=true`、`world_injections=true`、`reply_postprocess=true`、`affinity=10`；线上远程 E2E 返回 `remote_template_payload=true`、`remote_reply=Hello 星月`、`remote_affinity=10`，临时数据清理为 0。

- Symptom: Prompt Template 世界书里调用 `injectPrompt("CoT", "...")`，但后续 Prompt Manager 的 `getPromptsInjected("CoT")` 读不到内容。
  Cause: 给世界书渲染临时加入 `world_info` 时复制了 `template_context`，`prompt_slots` 写进了副本，没有共享回本次生成的主上下文。
  Fix: `template_context_with_world()` 复制上下文时显式共享同一个 `prompt_slots` dict；世界书、Prompt Manager 和回复处理复用同次生成上下文。
  Verify: 2026-07-01 本地 `verify_tavern_template_local.py` 返回 `global_seen=yes`、`imported_regex=2`，线上假上游 E2E 返回 `remote_global_seen=yes`、`remote_reply=渲染前 10\n\nHello 星月\n\n渲染后 2`。

- Symptom: `/app/` 首页顶栏标题或筛选按钮文字看起来像透明/低对比，尤其是筛选按钮出现白底浅色字。
  Cause: 顶栏标题需要显式覆盖 `-webkit-text-fill-color`，而 `.segmented button` 没有清掉浏览器默认 button 背景/外观，导致部分环境使用默认白色按钮背景。
  Fix: `frontend/app/assets/css/app.css` 给 `.app-topbar h1` 设置实体白色 `color` 和 `-webkit-text-fill-color`，给 `.segmented button` 设置 `border:0`、`background:transparent`、`appearance:none`；首页 CSS cache-buster 更新为 `20260701-title-fix`。
  Verify: `D:\Anconda3\python.exe .\output\verify_home_title_color_browser.py` 返回 `title_ok=true`、`inactive_button_background_ok=true`、`console_error_count=0`，截图 `output/playwright/home-title-color-fix.png`。

- Symptom: 实际聊天回复里出现英文过程标题（如 `Processing Initial Inputs` / `Narrative Flow`）或 JSON 格式内容，带 Regex/TavernHelper 的角色卡更容易把这些内容渲染给用户。
  Cause: 上游流式解析曾把 `reasoning_content` 当正文拼接；系统提示没有明确禁止推理/JSON 输出；`process_model_reply()` 在 Prompt Template、世界书 render 注入和 Regex 后没有最终可见内容清洗。
  Fix: `tools/ai_fengyue_local_server.py` 忽略 `reasoning_content`，系统提示禁止推理/JSON/英文过程标题，并在 Regex 后调用 `normalize_visible_chat_reply()`；`frontend/app/assets/js/chat.js` 对 assistant 历史消息做同一展示级清洗，用户消息不清洗；`chat.html` cache-buster 为 `20260702-reply-format`。
  Verify: `D:\Anconda3\python.exe .\output\verify_reply_format_local.py` 通过；线上 `/tmp/verify_reply_format_remote.py` 返回并保存 `你好 星月`，无 JSON/Processing/reasoning/SECRET，临时用户/角色/消息清理为 0；`D:\Anconda3\python.exe .\output\verify_reply_format_browser.py` 返回 `bubble_text=你好，星月。` 且 console/page error 为 0。

- Symptom: Tavo `.thm` 主题本身是深色，但 AI星月高级渲染页看起来太亮，白字或浅色字看不见。
  Cause: 高级渲染 iframe 默认透明背景，且没有给 Tavo/SillyTavern 卡片脚本提供 `--SmartTheme*` 变量；卡片落到浅色 AI星月聊天皮肤或浏览器默认控件样式后低对比。
  Fix: 在 `frontend/app/assets/js/chat.js` 的 `buildSandboxSrcdoc()` 中给 sandbox `srcdoc` 的 `:root` 和 `<html style>` 注入深色 SmartTheme 变量，并给 iframe body、消息容器和默认表单控件设置深色可读兜底；`frontend/app/chat.html` cache-buster 更新为 `20260703-tavo-theme`。
  Verify: 本地和线上 `verify_tavo_advanced_render_browser.py`、`verify_tavo_sandbox_browser.py`、`verify_tavern_opening_render_browser.py`/`verify_tavern_opening_render_live.py` 通过；线上 `chat.js` 包含 `--SmartThemeChatTintColor:#222222`，目标页截图显示深色卡面白字可读，沙箱仍无 `allow-same-origin`。

- Symptom: 关闭 APK 下载/充值渠道后，首页仍可能显示“下载 APK”或“在线充值”旧文案。
  Cause: 首页和 App 壳会从 `/console/api/public/site-settings` 拉取后台运营配置，旧 `site_settings` 会覆盖静态 HTML 默认文案。
  Fix: `tools/ai_fengyue_local_server.py` 用 `APK_DOWNLOAD_ENABLED` 和 `PAYMENT_CHANNEL_ENABLED` 运行开关生成公开安全视图；关闭状态强制 Web App 入口、充值维护文案、空套餐和空订阅，Nginx `/download/` 返回 404。
  Verify: `verify_channels_closed_browser.py` 返回首页无 APK 链接/无在线充值文案，Rewards/Me/Dashboard 为维护态；公网 `/download/ai-xingyue-latest.apk` 返回 404，`deposit-meta` 返回 `mode=closed`。

- Symptom: `/app/` 首页默认随机排序时，点击“加载更多”可能追加重复角色、看起来没有加载新内容，或过早显示到底。
  Cause: SQLite `order by random()` 每次请求都会重新洗牌，分页 `offset` 不能稳定对应 page 1/page 2。
  Fix: 前端对 `sort=random` 生成同一轮搜索的 `seed` 并传给 `/go/api/explore/search`；后端用 `rowid` 和 seed 生成稳定伪随机排序，前端追加时按角色 id 去重。
  Verify: 首页浏览器验证中 page 1 后点击“加载更多”卡片数量增加且 id 不重复，console/page error 为 0。

- Symptom: 历史会话里点击某一条后像是“一次生成两个”或打开了同角色的另一条对话。
  Cause: 历史页旧链接只带 `app_id`，聊天页会按角色选择最新会话；同一角色存在多条历史时，点击指定历史行可能打开另一条最新会话。
  Fix: 历史页继续/复制后跳转统一使用 `/app/chat.html?conv_id=...`，`chat.js` 优先按 `conv_id` 加载会话；后端提供 `/console/api/web/conversations/{id}/copy` 复制消息、swipes、摘要和会话变量。
  Verify: 2026-07-05 线上临时用户 API 验证复制/删除成功；Playwright 验证历史页所有继续链接包含 `conv_id`，复制后跳到新的 `conv_id`，历史页复制行显示删除按钮。

- Symptom: 用户不确定聊天消息下方“删除”是单条删除还是上下文回溯。
  Cause: 原消息操作只有 `deleteMessage()`，后端 `/console/api/web/messages/{id}/delete` 只删除该单条消息，不会删除后续上下文。
  Fix: 保留“删除”为单条删除；新增“回溯”按钮和 `/console/api/web/messages/{id}/rollback`，删除目标消息及其后的同会话消息，刷新会话 `last_message` 并清理摘要。
  Verify: 2026-07-05 本地 Store 验证和线上真实 API 验证均返回 `deleted_count=2`、`remaining_count=2`、`summary_cleared=true`；移动端 Playwright 验证气泡全宽、回溯按钮可见、点击回溯后后续消息消失且 console error 为 0。

- Symptom: 历史会话列表只显示头像和按钮，标题/预览像是消失了。
  Cause: `.list-row` 是三列 grid，但历史页把头像和文字一起包进第一个 `<a>` 子元素，链接默认只占第一列头像宽度，文字被挤压截断。
  Fix: 给历史主链接加 `.history-row__main`，桌面跨 `grid-column: 1 / 3`，移动端跨整行；操作按钮保留在独立 actions 区。
  Verify: 2026-07-05 Playwright 移动端验证历史标题为 `桐生莉音中文摘要验证`、预览为 `历史页应该显示这条预览`，点赞/收藏/继续/复制/删除按钮均可见且 console/page error 为 0。

- Symptom: 部署后 AI星月后端启动失败，日志出现 `no such column: conversation_id`，通常发生在给旧 SQLite 表新增列并同时新增索引时。
  Cause: `create table if not exists` 不会给既有表补新列；如果初始化 `executescript` 里的 `create index` 先引用新列，迁移函数还没来得及 `alter table` 就会失败。
  Fix: 新列相关索引只能放到显式迁移函数里，在确认 `alter table ... add column` 完成后再创建；初始化脚本只保留老库一定存在的列索引。
  Verify: 2026-07-05 移除初始脚本中的 `chat_memories(conversation_id)` 索引，改由 `ensure_chat_memory_columns()` 迁移后创建；重新部署后 `ai-fengyue-backend.service` active，公网 `/health` OK。

- Symptom: 聊天回复可见内容里出现 `<thinking>`、`</thinking>`、`真正的思考截止`、`格式加强` 或 `<content>` 包裹格式，像模型把内部格式说明直接发给用户。
  Cause: 旧清洗只做非贪婪标签移除，遇到截图式嵌套/残缺思考标签或格式说明行时会留下内部文本；同时没有把 `<content>正文</content>` 解包为最终正文。
  Fix: `normalize_visible_chat_reply()` 和前端 `normalizeVisibleAssistantContent()` 先贪婪移除内部 XML 标签并处理未闭合标签，再解包 `<content>`，最后删除格式说明泄露行；如果清洗后没有可见正文则返回空字符串而不是回退原文。
  Verify: 2026-07-06 本地函数级断言覆盖 `<thinking>内部</thinking><content>你好 星月</content>`、未闭合 `<thinking>`、纯 `<content>` 和截图式格式泄露；`py_compile`、`node --check` 通过。

- Symptom: `/app/` 首页高级搜索打开后，关键词筛选行在宽屏或截图比例下横向溢出，右侧“无图模式”或按钮贴到容器外。
  Cause: `.advanced-search-grid` 早期使用固定 6 列，缺少关键词列/中屏换行约束；后续移动端又暴露 `.xy-input { width:100%; padding:... }` 没有稳定 `box-sizing:border-box`，会形成 `100% + padding` 溢出。
  Fix: `frontend/app/assets/css/app.css` 将高级搜索改为宽屏 `minmax(260px, 1.55fr) repeat(4, minmax(140px, 1fr)) minmax(170px, .85fr)`，中屏 `max-width:1320px` 降为 3 列并让关键词跨 2 列，移动端保持 2 列；toggle 文本设置 ellipsis；`.xy-input` 和高级搜索字段显式 `box-sizing:border-box`、`min-width:0`、`max-width:100%`。
  Verify: 2026-07-07 线上 Playwright `verify_password_reset_filter_browser.py` 在 2048/1180/390 宽度均返回 `outsideCount=0`、document 无横向 overflow，console/page error 为 0；390 宽度精确 DOM 断言所有 `.xy-input/input/select/toggle` 均未越过高级搜索面板。

- Symptom: 登录页重置密码时报 `api.sendPasswordResetCode is not a function`。
  Cause: 登录页已更新到密码重置视图，但浏览器仍可能缓存旧的 `/assets/js/api.js` 或旧的共享 API 模块，导致新增方法不存在。
  Fix: `frontend/app/assets/js/login.js` 对 `api.sendPasswordResetCode` 和 `api.resetPassword` 增加同源 `fetch` 兜底，并更新 `frontend/app/login.html` 的 `login.js` cache-buster。
  Verify: 2026-07-07 本地和线上 Playwright 将 `/assets/js/api.js` 模拟成缺少重置方法的旧模块，点击“发送”仍命中 `/console/api/password-reset/email`，无 TypeError、console/page error 为 0；线上 service/nginx active，公网 `/health` OK，`CONTENT_MODE=local_only`。

- Symptom: 移动端从角色详情返回首页后回到顶部，用户需要重新滚到之前点击的位置。
  Cause: 只在首页初始化时恢复滚动不可靠；移动浏览器 back/bfcache、`pageshow`、`focus`、`visibilitychange` 的触发顺序会让异步角色列表重新渲染后覆盖滚动位置。
  Fix: 首页点击角色卡时把筛选条件、卡片列表、点击角色 id 和 `scrollY` 写入 `sessionStorage`；返回时在 `pageshow`、`popstate`、`focus`、`visibilitychange` 和列表加载后重复尝试恢复，优先对点击卡片 `scrollIntoView`，成功后再清除恢复标记。
  Verify: 2026-07-07 线上移动端 Playwright 从 `/app/` 滚到 `650` 后点角色详情再返回，回到 `scrollY=645` 且点击卡片可见，console/page error 为 0。

- Symptom: 移动端浏览器小窗拖大、横竖屏切换或地址栏收起后，聊天页 Tavo/高级渲染内容停在左侧窄列，右侧大片空白，底部输入/生成状态位置也可能不跟随真实可视高度。
  Cause: Tavo `srcdoc` 缺少 viewport 和父子 frame resize 握手，卡片内联固定宽度会保留初始小窗宽度；移动端底部组件还使用固定 `100vh` 和固定 bottom 像素，无法跟随 `visualViewport`/safe-area 变化。
  Fix: `frontend/app/assets/js/chat.js` 的 `buildSandboxSrcdoc()` 注入 viewport、响应式根容器和直接面板 `width:100%!important`，父页面在 `resize/orientationchange/visualViewport` 事件向 `.tavo-frame` postMessage；`frontend/app/chat.html` 用 `--xy-visual-height`、`--xy-chat-input-bottom`、`--xy-chat-generation-bottom`、`--xy-chat-quick-bottom` 计算移动端高度和底部控件位置。
  Verify: 2026-07-07 本地和线上 `D:\Anconda3\python.exe .\output\verify_chat_resize_mobile.py` 通过，覆盖 390->740->980 resize、无横向溢出、Tavo iframe 内容随父容器扩展、输入/生成状态/快捷回复不重叠，console/page error 为 0。

- Symptom: 后台角色卡详情能看到世界书、Regex、extensions 等字段，但管理员在编辑弹窗粘贴这些字段后保存不生效。
  Cause: `/admin/api/apps/{id}` 使用 `local_app_to_card()` 返回完整 `extra_settings`，但旧 `update_admin_app()` 只保存基础列，没有把 rich 字段合并回 `local_apps.extra_settings`；`create_admin_app()` 也会丢掉 Character Card V2 的 `character_book` / `extensions.regex_scripts`。
  Fix: 后台 create/update 都调用 `normalize_admin_rich_app_payload()` 和 `normalize_user_app_extras()`，把 `alternate_greetings`、`world_info`、`regex_scripts`、`extensions`、`prompt_blocks`、`quick_replies`、`sampling` 等字段写入 `extra_settings`；后台列表搜索也包含 `id`。
  Verify: 2026-07-08 本地临时 SQLite create/update/readback 验证 world/regex/extensions 保存成功；线上临时官方卡 API create/update/readback 通过并清理；Playwright 验证后台 raw 编辑器可见且无 console/page error。

- Symptom: 部署角色卡短编号后，`ai-fengyue-backend.service` 显示 `active` 但 8008 端口未监听，Nginx 返回 `502 Bad Gateway`。
  Cause: 在服务启动路径里对 8785 张 `local_apps` 做全量补号迁移，HTTP server 要等初始化结束才监听；长迁移会让 systemd 先显示 active，但健康检查和公网请求失败。
  Fix: 不在 `Store.__init__()` 启动路径执行全量数据迁移；启动只补列和索引。存量数据用独立脚本/离线 SQL 先备份 DB 再迁移，业务代码只在新建卡时追加下一个 `display_id`。
  Verify: 2026-07-10 重新部署后日志立即出现 `listening on http://127.0.0.1:8008/`；`/health` 本地和公网均 OK；远程 DB `total=8785/with_display_id=8785/distinct_display_id=8785`。

- Symptom: 远程验证脚本用 `sqlite3 /opt/ai-fengyue-backend/data/ai_fengyue.sqlite3 ...` 读取管理员 id 时失败，SSH 输出 `sqlite3: command not found`。
  Cause: 线上 Ubuntu 环境未安装 `sqlite3` 命令行工具，但 Python 3 自带 `sqlite3` 模块可用。
  Fix: 远程 DB 只读探测改用 `python3 -c "import sqlite3; ..."`，或上传临时 Python 验证脚本执行。
  Verify: 2026-07-10 `output\verify_tavo_plugin_remote.py` 使用远程 Python 读取管理员 id 后，线上 `.tpg` 插件导入、启用、runtime fragment 验证和删除清理全部通过。

- Symptom: 点击“AI续写”报错，或只复述上一条角色回复。
  Cause: 旧入口复用了 regenerate/swipe，会排除上一条 assistant 并重新发送之前的 user 内容；只有开场白时甚至会产生空 user 输入。
  Fix: 2026-07-10 新增 `/console/api/web/chat/continue/stream`，把包含上一条 assistant 的完整历史和隐藏续写指令发给模型，并追加新的 assistant 消息。
  Verify: `output/verify_backend_mobile_reliability_local.py` 验证无新增 user 气泡、续写追加、扣费和重复回复保护；线上端点已部署。

- Symptom: 流式回复截断、切后台或切会话后，页面显示上一轮内容或旧会话内容。
  Cause: 前端 SSE 未要求 `message_end`，没有 AbortController/generation id；生成中 visibility 刷新会替换消息数组；流完成后消息 ID 变化还可能让 Alpine DOM 保留旧临时对象。聊天页同时使用 Alpine 自动 `init()` 与 `x-init`，初始化请求执行两遍。
  Fix: 2026-07-10 增加流结束完整性检查、请求取消和 generation/conversation token，生成中延迟对账，最终 `message_end.reply` 强制覆盖，使用稳定 `_localKey` 刷新消息，并移除 chat/explore 的重复 `x-init`。后端在截流时清理本轮消息/空会话且不扣费。
  Verify: 本地 RST 测试确认 user/assistant 不落库且积分不变；430x932 与桌面 Playwright 模拟缺少 `message_end` 时显示“连接提前中断”，无旧回复回写和浏览器错误。

- Symptom: 邮箱验证码提交慢、探索随机页像卡住不换内容。
  Cause: 验证码每次同步走 SMTP 建连/STARTTLS/登录；探索旧请求可覆盖新 seed，且首页曾双发无 seed/带 seed 请求。
  Fix: 2026-07-10 Resend 配置优先走 HTTPS API、失败回退 SMTP、最终失败删除验证码；探索使用同一 seed、AbortController + epoch，并提供“换一批”。
  Verify: 线上日志出现 `accepted verification email ... via Resend HTTPS`；线上 Playwright 连续换批卡片集合变化，`CONTENT_MODE=local_only` 保持不变。

- Symptom: PowerShell 5.1 执行由 UTF-8 no BOM 保存、且脚本内含中文绝对路径的 `.ps1` 后，把 `E:\酒馆开发\output` 解析成乱码目录并在错误位置写文件。
  Cause: Windows PowerShell 5.1 会按旧 ANSI 规则读取无 BOM 脚本；`apply_patch` 写出的 UTF-8 no BOM 中文字符串被误解码。
  Fix: 临时/自动化 PowerShell 脚本中的工作路径和输出文件名使用 ASCII，完成后再用当前 PowerShell 命令的 `-LiteralPath` 改成中文交付名；或明确使用能正确读取 UTF-8 no BOM 的 `pwsh`。
  Verify: 2026-07-10 角色卡导出并行下载的 24 个分段合并为 394936716-byte ZIP，SHA-256 与服务器 `f4336a98...ee1ac` 完全一致；乱码临时目录经绝对路径、文件数和总字节数检查后已清理。

- Symptom: 需要把全部官方角色卡交给第三方重做标签，但直接重新导入角色卡会重复建卡或覆盖非标签内容。
  Cause: `/admin/api/apps/import` 会生成新角色 ID，且角色名/display_id 不是业务关联主键；完整卡还包含世界书、Regex、Prompt、封面等不应随标签回填变更的字段。
  Fix: 使用 `tools/export_role_cards_for_tagging.py` 导出公开已发布 admin 卡；Manifest 将 `display_id` 映射到 `local_apps.id`。回传时先备份 DB 和 dry-run，只按 internal ID 完整替换 `local_apps.tags`。
  Verify: 2026-07-10 导出 8778 张公开官方卡，internal/display ID 均唯一；完整包与轻量标签包通过 ZIP CRC、Manifest、CSV、抽样 JSON 和 SHA-256 校验，用户卡和私有卡未导出。

- Symptom: 第三方回传角色卡 ZIP 后，文件名同时包含标准分类和三位 `√/✗`，直接按文件名拆标签会把 `NTR/NTL`、`人妻/熟女` 等组合标签错误拆开，或把能力标记混进分类标签。
  Cause: 文件名是给人核对的展开视图；无损标准标签在 `tag-overrides.filled.csv` 的 `new_tags_json`，三位标记依次是主开场白、顶层世界书、顶层正则，属于独立能力维度。
  Fix: 使用 `tools/import_role_card_annotations.py` 校验 ZIP/Manifest/卡 SHA/CSV/ID，按 filled CSV 覆盖 `local_apps.tags`；能力写入 `role_card_annotations`，且不更新 `local_apps.updated_at`，避免全库探索排序漂移。
  Verify: 2026-07-11 线上 dry-run 8778/8778、冲突 0；备份和 live DB `quick_check=ok`；6351 行标签实际变化、8778 标注写入，逐卡标签/标注 mismatch 均为 0；Explore/详情在 375/1440 宽度显示能力徽标且 console error 0。

- Symptom: Web App 页面刷新或点击导航后，会瞬间露出 Alpine 模板、字面 `\n`、旧文案或未加载的 `0` 统计；创作工坊标题甚至会持续显示 `\n`。
  Cause: Web 页面都有 `x-cloak`，但直接加载的 `frontend/app/assets/css/app.css` 没有 cloak 规则；工坊 fallback 又把换行写成双转义 `\\n`。页面同时使用 Alpine 自动 `init()` 与 `x-init="init()"`，会重复请求。
  Fix: 在 app.css 顶部定义 `[x-cloak]`，所有页面统一刷新 CSS cache-buster；运营设置读取时归一化字面换行；移除重复 x-init；workshop/info 用 ready 骨架，暖黑橙金 Hero 和暖纸统计卡统一主题。
  Verify: 2026-07-11 静态检查 15 个 cloak 页面、旧 CSS 版本 0、双转义 0、重复 x-init 0；线上 8 个页面刷新冒烟无字面 `\\n`/横向溢出/浏览器错误；工坊/信息中心 API 各请求 1 次，信息中心显示 8778 公开官方角色。
