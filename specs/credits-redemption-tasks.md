# AI星月 Credits / 爱发电兑换码任务

| ID | 任务 | 状态 | 验证 |
|----|------|------|------|
| CR1 | 创建需求与设计 SPEC | Done | `credits-redemption-requirements.md`、`credits-redemption-design.md` |
| CR2 | 后端增加三类余额、兑换码表、兑换历史表 | Done | `D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py` 通过；本地 HTTP 验证自动建表 |
| CR3 | 后端增加用户兑换和 deposit meta API | Done | 本地和线上验证：兑换一次成功、重复兑换返回 `兑换码已被使用`、`deposit-meta` 返回 `aifadian_redeem_code` |
| CR4 | 后端增加管理员兑换码 API | Done | 本地和线上验证：管理员生成/列表/禁用成功；普通用户访问返回 `forbidden: admin only` |
| CR5 | 前端 Rewards/Me 增加购买跳转和兑换码 UI | Done | `agent-browser` 截图：`output/playwright/rewards-auth.png`、`output/playwright/me-auth.png` |
| CR6 | 后台增加兑换码管理 Tab | Done | `agent-browser` 截图：`output/playwright/admin-redeem-tab.png`；Tab 元素可交互 |
| CR7 | 部署到 `patcher.villainy.top` | Done | deploy helper 成功；`ai-fengyue-backend.service` 和 `nginx` 均 active；`/health` 返回 `OK` |
| CR8 | 线上端到端验收 | Done | 页面：`/app/rewards.html`、`/app/me.html`、`/dashboard.html`、`/admin.html` 均 HTTP 200；`/app` 为 301 跳转；线上 API 兑换闭环通过 |

## 2026-06-19 验证记录

- 本地编译：`D:\Anconda3\python.exe -m py_compile .\tools\ai_fengyue_local_server.py .\tools\deploy_ai_fengyue_villainy.py` 通过。
- 本地 HTTP 验证：管理员 `local@ctf.test` 生成 `paid` 兑换码；兑换一次增加 `paid_points`；二次兑换失败；普通用户访问后台兑换码 API 返回 forbidden；未使用码可禁用。
- 线上部署：`D:\Anconda3\python.exe .\tools\deploy_ai_fengyue_villainy.py --skip-apk --skip-mail-install --skip-certbot` 成功，`CONTENT_MODE=local_only` 保持不变。
- 线上 API 验证：管理员生成 `777` 额度兑换码并成功兑换；重复兑换失败；`/console/api/web/deposit-meta` 返回 `mode=aifadian_redeem_code`；普通用户后台访问 forbidden。
- 线上页面验证：`curl` 返回 `/app/rewards.html=200`、`/app/me.html=200`、`/dashboard.html=200`、`/admin.html=200`、`/health=OK`。
- 浏览器验证：`agent-browser` 已截图 Rewards、Me、Admin 兑换码 Tab；Rewards 展示三类余额、推荐套餐、兑换记录；Me 展示三类余额和兑换入口；Admin 兑换码 Tab 可见生成/筛选/列表控件。
- 当前 `AIFADIAN_URL` 未配置，页面显示“暂未配置购买链接，请联系站长获取兑换码”的兜底。拿到爱发电 URL 后只需写入 `/opt/ai-fengyue-backend/ai-fengyue.env` 并重启后端。
