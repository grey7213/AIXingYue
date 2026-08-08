# 惑梦《道渊》提示词助手与消息头像 Design

日期：2026-08-08

## 现有架构

- 对话页面运行固定 SillyTavern 1.18.0，Homer 集成位于 `sillytavern-runtime/public/scripts/extensions/homer-bridge/`。
- 公共扩展中 `js-slash-runner`、`ST-Prompt-Template`、`SillyTavern-MemoryBooks` 保持启用；`st-yuzi-phone` 强制停用。
- 角色卡内容由服务端同步到 runtime，会话锁定角色版本是脚本/预设的权威来源。

## Prior art 与定向调查

1. 直接复用仓库固定上游实现：SillyTavern 1.18.0 的 Character Card 生命周期与 JS-Slash-Runner 4.8.19 的 `data.extensions.tavern_helper.scripts` 角色脚本树；不另造脚本执行器。该固定扩展许可证和风险已在 `homer-sillytavern-apk-readiness-20260729-design.md` 登记。
2. 原夹具路径已失效；从 `E:\obs录制\惑梦-Homer-外部导入与角色卡兼容阶段备份-20260801.zip` 恢复原始 PNG 到 `output/homer-daoyuan-prompt-helper-20260808/recovered/daoyuan-v5.2-original.png`。SHA-256 和来源仅写入本轮本地验收产物，不把卡片正文写入日志。
3. 恢复夹具含 307 条世界书、17 条 Regex、3 个已启用 TavernHelper 脚本（MVU、ZOD、道渊配置助手）。生产两张已发布《道渊》只有 199/200 条规范化世界书、15 条 Regex，且当前行和全部历史版本均缺少 `sillytavern_card`、`extensions.tavern_helper.scripts`，因此丢失点是存量卡片数据，不是 bridge 缺少启用逻辑。
4. 隔离 E2E 证明完整卡片经当前导入/launch 链路后悬浮球 `#bp-switch-bubble` 和面板 `#bp-switch-panel` 可见、可点击；生产修复应只补回原始 `tavern_helper` 命名空间，不覆盖用户后来修改的世界书、Regex、Prompt 或公开状态。

## 头像处理

- 优先在 Homer bridge 样式层增加作用域明确的规则，仅隐藏 `#chat` 消息行内的 `.mesAvatarWrapper`/`.avatar`。
- 同步重置 `.mes_block`、`.mes_text`、消息操作栏等由头像宽度产生的 margin/padding/grid 列；不改上游通用角色列表样式。
- 若原版 ST 用设置类控制头像，仍以 Homer 样式作为生产确定性兜底，避免存量用户设置覆盖。

## 随卡脚本兼容

- 先复用原版 SillyTavern/`js-slash-runner` 已有角色脚本入口和事件生命周期，不复制一套平行执行器。
- 角色版本同步只传执行所需字段；普通用户 API 继续不返回脚本正文。
- 脚本继续运行在固定 SillyTavern 对话 runtime 的角色级 TavernHelper 生命周期内；不开放 `/api/extensions/install`、后台接口、模型 Key 或非 HttpOnly 身份凭据。卡片原有的三项固定 CDN 依赖不改写、不泛化为任意扩展安装能力。
- 若脚本已执行但悬浮窗不可见，只修作用域内的挂载点、层叠上下文、safe-area、overflow 和移动端尺寸，不改变脚本业务逻辑。

## 存量数据修复

- 先对生产 SQLite 做时间戳备份，再在单事务内为两张目标《道渊》的 `local_apps.extra_settings`、全部 `content_versions.snapshot_json` 和未发布 `content_drafts.snapshot_json` 合并原卡 `extensions.tavern_helper`。
- 保留目标 JSON 中其余字段，重新计算被修版本的 `content_hash`；不新建角色、不改 ID、作者、公开状态、版本号、世界书、Regex、Prompt 或会话锁定版本。
- 修复所有既有版本而不是仅切换 `current_version_id`，使已存在会话仍按原锁定版本获得同一随卡助手。

## 验证设计

- 静态：字段归一化/同步断言、Node syntax、Python compile、selftest、`git diff --check`。
- 浏览器：复用 `tools/_prepare_sillytavern_e2e.py`、`tools/_start_original_sillytavern_e2e.py`、`tools/_e2e_original_sillytavern_browser.py`，通过 `HOMER_COMPLEX_CARD_FIXTURE` 注入《道渊》PNG。
- UI：1440×900 与 390×844 截图；断言消息头像为 0、正文宽度释放、逐消息动作有效、提示词助手入口/面板可见且可交互。
- 安全：卡片固定 CDN 请求集合可解释，Yuzi 资源请求为 0，Prompt/脚本正文不进入普通详情 API、公开 runtime config、诊断日志或截图。
