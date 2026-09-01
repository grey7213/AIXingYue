# 惑梦 1.14.2 (267) 全局页面常驻上线 — Tasks

日期：2026-09-01
来源：`E:\酒馆开发\惑梦-风月式全局页面常驻更新包-20260901-r2.zip`（165 KB，23 个源文件 + 4 篇文档）

## 背景

用户报 265「启动还是有问题」，上一轮出了 266 修首屏层级 + 原生桥 receiver。本轮
更新包解决剩下两件事：**完整账户黑屏**、**每次回首页都重新刷新**。

包内 SHA256SUMS 26/26 全对。

## 三方比对（交接 ZIP 基线 / 本地仓库 / 更新包）

包仍然是从交接 ZIP 分叉的 —— 和 r1 同一个坑。整体覆盖会退掉 08-31/09-01 改回的
生产修复。以 ZIP 为基线做二次 diff 后逐文件判定：

| 文件 | 判定 | 处理 |
|---|---|---|
| `explore.js` / `me.js` / `layout.js` | 仓库与基线只差缓存串 | 整体照抄，缓存串改回本轮串 |
| `page-cache.js` | 新文件 | 照抄 |
| `admin.html` | 基线→包只有首字/完整耗时 2 处 | 只取增量 |
| `chat.js` | both-ahead | **只取增量**：`allowedNavigationPath` 放宽 |
| `homer-bridge/index.js` | both-ahead | **只取增量**：抽屉导航项 click → `notifyHost('navigate')` |
| `chat.html` | 包内与基线逐字节相同 | 跳过 |
| `HomerActivity.java` | 87 行纯新增，0 删除 | 照抄 |
| `ClientAssetRoutes.java` + 单测 | dashboard/admin 本地资源映射 | 照抄 |
| `PersistentPageNavigationTest.java` | 新文件 | 照抄 |
| `HomerCacheDatabase/LiveBridge/SnapshotBridge/StartupPresentation`、bridge `style.css`、`offline/style.css`、`verify_chat_loading_alignment.py` | 与本地逐字节相同 | 跳过 |

**拒掉的三处回退**（整体覆盖 `homer-bridge/index.js` 就会中）：
`URLSearchParams.size` 旧 WebView 兼容（Chrome 113 才有该属性，退回去低版本设备
直接死在「没有可启动的角色会话」）、生成失败回滚簇 `recoverFailedGeneration`、
抽屉标题「惑梦（Homer）」。另外包里把已判定为误报的 `#homer-api-error` 错误条加
回来了（`requestJson` 有 26 个调用点，很多是探测性可容错的，在最底层弹条会把正常
回退渲染成一条不消失的「对话服务连接失败」），也拒掉。

同样拒掉包内 `chat.js` 对 `nativeCall()` 的回退 —— 那正是 266 修的 receiver bug。

## 本轮真实改动

**完整账户黑屏**的根因链：主站发 `frame-ancestors 'none'`（实测 `curl` 确认），
所以在 dialogue iframe 或其他嵌套上下文里加载 `/dashboard.html` 会被浏览器直接
拒绝 —— 用户看到一整块黑。三处配合修：

1. `chat.js` 的 `allowedNavigationPath()` 放行 `/dashboard.html`、`/admin.html`
   （原来只放 4 条 `/app/` 白名单，navigate 消息到了也被丢掉）；
2. `ClientAssetRoutes.assetPath()` 给这两页加本地资源映射，APK 内不用回源；
3. `layout.js` 的 `installEmbeddedTopNavigation()`：`/app/` 页发现自己被嵌在
   iframe 里时，拦下站内链接改 `postMessage` 给顶层容器。

**第 3 条实测在当前产品路径上不触发**，得说清楚：APK 的七个常驻 WebView 都是顶层
文档（设备实测 `document.documentElement.dataset.homerTopNavigation === null`），
走的是原生 `shouldOverrideUrlLoading` → 切 WebView；站点侧也没有把 `/app/` 页嵌进
iframe 的地方（`#dialogue-frame` 里是运行时，不加载 `layout.js`）。所以它是包作者
留的防御层，只有真把 `/app/` 页嵌进 iframe 时才生效 —— 我用一个同源顶层探针页
构造了这个场景来验证它确实工作，且确认它在非 iframe 路径上直接早退、不影响现状。

**每次首页重新刷新**：新增 `page-cache.js`（按账号 id 隔离、24 小时 TTL 的
localStorage 封装），`explore.js` 存列表+筛选+随机种子，`me.js` 存余额/额度/人设；
二次进入先渲染缓存再后台刷新，`loadList(reset, {keepVisible})` 让刷新过程不清空
已渲染的卡。退登时 `clearPageCache` 清掉。

**Android 页面常驻**：`HomerActivity` 把单个 `liveView` 改成 `Map<String, WebView>`
七个键（chat/explore/favorites/workshop/me/account/admin），`shouldOverrideUrlLoading`
命中已知页面就切 WebView 而不是在同一个里换页；`ArrayDeque` 维护返回栈；
`LiveClient` 五个回调全部加 `view != liveView` 早退，否则后台页面的 onPageStarted
会把前台页面的快照状态搅掉；`onDestroy` 遍历销毁全部。

**模型检测耗时**：`admin.html` 同时显示首字和完整耗时（后端 `first_content_ms`
早就有了，前端一直只显示 `elapsed_ms`，1500–3500ms 的完整生成时间被说成网络延迟）。

## 自己修的一个真问题（包里没有）

`tools/sync_apk_build_workspace.py` 原来是「工作区没有这个文件就跳过」。本轮
`page-cache.js` 是新文件，于是它**不会进 APK**，而包内 `explore.js`/`me.js` 都
`import` 它 —— APK 里两页会因为 import 404 直接白屏。改成新文件也同步（`+` 前缀
区分显示）。这条如果没发现，出的包比 265 更坏。

## 验证

**Web（本机离线栈 127.0.0.1:8080，真实 Chromium）**

- `verify_chat_loading_alignment.py` exit=0：1440×900 首帧 128 ms / runtime 6052 ms，
  390×844 首帧 95 ms / runtime 4455 ms；抽屉未自动展开、AI 靠左用户靠右、
  0 横向溢出、0 console/page/network error
- 新增 `verify_page_cache_local_first.py` exit=0：**第二次加载直接 `route.abort()`
  掐断对应 API**，页面仍有内容才算缓存真的生效。探索 1 卡→1 卡 / 191 ms 与 187 ms，
  我的页余额字符串冷热完全一致 / 257 ms 与 144 ms，缓存键按账号 uuid 隔离。
  掐断产生的 `ERR_FAILED` 按失败资源 URL 精确摘除（它是断言手段本身），其余错误不放宽
- 新增 `verify_runtime_drawer_navigation.py` exit=0：运行时抽屉「我的」点击后
  iframe 不自己跳，顶层落到 `/app/me.html`
- `verify_sidebar_boxmodel.py`：6 个带侧栏页面全部 38 px / span 438 px

**Android（模拟器 Pixel_6_API_33，WebView 109 —— 故意用旧引擎）**

- 覆盖安装：266 → `install -r` 267 `Success`，`firstInstallTime` 保留
- 冷启动 Activity 684–1294 ms；4 次冷启动 0 `FATAL EXCEPTION`
- **页面常驻实测**：我的页打 `window.__homerPersistProbe` 标记并滚到 400 px →
  去探索 → 回我的，标记和 `scrollY=400` 都还在（旧 WebView 没被销毁）
- **完整账户不再黑屏**：容器内 `/dashboard.html` 渲染出 425 字可见内容、
  标题「用户中心 - 惑梦（Homer）」、能看到「管理后台」入口
- 运行时抽屉点「我的」→ 宿主新建 me WebView 换页，chat WebView 保留且
  `runtimeReady=true`、消息还在
- 断网冷启动 684 ms，离线壳显示「当前未连接网络…可以继续阅读本机记录」+ 2 条消息；
  恢复网络后冷启动 798 ms，runtime 正常接管、无 API 错误条
- `conversation_cache` 有行（266 修的 receiver 仍然有效）
- 单测 17/17（新增 `PersistentPageNavigationTest` 1 条、`ClientAssetRoutesTest` +2 断言）
- 静态审计与 266 逐字段一致，只差 apk 名/字节数/条目数（1137→1138，多的正是
  `page-cache.js`）；旧 IP / 旧品牌 / 凭据全 0；dex 内 host 只有 `patcher.villainy.top`；
  `password-assign` 10 条全是 `locales/*.json` 界面文案
- APK 内 12 个前端文件 + bridge 与仓库逐字节一致

**产物**：`homer-1.14.2-267-release-signed.apk`，41,023,695 bytes，
sha256 `6c1ae430…8bf6a92d`，cert `429b…f320`（与全部历史发布一致），v2+v3。

## 上线

推之前先跑新增的 `tools/diff_production_frontend.py` 把生产 47 个文件拉下来逐一
比对（归一化掉必然全量变化的 `?v=` 缓存串）：38 个仅差缓存串、7 个差异全部是本轮
预期改动、1 个（`page-cache.js`）生产上不存在。**这次没有再出现「生产跑着未提交
代码」**（08-25 那次是 217 行未提交的 bridge 改动）。

缓存串统一 bump `20260901-native-bridge` → `20260901-persistent-pages`（128 处 / 37 文件）。
前端 HTML 已是 `no-cache`（08-26 补的），不必让用户硬刷新。

## 回滚

- 逐文件备份：`/root/homer-push-backup-20260901-*`
- 数据库快照：`E:\homer-backups\homer-prod-20260901-224511`
- 上一版仍挂在 `/download/homer-android-1.14.1-266-release.apk`

## 新增工具

| 工具 | 用途 |
|---|---|
| `tools/verify_page_cache_local_first.py` | 掐断 API 断言探索/我的的本地优先恢复 + iframe 顶层导航 |
| `tools/verify_runtime_drawer_navigation.py` | 运行时抽屉导航交给宿主换页 |
| `tools/diff_production_frontend.py` | 推送前把生产文件拉下来归一化比对，防止覆盖线上手工修复 |

## 遗留

- **`android-app/` 仍不在 git 里**（`E:\homer-apk-1140` 是从交接 ZIP 抽的工作区）。
  本轮 4 个 Java 文件的改动只存在于那个目录。
- 常驻 WebView 是七个长活实例，每个都持有完整 WebView + 渲染进程。低内存设备上
  系统可能杀掉后台渲染进程，此时回到该页会白一下再重载 —— 模拟器（2 GB）上没触发，
  真机低端设备待观察。当前没有 LRU 上限。
- `persistentPageKey()` 只认七个路径，其余（如 `character.html`）仍在当前 WebView
  内换页，符合预期但意味着从探索点进角色详情会覆盖探索页的 WebView 内容。
- **运行时历史列表在页面存活期间不刷新**（不是本轮引入）：`loadConversationHistory()`
  只在 launch 后 250 ms 调一次，之后仅重命名/删除/复制/新建会重调。实测在后端新建
  第二个会话后，`/api/homer/conversations` 打进去返回 2 条，抽屉仍只渲染 1 条；软
  reload 无效（同一 WebView 内 `runtimeUiData` 保留），force-stop 冷启动才拉到 2 条。
  含义是：在另一台设备上新建会话，当前设备抽屉不会自己出现。
- **12 个 `/app/` 页面的 script 标签仍带 `?v=20260812-license-removal`**（既有状态，
  HEAD 就有 14 处，本轮改掉 explore/me 两处）。这些 JS 本轮只变了内部 layout.js 的
  import token（非缓存串差异 0 行），且都不 `import page-cache.js`，所以没有 404 风险；
  `/app/assets/` 是 `max-age=3600`，最坏一小时内用旧副本、之后自动取新字节。本轮
  故意不改：改了要动 12 个 HTML，APK 内置副本随之与仓库不一致，需重新构建签名审计，
  换来的只是一小时的提前生效。
