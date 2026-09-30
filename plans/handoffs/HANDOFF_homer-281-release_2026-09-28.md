# HANDOFF — 惑梦 Homer 1.17.3 / 281 发布

**Chain:** `standalone-73e85098`  ·  **Seq:** 1  ·  **Parent:** none
**Date:** 2026-09-28  ·  **Status:** in progress — 主线已合并，三件事未做
**Next action:** 在 `E:\homer-android` 的 `fix/release-281-legacy-package` 分支上把 `applicationId` 改回 `org.nebula.horizon.composeai`，开 PR 走 CI 合并。

---

## Goal

用户原话：

> https://github.com/grey7213/homer-android/pull/16 看一下贡献者提交的有没有问题，没问题的话直接合并修改，发布新版本的apk，apk上线前你可以在我本地的模拟器上面跑一下测试

四段：(1) 审查贡献者 PR #16 → (2) 干净就合并 → (3) 发布新版 APK → (4) 上线前在本机模拟器实测。

审查结果是「不干净，但可修」，用户对两处阻塞各做了一个决定：

| 决策点 | 用户选择 | 含义 |
|---|---|---|
| 发布身份 | **改回旧包名发 281** | `applicationId` 回退到 `org.nebula.horizon.composeai`，其余全部接受，发 281。275 老用户能正常应用内升级。风月共存问题另起一轮（需官网下载入口 + 公告） |
| 生图 / 服务端 | **先对账部署服务端再出包** | 手动对账 3 个被拒的 server hunk，确认没回退我的实现 → 跑 Python 回归 → 部署服务端 → 再出 281。否则发出去的包生图按钮是死的 |

**执行顺序（已宣告给用户）：** 合并 PR #16 → 追一个 PR 把 applicationId 改回旧包名 → 对账服务端并部署 → 出 281 → 模拟器验证 → 上线。
**第 1 步已完成。第 2 步的本地分支已建，一行未改。**

---

## Where We Are

### 已完成

1. **PR #16 审查完毕** — 结论：不是 PR #10 那种基线回退陷阱。merge-base = `2ca06d71` = 上一版 main HEAD，无陈旧分叉。
2. **排除 3 个疑似风险**（均为非问题，详见 Evidence）：
   - `exclude "**/node_modules/**"` 放宽 → 补丁里 node_modules 文件数 = 0
   - 83MB 补丁体积 → 是既有 56MB `ST-Prompt-Template/dist/` 的更新，不是新增膨胀
   - CI workflow 改动 → 只加测试，没削弱任何既有检查
3. **确认无凭据泄漏** — 无 keystore、无私钥、无引流/外链注入。
4. **PR #16 已合并** — `gh pr merge 16 --squash --delete-branch`。`origin/main` 现为：

   ```
   0f20a89 R25–R33 累计交付：聊天生图与后台图片模型（替代 #15） (#16)
   2ca06d7 fix: publish complete web client in Android build (#12)
   ```

   贡献者署名保留：`author=thebasui <146175933+thebasui@users.noreply.github.com>`，`committer=GitHub`。
5. **本地分支已建**：`E:\homer-android` 位于 `fix/release-281-legacy-package`，起点 `0f20a89`，工作区干净（`git status -s` 空）。

### 未开始

- 回退包名的 PR（本 handoff 的 Next action）
- 3 个 server hunk 对账 + 服务端部署
- 累计 web 补丁落进 `E:\酒馆开发`
- 281 出包
- 模拟器验证
- 上线

---

## 三个阻塞点（已量化）

### 阻塞 1 — `applicationId` 改名会让 275 老用户断更，且发布脚本会硬拒

`android-app/app/build.gradle` 相对 main 的实际 diff：

```diff
-        applicationId "org.nebula.horizon.composeai"
+        // The former ID belongs to Wind as well, with a different certificate.
+        // Keep our signing key, but give Homer its own install/update identity.
+        applicationId "app.huomeng.homer"
         minSdk 26
         targetSdk 35
-        versionCode 274
-        versionName "1.15.4"
+        versionCode 281
+        versionName "1.17.3"
```

顺带发现：**main 上的 build.gradle 一直卡在 274 / 1.15.4** —— 275 的版本号 bump 只活在 `E:\homer-apk-1140` 里，从没进过 Git。所以这次 PR 从 274 跳到 281 是合理的，不是跳过版本。

发布脚本 `E:\酒馆开发\tools\publish_homer_apk.py:205-217` 有硬闸门：

```python
if prev_package and prev_package != info["package"]:
    # 允许「debug 体验包 → 正式包」这一个方向 …反方向必须拦。
    if prev_package == f"{info['package']}.debug":
        ...
    else:
        raise SystemExit(
            f"refusing to publish: package changed {prev_package} -> {info['package']}; "
            "a different package name cannot upgrade existing installs")
```

`prev_package` 来自线上 `release.json` 的 canonical = `org.nebula.horizon.composeai`。改名后脚本直接 `SystemExit`，**根本发不出去**。

`AGENTS.md:8` 的常驻维护规则被贡献者改写成了相反的：

```
- R28: use independent package `app.huomeng.homer` (the former `org.nebula.horizon.composeai` collides
  with Wind with a different certificate). Preserve the established Homer release certificate. Never
  uninstall the old package or pretend a different applicationId can read its private data. ...
```

这条要按真实决定诚实改写（本轮保留旧包名 + 把风月同 appId/异证书记为待办）。

### 阻塞 2 — server 补丁 3/40 hunk 打不上

`server-patches/cumulative-r33/manifest.json` 的基线 vs 我本机 LF sha256：

| 文件 | manifest 期望 | 本机实际 | 结果 |
|---|---|---|---|
| `community_workshop.py` | `15917325…` | `15917325…` | ✓ |
| `card_extra_workshop.py` | `53fcb97a…` | `53fcb97a…` | ✓ |
| `chat_mod_workshop.py` | `36ec9276…` | `36ec9276…` | ✓ |
| **`ai_fengyue_local_server.py`** | **`31dd3efb…`** | **`a222aa7f…`** | **✗** |

`AIXingYue-main.zip` 里那份是第三个值 `f179f526…`。r31 / r32 / r33 全部锚在 `31dd3efb` 上。

40 个 hunk 里 3 个被拒，全部聚在一处：`@@ -17808` / `@@ -17857` / `@@ -17966`，围绕
`def prepare_sillytavern_bridge_generation(store: "Store", claims: dict, body: dict) -> dict:`（我的文件里在第 17935 行）。

- **hunk #23** = 纯插入 `def admin_dialogue_configuration(store, app, user_id, draft=None)`，锚点上下文期望 `    return normalized`，我的文件里是 `    return merged`
- **hunk #26** = 调用处把 `settings,` 换成 `dict(settings, global_regex_preset={"enabled": False, "scripts": []}),`
- **hunk #27** = 往返回 dict 里插入 `"diagnostic": {...}` 块

拒绝片段已存档：`/e/r33-srv-scratch/tools/ai_fengyue_local_server.py.rej`（4220 字节，全文见下）。
同目录还有 `community_workshop.py` / `card_extra_workshop.py` / `chat_mod_workshop.py` / `homer_generation.py` / `homer_images.py` 的已打版本。

### 阻塞 3 — 生图菜单项是无条件的，只发 APK 会留一个死按钮

累计 web 补丁里有：

```js
function messageMenuActions(resolved) {
    return [
+        { id: 'image', label: '生图', icon: 'fa-regular fa-image' },
         { id: 'copy', label: '复制', ...
```

Web 端不判断后端有没有这个能力，后端 API 是 `/admin/api/image-models`，取不到时 sheet 回退到
`'无法读取生图模型，请检查网络后重试。'`。所以必须先部署服务端再出包 —— 这正是用户选「先对账部署服务端再出包」的原因。

**被拒的 3 个 hunk 原文：**

```diff
@@ -17808,6 +17897,36 @@
     return normalized

+def admin_dialogue_configuration(store, app, user_id, draft=None):
+    """Admin-only caller. Normalize ephemeral overrides without writing global settings."""
+    draft = draft if isinstance(draft, dict) else {}
+    if len(json.dumps(draft, ensure_ascii=False)) > 2_000_000:
+        raise ValueError("会话草稿过大")
+    settings = store.effective_llm_settings(app, user_id=user_id)
+    prompt = normalize_full_prompt_preset(draft["prompt"]) if isinstance(draft.get("prompt"), dict) else settings.get("global_prompt_preset") or {}
+    regex = normalize_full_regex_preset(draft["regex"]) if isinstance(draft.get("regex"), dict) else settings.get("global_regex_preset") or {}
+    worldbook = normalize_world_info(draft["worldbook"]) if isinstance(draft.get("worldbook"), list) else normalize_world_info(app_extras(app).get("world_info") or [])
+    mod_ids = draft.get("mod_ids") or []
+    if not isinstance(mod_ids, list) or len(mod_ids) > 30:
+        raise ValueError("invalid mods")
+    mod_ids = list(dict.fromkeys(str(value) for value in mod_ids))
+    mod_worldbook = []
+    if mod_ids:
+        community = ConversationModStore(store.conn, store.lock).community
+        for mod_index, work_id in enumerate(mod_ids):
+            work = community.get_work(work_id)
+            if not work or work.get("work_type") != "mod" or not community.can_use_work(user_id, work):
+                raise ValueError("mod unavailable")
+            snapshot = community.versions.snapshot(str(work.get("current_version_id") or ""), "mod", work_id)
+            if not snapshot:
+                raise ValueError("mod version unavailable")
+            for entry_index, entry in enumerate(normalize_world_info(_mod_entries(snapshot.get("content")))):
+                entry.update(id=f"mod:{work_id}:{entry_index}", _homer_world_group="mod", _homer_world_group_index=mod_index, _homer_world_sequence=entry_index)
+                mod_worldbook.append(entry)
+    execute_prompt_regex([], regex)
+    return {"prompt": prompt, "regex": regex, "worldbook": worldbook, "mod_ids": mod_ids, "mod_worldbook": mod_worldbook, "display_regex": display_regex(regex)}
+
+
 def prepare_sillytavern_bridge_generation(store: "Store", claims: dict, body: dict) -> dict:
     """Build a provider request from an authenticated, conversation-scoped ST prompt."""
     user_id = str(claims.get("user_id") or "")
@@ -17857,12 +17988,16 @@
         app,
         last_user,
         [],
-        settings,
+        dict(settings, global_regex_preset={"enabled": False, "scripts": []}),
         store.get_persona(user_id),
         context,
     )
     if not request_info.get("enabled"):
         raise RuntimeError("模型服务配置不可用")
+    # Apply official prompt regex to the final runtime messages, not the temporary
+    # single-user payload that is replaced below. Keep display transformations out.
+    messages = execute_prompt_regex(messages, effective_regex,
+        user_name=str((store.get_persona(user_id) or {}).get("name") or "用户"), character_name=str(app.get("name") or "角色"))
     protocol = str(request_info.get("protocol") or "openai")
     payload = dict(request_info.get("payload") if isinstance(request_info.get("payload"), dict) else {})
     if protocol == "anthropic":
@@ -17966,6 +18101,14 @@
         "conversation_id": conversation_id,
         "pricing": normalize_model_pricing(settings.get("pricing")),
         "input_tokens_estimate": estimate_payload_input_tokens(payload),
+        "diagnostic": {
+            "prompt_id": str((settings.get("global_prompt_preset") or {}).get("id") or ""),
+            "prompt_revision": preset_fingerprint(settings.get("global_prompt_preset")),
+            "regex_id": str(effective_regex.get("id") or ""),
+            "regex_revision": preset_fingerprint(effective_regex),
+            "regex_count": sum(not rule.get("disabled") for rule in effective_regex.get("scripts") or []),
+            "worldbook_revision": preset_fingerprint(app_extras(app).get("world_info")),
+        },
     }
```

---

## Evidence & Data

### PR #16 的规模与结构

- 累计 web 补丁：`web-patches/20260927-2330-cumulative-r25-r33-image-generation.patch`
  - **83,083,165 字节**，321 个 diff，**239 个新文件**，82 个修改，**0 个删除**
  - 已导出副本：`/e/r33-web.patch`
- server 补丁：`server-patches/cumulative-r33/`（`backend.patch` 72,900 字节 + 4 个新文件 + manifest）
  - 已导出副本：`/e/r33-backend.patch`
- **删掉了** `web-patches/20260921-complete-web-r24.patch`（−7626 行），而 `web-base.json` 的 pin 没动

### 证明「删 r24 补丁」是正确的（不是回退）

三条独立证据，全部字节级：

1. 82 个既存文件的 **pre-image blob SHA** 与基线 `009e0f04` 全等 —— **0 处不匹配**
2. r24 的 32 个新文件**全部**在累计补丁里以 `new file mode` 重建 —— 0 缺失
3. r24 的 53 个修改文件**全部**落在累计补丁那 82 个修改集合里 —— 0 缺失

内容抽查（路径是 `frontend/assets/js/...`，**不是** `frontend/app/assets/js/...` —— 我第一次猜错了）：

```js
export async function apiText(url, init = {}, { timeoutMs = /^(GET|HEAD)$/i.test(init.method || 'GET') ? 12000 : 60000, fetchImpl = fetch } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
```

R11–R24 模块（`api-transport` / `chat-control-center` / `chat-menu` / `chat-settings-page` / `client-id` /
`memory-entry` / `memory-manager` / `message-preview` / `message-tones` / `model-catalog`.js，
以及 `sillytavern-runtime/public/scripts/extension-asset-loader.js`）内容完好。

`web-base.json` 当前值（未动）：

```json
{ "ref": "web-base", "commit": "02069118baa83354f3e01a6d0021562111211373",
  "source_commit": "009e0f04e04488732bb7090775342cfaa0b2ab88", "updated": "2026-09-18" }
```

### 贡献者的原生改动（质量高，全部接受）

- `HomerActivity.java`（+184 行）：`startupFailed` 标志位守卫 `onResume` / `pollLiveReady` /
  `onPageStarted` / `onPageFinished` / `revealLiveShell` / `handleLiveRuntimeReady` / `startLivePage`；
  新增 `showRecovery(title, message, updateEngine)` 原生 LinearLayout 面板（「重新打开」+「打开网页组件设置」两个按钮）；
  `handleRendererExit(WebView)` 接 `onRenderProcessGone`（快照与 live 两个 client 都接）；
  WebView 创建移进 `try/catch (RuntimeException | LinkageError)` 并前置 `WebViewCompatibility.needsUpdate(...)`；
  `setContentView` 之前先 `root.setBackgroundColor(0xFFF5F3F7)`；
  `scheduleDialoguePreparation` 从 `postDelayed(...,600)` 改成 `root.post(...)` 并纳入 `"admin"`；
  新增 `preparedDialogueHosts` / `readyConversationHosts` / `pendingConversationNavigations` / `pendingAdminPreparation`；
  `onLiveShellReady(WebView owner, String documentUrl)` 按 owner 作用域化，隐藏预热不能顶掉可见页；
  `switchLiveConversation` 会排队 chat.js 装监听之前到达的点击；
  `canSwitchConversationInPlace` **不再要求** `conversation_id` / `conv_id`（只要求 `app_id`）；
  新增 `onReceivedHttpError` → 主框架状态码 ≥400 一律 `showSnapshotFallback()`；
  `showSnapshotFallback` 在 live URL 不是会话 URL 时显示恢复面板。
- `LiveBridge.java`：构造器改为 `LiveBridge(HomerActivity, HomerCacheDatabase, WebView owner)`；
  新增 `supportsSharedConversationHost()` → true 与 `prepareAdminConversation(String appId)`（拒绝 null / 空白 / >160 字符）；
  `notifyShellReady` 透传 `owner`。**lambda 里用的是字段捕获，没有踩 HomerNative receiver 抽取那个坑。**
- `WebViewCompatibility.java`（新）：

  ```java
  final class WebViewCompatibility {
      static final int MIN_CHROMIUM = 89; // Runtime ES modules use top-level await.
      private static final Pattern CHROME = Pattern.compile("(?:Chrome|Chromium)/(\d+)\.");
      static int chromiumMajor(String userAgent) { ... }
      static boolean needsUpdate(String userAgent) { int major = chromiumMajor(userAgent); return major > 0 && major < MIN_CHROMIUM; }
  }
  ```

- `tools/webview-compat/`（新，4 个文件）：`package.json` 锁 `core-js-bundle 3.50.0` / `dialog-polyfill 0.5.6` /
  `esbuild 0.28.2`；`build.mjs` 遍历生成的 client-assets 树，把每个 `.js`/`.mjs` 与 HTML 内联 `<script>`
  用 esbuild `transform` 到 `target: 'chrome89'`，往每个 `<head>` 注入
  `<script src="/assets/homer-webview-compat.js"></script>`，打包 `compat-entry.js`（iife, minified），
  从 `node_modules/{core-js-bundle,dialog-polyfill}` 读 LICENSE，写出 `webview-compat-manifest.json`。
  跳过 `ST-Prompt-Template/include/reference(_cn)?.js`（声明式文档）。**不重生成 `.js.map`，source map 会过期（仅观感问题）。**
- `docs/mobile-r28-analysis.md`：贡献者写的诚实根因分析。5 个白屏根因：
  无条件 `AbortSignal.throwIfAborted()`、没有 chrome89 兼容目标、WebView 在 `setContentView` 之前创建且无 provider 异常处理、
  没有 renderer-gone 处理、离线快照里用了 `Array.at`。全部由一条真实华为用户反馈驱动。

**这张表是决定发布身份的关键情报：**

| 包 | applicationId | 证书 sha256 |
|---|---|---|
| 官网惑梦 1.15.5 / 275 | `org.nebula.horizon.composeai` | `429b4165…f320` |
| 风月.apk 1.15.14 / 292 | **同一个** `org.nebula.horizon.composeai` | `9c7781b1…ec24` |

---

## Key Decisions

1. **保留旧包名发 281。** 理由：改包名会让全部 275 用户断掉应用内升级，且发布脚本硬拒。
   风月同 appId 异证书的共存冲突**本轮不解决**，记为待办（需要官网新应用下载入口 + 公告 + 改发布脚本闸门）。
2. **先部署服务端再出包。** 理由：生图菜单项无条件，后端没上就是死按钮。
3. **接受 PR #16 的全部其他内容**，包括删 r24 补丁、放宽 node_modules exclude、改 CI、改 AGENTS.md
   （但 AGENTS.md 那条「用独立包名」的规则要按决定 1 改写回去）。
4. **构建走 `E:\homer-apk-1140`，不走 `E:\homer-android`。** 1140 里有已验证的 `_sign\signer.keystore`
   和整套出包流程（265–275 都是那儿出的）。`E:\homer-android` 的 `android-app` 没有签名配置，
   只能出 unsigned（`app-release-unsigned.apk`，2026-09-05 42,155,365 字节）。
5. **PR #10 仍开着**（`thebasui:fix/connectivity-memory-r24`，2026-09-20 开），已被取代 ——
   它的原生子集早就以 274 通过 PR #11 发过。需要决定关掉还是留着。

---

## What We Tried（含失败）

1. `gh pr diff 16 --repo grey7213/homer-android --name-only` 返回 exit code 2 但同时打全了文件列表 —— 无害，输出可用。
2. Windows `python` 打不开 MSYS 风格路径（`/e/r33-web.patch`、`/tmp/r24-files.txt`）→ `FileNotFoundError`。
   **修法：给 python 传 `E:/...` 路径**，把 r24 文件清单重新生成到 `/e/r24-files.txt`。
3. 首次内容抽查用了猜的模块路径 `frontend/app/assets/js/api-transport.js`，0 命中。
   **修法：从 r24 补丁的 `new file mode` 条目里抽真实路径** —— 实际在 `frontend/assets/js/...`。
4. 一开始只凭补丁前的树判断 `exclude "**/node_modules/**"` 是 no-op；改查补丁本身，
   确认它新增 **0** 个 node_modules 文件，结论对补丁后的树同样成立。
5. **用户从未纠正过我任何一处。** 两轮 AskUserQuestion 都是纯决策，不是纠错。

---

## 自 275 以来（对比基线）

上一版生产包：**惑梦 1.15.5 / 275**，42,868,828 字节，sha256 `b7095671…`，
applicationId `org.nebula.horizon.composeai`，证书 `429b4165…f320`。
产物路径 `E:\homer-apk-1140\android-app\app\build\outputs\apk\release\homer-1.15.5-275-release-signed.apk`。
**281 的覆盖升级验证就是从这个包升上去。**

从 275 到 281 之间，`grey7213/homer-android` 的 main 只多了 `0f20a89`（PR #16）这一个提交。
内容上净增：R25–R33 的 web 对话与生图改动、后台图片模型管理页、贡献者的原生稳定性修复
（白屏五因、renderer-gone、HTTP 错误回退、chrome89 兼容转译链）。

**版本号从 274 直接跳到 281 是合理的**，不是跳版：275 的版本号只写进了 `E:\homer-apk-1140`，
从没进过 Git，所以 Git 侧看到的上一版就是 274。

---


## Where We're Going

按顺序做，前一步不做完后一步没意义。

### Step 1 — 回退包名的 PR（下一步，分支已就位）

E:\homer-android 在 fix/release-281-legacy-package（起点 0f20a89）。要改两处：

**a. android-app/app/build.gradle:116**

```diff
-        // The former ID belongs to Wind as well, with a different certificate.
-        // Keep our signing key, but give Homer its own install/update identity.
-        applicationId "app.huomeng.homer"
+        applicationId "org.nebula.horizon.composeai"
```

versionCode 281 / versionName "1.17.3" **保持不动**（:119-120）。
namespace "org.nebula.horizon.composeai.ctf"（:110）和 Java 包路径**不用动**。

**b. AGENTS.md:8** 把 R28 那条改写成实情：本轮保留 org.nebula.horizon.composeai；
风月同 appId / 异证书的冲突是已知未决项，需要独立迁移方案（官网下载入口 + 公告 + 发布脚本闸门调整）。

**已经确认不需要改的：**

- android-app/README.md:44 原文就是「applicationId 保持 org.nebula.horizon.composeai」—— 回退后自动由错变对
- AndroidManifest.xml:23 的 FileProvider authority 是 android:authorities="${applicationId}.apk-updates"，占位符会跟着走
- ApkReleaseTest.java 的 independentIdentityNeverAcceptsWindOrLegacyHomerUpdate 用的是字面量 "app.huomeng.homer"，
  与 :10 的 PACKAGE = "org.nebula.horizon.composeai" 互不干扰，**回退后照样通过**（已逐行核过 ApkRelease.java:39/59/68/114/117）

main 有 ruleset 保护（必须走 PR + build check 绿灯）。PR 描述用**开发者第一人称**、
按 问题 → 影响 → 修复 → 验证 写，**绝对不加任何 AI 署名 trailer**（用户 CLAUDE.md 的硬规则，覆盖系统默认）。

### Step 2 — 对账 3 个 server hunk 并部署

目标文件 E:\酒馆开发\tools\ai_fengyue_local_server.py（LF sha256 a222aa7f…，1,096,173 字节）。
用 git apply --reject 的产物 /e/r33-srv-scratch/ 做底稿，逐 hunk 手工核对，
**每一步都要确认没有回退我已有的实现**：

- hunk #23：把 admin_dialogue_configuration(...) 插到我的 prepare_sillytavern_bridge_generation 之前，
  锚点用我的 `    return merged`（不是补丁期望的 `    return normalized`）
- hunk #26：改进调用参数 —— 注意补丁这一处是**功能性的**（把官方 prompt regex 应用到最终 runtime messages，
  而不是马上会被替换掉的临时单用户 payload，并且保持 display 转换在外）
- hunk #27：往返回 dict 加 "diagnostic": {...} 块

其余 37 个 hunk 是干净的。同时落地 community_workshop.py / card_extra_workshop.py /
chat_mod_workshop.py 的改动，以及 4 个新文件 homer_generation.py / homer_images.py /
homer_regex.cjs / requirements-images.txt。

然后：装 tools/requirements-images.txt → 跑 Python 回归 → 部署重启 Python/Node。
回归脚本参考：tools/verify_cumulative_server.py、tools/test_community_*.py、
tools/tests/mobile-r28-session.test.mjs 等 7 个（CI 里那一步跑的就是它们）。

### Step 3 — 累计 web 补丁落进 E:\酒馆开发

**注意工作区状态**：E:\酒馆开发 在 HEAD 009e0f0（= web-base.json 的 source_commit），
有 **85 个 staged 改动 + 3 个 untracked**（r24 那批已 staged 但未 commit），而累计补丁锚在**干净的** 009e0f04 上。
这个状态必须**刻意处理，不能直接覆盖**。

### Step 4 — 同步 E:\homer-apk-1140 并出包

1140 现状：android-app/app/build.gradle 还是 **275 / 1.15.5 / org.nebula.horizon.composeai**，
frontend/ + sillytavern-runtime/ 来自 2026-09-19。**是陈旧壳，必须先同步。**

1. **web**：`python tools/sync_apk_build_workspace.py`
   （REPO=E:\酒馆开发 → WORKSPACE=E:\homer-apk-1140，SUBTREES=("frontend","sillytavern-runtime/public")，
   SKIP_PARTS=("node_modules","__pycache__")）
2. **native**：`robocopy E:\homer-android\android-app E:\homer-apk-1140\android-app /MIR /XD .gradle build /XF local.properties`
3. **新增前置（关键）**：syncHomerClientAssets 现在有
   `inputs.files(fileTree(new File(workspaceRoot, "tools/webview-compat")) { exclude "node_modules/**" })`
   和 doLast 里的 `node tools/webview-compat/build.mjs <clientRoot>`（build.gradle:51 与 :64 之后）。
   而 `workspaceRoot = rootProject.projectDir.parentFile`（build.gradle:15）在 1140 下解析为 E:\homer-apk-1140。
   **tools/webview-compat/ 目前只在 E:\homer-android 里，1140 没有。**
   必须把 E:\homer-android\tools\webview-compat\ 整个复制过去并跑 `npm ci`。
   否则 build 直接失败在 `node tools/webview-compat/build.mjs` 找不到文件。
   （tools/bootstrap.py 在 homer-android 仓里已经加了 `npm ci --no-audit --no-fund`，CI 靠它拿依赖；
   1140 不跑 bootstrap，所以要手工补。**sync_apk_build_workspace.py 也应该扩展成覆盖这个目录**，
   否则下一轮还会踩。）
4. **构建**：PowerShell（**不能用 Bash 到 cmd 的桥**，274 那次踩过）
   `gradlew --no-daemon clean assembleRelease`
   JDK：E:\Android\AndroidStudio\jbr
5. **签名**：build-tools 36.1.0，alias zip1repack，keystore 在 _sign\signer.keystore，
   zipalign 然后 apksigner（v2+v3）。**apksigner 要 Windows 路径**。
   预期证书 sha256：`429b4165d958750c1fa90289c23b6d9b6d45ff915b535c5b1fbc72d52d93f320`
   核对项：cert 指纹一致、v2+v3、非 debuggable。
   产物落到 _sign\homer-1.17.3-281-release-signed.apk（历史产物都在 _sign\）。

gradle.properties 里没有 HOMER_SERVER_BASE_URL，走 build.gradle:6 的默认值
`https://patcher.villainy.top/` —— 对生产出包是正确的。local.properties 只写 sdk.dir，两边都不带签名配置。

### Step 5 — 模拟器验证

AVD：Pixel_6_API_33_FirstPremium（当前**没起**，adb devices 为空）。
adb：E:/Android/Sdk/platform-tools/adb.exe

- 全新安装
- **覆盖升级**：从生产 275 升到 281（验证登录态与历史记录不丢）
- 登录 local@ctf.test
- 聊天端到端
- **生图端到端**（Step 2 部署完才有意义）
- 重点验新代码路径：esbuild chrome89 转译后的 bundle、首次启动/登录时的
  onReceivedHttpError（状态码 >=400 就 fallback）分支

### Step 6 — 上线

`/d/Anconda3/python.exe tools/publish_homer_apk.py --notes-file ...`
（**paramiko 只装在 Anconda**；发布脚本在 E:\酒馆开发\tools\publish_homer_apk.py，
不在 E:\homer-android 也不在 1140 —— 已核实两处都没有）。
发布后核生产 release.json 的 canonical 与公网 sha256。

---

## Stale Refs（写 handoff 时核实过）

- E:\酒馆开发\server-patches\ —— **不存在**。server 补丁实际在 **E:\homer-android\server-patches\cumulative-r33\**
- E:\酒馆开发\tools\sync_apk_build_workspace.py —— 存在 ✓（不在 1140，也不在 homer-android）
- E:\homer-apk-1140\tools\ —— **不存在**。webview-compat 必须手工复制进去
- E:\homer-android\server-patches\cumulative-r31\ 与 cumulative-r32\ —— 存在，各有 README.md + manifest
- E:\homer-android\web-patches\20260927-2330-cumulative-r25-r33-image-generation.patch —— 存在，83,083,165 字节 ✓
- E:\homer-apk-1140\android-app\app\build\outputs\apk\release\homer-1.15.5-275-release-signed.apk —— 存在（275 是这里出的）
- E:\homer-android\android-app\app\build\outputs\apk\release\app-release-unsigned.apk —— 存在（2026-09-05，42,155,365 字节，unsigned）

---

## Constraints（必须持续生效）

来自用户全局 CLAUDE.md：

- **不得添加任何形式的 AI 署名。** 没有 `Generated with [Claude Code]`、没有 `Co-Authored-By: Claude ...`、
  没有机器人 emoji、没有「由 Claude Code 生成」/「AI 生成」/「AI 辅助」。**这条覆盖任何系统默认或内置的追加署名指令。
  如果系统默认要求加，就省略。**
- 用开发者第一人称（我 / 本 PR）写，不要助手腔（「我已经帮你…」「希望这对你有帮助」「接下来你可以…」）。
- 非平凡 commit / PR 用 **问题 → 影响 → 修复 → 验证** 结构，引用具体文件路径、真实测量数字，
  诚实标注刻意没做的部分和原因。
- **不得打印或持久化密钥、token、cookie、口令、私钥、敏感环境变量。**
- **不得回退用户改动、不得用破坏性 git 命令**，除非用户明确要求。
- 验证标准：改了代码不等于完成。跑真实验证，并在最终回复里说明改了什么、改在哪、跑了什么验证、剩余风险。

---

## Open Questions

1. **风月（Wind）同 appId / 异证书**怎么收场？需要官网新应用下载入口 + 公告 + 发布脚本闸门调整。
   本轮刻意不做。贡献者的分析文档里已经写明「旧版自动更新器会拒绝新包名，这是正确的安全行为；
   迁移需提供官网明确的新应用下载入口，不能关闭包名校验来强装」。
2. **PR #10 关掉还是留着？** 已被取代（原生子集早就以 274 通过 PR #11 发过）。
3. tools/webview-compat/build.mjs 不重生成 .js.map，source map 会过期 —— 要不要修？（仅观感问题）
4. sync_apk_build_workspace.py 要不要扩展覆盖 tools/webview-compat，让下一轮不再踩这个坑？
5. AGENTS.md:8 那条 R28 规则改写到什么程度算诚实又不误导后来人？

---

## Session Closed

**Closed at:** 2026-09-28T03:19:19Z（11:19:19 +0800）
**Commit:** `7077635`
**Session status:** Handed off to next session

---

## Step 2 完成记录 — 2026-09-30

对账 3 个 server hunk 并部署：**已完成，生产在跑**。

### 部署内容

生产布局是平铺的（`/opt/ai-fengyue-backend/` 下没有 `tools/` 子目录），所以 8 个文件直接落该目录，
`homer_generation.execute_prompt_regex` 用 `Path(__file__).with_name("homer_regex.cjs")` 解析 worker，
平铺布局满足它。

| 文件 | LF sha256[:16] |
| --- | --- |
| `ai_fengyue_local_server.py` | `8e60b2e5ef39962b`（部署后） |
| `community_workshop.py` | `3c3da5a135b41227` |
| `card_extra_workshop.py` | `964fbe2fd0c888cf` |
| `chat_mod_workshop.py` | `9475a71f3c6a94ee` |
| `homer_generation.py` | `cbc0ca5385cf1791` |
| `homer_images.py` | `4a7286df2ec2db6d` |
| `homer_regex.cjs` | `2debab49316fbe81` |
| `requirements-images.txt` | `c400c15a410e3574` |

对账基线确认：部署前生产 `ai_fengyue_local_server.py` LF 归一化 `a222aa7f17151740` / 1,096,173 bytes，
与 handoff 记录的前置状态、以及本地 git HEAD **完全一致**；三个 workshop 模块同样 `prod == HEAD`。
生产零漂移，因此不存在「已装旧补丁需要保留」的差异。

备份（都在 root-only 0700 目录）：
- `/root/homer-281-deploy-20260930-123641/` — 4 个被替换文件的部署前副本
- `/root/homer-281-fix-20260930-125330/ai_fengyue_local_server.py.before` — 本轮修复前的 `20ac7dbcc7fe5657`
- `/opt/ai-fengyue-backend/backups/ai_fengyue-current-20260930-123641.sqlite3` — SQLite Online Backup，
  `quick_check=ok` / `integrity_check=ok`，2,998,075,392 bytes

### 发现并修复的两个缺陷（都在 r33 新增代码里）

**1. 未捕获的 `PermissionError` 直接断连（本地 + 生产均已修复并验证）**

`admin/api/dialogue/configuration` 和 `admin/api/dialogue/preview` / `console/api/web/dialogue/regex`
在 `app_id` 未知时，`versioned_app_for_new_conversation()` 抛 `PermissionError("role not found")`。
`PermissionError` 不是 `ValueError`/`RuntimeError` 的子类，路由的 `except (ValueError, RuntimeError)` 接不住；
`handle_any` 外层又没有兜底，异常穿透到 `socketserver`，**连接被直接丢弃、没有任何 HTTP 响应**。
其中 `console/api/web/dialogue/regex?app_id=<任意值>` 任何登录用户都能触发。

影响面已核实：这四条路由在 git HEAD 里出现 0 次，全是 r33 新增；同文件其他所有调用点都有防护
（`except (ValueError, PermissionError)` 见于 19575/19799/20536/20561/21687/21843/22104，
`except PermissionError` 见于 19999/22380），只有这两处漏了。修复即按文件自身既有写法补上
`except PermissionError: return error_response("role not found", 404)`。

**2. `homer_images.route()` 读原始列判断管理员，把 env 管理员挡在外面（生产已复现并修复）**

`homer_images.py` 用 `user['is_admin']`（数据库原始列）判定，而全后端其余地方用 `is_admin(user)`
（= `ADMIN_EMAILS` 环境变量 **或** 数据库列）。生产唯一管理员 `local@ctf.test` 走的是环境变量路径，
其 `users.is_admin` 列为 `0`：

```
raw users.is_admin column : 0     -> 403 FORBIDDEN
S.is_admin(row)           : True  -> ALLOWED
S.admin_source(row)       : env
```

后果是**运营在后台配不了生图模型**，正好是 handoff 阻塞 3 要避免的「死按钮」。
该陷阱本仓库早有记录（见 `ai_fengyue_local_server.py:20737` 注释「只读 users.is_admin 会把 env 管理员
挡在社区管理端之外」），属于同类问题在新模块里复发。修复放在调用点，不改进贡献者模块的接口：

```python
image_user = self.authenticated_token_user()
if image_user is not None:
    image_user = dict(image_user, is_admin=is_admin(image_user))
```

### 验证（真实执行，非推断）

本地（改动后的文件）**144 项断言全绿**，服务端 traceback 计数 0：

| 套件 | 结果 |
| --- | --- |
| `verify_regex_worker.py` | 24/24 |
| `verify_admin_dialogue_config.py` | 18/18 |
| `verify_image_tasks.py` | 30/30 |
| `verify_homer_images.py`（需 Pillow，用 Anconda） | 48/48 |
| `live_admin_probe.py` | 8/8 |
| `happy_path_probe.py` | 7/7 |
| `verify_env_admin_image_route.py`（本轮新增回归） | 9/9 |
| `probe2.py`（5 条曾经断连的路由） | 5/5 全部返回干净 404，不再 DROP |

生产（`prod_guard_probe.py`，对真实 8008 打真实请求，**17/17 通过**）：
- 曾断连的 5 条路由现在分别返回 404 / 404 / 404 / 405（preview 是 GET-only，属设计）/ 404
- 生图管理路由：匿名 401、普通用户 403、**env 管理员 200**（修复前是 403）
- 正常路径未回归：真实公开卡 `dialogue/regex` 200；生图用户路由 401/200/400/404 均为预期
- 未知路由不再丢连接，匿名 401、带凭证返回通用空信封并回显 `path`

生产最终状态：`ai-fengyue-backend` / `homer-dialogue` / `nginx` 三者 active，`NRestarts=0`，
loopback 与公网 `/health` 均 200，监听 `127.0.0.1:8008`(python3, pid 2020423) 与 `127.0.0.1:8091`(node)，
业务库 `quick_check=ok`，users 225 / local_apps 8824 / conversations 1476 / messages 4359（部署前后一致），
`homer_image_tasks` 表已由新模块建出（0 行），证明新代码在生产真的初始化了。

另外以服务账号 `ai-xingyue` 在生产实测了 node 正则 worker：`execute_prompt_regex` 正确改写 assistant 消息、
不动 system/user 消息，`generation_error(402)` 返回 `HM-G402`。

### Pillow 决策

jammy 的 `python3-pil` 候选版本是 **9.0.1**，低于 `requirements-images.txt` 声明的 `Pillow>=11.3,<13`。
我没有接受发行版包：2022 年的 Pillow 要解析不受信任的远端图片，带已知 CVE。
改为装 pip 与 `Pillow==12.3.0`（cp310 manylinux wheel），与本地版本一致。

### homer-dialogue 重启：明确延后到 Step 3

handoff Step 2 写的是「部署重启 Python/Node」，本轮只重启了 Python。理由：这一步改动的文件里
没有任何一个属于 `homer-dialogue` 运行时——runtime 代码要等累计 web 补丁（Step 3）落地才变。
现在重启 Node 不会带来任何变化，等 Step 3 一起重启更干净。8091 目前仍在跑 pid 671。

### 剩余风险

- 服务端文件真正的 r33 基线不可恢复，这 3 个 hunk 只能做**语义校验**，不能做哈希校验。
- 生图**仍未端到端跑通**：还没有配置任何图片服务商。配置时要注意 `endpoint()` 的 SSRF 守卫要求
  主机名解析出的**每一条**记录都是全局地址，否则会以「不允许连接本机或内网地址」被拒。
- 未知路由对已登录用户返回 `200 + 空信封` 是本后端既有兜底行为（不是 r33 引入），
  `prod_guard_probe.py` 现在按实际行为断言并回显 `path`。
