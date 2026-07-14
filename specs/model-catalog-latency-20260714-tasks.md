# 惑梦对话模型目录与延迟优化任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| ML1 | 核对截图 48 模型与现网差异 | Done | 目标 48，现网 8，缺失 40，额外 0 |
| ML2 | 审计 20–50 秒等待链路 | Done | 定位默认 max 模型、handler 全文缓冲、CelestiAI 429/500/timeout |
| ML3 | 修复中文前缀模型选择 ID 和默认项映射 | Done | 本地验证 48 个模型得到 48 个唯一选择 ID；minimal 为唯一推荐默认项 |
| ML4 | 增加安全真流式、buffered 状态和分段耗时日志 | Done | 线上 buffered 请求约 2.1 秒收到 `postprocessing` 状态；日志包含首 delta/上游/后处理/总耗时 |
| ML5 | 备份并写入 48 模型，默认切换 minimal | Done | 公开 API `total=48/unique_ids=48/unique_models=48`，三组各 16，未暴露 API Key |
| ML6 | 部署、浏览器/API/健康/DB 回归 | Done | backend/Nginx active，内外 `/health` OK，`CONTENT_MODE=local_only`，DB/备份 `quick_check=ok` |
| ML7 | Git 提交并推送 `origin/main` | Done | 本轮文件已按项目备份策略提交并推送 |

## 已验证基线

- 2026-07-14 线上 backend/Nginx active，内网 `/health` OK，`CONTENT_MODE=local_only`。
- 后端本地/线上 SHA-256 一致：`7882f237...cc6a91`。
- CelestiAI 短回复旁路实测：max `14.4s`、普通 `24.3s`、low `9.1s`、minimal `2.8s`、抗截断 minimal `5.0s`。
- 近 6 小时日志：LLM 429 `7`、500 `8`、read timeout `4`、普通/续写客户端断开 `13`。

## 完成结果

- 线上备份：`/opt/ai-fengyue-backend/data/backups/ai_fengyue-before-model-catalog-20260714-160333.sqlite3`，备份和 live DB 均 `quick_check=ok`。
- 旧重复 preset `preset-y92e76gq` 已合并删除；唯一引用该旧 preset 的 1 张角色卡已迁移到对应的 `流式抗截断/gemini-2.5-pro-search-cli` 新选择 ID。
- 使用相同临时角色/提示的线上平台验收：minimal 总耗时约 `18.7s`，max 约 `38.5s`；minimal 约缩短 `51%`。两次都在约 `2s` 收到模型首 delta/status。
- 需要全局/角色 Regex 的请求仍等待最终处理文本，但 UI 会从“已思考”切换为“模型已响应，正在整理角色回复”；无全文后处理的请求具备逐 delta 真流式路径。
- 浏览器模型选择器显示 48 个模型，minimal 标记为“推荐模型”，console error 为 `0`。截图：`output/playwright/model-catalog-48-live.png`。
