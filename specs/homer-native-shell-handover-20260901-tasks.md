# 惑梦 1.14.1 (266) 首屏接管上线 — Tasks

日期：2026-09-01
来源：`E:\酒馆开发\惑梦-正式版覆盖更新包-20260901-r1.zip`（111 KB，13 个源文件 + 3 篇文档）

## 背景

用户报 265 「启动还是有问题」。交接包给的诊断是：Android 端把实时 WebView 加在
本地快照**之上**，所以「本地界面先可用、网络后台接管」名义上做了、实际被覆盖，
用户在完整 runtime 就绪前（历史实测 6.2–7.8 s）一直看加载态；ready 超时 150 s。

包内 SHA256SUMS 15/15 全对。三方比对（交接 ZIP / 构建工作区 / 本包）结论：

| 文件 | 判定 | 处理 |
|---|---|---|
| `HomerActivity.java` / `LiveBridge.java` / `SnapshotBridge.java` | pkg-only-ahead | 逐字节照抄 |
| `StartupPresentation.java` + 其单测 | 新文件 | 照抄 |
| `assets/offline/style.css` | pkg-only-ahead | 照抄 |
| `HomerCacheDatabase.java` / bridge `style.css` | 与本地逐字节相同 | 跳过 |
| `frontend/app/chat.html` | 包内是 ZIP 版，本地更新 | **只取增量**（否则回退 `?v=` 缓存串） |
| `frontend/app/assets/js/chat.js` | both-ahead | **只取增量** 5 行 |
| `homer-bridge/index.js` | both-ahead，包内基于 ZIP | **只取增量** 1 处 |

**关键点：包内 `index.js` 是从交接 ZIP 分叉的**，整体覆盖会把 08-31 改回的 3 处
生产修复重新退掉（`URLSearchParams.size` 旧设备 bug、生成失败恢复簇、抽屉标题），
并把已判定为误报的 API 错误条加回来。用 ZIP 作基线做二次 diff 才看清：本包对
`index.js` 的真实改动只有 `setDrawerOpen()` 去掉桌面自动展开这一处。

## 自己查出来并修掉的真 bug（包里没有）

`frontend/app/assets/js/chat.js` 的 `nativeCall()` 把方法从 `window.HomerNative`
上摘下来再调：

```js
const method = window.HomerNative?.[name];
return typeof method === 'function' ? method(...args) : undefined;
```

WebView 的 `@JavascriptInterface` 方法**必须以注入对象为 receiver**。脱离后调用抛
`Java bridge method can't be invoked on a non-injected object`，被 `catch` 吞掉返回
`undefined` —— 于是 6 个原生桥调用（读/写会话快照、读历史、读旧快照、通知壳就绪）
全部静默失效，`conversation_cache` **一行都没写进去**。

真机实测（模拟器 API 33 / WebView 109，CDP 逐一验证）：6 个方法 bound 调用全通、
detached 调用全抛。这正是交接包诊断里「新装/清数据/新会话没有 `conversation_cache`」
的成因之一 —— 不是没命中缓存，是**从来没写成功过**。

修法：保留 receiver（`bridge[name](...args)`）。改完实测：清空 `conversation_cache`
后跑一次完整会话，设备上出现正确行；再冷启动，离线壳直接渲染出上次会话内容，
断网冷启动同样。修前同样流程 0 行。

该 bug 从 `7f9c866`（合并交接 ZIP）带进来，**已发布的 265 里也有**。

## 验证

**Web（包内 `verify_chat_loading_alignment.py`，本地离线栈真实浏览器）**：
exit=0。1440×900 首帧 87 ms / runtime 4282 ms；390×844 首帧 77 ms / runtime 4094 ms。
两视口都是左抽屉未自动展开、AI 靠左用户靠右、0 横向溢出、0 console/page/network error。

**Android（模拟器 Pixel_6_API_33，WebView 109 —— 故意用旧引擎）**：

- 覆盖安装：装已发布 265 → 直接 `install -r` 266，`Success`，`firstInstallTime` 保留（未卸载）
- 冷启动 Activity 787–921 ms；0 `FATAL EXCEPTION`
- 首帧本地壳：`shellReady=true`、`has-preview` 生效、设置键与输入框 `elementFromPoint` 命中可点、
  runtime 仍在后台（`is-ready=false`）
- 接管后：`homer-runtime-ready`、`has-preview` 撤掉、左右抽屉均关闭、
  抽屉标题「惑梦（Homer）」、无 API 错误条、composer/send 可点
- 缓存命中冷启动：3 s 截图已是完整本地对话壳（带上次消息）
- 断网冷启动：状态显示「离线记录」、消息照常渲染、0 崩溃；恢复网络后点「重新连接」
  → runtime 正常接管，之后 logcat 0 error
- 单测 16/16（新增 `StartupPresentationTest` 2 条）

**产物**：`homer-1.14.1-266-release-signed.apk`，41,019,508 bytes，
sha256 `9507231d…12dfd8f5`，cert `429b…f320`（与历史发布一致），v2+v3。
静态审计：旧 IP / 旧品牌 / 凭据全 0；`password-assign` 10 条全部是
`locales/*.json` 的界面文案，与 265 同值。

## 上线

用 `push_homer_file.py`（不跑整套 deploy，避免重建 Nginx / 全量同步 / 新 runtime release）：

- 40 个文件：后端 1、dialogue bridge 1、前端 38；每个都推后校验 sha256，6 个已相同的跳过
- `ai-fengyue-backend` 重启后 `NRestarts=0`；`homer-dialogue` 未重启（静态文件热生效）
- APK 走 `publish_homer_apk.py`：包名/versionCode/证书三重 guard 通过，
  原子 mv 上传，远端哈希核对，重写 `release.json`，公网重下哈希一致
- 公网下载的包在装有 265 的设备上直接覆盖安装成功，启动无崩溃

**缓存串统一 bump** `20260901-download-warm` → `20260901-native-bridge`（123 处 / 38 文件）。
前端 HTML 已是 `no-cache`（08-26 补的），所以这次不必让用户硬刷新。

线上核对：`/health` OK、首页版本文案 v1.14.1、`chat.html` 指向新串、
线上 `chat.js` 同时含 receiver 修复与 `notifyShellReady`、
服务器上 bridge 文件哈希与本地一致且 3 处生产修复都在、API 错误条 0 处。
真实浏览器跑首页（1440/390）与登录页：0 console error / 0 page error / 0 ≥400 响应、
无残留旧缓存串。

## 一个需要说明的非回归

`curl https://patcher.villainy.top/module/dialogue/scripts/**` 返回 500 —— 看着像推坏了，
但**未被本次推送触碰的 `script.js` 同样 500**：SillyTavern 的 `setUserDataMiddleware`
对无有效会话的请求直接 `sendStatus(500)`（`src/users.js:1054`，日志里的
`Session not available`）。带 cookie jar / csrf-token / Referer 都不行，因为匿名客户端
在 `/module/dialogue/` 就被 302 到 `/app/chat.html` 或 `/app/login.html`，拿不到会话。
Nginx 日志佐证：13 个 500 全来自我这台机器的 curl；推送后没有任何真实用户 500，
最近 2000 条运行时静态请求是 975×304 + 969×200。

## 回滚

- 逐文件备份：`/root/homer-push-backup-20260901-*`
- 数据库快照：`E:\homer-backups\homer-prod-20260901-160424`（284 MB，
  `quick_check`+`integrity_check` 通过，8782 角色卡 / 74 用户 / 202 会话）
- 上一版仍挂在 `/download/homer-android-1.14.0-265-release.apk`

## 新增工具

| 工具 | 用途 |
|---|---|
| `tools/verify_chat_loading_alignment.py` | 交接包带的桌面/手机首屏回归（首帧耗时、抽屉状态、消息左右、错误计数） |
| `tools/sync_apk_build_workspace.py` | 把仓库 frontend/runtime 同步进纯 ASCII 构建目录（跳过 MemoryBooks 的 node_modules） |
| `tools/verify_prod_native_bridge.py` | 生产实测：运行时模块图 + 三个页面的 error/缓存串检查 |

## 遗留

- **`android-app/` 仍不在 git 里**（`E:\homer-apk-1140` 是从交接 ZIP 抽的工作区）。
  本次 6 个 Java 文件的改动只存在于那个目录，丢了就得重新从包里取。
- 交接包 README 要求的七场景实机验收里，「切换历史会话」只在 web 侧验过
  （离线栈只有 1 个种子会话，构不出多会话切换）。
- 运行时那颗 `#homer-runtime-gate` 在 `releaseRuntimeGate()` 后仍留在 DOM
  （被挪进 `#homer-internal-parking`，尺寸 0×0，无害）。若某条路径重新加上
  `homer-runtime-pending`，`#sheld`/`#homer-runtime-root` 会被整体 `visibility:hidden`
  —— 断网重载时观察到过一次这个中间态，恢复网络后正常。
