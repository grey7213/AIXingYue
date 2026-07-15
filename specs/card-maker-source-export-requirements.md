# 制卡架构源码导出需求

## 目标

整理一份可直接转发给第三方开发者的当前制卡架构源码包，覆盖角色卡创建、编辑、导入导出、富字段与平台集成边界。

## 范围

- Web 制卡器与“我的角色卡”管理源码。
- 角色卡 JSON/PNG 导入导出及 Character Card V2/V3 兼容逻辑。
- `alternate_greetings`、世界书、Regex、Prompt Manager、quick replies、sampling、Tavo 扩展字段。
- 用户端与管理员端角色卡 CRUD 的后端参考实现。
- `local_apps.id`、`display_id`、`extra_settings` 的数据结构说明。
- 全局 Prompt/Regex 预设的接口与运行时衔接说明。

## 安全边界

- 不包含数据库、用户资料、对话、真实角色库内容、日志或部署凭据。
- 不包含 API key、支付密钥、SMTP 密钥、token、cookie、私钥或 `.env`。
- 不分发平台私有反扒世界书的真实内容，只保留扩展点说明。
- 普通用户 BYOK/API Key 输入保持关闭；模型仅引用管理员公开 preset ID。

## 验收标准

- 输出独立目录及 ZIP，可正常解压。
- README 能说明入口、模块关系、集成顺序和不可直接复制的私有边界。
- 源码文件通过适用的 Python/JavaScript 语法检查。
- 生成 SHA-256 清单且复核一致。
- 敏感信息扫描无密钥、数据库和用户数据泄漏。

## 非目标

- 不提供可直接上线的完整惑梦平台。
- 不迁移或修改线上数据。
- 不包含聊天、支付、注册、农场、好友等无关业务源码。
