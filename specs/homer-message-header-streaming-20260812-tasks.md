# 惑梦消息头与统一流式输出 Tasks

日期：2026-08-12

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HMS1 | 建立 requirements/design/tasks 并登记导航 | Done | 新 SPEC 覆盖旧“完全隐藏消息头”要求 |
| HMS2 | 后端 launch 补充锁定角色版本元数据 | Done | 只返回版本 id/no/name/created_at，不包含卡片正文、Prompt 或秘密 |
| HMS3 | 恢复轻量消息头并接通帮助/更多/编辑 | Done | 本地 1440×900 与 390×844 完整可见且无溢出 |
| HMS4 | 固定全部真实生成入口为流式 | Done | send/continue/regenerate/next/new swipe 均强制 `stream_openai=true`；代理按请求体识别丢失 Content-Type 的 SSE |
| HMS5 | 强化模型桩与浏览器增量验收 | Done | 五类生成各记录 5 次可见正文更新、7 个流 token 事件，delta 间隔约 110ms |
| HMS6 | 完成静态、自测和桌面/手机 Chromium 回归 | Done | `node --check`、`py_compile`、两个 selftest、完整 Chromium E2E 连续两次通过；console/page/network error=0 |
| HMS7 | 更新 AGENTS、部署、线上验证并本地提交 | Done | release `20260812-044851`；生产桌面/手机与五类真流式验收通过；历史备份已裁剪；仅本地提交，不推送、不构建 APK |

## 当前约束

- 保留现有长按/右键消息菜单和精确消息绑定。
- 不修改或提交 `Tavo_主题效果_14G5y(1).thm`。
- 不输出或记录 API Key、Cookie、Token、角色 Prompt 或世界书正文。

## 本地验收记录

- 桌面 `1440×900`：角色名为 `《惑梦 E2E 角色》`，版本 `v3.0`，时间非空，帮助/更多/编辑均精确绑定目标消息；用户消息不显示角色版本。
- 手机 `390×844`：消息头和长按菜单均在安全区内，页面无横向溢出。
- 发送、续写、重写、下回、新 Swipe 各有 5 次生成结束前可见正文更新；已有 Swipe 左切只切换候选，不伪装生成。
- 旧操作坞和原生 Swipe chrome 可见数为 0，Yuzi JS/CSS 请求为 0，console/page/network error 为 0。

## 生产验收记录

- 已部署到 `/opt/homer-dialogue-runtime/releases/20260812-044851`；backend、dialogue、Nginx 均 `active`，8008 health、8091 CSRF、公网 `/health` 正常，`CONTENT_MODE=local_only`。
- 生产 Chromium：发送、续写、重写、下回、新 Swipe 各有 5 次可见正文增量和 7 个流事件，delta 间隔约 110ms；桌面 `1440×900`、手机 `390×844` 均无消息头溢出或关键词 rail 遮挡。
- 生产模型夹具已断言临时 preset 同时命中 `#custom_model_id` 与保存设置，模型桩只走 loopback；验收后临时用户、角色、会话、preset、runtime state、dialogue 用户目录均清零，SQLite `quick_check=ok`。
- 消息帮助/更多、长按/右键/键盘菜单、原生编辑、单条删除、既有候选切换和云同步回归通过；Yuzi JS/CSS 请求为 0。原始结果中的两个 STMB 可选文件 404 与页面切换中止 ping 为白名单噪声，page error 和未预期业务错误为 0。
- 网站平台许可入口保持移除：`/app/open-source.html` 返回 404，导航和信息页无“许可/开源许可与源码”入口。
- 验收证据：`output/playwright/homer-header-streaming-production-20260812/result.json`、`desktop.png`、`mobile.png`。

## 服务器备份清理记录

- 前序清理删除 652 项历史备份/旧 release，脚本统计约 `14.42 GB`；收尾复核又删除 44 个旧 `.bak*` 和 2 个空 SQLite 伴随文件，共 `138,647,838` bytes（约 `132.2 MiB`）。
- 当前同一源文件只保留最近一份备份；dialogue release 只保留 `20260812-044851`，`/opt/ai-fengyue-backend/data/backups/` 为空。
- 最近恢复集：数据库 `ai_fengyue-before-community-versions-20260812-044851.sqlite3`、前端源码 `frontend-source-before-community-versions-20260812-044851.tgz`、对话数据 `homer-dialogue-data-20260812-044851.tgz`；env、Nginx、systemd 和后端模块各按源文件保留最近一份。
- 恢复验证：数据库 `quick_check=ok`；前端 tar `130` 项、对话数据 tar `7914` 项可读；`nginx -t` 通过，三项服务 active，内外 health 正常。
- 根分区最终可用空间 `55,341,715,456` bytes（约 `55.34 GB`）。
