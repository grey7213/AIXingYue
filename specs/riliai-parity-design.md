# AI星月 Web 对齐 RiliaiChat 功能设计

## 产品结构

- 保持现有静态 HTML + Alpine.js + 单文件 Python 后端结构。
- `/app/index.html` 作为 Home 入口，加载与 `explore.html` 同一套发现流。
- 新增页面：
  - `workshop.html`：创作中心。
  - `histories.html`：历史会话。
  - `favorites.html`：收藏角色。
  - `image-chat.html`：图片聊天入口。
  - `rewards.html`：奖励中心。
  - `logs.html`：用户日志。
  - `info.html`：信息中心 / APK 对齐说明。

## 导航

- 桌面侧栏对齐参考站的信息架构：
  - Home
  - Workshop
  - Histories
  - Favorites
  - Image Chat
  - Rewards
  - Logs
  - Deposit
  - Info Center App
- 移动底栏保留 5 个高频入口：
  - Home
  - Chat
  - Create
  - Favorites
  - Me
- 次级入口放在页面顶部快捷入口或侧栏。

## 后端补充

- 新表 `user_favorites`：
  - `user_id`
  - `app_id`
  - `created_at`
  - unique `(user_id, app_id)`
- 新表 `user_events`：
  - `id`
  - `user_id`
  - `event_type`
  - `summary`
  - `payload_json`
  - `created_at`
- 新 API：
  - `GET /console/api/web/favorites`
  - `POST /console/api/web/favorites/{app_id}/toggle`
  - `GET /console/api/web/logs`
  - `GET /console/api/web/rewards`
  - `POST /console/api/web/rewards/daily`
  - `POST /console/api/web/image-chat`
  - `GET /console/api/web/home-stats`
- 复用已有：
  - `GET /go/api/explore/search`
  - `GET /console/api/web/conversations`
  - `POST /console/api/web/chat`
  - `GET/POST /console/api/web/my-apps*`
  - `POST /console/api/ctf/recharge`

## 探索排序/分类

- 后端当前角色库可按 `sort_weight`、`players_count`、`updated_at`、`created_at` 做本地排序。
- `rank` 参数先作为 UI 状态和轻量排序权重，不引入复杂榜单统计：
  - `daily` / `weekly` / `monthly` / `overall`
- `tag` 参数按 `tags` JSON 文本模糊匹配。
- `pictureless=true` 时后端仍返回角色，但前端隐藏封面并使用紧凑文本卡。

## 视觉

- 不复制参考站样式；采用 AI星月已有深色星空、APK logo、角色封面和移动 App 密度。
- 方向选择：Glow + grain，但降低紫色占比，混入青蓝、玫红和暗金点缀，避免单一紫色主题。
- 页面不是营销 landing，首屏直接是可使用的角色发现/聊天产品。

## 验证

- 本地 `py_compile` 后端。
- 静态页面检查和关键文本/API 路径 grep。
- 部署后 `curl` 验证页面 200 和 API 成功。
- 用浏览器截图验证桌面和移动 `/app/`、`/app/favorites.html`、`/app/image-chat.html`、`/app/logs.html`。
