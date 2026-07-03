# AI星月后台内容管理设计

## 后端

### Store 方法

- `create_admin_app(data)`：继续用于单张官方角色创建。
- `update_admin_app(app_id, data)`：放宽为管理员更新任意 `local_apps` 行。
- `bulk_update_admin_apps(ids, data)`：管理员批量更新指定 `local_apps` 行。
  - 标签：读取/写入 `local_apps.tags` JSON，支持 `replace`、`append`、`remove`。
  - 简介/角色设定：只有 `summary_enabled` / `description_enabled` 为真时才写入对应列。
  - 世界书：读取/写入 `extra_settings.world_info`，保留同一 JSON 内的 `regex_scripts`、`prompt_blocks`、`alternate_greetings` 等其它扩展字段。
  - 世界书输入兼容数组、`{entries:[...]}`、`{world_info:[...]}`、Character Book 和 Character Card V2 `data.character_book.entries`。
  - `merge` 按非自动生成 `id` 优先，其次按 `name` 合并；没有命中的条目追加到末尾。
- `delete_admin_app(app_id)`：放宽为管理员删除任意 `local_apps` 行。
- `import_admin_apps(items, created_by)`：批量规范化导入角色卡，写入 `source=admin`。

### API

- `GET /admin/api/apps`
  - 已存在，继续支持 `source=admin|user|upstream|all`、`q`、分页。
  - 支持 `lightweight=1` 返回轻量列表卡，避免后台列表拉取大世界书/正则/扩展字段。
- `GET /admin/api/apps/{id}`
  - 管理员按需读取完整角色卡详情，用于编辑弹窗。
- `POST /admin/api/apps/create`
  - 已存在，创建单张官方角色。
- `POST /admin/api/apps/import`
  - body: `{ items: [...], source?: "admin" }`
  - 返回：`created`、`errors`、`count`。
- `POST /admin/api/apps/bulk-update`
  - body:
    ```json
    {
      "ids": ["admin-1", "user-2"],
      "tags_mode": "replace|append|remove|none",
      "tags": ["恋爱", "校园"],
      "summary_enabled": true,
      "summary": "新的短简介",
      "description_enabled": true,
      "description": "新的角色设定",
      "world_mode": "replace|append|merge|none",
      "world_info": [{"name": "地点", "keys": ["图书馆"], "content": "..."}]
    }
    ```
  - 返回：`requested`、`updated`、`not_found`、`errors`、`ids`。
  - 单次最多处理 200 个 ID。
- `POST /admin/api/apps/{id}/update`
  - 管理员可更新任意来源角色字段。
- `POST /admin/api/apps/{id}/delete`
  - 管理员可删除任意来源角色。

## 前端

### `frontend/assets/js/api.js`

- 增加 `admin.importApps(payload)`。

### `frontend/assets/js/admin-app.js`

- 增加导入弹窗状态：
  - `appImportDialog`
  - `appImportRaw`
  - `appImportFileName`
  - `appImportResult`
- 增加批量编辑状态：
  - `selectedAppIds`
  - `appBulkDialog`
  - `appBulkForm`
  - `appBulkResult`
- 增加：
  - `openImportDialog()`
  - `onAppImportFileChange()`
  - `parseImportItems()`
  - `submitAppImport()`
  - `toggleAppSelection(app)`
  - `toggleSelectCurrentApps(checked)`
  - `openBulkDialog()`
  - `submitBulkUpdate()`
  - `quickToggleAppPublic(app)`
  - `quickSetAppStatus(app, status)`
- 编辑弹窗复用现有字段，增加来源提示。
- 角色列表请求 `lightweight=1`；点击编辑时再调用 `admin.appDetail(id)` 拉完整字段。

### `frontend/admin.html`

- 角色卡 Tab 顶部增加“导入 JSON”按钮。
- 角色卡 Tab 表格增加勾选列、当前页全选和“批量编辑”按钮。
- 批量编辑弹窗提供标签模式、简介覆盖、角色设定覆盖和世界书模式输入。
- 表格操作对所有来源开放“编辑/删除/上下架/公开切换”。
- 增加导入 JSON 弹窗，支持文件上传和文本粘贴。

## 数据安全

- API 仍走管理员鉴权。
- 批量编辑只修改显式传入的 ID，不按筛选条件隐式批量更新。
- 简介、角色设定、世界书替换属于覆盖操作，前端提交前二次确认。
- 删除动作前端二次确认。
- 导入失败逐条返回错误，不影响其它有效卡片。
