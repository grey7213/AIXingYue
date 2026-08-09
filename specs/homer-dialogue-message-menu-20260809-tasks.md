# 惑梦对话消息长按菜单 Tasks

日期：2026-08-09

| ID | 任务 | 状态 | 验证/备注 |
|---|---|---|---|
| HDM1 | 建立 requirements/design/tasks 并登记导航 | Done | 原型 ZIP 只读基线已记录 |
| HDM2 | 隐藏消息头、常驻操作条和原生 Swipe 控件 | Done | 普通态可见数均为 0；编辑态只恢复原生保存/取消 |
| HDM3 | 实现 Pointer/右键/键盘消息菜单及安全定位 | Done | 520ms、12px、右键、Shift+F10；手机弹层实测 `left=8/right=382/top=431.5/bottom=836` |
| HDM4 | 将复制/编辑/回溯/生成/Swipe/删除绑定准确消息 | Done | 稳定消息 ID 重解析；准确编辑、单条删除、回溯、三种生成和双向候选均通过 |
| HDM5 | 更新原版 SillyTavern E2E | Done | 桌面 1440×900、手机 390×844；新增 `original-sillytavern-mobile-message-menu.png` |
| HDM6 | 完成静态、自测和 Chromium 验收 | Done | Node/Python/diff/selftest 全通过；两套 Chromium E2E console/page/network error=0，Yuzi 请求=0 |
| HDM7 | 更新 AGENTS、部署、核对哈希、提交并推送 | Done | release `20260809-202235`；仅提交本轮源码/SPEC/测试，排除用户 `.thm`，未构建 APK |

## 当前约束

- 保留并不改写 `E:\酒馆开发\对话界面UI原型-开发交接包-网站弹窗视觉统一-20260809.zip`。
- 不修改或提交 `Tavo_主题效果_14G5y(1).thm`。
- 不启用 `st-yuzi-phone`，不恢复全局操作坞，不构建 APK。
- 不把角色脚本、Prompt、世界书、Cookie、Token 或模型 Key 写入日志、截图或公开响应。

## 本地验证记录

- `node --check`、`python -m py_compile`、`git diff --check`：通过。
- `_selftest_sillytavern_runtime.py`：全部通过。
- `_selftest_conversation_database.py`：全部通过。
- `_e2e_original_sillytavern_browser.py`：原版 SillyTavern 1.18.0 桌面/手机通过；长按用户编辑、角色右键/键盘菜单、continue/regenerate/next、swipe-right/swipe-left、单条删除、实时 rollback 全部通过。
- `_e2e_sillytavern_runtime.py`：桌面/手机通过，RoleplayHub、Card Stage、沙箱、世界书权限和旧页面回归无误；console/page/network error 均为 0。
- 隔离测试进程已按登记 PID 与命令特征停止，`18080/18081/18082/18091` 剩余监听为 0。
- 生产部署：dialogue release `20260809-202235`，webpack `5.105.4`；backend/dialogue/Nginx active，`127.0.0.1:8008/8091` 仅 loopback 监听，内外 `/health` OK，`CONTENT_MODE=local_only`。
- 线上源码：`index.js` SHA-256 `0525e954fb9d5baec645721d5d599833db3955b76fd3b9cab7a152f498f6899f`，`style.css` SHA-256 `4d5d243e7a883c8384e191724d62f1a5b14accd57e22f7377b47e05e73496dee`，与本地一致。
- 生产只读 Chromium：1440×900 右键菜单、390×844 长按菜单均准确绑定第 1 条角色回复；常驻 chrome 可见数 0、旧 Homer action DOM 数 0、菜单不越界、Yuzi 请求 0、console/page/network error 0；未触发生成、编辑、删除或存档变更。
- 保留原型 ZIP 最终复核：`4,078,721` bytes，SHA-256 `699D71E86FDD2420262DCF41B03413460B3D30BF6B030C9212795747E332DE11`。
