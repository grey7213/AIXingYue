# AI星月 Web 首帧防闪与主题统一 Design

Updated: 2026-07-11

## 首帧与文案

- 在 `frontend/app/assets/css/app.css` 顶部直接定义 `[x-cloak] { display:none!important; }`，不再依赖未直接加载的 `custom.css`。
- `loadPublicSiteSettings()` 只对运营 UI 设置递归还原字面 `\\n/\\r`，不触碰角色提示词、聊天内容或代码字段。
- 删除页面上的 `x-init="init()"`，依赖 Alpine Data 对象的 `init()` 自动生命周期，避免重复请求。
- workshop/info 增加 `ready` 状态和暖色骨架；真实设置与统计完成后一次性展示主体。

## 视觉方向

- Hero：暖黑棕到陶土橙渐变，橙金 eyebrow，奶油白标题与说明，轻颗粒/光晕。
- 快捷入口：暖白面板、顶部色条、轻阴影，hover 上移 2px。
- 比赛：暖米底；排行榜：白底 + 行分隔；空态：虚线边框。
- 信息统计卡：橙、金、砖红、暖棕四种顶边状态色，数字与标签保持 AA 对比。
- 深色模式使用同样的暖色语义，不重新引入紫粉渐变。

