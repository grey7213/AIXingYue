#!/usr/bin/env python3
"""量角色卡舞台层在移动视口下是否真的铺满，用来判断 CSS 改动是否等价。

背景：交接分支把 `:host` 的 `height: 100vh; height: 100dvh` 双声明降级写法改成
只写 `height: 100dvh`，把 `.ce-stage` 的 `min-height: 100vh/100dvh` 改成
`min-height: 100%`。静态契约测试卡在 `min-height: 100dvh` 这个字面量上，但字面量
不等于行为。这里在真实 Chromium 里渲染两种写法，量 boundingClientRect 是否铺满，
并额外模拟一次「浏览器工具栏收起导致视口变高」的动态视口变化。
"""

from __future__ import annotations

import argparse
import json
import sys

from playwright.sync_api import sync_playwright

HOST_OLD = ":host { position: fixed; inset: 0; display: block; width: 100vw; height: 100vh; height: 100dvh; }"
STAGE_OLD = ".ce-stage { position: absolute; inset: 0; width: 100%; height: 100%; min-height: 100vh; min-height: 100dvh; }"

HOST_NEW = ":host { position: fixed; inset: 0; display: block; width: 100vw; height: 100dvh; }"
STAGE_NEW = ".ce-stage { position: absolute; inset: 0; width: 100%; height: 100%; min-height: 100%; }"

# 旧 WebView 不认 dvh（Chrome 108 才有，APK minSdk 26 覆盖到更老的引擎），
# 那条声明会被整条丢弃。用一个必然无效的单位模拟这种情况，验证 `inset: 0`
# 是否仍然独立撑满视口 —— 这正是 params.size 那类「老引擎静默降级」的同款风险。
HOST_NO_DVH = ":host { position: fixed; inset: 0; display: block; width: 100vw; height: 100qqh; }"

PAGE = """<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0">
<div id="mount"></div>
<script>
window.build = (hostCss, stageCss) => {
  document.querySelector('#mount').replaceChildren();
  const host = document.createElement('div');
  document.querySelector('#mount').append(host);
  const root = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = hostCss + '\\n' + stageCss;
  const stage = document.createElement('div');
  stage.className = 'ce-stage';
  root.append(style, stage);
  const h = host.getBoundingClientRect();
  const s = stage.getBoundingClientRect();
  return {
    viewport: { w: innerWidth, h: innerHeight },
    host: { w: Math.round(h.width), h: Math.round(h.height) },
    stage: { w: Math.round(s.width), h: Math.round(s.height) },
  };
};
</script>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out")
    args = ap.parse_args()

    viewports = [
        ("phone 390x844", 390, 844),
        ("phone 360x640", 360, 640),
        ("phone tall 412x915", 412, 915),
        ("toolbar collapsed 390x900", 390, 900),
        ("desktop 1440x900", 1440, 900),
    ]
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(PAGE)
        for label, w, h in viewports:
            page.set_viewport_size({"width": w, "height": h})
            old = page.evaluate("([a,b]) => window.build(a,b)", [HOST_OLD, STAGE_OLD])
            new = page.evaluate("([a,b]) => window.build(a,b)", [HOST_NEW, STAGE_NEW])
            nodvh = page.evaluate("([a,b]) => window.build(a,b)", [HOST_NO_DVH, STAGE_NEW])
            results.append({"viewport": label, "old": old, "new": new, "no_dvh": nodvh})
        browser.close()

    print(f"{'viewport':26s} {'old':>12s} {'new':>12s} {'no-dvh':>12s}  {'expected':>12s}  verdict")
    ok = True
    for row in results:
        vp = row["old"]["viewport"]
        want = f"{vp['w']}x{vp['h']}"
        o = f"{row['old']['stage']['w']}x{row['old']['stage']['h']}"
        n = f"{row['new']['stage']['w']}x{row['new']['stage']['h']}"
        d = f"{row['no_dvh']['stage']['w']}x{row['no_dvh']['stage']['h']}"
        good = (o == want) and (n == want) and (d == want)
        ok = ok and good
        print(f"{row['viewport']:26s} {o:>12s} {n:>12s} {d:>12s}  {want:>12s}  "
              f"{'equivalent' if good else 'DIFFERS'}")
    print()
    print("verdict:", "三种写法（含 dvh 完全不被支持）在所有视口下都铺满，"
          "字面量差异不影响行为"
          if ok else "行为不一致，不能只改测试")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
