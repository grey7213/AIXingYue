# 惑梦社区工坊、不可变版本与 Spine 稳定化任务（2026-07-20）

- [x] 读取技能、项目规则、现有 SPEC 和新交接 ZIP。
- [x] 确认新 ZIP 哈希与旧交接不同，并隔离解压审计。
- [x] 审计历史菜单、社区、Mod、版本、赛事和 Spine 的现有实现缺口。
- [x] 合并历史会话三点菜单与社区前端基础。
- [x] 合并并加固社区作品、收藏、赛事和投票后端。
- [x] 实现统一不可变版本、初始 v1、原子发布和会话版本锁定。
- [x] 统一社区 Mod 与对话 Mod，保存有序版本引用并接入全部生成链路。
- [x] 持久化角色开源、赛事报名、收藏预设/UI 模板引用。
- [x] 加固 UI 模板演示沙箱。
- [x] 完成 Spine 包版本/atlas 校验、运行时生命周期和连续切换稳定性。
- [x] 完成 Python/JS 语法、临时 SQLite、API、并发/越权和媒体引用测试。
- [x] 使用真实浏览器完成桌面/390px 历史、社区、创作、详情、聊天 Mod、版本选择与 Spine 验收。
- [x] 更新 AGENTS/导航/任务验证记录。
- [x] 提交并推送。
- [x] 备份并部署生产，验证服务、Nginx、health、MIME、`CONTENT_MODE` 和 SQLite。

## 当前审计结论

- 新 ZIP SHA-256：`FB8F644F6F219EE91B70E75F0B0C27689BE53749411C8B900D14A87CF6B134C5`。
- ZIP 版本实现会先覆盖 `local_apps` 再快照，且空会话版本跟随最新，不能直接上线。
- ZIP 的社区 Mod 与聊天 Mod 使用两套表，必须统一。
- ZIP 的 UI demo 使用 `allow-same-origin`，必须改为现有安全沙箱边界。
- ZIP 的 Spine 图层把 `_render()` 方法覆盖为对象，第二次切换会稳定失败；这是本轮优先修复点。

## Spine 验证记录（2026-07-20）

- 固定本地官方 `@esotericsoftware/spine-webgl@4.2.119`，与 npm 包 IIFE 文件逐字节一致，SHA-256 为 `FACCF252486DE234C69A045AA6024B6688DED578EFF09103607ADFAEDD7752B6`；许可证与 4.2.119 包内 `LICENSE` 一致。
- `output/homer-spine-runtime/selftest_spine_support.py` 通过：20/20 个真实包，导出版本覆盖 4.2.0/4.2.33，最多 37 张 atlas 纹理页；4.1、多 skeleton、多 atlas 均被拒绝，旧表迁移和上传/删除通过。
- 真实 Chromium 夹具通过：连续 A→B→C→A、竞态快速切换、ResizeObserver、显隐、`WEBGL_lose_context` 丢失/恢复、单素材失败静态降级后重新加载、dispose 均成功，console warning/error 为 0；截图位于 `output/playwright/spine-runtime-audit-20260720.png`。
- 修复生产上传链路：Nginx 仅素材 PUT 路由放宽到 60 MiB，普通 API 保持 32 MiB；空/octet-stream ZIP MIME 规范为 `application/zip`。

## 社区、版本与浏览器验证记录（2026-07-20）

- `output/verify_community_versions_backend.py` 通过：初始 v1/发布新版本、版本名和作者介绍必填、事务回调回滚、双击发布第二次 409、跨卡版本拒绝、私有卡禁止新会话但已锁定历史会话可继续、runtime-card 固定旧版本、Mod/预设/UI 模板锁定版本、群聊成员版本、赛事投票/换版本清票、SQLite `quick_check=ok`。
- `output/verify_backend_mobile_reliability_local.py`、`verify_chat_rollback_local.py`、`verify_tavo_plugin_local.py`、`verify_card_png_metadata.py` 均通过；后端流式中断清理、续写、回溯、Tavo 插件与 PNG 角色卡兼容未回退。
- 相关 13 个 Python 文件 `py_compile`、13 个 JS/MJS `node --check`、`git diff --check` 全部通过。
- `output/homer-community-browser/run_browser_acceptance.py` 在真实 Chromium 完成桌面 1440px 与移动端 390px 共 94 项断言：历史三点菜单、工坊新建、三类社区作品与隔离 UI 演示、赛事榜、开源/赛事/收藏预设与 UI、角色历史版本/票数/选择、聊天版本锁定与双列 Mod 均通过；failure/pageerror/console error 均为 0，共生成 17 张验收截图。

## 生产部署记录（2026-07-20）

- 功能提交 `e3d04b5` 已推送至 `origin/main`；部署使用 `tools/deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot`，未重建 APK。
- 部署前 SQLite Online Backup：`/opt/ai-fengyue-backend/backups/ai_fengyue-before-community-versions-20260720-130848.sqlite3`，live/backup `quick_check=ok`；同时备份前端源码 tar、systemd unit、Nginx 和原后端模块。
- 部署后 `ai-fengyue-backend.service`、Nginx 均 active，内外 `/health` 为 `OK`，`CONTENT_MODE=local_only`，线上 SQLite `quick_check=ok`。
- Nginx 素材 PUT 路由为 `client_max_body_size 60M`；`.mjs` 返回 `text/javascript`，固定 Spine runtime 返回 JavaScript MIME，许可证 HTTP 200。
- 线上后端 SHA-256 与本地一致：`2B13BA675D4BACB80CBDA9AB4C2802AEEF433E0BD4011A7FEFB85711476D33DF`；线上 Spine runtime SHA-256 为 `FACCF252486DE234C69A045AA6024B6688DED578EFF09103607ADFAEDD7752B6`。
- 生产真实 Chromium 只读烟测在桌面 1440px/移动端 390px 共 14 项通过：工坊九入口和四类新建、社区四页签及无横向溢出、制卡开源/赛事/Spine 入口均正常，console/page error 为 0。

## 社区浅色主题可读性修复（2026-07-20）

- [x] 定位 Mod、UI 模板、预设、当前赛事共用样式仍沿用深色原型，导致浅色页面上出现近白文字。
- [x] 统一修复分类标签、范围筛选、搜索框、作品卡、空状态、赛事信息和排行榜的浅色主题对比度。
- [x] 完成桌面与 390px 四分类、三种范围筛选、空状态、hover/focus、无溢出及浏览器错误验证。
- [ ] 提交、推送并部署生产，复查服务、Nginx、health、`CONTENT_MODE` 和 SQLite。

### 本地浏览器验证

- `output/homer-community-browser/run_browser_acceptance.py` 在真实 Chromium 完成 130 项断言，桌面 1440px 与移动端 390px 均无横向溢出，console/page error/failure 均为 0。
- 四类标签最低对比度 `6.81:1`，三种范围筛选最低 `7.02:1`，作品空状态 `7.83:1`；作品卡最低 `5.70:1`，赛事与排行最低 `5.93:1`，全部高于普通文字 `4.5:1` 目标。
- 截图：`output/playwright/homer-community-browser/desktop-community-preset-empty.png`、`mobile-390-community-preset-empty.png`、`desktop-community-contest.png`、`mobile-390-community-contest.png`。
