# Spine 卡片与交互桥接任务（2026-07-18）

- [x] 解析目标 PNG 并定位 `window.triggerSlash()` 缺失。
- [x] 增加安全 iframe → 父聊天发送桥接。
- [ ] 扩展卡包 Spine 文件组识别、校验和上传协议。
- [x] 完成本地 `triggerSlash` iframe 浏览器回归：桥存在、消息到达父页面、卡内显示“角色设定已发送”。
- [ ] 取得实际 Spine 导出包和版本后完成资源组测试（当前 PNG 元数据不含 `.json/.skel/.atlas` 或 Spine 版本）。
- [ ] 备份、部署、线上验证、提交并推送。
