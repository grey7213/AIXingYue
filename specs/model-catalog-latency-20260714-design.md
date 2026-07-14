# 惑梦对话模型目录与延迟优化设计

## 现状结论

- 线上只有 `8` 个公开选择，默认是 `gemini-2.5-pro-max-cli`。
- 实测短回复：max 首 delta 约 `14.4s`，low 约 `9.1s`，minimal 约 `2.8s`。
- 后端 `stream_user_llm_chunks()` 能实时读取上游 SSE，但聊天 handler 先 `join` 全文再发给浏览器，导致首字等待等于整段生成耗时。
- 线上全局 Regex 启用且包含 assistant/render 规则，不能无条件展示处理前文本。
- 原 `model_selection_id()` 会把中文前缀剥掉，三组同名模型可能产生重复选择 ID。

## 设计

### 模型配置

- 使用一个 CelestiAI preset 保存完整 `48` 模型，共用现有服务端 Base URL/API Key。
- 删除旧的单模型重复 preset，避免同一上游模型出现重复入口。
- preset 默认模型设为 `gemini-2.5-pro-minimal-cli`，模型列表仍保留全部档位。

### 选择 ID

- 纯 ASCII 模型继续使用旧 slug，保持已有角色引用兼容。
- 含非 ASCII 前缀的模型在 slug 后增加模型名 SHA-1 短后缀，确保 `假流式/` 与 `流式抗截断/` 不冲突。
- 公开默认项根据 preset 的真实 `model` 字段判断，不再固定认为模型列表第一个是默认。

### 流式与后处理

- 新增保守判定：角色 Regex、assistant/render 全局 Regex、世界书 render 注入存在时使用 buffered 模式。
- buffered 模式收到首个上游 delta 后发 SSE `status: postprocessing`，前端显示“模型已响应，正在整理角色回复”。
- 无上述全文变换时逐 delta 发送并同时累计原文；完成后仍执行最终规范化，以 `message_end.reply` 校正并作为落库正文。
- 发送/续写均记录 `first_delta_ms`、`upstream_total_ms`、`postprocess_ms`、`total_ms`、模型和 buffered 标记。

### 兼容与安全

- API Key 继续只保存在服务器 SQLite，不进入公开 API、Git、日志或验证输出。
- 全局/角色 Regex 仍在完整回复上执行；不改变积分扣费、消息事务和客户端断开清理逻辑。
- 前端仅处理新的普通 `status` SSE 事件，不放宽 sandbox 或用户 API 权限。

## 验证

- 本地函数级检查 48 模型唯一 ID、默认模型映射、buffer 判定和空内容兜底。
- 线上更新前做 SQLite Online Backup；更新后检查 48 个公开模型唯一且无密钥。
- 用临时用户/普通无 Regex 角色验证真流式首 delta；用带 Regex 角色验证 buffered 状态和最终处理结果。
- 抽测 minimal 模型平台首响应/总耗时并清理测试数据。
