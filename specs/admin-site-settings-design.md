# AI星月后台运营配置设计

## 后端

### 存储

- 使用现有 `api_settings` 表保存 `site_settings` JSON。
- `Store.site_settings()` 合并默认值和已保存值。
- `Store.update_site_settings(data)` 只接受白名单字段并做长度/类型裁剪。

### 默认配置

- `home`：官网首页可见文案、按钮链接、功能卡片、下载信息和 FAQ。
- `app`：全局公告开关和文案、信息中心文案和统计标签、桌面/移动导航标签、App Shell 用户卡兜底文案。
- `app_home`：App 首页/探索页标题、搜索框、筛选标签、排序标签、无图模式、卡片兜底和加载按钮。
- `auth`：登录/注册页和用户中心未登录面板的标题、Tab、按钮和提示。
- `dashboard`：用户中心余额、签到、下载、后台入口、API 信息、登录/注册字段和签到/兑换/登录 toast 文案。
- `account`：“我的”页账户、人设、模型连接器、APP 接入信息、字段占位和账号操作 toast 文案。
- `my_apps`：我的角色页标题、按钮、卡片兜底、编辑弹窗字段和保存/删除提示。
- `character`：角色详情页标题、按钮、徽标、空态和分区标题。
- `chat`：聊天页会话列表、角色头图空态、记忆抽屉、消息操作、输入框、确认/报错提示。
- `creator`：角色编辑器工具栏、基础字段、提示词、Prompt Manager、备用开场白、世界书、高级提示词、默认模型、语音/分享占位和保存删除提示。
- `group_chat`：群聊页列表、创建面板、成员/消息提示、输入框、toast 和确认文案。
- `rewards`：每日签到积分、任务列表、奖励页 Credits/余额/套餐/任务状态/兑换记录和领取按钮文案。
- `deposit`：购买链接、汇率说明、购买/兑换展示文案、支持说明、套餐列表。
- `empty_states`：探索、收藏、历史、我的角色、操作记录、兑换记录、工坊和图片聊天空状态/占位文案。

### API

- `GET /console/api/public/site-settings`
  - 公开读取，无需登录，不含密钥。
- `GET /admin/api/site-settings`
  - 管理员读取完整可编辑配置。
- `POST /admin/api/site-settings`
  - 管理员保存配置。

### 业务接入

- `deposit_meta_json()` 从 `site_settings.deposit` 读取购买链接、说明和套餐。
- `/console/api/web/rewards` 从 `site_settings.rewards` 读取每日积分和任务。
- `/console/api/web/rewards/daily` 和旧 `/console/api/ctf/dailyapppoints` 使用配置的每日积分。

## 前端

### 官网

- 新增 `frontend/assets/js/site-settings.js`。
- 首页给关键文案/链接增加 `data-site-text` / `data-site-href` 标记。
- 脚本加载公开配置，按路径替换文本和链接，并渲染功能卡片、下载信息和 FAQ；失败时保留静态默认文案。

### App Shell

- `layout.js` 加载公开配置。
- 若 `app.announcement_enabled` 为真，在 `.app-main` 顶部插入公告条。
- `layout.js` 用 `app.nav_labels` 和 `app.mobile_nav_labels` 替换桌面侧栏、移动底栏菜单名。
- 信息中心页面复用 `loadPublicSiteSettings()`，从 `app.info_*` 字段渲染文案和统计标签。
- 登录页、用户中心、“我的”页、工坊、收藏、历史、操作记录、图片聊天、我的角色页读取公开配置；失败时保留静态默认文案。
- 角色详情页、聊天页、角色编辑器和群聊页读取公开配置；失败时保留静态默认文案。
- App 首页/探索页从 `app_home` 读取筛选/排序/卡片/加载文案；我的角色页从 `my_apps` 读取管理弹窗和 toast 文案；用户中心和“我的”页从扩展后的 `auth`、`dashboard`、`account` 读取字段和交互文案。
- 登录页复用 `auth` 字段；奖励页从 `rewards`/`deposit`/`dashboard` 读取 Credits、套餐、领取、兑换记录和任务状态文案；App Shell 用户卡从 `app` 读取兜底昵称、积分后缀和链接 title。
- ASS13 补漏项仍复用已有配置分区：`empty_states.image_reply_title`、`chat.no_conversations_prefix`、`creator.prompt_position_*` 和 `creator.load_existing_failed`。
- 交互类文案（confirm、alert、toast、placeholder、title、aria-label）只使用纯文本配置，不插入 HTML。

### 后台

- `api.admin.siteSettings()` 和 `api.admin.saveSiteSettings()`。
- `admin-app.js` 增加 `siteSettings`、`siteForm` 和保存/套餐/任务编辑方法。
- `admin.html` 增加“运营配置” Tab，分块编辑官网、功能卡片、下载信息、FAQ、App 公告、信息中心、登录/注册、导航、App 首页/探索、用户中心/我的页、我的角色管理、角色详情、聊天页、角色编辑器、群聊页、空状态、奖励、购买套餐。

## 安全

- 只写纯文本和 URL，不写任意 HTML。
- URL 只允许空值、站内相对路径、`http://`、`https://`、锚点。
- API Key/SMTP 等敏感配置不进入运营配置。
