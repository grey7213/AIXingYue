# AI星月运营后台增强设计

## 后端设计

### 数据结构

- `users.is_admin integer not null default 0`
  - 数据库管理员权限标记。
  - `ADMIN_EMAILS` 仍拥有最高优先级，作为环境兜底管理员。

### 权限判断

- `is_admin(user)` 返回：
  - 用户邮箱在 `ADMIN_EMAILS` 中；或
  - `users.is_admin=1`。
- `admin_user_json(row)` 给前端返回：
  - `is_admin`
  - `admin_source`: `env` / `database` / `none`
  - `can_toggle_admin`: 环境管理员不可被页面撤销，避免误导。

### API

- `GET /admin/api/users`
  - 继续分页和搜索。
  - 返回用户权限状态。
- `POST /admin/api/users/{id}/admin`
  - body: `{ "is_admin": true|false }`
  - 环境管理员用户不能通过页面撤销，只能改服务器配置。
  - 返回更新后的用户摘要。
- `GET /admin/api/stats`
  - 保留旧字段。
  - 新增：
    - `admin_count`
    - `charts.daily_users`
    - `charts.daily_requests`
    - `charts.request_status`
    - `charts.points_split`
    - `charts.app_sources`
    - `charts.top_paths`

## 前端设计

### 用户管理

- 表格新增“权限”列。
- 管理员显示徽标和来源：
  - `环境管理员`
  - `后台授权`
  - `普通用户`
- 操作区增加“设为管理员 / 撤销管理员”按钮。

### 数据总览

- 使用纯 HTML/CSS/Alpine 渲染：
  - 7 日新增用户条形图。
  - 7 日请求量条形图。
  - 积分余额构成横向分布条。
  - 角色来源构成横向分布条。
  - 请求状态分布横向分布条。
  - 24h 热门路径列表。

## 安全边界

- 所有新 API 仍走现有管理员鉴权。
- 不在前端暴露 API Key、SMTP 密钥、服务器凭据。
- 页面撤销管理员不能影响环境变量兜底管理员。
