# AI星月 Web 首帧防闪与主题统一 Tasks

Updated: 2026-07-11

| ID | 任务 | 状态 | 验证 |
|---|---|---|---|
| WCT1 | 定位全站首帧闪现和 `\\n` 根因 | Done | app.css 缺 cloak；workshop 双转义 |
| WCT2 | 加入全局 cloak、运营文案换行归一化 | Done | 15 页统一 CSS；双转义 0；字面 `\\n` 0 |
| WCT3 | 移除重复 x-init，增加 Hub ready 骨架 | Done | 相关 API 每页各 1 次；骨架后一次性展示 |
| WCT4 | 统一工坊/信息中心主题和统计口径 | Done | 公开官方角色 8778；桌面/移动无溢出 |
| WCT5 | 部署、线上回归、记录并推送 | Done | `79ee4f5` 已推送 origin/main；本记录随后补齐 |

## 验证结果

- 15 个带 `x-cloak` 的 App 页面统一加载 `app.css?v=20260711-cloak-theme`。
- HTML 双重换行转义 0，重复 `x-init="init()"` 0，共享 cloak 规则存在。
- workshop/info 最终 DOM 均不包含字面 `\\n`，加载后 skeleton 隐藏、主体显示。
- 工坊显示真实换行和 `已同步 8786 张卡`；信息中心显示 `8778 公开官方角色`、`6 用户角色`、`11 会话`。
- workshop/info 的设置、profile、home-stats 等请求均各 1 次，没有重复初始化。
- 375/1440 宽度横向 overflow 为 0；explore/favorites/histories/group/me/rewards/logs/create 冒烟页均无字面 `\\n`、无浏览器错误。
- 截图：`output/playwright/workshop-warm-cloak-desktop.png`、`workshop-warm-cloak-mobile.png`、`info-warm-cloak-desktop.png`、`info-warm-cloak-mobile.png`。
- 线上 backend/nginx active，`/health` OK，`CONTENT_MODE=local_only`。
