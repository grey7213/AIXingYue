# 惑梦 Android 交付仓任务（2026-09-02）

设计见 [homer-android-repo-20260902-design.md](homer-android-repo-20260902-design.md)。

## 已完成

### 1. 建两个私有仓库
- `grey7213/homer-android` —— 原生壳源码 + 装配脚本，默认分支 `main`
- `grey7213/homer-android-apk` —— 成品包交付，只走 Releases

### 2. 原生壳进版本控制
`E:\homer-apk-1140\android-app` 的 49 个源文件迁入 `homer-android/android-app`，
排除 `.gradle/`、`app/build/`、`local.properties`。`main` 首个提交 4597 行、仓库 1.8 MB。

`gradlew` 的可执行位单独补了一个提交 —— 从 Windows 工作区 add 进来是 100644，
首次 CI 在 Linux runner 上报 `Permission denied` exit 126。

### 3. web 基线分支
`homer-android` 的孤立分支 `web-base` = 主仓库 `HEAD` 的 `frontend/` +
`sillytavern-runtime/` 两棵树。校验过 tree SHA 与主仓库逐字节一致：
`frontend` `3811bb48`，`sillytavern-runtime` `cbc45cec`。

### 4. 脚本
| 脚本 | 作用 |
| --- | --- |
| `tools/bootstrap.py` | 装配可构建工作区：检出 web 基线、建目录联接、装 node 依赖、生成 `local.properties` |
| `tools/export_web_patch.py` | web 改动 → 对着基线 commit 的 git patch |
| `tools/apply_web_patches.py` | 把 `web-patches/` 的补丁三方落地（CI 用 `--strict`） |
| `tools/verify_apk_assets.py` | 核对前端与运行时资源真的进了 APK |
| `tools/push_web_base.py` | 维护者推进 web 基线并更新 pin |

### 5. 两道防白屏的闸
`app/build.gradle` 配置期检查 web 树与 webpack 是否就位；`verify_apk_assets.py`
逐文件核对包内资源。

### 6. CI
`.github/workflows/pr-build.yml`：装配 → 落地补丁 → 单测 + assembleDebug →
校验资源 → 传 debug APK（14 天）。

### 7. 文档
- `README.md` —— 仓库分工、快速开始、环境要求
- `CONTRIBUTING.md` —— 贡献者八节操作手册，含自查清单和 9 条报错对照
- `MAINTAINER.md` —— 我这边收 PR、落地补丁、出正式包、推进基线、邀请协作者
- `homer-android-apk/README.md` —— 交付方式、tag 规范、签名边界

## 验证结果

| 项 | 结果 |
| --- | --- |
| `bootstrap.py --check` | 5 项环境全部识别 |
| `bootstrap.py` 从零装配 | web 基线检出 + 目录联接 + `npm install --omit=dev`，webpack 就位 |
| `testDebugUnitTest` | 17 个全过 |
| `assembleDebug` | 出包 45.2 MB，2 分 30 秒 |
| `verify_apk_assets.py` 本地 debug 包 | 通过，109 个前端文件全在包内，`page-cache.js` / `dialogue-prewarm.js` 确认打进去 |
| `verify_apk_assets.py` 反向验证 265 包 | 正确报出缺 `page-cache.js`，exit 1 |
| patch 干净落地 | 通过 |
| patch 同文件不同位置 | 自动合并，两边改动都保留 |
| patch 同一行 | `with conflicts`，留 `<<<<<<< ours` 标记 |
| Gradle 缺 web 树时 | 抛 `GradleException` 并提示跑 bootstrap |
| `push_web_base.py --dry-run` | 基线未变时正确判定「无需推进」；`source_commit` 改掉后正确造出孤立提交 |
| CI run#1 | 失败于 `./gradlew: Permission denied` —— Windows 上 add 进来是 100644，已用 `update-index --chmod=+x` 修 |
| CI run#2 | 全绿，2 分 08 秒（冷缓存：装配 15s、构建 93s） |
| CI run#4 | 全绿，1 分 30 秒（热缓存：缓存命中 3s、构建 74s） |
| PR #1 的 CI | 全绿 —— 即去掉凭据改写后的 workflow 首次验证 |
| PR #1 squash 合并 | 成功，走的是完整的「CI 绿灯 → squash → 删分支」路径 |

## 转公开（同日追加）

两个仓库都转为 public。带来的三处变更：

### main 的保护规则

公开仓能免费用 ruleset。开了 `main 保护`（id `22080138`）：

| 规则 | 效果 |
| --- | --- |
| `pull_request` | 不能直推 `main` |
| `required_status_checks` = `build`（strict） | CI 绿灯且分支跟上 `main` 才能合 |
| `non_fast_forward` | 禁 force push |
| `deletion` | 禁删 `main` |

bypass 给 `RepositoryRole` id 5（admin），我推 `web-base.json` 的 pin 不必绕 PR。

双向实测：撤掉 bypass 时我自己直推被 `push declined due to repository rule
violations` 挡下，加回来才通。CI 上报的 check 名确认是 `build`，与规则一致 ——
名字对不上会让所有 PR 永远卡在「等待 build」。

### CI 去掉凭据改写

原有一步 `git config --global url.insteadOf` 把 `github.token` 注进全局，
让 bootstrap 在 `.web-cache/tree` 里能拉私有的 `web-base`。公开后多余，删掉。
无凭据 `git fetch --depth 1 origin web-base` 实测通过。

### 转公开前的凭据审计

- `android-app` 追踪文件：无密码/密钥赋值；URL 全是 `example.test`、`127.0.0.1`、
  RFC1918 私网地址和 `schemas.android.com`
- `main` 全历史扫 private key / AWS / GitHub token / keystore 口令：无
- 历史里无 `.keystore`/`.jks`/`.pem`/`.key` 文件
- web 树扫赋值型凭据：无
- MAINTAINER.md 原写了 keystore 文件名、alias、证书指纹 —— 指纹用
  `apksigner verify --print-certs` 从已发布 APK 就能读出（实测确认
  `429b4165…f320`），不算秘密，但 alias 和位置挪去 `AGENTS.md`

### 文档改双轨

fork 路线（任何人，我零操作，首个 PR 要我点 Approve and run）与 collaborator
路线（省掉 fork，发 Release 的必要条件）。`read`/`triage` 建不了 Release。

## 首个外部 PR 的实测（2026-09-03）

@thebasui 从 fork 提了 PR #2「修复历史会话与新建对话路由」：99 增 5 删，
改 `HomerActivity.switchPersistentPage`、加 1 个单测、带 1 个 web 补丁。
流程整体走通了，但暴露两处工具链缺陷。

### 缺陷一：缓存命中时补丁全军覆没

PR #2 首跑 CI 在「落地 PR 内的 web 补丁」失败，三个文件全报
`does not match index`，而补丁 preimage 哈希与 pin 的 blob 逐字节一致。

根因：`git apply` 判断目标文件「未修改」用的是 index 里的 stat（mtime/size/inode），
不是内容哈希。CI 从 `actions/cache` 解包 `.web-cache` 时 mtime 全是新的，
内容没动的文件也被判成已修改。只有缓存命中那一路会踩到 —— PR #1 是首次跑、
缓存未命中、现场 clone，index stat 是新写的，所以没暴露。

修复：`apply_web_patches.py` 落补丁前先 `git update-index --refresh`（PR #3）。
本地把四个目标文件 mtime 改旧复现过：不带修复报 3 个 `does not match index`
与 CI 日志一致，带修复 `[落地]` 通过；另在临时仓库确认内容真有差异时
refresh 之后 `git apply` 仍然失败，检查强度没被削弱。

### 缺陷二：基线推进后旧补丁必须删

`push_web_base.py` 把 pin 推到 `f418c3f` 之后，`web-patches/` 里那个已落地的
补丁让 `apply_web_patches.py --strict` 报「基线不符」，之后每个 PR 都会红灯。
MAINTAINER.md 的「推进 web 基线」已补上删补丁这一步（和提交 pin 同一个提交）。

### 走过的完整路径

1. fork PR 的 workflow 要在 Actions 页点 Approve and run —— 实测确认
   `gh api -X POST .../actions/runs/<id>/approve` 也能批
2. `gh pr update-branch 2` 让分支跟上 `main`（strict 规则要求），
   更新后又产生一个新的 `action_required` run，要再批一次
3. 本地独立验证：`testDebugUnitTest assembleDebug` + `verify_apk_assets.py`
   （109 个前端文件缺 0 个），不只信 CI
4. web 补丁 `git apply -3` 落进主仓库并单独提交
5. `gh pr merge 2 --squash --delete-branch`
6. `push_web_base.py` 推进基线 → 删旧补丁 + 提交 pin
7. 版本号 267/1.14.2 → 268/1.14.3，`sync_apk_build_workspace.py` +
   robocopy 同步到 `E:\homer-apk-1140`，`assembleRelease` → zipalign →
   apksigner，拆包确认 `assets/client/web/` 里是修复后的代码
8. `publish_homer_apk.py` 发到生产，`release-1.14.3-268` 发到
   homer-android-apk 的 Releases

## 第二个外部 PR（2026-09-04，PR #4 → 1.14.4/269）

@thebasui 提了 PR #4「修复重复建会话并让历史存档本地优先打开」：纯 web 补丁，
177 行，改 5 个文件，无原生壳改动。流程本身没再出新问题（缓存那条已被 PR #3 修掉，
CI 一次绿），但查出了 web 前端交付链上的两件事。

### 端点有第二条建会话路径

`dialogue/session` 在只给 `app_id`、不给 `conversation_id` 时会自己 `upsert_conversation`
（`tools/ai_fengyue_local_server.py` 20220 行附近），和 `conversations/start` 并列。
角色页的预热正好命中这条路，所以每张新卡多一条空壳存档。后端直连实测：
`?app_id=X&launch_only=1` 新增 1 条会话，而隐藏帧启动时那个不带任何 id 的
`?launch_only=1` 探测新增 0 条 —— 写验证脚本时必须区分这两个，否则断言会误报。

### 缓存串只 bump 了一半（本轮的真实缺口）

补丁把 `layout.js` 里指向 `dialogue-prewarm.js` 的令牌换成
`20260904-instant-history-v1`，但引用 `layout.js` 的 10 处令牌全部没动，仍是
`20260901-persistent-pages`。APK 的 `ClientAssetStore` 对 `.js` 发
`public, max-age=31536000, immutable`，nginx 那边 `/app/assets/` 是 `expires 1h`。

用真实 `frontend/` 树 + 这套响应头复现（`E:\tmp` 下的一次性脚本，未入库）：
旧版填满缓存后把 5 个文件换成新内容，重载时 `hub-pages.js` / `layout.js` /
`dialogue-prewarm.js` 的 `transferSize` 全是 0，取到的仍是旧代码。也就是说
**光靠这个补丁，老用户在缓存过期前拿不到 prewarm 修复**。chat 页不受影响 ——
`chat.html` 是 `no-cache`，且 `chat.js` 的令牌确实换了。

APK 侧其实躲过了这一发：`assets/client/index.txt` 走的是包内拦截，装新包等于换
文件，实测模拟器 268 覆盖装 269 后 code-cache 里 `dialogue-prewarm.js` 的条目
从旧令牌 `4fb8193ab4bb8bd8_0` 变成新令牌 `99bfd98c1e3cc0a8_0`，执行的是新码。
纯网页端用户才是受影响的那一批，需要在下次前端上线时把那 10 处令牌一起 bump。

### 模拟器验收（这次补上了 PR #2 缺的那一步）

Pixel_6_API_33（WebView 109）：
- 268 覆盖装 269，`firstInstallTime` 保留、`lastUpdateTime` 更新，冷启动无崩溃
- debug 包指向 `http://10.0.2.2:8080/` 的本机离线栈，用裸 CDP over
  `adb forward` 驱动（Playwright 的 `connect_over_cdp` 会先发
  `Browser.setDownloadBehavior`，Android WebView 不支持 browser context 管理，
  直接报错，所以只能自己发 CDP）
- 角色页停留期间 app-only 预热请求 0 次
- 历史点击：本地壳 267ms 出现且输入框可用、已渲染 1 条缓存消息，
  运行时 ready 要 7919ms —— 壳确实先到（改动前这 7.9 秒是白屏等待）
- 运行时内切历史：URL 立即换到目标会话，输入框可用，运行时未崩

写探针时踩到两个 CDP 坑，记下来免得重踩：`Page.addScriptToEvaluateOnNewDocument`
在没 `Page.enable` 时静默不注入（调用返回成功，脚本从不执行）；探针里不能用
`MutationObserver` observe `document.documentElement`，document-start 时它可能
还是 null，构造就抛，探针等于没装。另外别拿 `body.has-preview` 当「壳到了」的
信号 —— `chat.html` 的 `<body>` 静态就带这个类，首帧即为真，断言永远通过。
真正的信号是 `documentElement.dataset.homerShellReady`，原生壳也是靠它揭开
本地快照层的。

## 待办

- [x] 收第一个外部 PR，验证补丁落地流程在真实分歧下的表现（PR #2，见上）
- [ ] 有人要发 Release 时给 homer-android-apk 的 write
- [ ] 下次改前端时把引用 `layout.js` 的 10 处 `?v=` 令牌一起 bump，
      让纯网页端老用户也能拿到 prewarm 修复

## 风险

- `E:\homer-apk-1140` 仍是出包工作区，方向是 homer-android → 1140 单向同步；
  两边都改会重演分叉
- pin 更新后忘记把 `web-base.json` 提交到 `main`，贡献者会卡在「基线不符」
- `web-base` 每次推进 force push 约 140 MB。`non_fast_forward` 只作用于
  `~DEFAULT_BRANCH`，不挡 `web-base`
- 仓库无 LICENSE 文件。构建编入 AGPL-3.0 的 SillyTavern，README 已说明，
  但本项目自有代码的许可仍未声明
- `hub-pages.js` 里 `groupConversations` / `archived_conversations` 现在没人调用，
  `archiveLabel` 也永远返回空串（`archive_count` 只有分组逻辑会写）。
  PR #2 没清，这次发版也没顺手删 —— 留给下次改历史页时一起处理
- 这一版没在真机/模拟器上点过历史页。本机 MuMu 已不在（`adb devices` 空），
  只做了拆包核对与单测。多存档恢复这条路的端到端行为未经人工验收


