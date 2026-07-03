# AI星月多模型预设需求

## 目标

- 管理端可以配置多个 OpenAI-compatible 模型预设。
- 每个预设可有独立名称、Base URL、模型名、Temperature、API Key、启用状态。
- 管理员选择一个默认预设。
- 用户创建角色卡时只能从管理员配置好的启用预设中选择，不直接填写 API Key。
- 旧的单模型配置要兼容，不能让已有模型配置失效。

## 用户流程

- 管理员进入 `/admin.html` 的“模型配置”。
- 管理员可添加多个模型预设，例如“默认聊天”“便宜快速”“高质量角色扮演”。
- 管理员保存后，用户在 `/app/create.html` 创建角色卡时看到模型下拉框。
- 用户选择模型预设后创建角色，聊天时后端按该角色选择的预设调用模型。

## 验收标准

- `GET /admin/api/llm-settings` 返回预设列表和默认预设。
- `POST /admin/api/llm-settings` 可以保存多个预设，API Key 不明文回显。
- `GET /console/api/web/model-presets` 返回启用预设，不包含 API Key。
- 创建角色卡时保存用户选择的 `llm_model`。
- 聊天调用能根据角色卡的 `llm_model` 找到对应预设的 Base URL/API Key/model。
- 本地和线上验证 API 正常，页面渲染可见多模型配置和用户选择控件。

## 非目标

- 不做每个用户自带模型 Key。
- 不做模型用量计费统计。
- 不改变 APK 原生端模型配置。
