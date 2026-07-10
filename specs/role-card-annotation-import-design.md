# AI星月角色卡标注回填与展示 Design

Updated: 2026-07-11

## 回填流程

1. `prepare` 只读扫描 ZIP，验证 Manifest、CSV、文件名三位标记和每张卡 SHA。
2. 生成小型计划 JSON，记录 `internal_id`、`display_id`、原/新标签、动作、导出更新时间和三项能力。
3. 在服务器数据库上先运行 dry-run，要求 8778 张全部匹配且冲突为零。
4. 用 SQLite Online Backup API 创建时间戳备份。
5. 单事务更新 6366 个 `replace` 标签，并 upsert 8778 条能力标注。
6. 回读标签与能力标注，生成 apply 报告；不改变 `local_apps.updated_at`，避免标签维护使探索排序整体漂移。

## 数据结构

新增轻量表：

```sql
role_card_annotations(
  app_id text primary key,
  has_opening integer not null,
  has_world_info integer not null,
  has_regex integer not null,
  annotation_source text not null,
  annotated_at integer not null
)
```

- 表只保存人工核验的能力布尔值与来源，不复制角色内容。
- Explore 轻量查询用相关子查询读取三列，避免加载巨大的 `extra_settings`。
- 详情接口优先使用人工标注；没有标注的用户卡/新卡回退到内容字段实时判定。

## API 形状

列表和详情角色对象增加：

```json
{
  "has_opening": true,
  "has_world_info": true,
  "has_regex": false,
  "feature_flags": {
    "opening": true,
    "world_info": true,
    "regex": false
  }
}
```

## UI 方向

- 保留 AI星月暖纸橙金主色与暖黑深色模式。
- 使用细腻径向光晕、极轻颗粒、非纯白面板、分层边框与克制阴影，避免大面积紫粉霓虹和统一圆角模板感。
- 推荐卡强调封面与标题；普通卡用三项能力胶囊建立快速扫描层级。
- 详情页改为封面舞台 + 信息面板，能力面板位于摘要和分类标签之间。
- 动效仅保留卡片入场、封面轻微缩放和按钮反馈；减少位移，尊重 reduced motion。

