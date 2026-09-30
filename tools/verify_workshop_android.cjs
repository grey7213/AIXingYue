// Exercise the installed debug APK through Playwright's Android transport.
// Static files must come from the APK; only API responses use synthetic accounts.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { _android } = require(process.env.HOMER_PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const fixture = fs.readFileSync(path.join(__dirname, 'verify_workshop_account_isolation.py'), 'utf8');
const seed = fixture.match(/SEED = """([\s\S]*?)"""/)[1];
const stateScript = fixture.match(/STATE = """([\s\S]*?)"""/)[1];
const out = path.join(root, 'output/workshop-cache-fix-20261001/android');
fs.mkdirSync(out, { recursive: true });
const base = 'https://patcher.villainy.top';
const results = [];

(async () => {
  const device = (await _android.devices()).find(d => d.serial() === 'emulator-5554');
  assert(device, 'Pixel emulator must be connected');
  try {
    let page;
    async function wait(condition) {
      const until = Date.now() + 15000;
      while (Date.now() < until) { if (await condition()) return; await page.waitForTimeout(25); }
      throw Error('Android condition timed out');
    }
    const snapshot = () => page.evaluate('(' + stateScript + ')()');
    const visible = () => page.evaluate(() => window.dispatchEvent(new Event('homer:page-visible')));
    for (const name of ['slow-profile', 'visible-during-init', 'visible-switch-account', 'account-changes-in-flight', 'logout-pending', 'profile-failure', 'verified-cache-on-list-failure', 'destroy-pending']) {
      // This package was installed solely for this test; never clear the formal package.
      await device.shell('am force-stop org.nebula.horizon.composeai.debug');
      await device.shell('pm clear org.nebula.horizon.composeai.debug');
      await device.shell('am start -n org.nebula.horizon.composeai.debug/org.nebula.horizon.composeai.ctf.HomerActivity');
      page = await (await device.webView({ pkg: 'org.nebula.horizon.composeai.debug' })).page();
      const context = page.context();
      await wait(() => context.pages().some(p => p.url().startsWith(base)));
      page = context.pages().find(p => p.url().startsWith(base));
      page.setDefaultTimeout(12000);
      await page.addInitScript(seed);
      const s = { account: 'account-b', profiles: 0, works: 0,
        holdProfile: ['slow-profile', 'visible-during-init', 'logout-pending'].includes(name),
        holdWorks: ['account-changes-in-flight', 'destroy-pending'].includes(name),
        failProfile: name === 'profile-failure', failWorks: name === 'verified-cache-on-list-failure' };
      const profiles = [], works = [], errors = [];
      const onError = error => errors.push(error.message);
      page.on('pageerror', onError);
      const send = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
      const profile = account => ({ id: account, name: '验收账号 ' + account, is_admin: false });
      const entries = account => ({ data: { list: [{ id: 'private-' + account, name: '私有作品 ' + account, is_public: false }], total: 1 } });
      const handler = async route => {
        const p = new URL(route.request().url()).pathname, account = s.account;
        if (p === '/console/api/account/profile') {
          s.profiles++; if (s.holdProfile) { profiles.push([route, account]); return; }
          return send(route, s.failProfile ? { message: 'fixture unavailable' } : profile(account), s.failProfile ? 503 : 200);
        }
        if (p === '/console/api/web/my-apps') {
          s.works++; if (s.holdWorks) { works.push([route, account]); return; }
          return send(route, s.failWorks ? { message: 'fixture unavailable' } : entries(account), s.failWorks ? 503 : 200);
        }
        if (p === '/admin/api/me') return send(route, { message: 'admin required' }, 403);
        if (p.endsWith('/home-stats')) return send(route, { data: { apps: { total: 2 } } });
        if (p.endsWith('/site-settings')) return send(route, { data: {} });
        return send(route, { data: { list: [], total: 0 }, points: 100 });
      };
      for (const pattern of ['**/console/**', '**/go/**', '**/admin/api/**', '**/api/homer/**']) await page.route(pattern, handler);
      const releaseProfiles = async () => { s.holdProfile = false; for (const [r, a] of profiles.splice(0)) await send(r, profile(a)); };
      const releaseWorks = async () => { s.holdWorks = false; for (const [r, a] of works.splice(0)) await send(r, entries(a)); };
      const complete = (account = 'account-b') => wait(async () => { const v = await snapshot(); return v && !v.refreshing && JSON.stringify(v.ids) === JSON.stringify(['private-' + account]); });
      try {
        await page.goto(base + '/app/workshop.html', { waitUntil: 'domcontentloaded' });
        await wait(async () => s.profiles > 0 && await snapshot());
        if (name === 'slow-profile') {
          const v = await snapshot(); assert(v.ready && !v.ids.length && !s.works);
          assert(!Object.keys(v.cache).some(k => k.startsWith('homer.page-cache.v1.workshop.')));
          assert(v.cache['homer.page-cache.v1.histories.account-a']);
          await releaseProfiles(); await complete();
        } else if (name === 'visible-during-init') {
          for (let n = 0; n < 4; n++) await visible();
          assert.equal(s.works, 0); await releaseProfiles(); await complete(); assert.equal(s.works, 1);
        } else if (name === 'visible-switch-account') {
          await complete(); const n = s.works; s.account = 'account-c'; s.holdProfile = true;
          await visible(); await wait(() => profiles.length); assert(!(await snapshot()).ids.length); assert.equal(s.works, n);
          await releaseProfiles(); await complete('account-c');
        } else if (name === 'account-changes-in-flight') {
          await wait(() => works.length); s.account = 'account-c';
          await page.evaluate(() => localStorage.setItem('ai_xingyue_user', JSON.stringify({ id: 'account-c' })));
          await visible(); await releaseWorks(); await complete('account-c');
          assert(!(await snapshot()).cache['homer.page-cache.v1.workshop-v2.account-b'].includes('private-account-b'));
        } else if (name === 'logout-pending') {
          await page.evaluate(async () => (await import('/assets/js/api.js?v=20260917-r8')).clearAuth());
          await visible();
          await releaseProfiles(); await wait(async () => !(await snapshot()).refreshing);
          const v = await snapshot(); assert(v.cachedUser === null && !v.ids.length && !s.works);
        } else if (name === 'profile-failure') {
          await wait(async () => !(await snapshot()).refreshing); const v = await snapshot(); assert(v.error && !v.ids.length && !s.works);
          s.failProfile = false;
          await page.evaluate(() => {
            const retry = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '重试' && b.getClientRects().length);
            if (retry) retry.click();
          });
          await complete();
        } else if (name === 'verified-cache-on-list-failure') {
          await wait(async () => !(await snapshot()).refreshing); const v = await snapshot(); assert.deepEqual(v.ids, ['cached-b']); assert(v.error);
        } else {
          await wait(() => works.length); const before = (await snapshot()).cache;
          await page.evaluate(() => Alpine.$data(document.querySelector('[x-data="workshopPage()"]')).destroy());
          await releaseWorks(); await wait(async () => !(await snapshot()).refreshing); assert.deepEqual((await snapshot()).cache, before);
        }
        const v = await snapshot();
        assert(!v.cache['homer.page-cache.v1.workshop-v2.account-a']?.includes('private-account-b'));
        assert(!v.cache['homer.page-cache.v1.workshop-v2.account-b']?.includes('private-account-c'));
        assert.deepEqual(errors, []);
        const assets = await page.evaluate(async () => {
          const r = await fetch('/app/assets/js/hub-pages.js?v=20261001-workshop-auth', { cache: 'no-store' });
          return { source: r.headers.get('X-Homer-Client-Asset'), fixedScope: (await r.text()).includes('workshop-v2') };
        });
        assert.equal(assets.source, 'apk'); assert(assets.fixedScope);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1); assert(!overflow);
        results.push({ name, passed: true, profiles: s.profiles, privateRequests: s.works, visibleIds: v.ids, cacheKeys: Object.keys(v.cache), assets, overflow, pageErrors: errors });
        if (['slow-profile', 'visible-switch-account'].includes(name)) {
          await page.screenshot({ path: path.join(out, name + '-webview.png') });
          fs.writeFileSync(path.join(out, name + '-device.png'), await device.screenshot());
        }
      } catch (e) {
        results.push({ name, passed: false, error: e.message, requests: {profiles:s.profiles,works:s.works}, state: await snapshot().catch(()=>null), url:page.url() });
        await page.screenshot({ path: path.join(out, name + '-failure.png') }).catch(() => {});
      } finally {
        for (const [r] of [...profiles, ...works]) await r.abort().catch(() => {});
        await page.unrouteAll({ behavior: 'ignoreErrors' }); page.removeListener('pageerror', onError);
      }
      console.log(JSON.stringify(results.at(-1)));
      fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify({ serial: device.serial(), model: device.model(), results }, null, 2));
    }
  } finally { await device.close(); }
  if (results.some(x => !x.passed)) process.exitCode = 1;
})().catch(e => { console.error(e.message); process.exitCode = 1; });
