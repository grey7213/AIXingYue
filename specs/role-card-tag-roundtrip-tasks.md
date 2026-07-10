# AI星月角色卡标签往返 Tasks

Updated: 2026-07-10

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| RCT1 | 核对线上导出范围和字段 | Done | 8785 总卡；8778 公开已发布 admin 卡；用户/私有卡排除 |
| RCT2 | 定义文件名、Manifest、CSV 和冲突规则 | Done | requirements/design 已建立 |
| RCT3 | 实现可复用导出工具 | Done | `py_compile` 与 2-card/1-user 排除小库测试通过 |
| RCT4 | 在线生成完整包和轻量标签包 | Done | 导出 8778 张；完整包 394936716 bytes，标签包 3617223 bytes |
| RCT5 | 校验数量、唯一 ID、JSON、CSV、SHA-256 | Done | ZIP CRC、8778 唯一 internal/display ID、CSV 8778 行、抽样 JSON/hash 全通过 |
| RCT6 | 更新项目记录、提交并推送 | Done | AGENTS/current-state 更新；聚焦提交并推送 origin/main |

## 导出结果

- 公开官方卡：8778。
- 已有标签：2338；空标签：6440；文件名因过长使用 `KEEP`：16。
- 完整包 SHA-256：`f4336a98f105c60f0af43660e02e6328629575bdbef501269e0ed01c797ee1ac`。
- 标签包 SHA-256：`71d53b5e454460149c1fccec288f2097c315e47a4902fd7806b544e57644db1f`。
- 本地验证：`D:\Anconda3\python.exe output\verify_role_card_tag_export.py` → `PASS`。
- 线上数据库未写入；临时公网入口和 `/tmp` 导出文件已清理。
