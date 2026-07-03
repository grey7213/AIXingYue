# AI星月多模型预设设计

## 存储

继续使用 `api_settings` KV 表，新增 JSON 字段：

- `model_presets`: JSON 数组。
- `default_model_preset_id`: 默认预设 ID。

预设结构：

```json
{
  "id": "preset_xxx",
  "name": "默认聊天",
  "enabled": true,
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "temperature": 0.8,
  "api_key": "sk-..."
}
```

兼容旧字段：

- `base_url`
- `model`
- `temperature`
- `api_key`
- `enabled`

如果 `model_presets` 为空，则从旧字段构造一个 `default` 预设。

## 后端方法

- `llm_presets(include_secrets=False)`：返回规范化预设。
- `public_model_presets()`：给用户创建角色页面使用，不包含 Key。
- `effective_llm_settings(app=None)`：如果 `app.llm_model` 命中预设 ID 或模型名，则返回该预设；否则返回默认预设。
- `update_llm_settings(data)`：保存多个预设，保留未改 Key。

## API

- `GET/POST /admin/api/llm-settings`：后台配置多个预设。
- `GET /console/api/web/model-presets`：用户端获取启用预设。

## 前端

### Admin

- `llmForm.presets[]`
- 增加“添加模型预设”“删除”“设为默认”。
- 每个预设字段：名称、启用、Base URL、模型、Temperature、API Key、清空 Key。

### User Create

- 加载 `api.modelPresets()`。
- 将原模型文本输入替换为 select。
- 默认选择后端返回的默认预设。
