# 惑梦 1.14.0 (265) 交接合并上线 — Tasks

日期：2026-08-31 → 2026-09-01
来源：`E:\酒馆开发\AIXingYue-main.zip`（1.64 GB，2026-08-31 11:51）

## 背景

交接 ZIP 带来三块新东西：APK 内置整套前端与对话运行时（进对话几乎无网络加载）、
银白猫耳品牌资源、会话管理（改名/置顶/导出/导入）。但 ZIP 是从 `7fa822f` 分叉的
**下游分支**，不含线上未提交的热修；直接铺上去会静默回退多处生产修复。

关键判断：**工作区和生产跑的代码本身就不是 HEAD**（`git diff HEAD` 有 226 增 42 删），
所以这不是「新版覆盖旧版」，而是两条分叉分支的三方合并。

## 任务与验证

| ID | 任务 | 状态 | 真实验证结果 |
|---|---|---|---|
| M1 | 抽出可构建工作区 | Done | `tools/extract_zip_android_build.py`，24366 文件 / 444.7 MB → `E:\homer-apk-1140`（纯 ASCII 路径，aapt/apksigner 读不了中文路径） |
| M2 | 审计 ZIP 的 APK | Done | `app-debug.apk` 45 MB 是 **debug 签名 + `.debug` 包名**，装出来是并存的第二个应用，不能直接发布；必须自己走 `assembleRelease` |
| M3 | 三方分类差异 | Done | 新增 `tools/diff_three_way.py`（zip/local/HEAD 三方，按 `local-only-ahead` / `both-ahead` / `zip-only-ahead` 分桶）。前端 20 个 both-ahead、runtime 14 个 local-only-ahead |
| M4 | 后端合并 | Done | 6 个新端点、0 路由删除；6 处按下述决定改回。5 个 selftest 全过 |
| M5 | 后端本地真跑验证 | Done | 临时 DB 起服务，实测 rename/pin/export/import 全通、导出→导入往返成功、`title`/`pinned` 落库 |
| M6 | 农场经济回退 | Done | 用户决定保留农场币独立。实测种植 `coins 300→250` 且 `points` 不变；收获 `coins 250→340`，`points` 只 +10（每日首收奖励） |
| M7 | 前端合并 | Done | 94 文件逐一 sha256 核对与生产一致；侧栏 6 页全部 38px/438px |
| M8 | runtime 合并 | Done | 取 zip 9 个 `zip-only-ahead`，保留 local 的 `config.yaml`/`index.html`/`extensions.js`/`openai.js`/MemoryBooks |
| M9 | 部署（三阶段） | Done | 后端→runtime→前端，各阶段独立健康检查。两个服务 `NRestarts=0` |
| M10 | 出 APK 265 并发布 | Done | 41,015,412 bytes，sha256 `67a45f2b…f626d1cb`，cert `429b…f320`，v2+v3；14/14 单测；263→265 覆盖安装 `firstInstallTime` 保留 |

## 从 ZIP 改回来的 6 处（后端）

1. **ST 提示词硬预算**（2 常量 + 5 函数 + `prompt_stats`）。ZIP 无界拼接，只剩 8 MB 上限；
   长会话会 400，且 ZIP 新引入按 token 计费后单轮费用无上界。
2. **Anthropic 分支丢弃客户端 system**。ZIP 把运行时上传的 system 并进服务端那份 ——
   用户可在客户端改，等于允许往系统提示注入任意内容。selftest 断言 `RAW_SYSTEM_SECRET` 不得出现。
3. **`trailing_empty_assistant` 守卫**。缺了它，生成失败会留下永远没有回复的用户消息。
4. **农场币保持独立**（见 M6）。ZIP 把它并入 `free_points`，且收成不变 ——
   8 块地每 3 小时净产约 320 分而单次对话只花 50 分，等于白嫖聊天。
5. **`preset` 同时发新旧两套键**。ZIP 把 `card_prompt`/`global_prompt` 改名成
   `current_prompt`，线上 bridge 读旧名，角色卡分组会永久空白。
6. **`dialogue_url` 读回 env**；默认头像 remap 补上真实存在过的 `?v=20260627-logo`
   （ZIP 只列了新版本号那条）。生产 69 个用户 `avatar_url` 全为 NULL，属潜在问题，一并修掉。

## 从 ZIP 改回来的 3 处（对话运行时 bridge）

1. **`URLSearchParams.size`** —— 08-27 修过的同一个 bug 又回来了。该属性 Chrome 113 才有，
   API 33 系统镜像是 109，`undefined` 会让 `app_id`/`conversation_id` 被静默丢弃，
   APK 死在「没有可启动的角色会话」。**只在旧设备复现**，现代引擎上测不出来。
2. **生成失败恢复簇**（5 函数约 110 行）。手工移植并接进
   `GENERATION_STARTED`/`ENDED`，保留 ZIP 的 dry-run 守卫和 host 状态通知。
3. **抽屉标题**从「导航与历史」改回「惑梦（Homer）」。

另**移除 ZIP 新加的 API 错误条**：它在 `requestJson` 最底层触发，而该函数有 26 个调用点，
包括 `fetchSession` —— 第一个端点失败后面还有回退，属正常路径，会在加载成功时
显示一条不消失的「对话服务连接失败」。生成请求根本不走 `requestJson`，
所以这个条报不了真正要紧的失败。`showHostNotice` 已覆盖真实错误。

## 改测试而非改代码的 1 处

`_selftest_card_stage_renderer` 原先断言字面量 `height: 100dvh` + `min-height: 100dvh`，
ZIP 重写了这两条规则。新增 `tools/verify_card_stage_viewport.py`，在真实 Chromium 上
量 5 视口 × 3 种写法（含 dvh 完全不被支持的老引擎降级），stage 尺寸 15/15 全等于视口 ——
铺满由 `position: fixed; inset: 0` 保证，dvh 是冗余。据此把断言改为结构不变量。

## 上线后实测

- 后端 `/health` OK；4 个新会话端点 401（路由存在、鉴权先行），而非合并前的静默空 200
- dialogue 4 个新路由 500 而非 404；webpack 5.105.4 编译成功
- `conversations.pinned` 列已加；`farm_balance_migrations` **0 行**（迁移确实没跑）；
  `farm_profiles.coins` 仍分布在 120–300（14 用户），农场币完好
- `hostWhitelist` 未被冲掉：直连 runtime 探测，白名单 host 302、`evil.example.com`/`villainy.top` 403
- 真实浏览器 1440/390 双视口跑 `/`、`/dashboard.html`、`/app/login.html`：**0 page error、0 console error**
- 侧栏 6 页全部 38px/438px（回退前 explore/farm 是 56px/636px）
- **APK 内置前端确实生效**：265 三次启动共 3 个服务器请求（全是 `site-settings`），
  263 单次启动就 15 个 —— `ClientAssetStore` 在本地拦截了全部 HTML/CSS/JS
- 冷启动 1966 ms（263 是 1381–1608 ms；多出的是 41 MB 包体的 dex/资源解析）
- 公网 `ai-xingyue-latest.apk` 返回 200 + `application/vnd.android.package-archive` + `attachment`

## 新增工具

| 工具 | 用途 |
|---|---|
| `tools/extract_zip_android_build.py` | 从交接 ZIP 抽最小可构建工作区到纯 ASCII 路径 |
| `tools/diff_trees.py` | 归一化换行的目录树比较（避免 CRLF 假差异） |
| `tools/diff_three_way.py` | zip/local/HEAD 三方分类，指出「照抄 ZIP 会丢哪些工作」 |
| `tools/audit_apk_static.py` | APK 静态审计：URL/旧 IP/旧品牌/凭据/dex 结构 |
| `tools/verify_sidebar_boxmodel.py` | 真实 Chromium 量侧栏盒模型（本地 http + API 打桩 + 伪造登录态） |
| `tools/verify_card_stage_viewport.py` | 量舞台层铺满行为，判断 CSS 改动是否等价 |

`tools/push_homer_file.py` 也扩了：新增 `backend-card-ext` 与 8 个 dialogue 目标，
并在上传前 `install -d` 建父目录（SFTP `put` 不会自动建，新资源目录会 ENOENT）。

## 回滚

- 生产逐文件备份：`/root/homer-push-backup-20260831-*`（98 个）
- 数据库快照：`E:\homer-backups\homer-prod-20260831-155027`（284 MB，`quick_check`+`integrity_check` 通过，8781 角色卡）
- 上一版 APK 仍挂在 `/download/homer-android-1.13.1-263-release.apk`

## 遗留

- **保留了 ZIP 的一处行为**（用户 2026-08-31 确认）：全局预设有条目时禁用角色卡自带预设。
  代价是卡自带预设的会话在管理员启用全局预设后会失效。
- `zip1-repack.keystore` 仍全盘一份，且不在 `E:\homer-backups\` 里，需离线单独保管。
- 生产后端此前长期跑未提交代码；本次合并版已落在工作区，仍待提交进 git。
- `style.css` 里 `homer-api-error` 的样式规则还在（4 处），DOM 不再创建，无害。
