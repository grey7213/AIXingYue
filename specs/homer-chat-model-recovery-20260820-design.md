# 惑梦对话与模型选择恢复设计（2026-08-20）

## 已知事实

- 生产服务与健康检查正常；公开模型接口当前返回 20 个启用模型和一个默认模型。
- 真实浏览器可打开右上角模型弹窗，选项可见且未禁用。
- 当前真实发送进入 SillyTavern generate → Homer dialogue bridge → Backend，但上游返回 HTTP 500，页面留下空 assistant。
- 线上 Backend、`chat.html/chat.js` 和 `homer-dialogue` release 与当前工作区并非同一哈希；修复必须以线上 release/8 月 18 日 staging 快照为基线。

## 诊断顺序

1. 清理前轮临时用户/会话/token，确认 DB 完整。
2. 从服务器读取现有站点预设，不输出密钥；对 `/models` 与候选模型做极简 `stream:true` 探测。
3. 通过临时极简私有角色走正式 Homer/SillyTavern 全链路，排除重型角色大 Prompt 的干扰。
4. 对模型切换执行保存、`#custom_model_id`、runtime-state 与刷新一致性检查。

## 修复边界

- Backend：若节点/模型已失效，禁用失败模型并把默认切到已实测可用模型；所有失败路径清理本轮临时消息并不扣费。
- Dialogue runtime：生成失败后移除 SillyTavern 本地空 assistant 占位，重新从云端对账；显示服务端脱敏错误。模型保存后立即更新连接配置和当前下拉值。
- 隐私：关闭/脱敏 dialogue 请求正文日志，只记录模型、HTTP 状态、首 delta、总耗时和错误分类。
- 缓存：对变更的 frontend/runtime 资源更新 cache-buster 或发布新版本化 release，避免旧浏览器继续使用旧逻辑。

## 部署

- 修改前分别备份 SQLite、Backend、Frontend 与当前 dialogue release/current 指针。
- Backend/Frontend 采用定向替换；dialogue 采用新版本化 release 并原子切换，不直接修改旧 release。
- 任一步验收失败即恢复对应备份/旧 current，角色库与用户业务数据不做重导入。

