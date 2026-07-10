# AI星月角色卡标签往返 Design

Updated: 2026-07-10

## 包结构

完整包：

```text
AI星月-全部公开官方角色卡-<export_id>.zip
├─ README-标签修改说明.txt
├─ manifest.original.json
├─ manifest.original.sha256
├─ tag-overrides.csv
└─ cards/<display_id>__<标签表达式>.json
```

轻量包：

```text
AI星月-角色卡标签改名包-<export_id>.zip
├─ README-标签修改说明.txt
├─ manifest.original.json
├─ manifest.original.sha256
├─ tag-overrides.csv
└─ labels/<display_id>__<标签表达式>.tag
```

## 标签表达式

- `[恋爱][治愈]`：回传时完整替换为两个标签。
- `CLEAR`：明确清空标签。
- `KEEP`：文件名不表达覆盖，使用 CSV 的 `new_tags_json`；空 CSV 单元格表示保持不变。
- 标签中的 `%[]<>:"/\\|?*`、控制字符和尾随点/空格使用 UTF-8 百分号转义。
- 文件名过长时使用 `KEEP`，原标签仍完整保存在 Manifest/CSV。

## 稳定匹配

- 人工操作使用 `display_id`，保留前导零。
- 实际数据库写入必须通过只读 Manifest 映射到 `internal_id=local_apps.id`。
- Manifest 同时记录原始标签、原始文件名、角色 JSON SHA-256 和数据库 `updated_at`。
- 回传时遇到重复、未知、缺失映射、Manifest 哈希变化、JSON 内容变化或数据库并发变化时拒绝对应记录。

## 后续覆盖流程

1. 备份线上 SQLite。
2. 解析回传包，生成 dry-run 报告。
3. 校验 Manifest SHA、ID 唯一性、标签语法和数据库并发状态。
4. 只执行 `UPDATE local_apps SET tags=?, updated_at=? WHERE id=?`。
5. 逐项回读，确认其他字段哈希不变。

