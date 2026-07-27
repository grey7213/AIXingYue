# 惑梦后台模型 API 自动发现与可用性检测任务

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| AMD1 | 建立 requirements/design/tasks SPEC | Done | 本组三份文档 |
| AMD2 | 实现目录发现、Key 安全复用和模型解析 | Done | `verify_admin_model_discovery_local.py` 覆盖 OpenAI/Anthropic、已保存 Key 留空复用 |
| AMD3 | 实现真实流式批量探测、限额与错误脱敏 | Done | 成功正文、空正文、HTTP 失败均覆盖；仅返回管理员可用的脱敏结果 |
| AMD4 | 后台新增节点、自动填充和检测结果 UI | Done | Node 检查及 `verify_admin_model_discovery_browser.py` 桌面/390px 通过，console/page error=0 |
| AMD5 | 回归公开模型目录和用户对话 | Done | 公开接口仅包含可用模型，不含 Key/Base URL/失败详情；会话运行时联合回归通过 |
| AMD6 | 备份、部署、健康/DB 验证 | Done | production backend/Nginx active，内外 health OK，local_only，quick_check=ok，真实目录/探测/聊天通过 |
| AMD7 | 更新 AGENTS 错误记忆并提交推送 | In Progress | 文档已更新；待聚焦 commit + origin/main |

## 当前边界

- 工作区已有未提交的单会话预设/世界书覆盖改动，必须保留并联合验证；不能回滚或覆盖。
- 普通用户 BYOK 继续关闭。

## 本地验收结果（2026-07-28）

- 后端、四个前端脚本静态检查通过。
- 自动发现会读取上游模型目录，批量探测后仅保留产生有效流式正文的模型。
- 已保存节点不重新输入 Key 也可由服务端安全复用；浏览器保存成功后会清空 Key 输入框。
- 会话配置后端与浏览器联合回归通过，SQLite `quick_check=ok`。

## 线上验收结果（2026-07-28）

- 发布前 live/backup SQLite `quick_check=ok`；部署后 backend/Nginx active，内外 `/health` 为 `OK`，`CONTENT_MODE=local_only`。
- 目标 `http://154.12.55.233:3000/v1` 已在后台节点中；留空复用服务端 Key 成功读取 17 个模型，抽测 `gemini-2.5-flash-cli` 可用。
- 匿名公开目录包含 43 个用户可选模型且无 Key、Base URL、Key 预览或错误详情；生产聊天选择器实际渲染 43 项，桌面/390px 均在视口内。
- 临时账号 + 极简私有角色通过正式 `/chat` 路径选中该模型，约 6 秒得到有效回复；测试账号、角色和会话全部清理，最终 `quick_check=ok`。
