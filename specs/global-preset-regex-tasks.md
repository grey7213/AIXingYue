# 全局提示词与正则预设任务

| 任务 | 状态 | 验证 |
| --- | --- | --- |
| 只读解析用户文件并确认结构/安全性 | Done | Prompt 85 条；Regex 26 条；ZIP CRC/路径检查通过 |
| 增加预设库归一化、兼容迁移和独立管理 API | Done | 本地/线上导入、保存、回读、唯一 active 断言通过 |
| 将当前提示词预设运行时改为完整条目模型 | Done | 85 定义、81 顺序、4 未排序；运行时 28 个有效注入块 |
| 增加全局正则 prompt/render 运行时 | Done | placement、prompt/render 阶段、深度和角色正则后执行验证通过 |
| 增加后台完整列表、导入、编辑、保存、启用 UI | Done | 桌面与 390x844 真实浏览器验证；条目编辑保存刷新回读并恢复原值 |
| 线上备份、部署、导入并停用旧预设 | Done | 备份 `global-presets-20260713-090844`；旧 Tavo v3.51 保留并停用；新 Prompt/Regex 唯一启用 |
| 更新项目记录、提交并推送 | Done | focused commit + origin/main |

## 2026-07-13 验证记录

- 本地 `py_compile`、`node --check`、`git diff --check` 通过。
- 本地函数验证：Prompt 85/81/4，Regex 26/24/2，未知字段、前后空白、反斜杠和 `$1` round-trip 保留，阶段过滤通过。
- 线上后台显示旧 `Tavo v3.51` 为“已搁置”，新 V4 提示词为 85 条/启用 36，新 Regex 为 26 条/启用 24。
- 线上分别修改 `Enhance Definitions` 与最后一条 `[🦋美化]梦境状态栏` 名称，保存刷新后回读成功，随后恢复原值。
- 线上函数验证确认 Prompt 运行时 28 块，历史消息 prompt Regex 生效，upstream blocking/regenerate 在全局预设启用时走站点 LLM。
- 桌面和 390x844 移动端无横向溢出；修复 Alpine 内联 `try/catch` 后新控制台错误为 0。
- 线上 DB `quick_check=ok`；备份后至验收期间业务表只新增、无删除；服务/nginx active，内外 `/health` 为 OK，`CONTENT_MODE=local_only`。
