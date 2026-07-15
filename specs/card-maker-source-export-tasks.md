# 制卡架构源码导出任务

- [x] 读取项目规则与制卡相关 SPEC。
- [x] 定位前端页面、共享依赖、后端函数、接口和表结构。
- [x] 确认可分发边界与脱敏规则。
- [x] 生成源码导出目录、后端原始片段、文档和虚构示例。
- [x] 执行 Python/JavaScript/JSON、敏感信息、哈希和 ZIP 解压验证。
- [x] 记录最终文件数、大小、SHA-256 与剩余风险。

## 2026-07-15 验证结果

- 交付目录：`output/card-maker-source-export-20260715/`。
- ZIP：`output/card-maker-source-export-20260715.zip`，192457 bytes。
- ZIP SHA-256：`2cb18702aaf91467d424ef6d683adcd474c2b647546a7be41025cbae5b8ba7cd`。
- 文件：24 个（含 `MANIFEST.sha256`），Manifest 23 个内容文件逐项校验通过。
- `py_compile`：生产后端与导出工具通过。
- `node --check`：包内全部 JavaScript 通过。
- JSON：示例角色卡解析通过。
- ZIP：解压后逐项 SHA-256 与 staging 目录一致。
- 扫描：密钥形态 0、生产/私有标记 0、禁止扩展名文件 0。
- 已排除数据库、用户/对话数据、角色库、卡密、`.env`、证书/keystore、部署与支付源码、真实平台必需世界书。
- 剩余边界：后台和共享 API 文件是当前单体源码快照，仍含与制卡无关的普通业务函数，但不含已知密钥；接收方应按 `docs/architecture.md` 的源码地图拆分，不应把本包视为完整可上线系统。
