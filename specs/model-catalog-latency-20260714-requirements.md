# 惑梦对话模型目录与延迟优化需求

## 目标

- 将用户截图中的 CelestiAI Gemini 对话模型完整加入后台，共 `48` 个。
- 普通、`假流式/`、`流式抗截断/` 三组各 `16` 个，普通用户只能看到模型名称/选择 ID，不得看到 API Key。
- 降低默认对话的实际等待时间，并让需要全文 Regex/模板处理的角色在上游已有响应后不再一直显示“思考中”。

## 范围

- 后台站点模型预设、公开模型列表、单聊发送和 AI 续写流式链路。
- 保留全局 Prompt、全局 Regex、角色 Regex、Tavo/酒馆助手模板、积分扣费和消息完整性校验。
- 不恢复普通用户 BYOK，不修改 APK，不迁移历史接口/数据库命名。

## 模型集合

每组包含：

- `gemini-2.5-pro-cli`
- `gemini-2.5-pro-high-cli`
- `gemini-2.5-pro-high-search-cli`
- `gemini-2.5-pro-low-cli`
- `gemini-2.5-pro-low-search-cli`
- `gemini-2.5-pro-max-cli`
- `gemini-2.5-pro-max-search-cli`
- `gemini-2.5-pro-medium-cli`
- `gemini-2.5-pro-medium-search-cli`
- `gemini-2.5-pro-minimal-cli`
- `gemini-2.5-pro-minimal-search-cli`
- `gemini-2.5-pro-search-cli`
- `gemini-3.1-pro-preview-cli`
- `gemini-3.1-pro-preview-low-cli`
- `gemini-3.1-pro-preview-low-search-cli`
- `gemini-3.1-pro-preview-search-cli`

三组前缀分别为空、`假流式/`、`流式抗截断/`。

## 验收标准

- 公开 `/console/api/web/model-presets` 返回 `48` 个唯一模型选择，目标模型缺失数为 `0`，响应不包含 API Key。
- 中文前缀模型的公开选择 ID 唯一，能够准确还原到对应上游模型名。
- 默认模型改为实测更快的 `gemini-2.5-pro-minimal-cli`；显式绑定其他模型的少量角色保持原选择。
- 对无需全文后处理的回复，后端可以逐个透传上游 delta；需要 Regex/模板全文处理时继续缓冲，但首个上游 delta 到达后发送“正在整理角色回复”状态。
- 服务端记录脱敏的首 delta、上游总耗时、后处理耗时和总耗时，不记录提示词、回复正文或密钥。
- 单聊/续写完成事件、扣费、落库和截断清理保持正确；空内容兜底不再触发 `IndexError`。
- 部署前备份 SQLite 和相关代码；部署后 backend/Nginx active，内外 `/health` OK，`CONTENT_MODE=local_only`，DB `quick_check=ok`。

## 非目标

- 不承诺消除 CelestiAI 自身的 429/500/超时。
- 不默认使用 search/high/max 模型；这些保留为用户主动选择项。
- 不让需要全文 Regex/Tavo 处理的卡直接展示未经处理的原始模型文本。
