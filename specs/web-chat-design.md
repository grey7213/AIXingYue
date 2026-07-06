# AI星月 Web 角色聊天设计

## 架构

- 后端继续使用单文件 Python HTTP 服务和 SQLite。
- 账号、积分、充值、角色、聊天会话都使用同一个 SQLite 数据库。
- `local_apps` 作为角色卡主表：
  - `source='upstream'`：管理员同步/发布的上游角色。
  - `source='user'`：普通用户创建的角色。
  - `owner_user_id`：用户角色归属。
- `conversations` / `conversation_messages` 保存 Web 聊天历史。
- 新增 `api_settings` 表保存站点级模型 API 配置。

## 模型 API 配置

- 启动时仍支持环境变量兜底：
  - `USER_LLM_BASE_URL` / `OPENAI_BASE_URL`
  - `USER_LLM_API_KEY` / `OPENAI_API_KEY`
  - `USER_LLM_MODEL` / `LLM_MODEL`
- 数据库配置优先级高于环境变量。
- 管理接口：
  - `GET /admin/api/llm-settings`
  - `POST /admin/api/llm-settings`
- 返回字段：
  - `enabled`
  - `base_url`
  - `model`
  - `temperature`
  - `has_api_key`
  - `api_key_preview`
- 保存时：
  - `api_key` 为空表示保留原 key。
  - `clear_api_key=true` 清空 key。

## 积分扣费

- 新用户注册时写入 `2500` 到 `points` 和 `free_points`，对应 50 次成功角色回复。
- `CHAT_MESSAGE_COST=50` 表示一次成功角色回复的固定扣费。
- 扣费前校验总余额，余额不足直接返回错误，不进入模型生成。
- 扣费发生在助手回复成功保存后；生成失败不扣费。
- 扣费顺序为 `free_points` -> `reward_points` -> `paid_points`，并同步兼容字段 `points`。
- Web 单聊流式/阻塞、旧 APK chat-messages 兼容入口、群聊角色回复都复用同一扣费方法。

## Web 页面

- `login.html` 保持现状。
- `explore.html`：移动优先发现流，桌面保留侧栏，移动端使用底部导航。
- `character.html`：新增角色详情页，作为探索页到聊天页之间的确认层。
- `character.html`：对 JSON/Character Card 风格设定做可读化渲染，优先抽取姓名、年龄、性别、学校/身份、描述等常见字段，避免移动端直接显示一整段原始 JSON。
- `chat.html`：桌面双栏，移动端聚焦单会话输入。
- `histories.html`：历史会话列表支持继续、复制和删除；复制会话在服务端克隆 conversation/messages/summary，删除调用已有会话删除接口。
- `create.html`：普通用户只填写角色设定，不暴露 API key。
- `my-apps.html`：编辑/删除我的角色。
- `me.html`：个人信息、积分、充值、账号共享说明。

## 视觉

- 延续现有 AI星月深色星空风格和登录页资产。
- 控件密度更接近移动 App：底部导航、紧凑顶部栏、全屏卡片和大封面详情。
- 不做营销式 hero；进入后就是可用的角色聊天产品。

## 验证

- 本地静态文件结构检查。
- Python 后端 `py_compile`。
- 线上部署后用 `curl` 验证 health、explore、app detail、admin llm settings。
- 用网页登录测试创建角色、聊天、封面/角色读取。
