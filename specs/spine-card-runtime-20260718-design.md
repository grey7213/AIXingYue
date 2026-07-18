# Spine 卡片与交互桥接设计（2026-07-18）

## 交互桥接

- iframe 内提供兼容 `window.triggerSlash()`，仅通过 `postMessage` 请求父聊天页发送普通用户消息。
- 父页面校验消息来源必须是当前 `iframe.tavo-frame`，再调用现有 `sendMessage()`；鉴权、扣费、流式和持久化仍走原链路。

## Spine 资源

- Spine 是多文件资源组，至少包含 skeleton JSON 或 SKEL、atlas 和 atlas 引用的纹理。
- 卡包解析器按同目录/manifest group 收集资源组，上传时保存角色、组名和相对路径元数据。
- 服务端继续校验 MIME、文件头、SHA、大小和当前用户/卡片所有权。
- Spine 官方 Web Runtime 受其许可证约束；不得把未获授权的 runtime 代码直接 vendoring 到站点。资源导入与存储先保持 runtime-neutral，渲染器仅在项目存在合法 runtime 时启用。
