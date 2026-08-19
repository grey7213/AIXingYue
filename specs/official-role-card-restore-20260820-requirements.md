# 惑梦官方角色卡完整恢复 Requirements

Updated: 2026-08-20

## 目标

- 将 `E:\obs录制\AI星月-全部公开官方角色卡.zip` 恢复到生产服务器 `38.76.218.46`。
- 恢复压缩包原始 Manifest 中的全部 8,778 张官方角色卡，并按交付 JSON 中的最终标签公开发布。
- 同步恢复本地可用封面、角色不可变基线版本和角色特征注释。

## 范围

- 角色来源固定为 `source='admin'`，状态固定为 `published`，公开状态固定为 `is_public=1`。
- 内部主键使用每张卡的 `record.id`；公开短编号使用 `manifest.original.json` 的 `display_id`，保持 `0001`–`8778`。
- `cards/` 与 `removed-cards-refinement/` 按内部 ID 合并；二者并集必须与原始 Manifest 完全一致。
- 标签使用各交付 JSON 的 `record.tags`，不把文件名末尾的世界书/Regex 数量或功能标记当标签。
- 封面优先从已有本地导入归档恢复；仅对确实不存在的外部封面保留原 URL 或单独本地化。

## 安全约束

- 导入前必须创建并验证 SQLite Online Backup。
- 不删除或覆盖用户、积分、支付、邮件、模型、会话及其他业务表数据。
- 若目标内部 ID、公开编号或版本 ID 与现有非目标数据冲突，事务必须拒绝执行。
- 生产 `CONTENT_MODE=local_only`、支付、邮箱、安全开关和模型配置保持不变。
- 角色 ZIP、封面归档、临时脚本和报告不得进入 Git。

## 验收标准

- ZIP CRC、Manifest SHA-256、8,778 个唯一内部 ID、8,778 个唯一公开编号全部通过。
- `local_apps` 中公开已发布官方角色为 8,778，公开编号连续为 `0001`–`8778`。
- `content_versions` 为每张角色建立一个基线版本，`current_version_id` 全部有效。
- `role_card_annotations` 覆盖全部角色，并与角色内容中的开场白、世界书和 Regex 特征一致。
- 所有本地封面 URL 对应的服务器文件存在；随机抽样公开详情与封面返回 200。
- SQLite `quick_check=ok`，backend、dialogue、Nginx active，内外 `/health` 正常。
- 桌面和手机端真实浏览器可看到角色列表、标签筛选与角色详情，console/page error 为 0。

## 非目标

- 不修改角色正文、世界书、Regex、TavernHelper 脚本或对话模型配置。
- 不重新打包 APK。
- 不恢复旧生产用户、积分或历史会话。

