# AI星月运营后台增强任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| AOE1 | 建立运营后台增强 SPEC | Done | requirements/design/tasks |
| AOE2 | 后端增加数据库管理员标记和授权 API | Done | `py_compile`；本地/线上 API 授权、进入后台、撤销测试通过 |
| AOE3 | 后端 stats 增加图表数据 | Done | 本地/线上 `/admin/api/stats` 返回 `charts.daily_users`、`daily_requests`、分布数据 |
| AOE4 | 前端用户管理显示和切换管理员权限 | Done | 线上 `/admin.html` 用户表格显示“权限”列和“设为管理员/撤销管理员”按钮 |
| AOE5 | 前端数据总览增加可视化图表 | Done | 线上浏览器截图确认近 7 日用户/请求、余额构成、角色来源、状态分布、热门路径渲染 |
| AOE6 | 部署与线上验证 | Done | deploy helper 成功；服务 active；Nginx OK；`/health` OK；线上 admin API/UI 验证通过 |

## 2026-06-26 验证记录

- 本地编译：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过。
- 本地 API：`D:\Anconda3\python.exe .\output\verify_admin_ops_local.py` 返回 `stats_charts=true`、`ordinary_denied=true`、`grant_admin=true`、`revoke_admin=true`、`env_admin_protected=true`。
- 线上部署：`D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` 成功；`ai-fengyue-backend.service` active；Nginx 配置测试成功；`https://patcher.villainy.top/health` 返回 `OK`。
- 线上 API：远程验证脚本返回 `ordinary_denied=true`、`charts_daily_users=true`、`charts_daily_requests=true`、`charts_distributions=true`、`listed_as_normal=true`、`grant_database_admin=true`、`granted_can_enter_admin=true`、`revoke_database_admin=true`，测试用户已清理。
- 浏览器：Playwright 打开线上 `/admin.html`，数据总览图表和用户权限列渲染正常；控制台无错误，只有既有 Tailwind CDN production warning。
- 截图：
  - `output/playwright/admin-ops-overview.png`
  - `output/playwright/admin-ops-users.png`
