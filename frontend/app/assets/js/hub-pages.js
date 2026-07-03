import { api, requireAuth, getCachedUser, setCachedUser, clearAuth, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260627-logo';

async function loadUser(ctx) {
  if (!requireAuth()) return false;
  const cached = getCachedUser();
  if (cached) ctx.user = cached;
  try {
    const profile = await api.profile();
    ctx.user = profile?.data || profile;
    setCachedUser(ctx.user);
    const p = await api.points();
    ctx.points = parseInt(p.points || p.data?.points || 0, 10);
    return true;
  } catch (err) {
    if (err instanceof ApiError && err.code === 401) {
      clearAuth();
      location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname + location.search));
    }
    return false;
  }
}

async function loadSiteSettings(ctx) {
  ctx.siteSettings = await loadPublicSiteSettings().catch(() => null);
}

function siteText(ctx, section, key, fallback = '') {
  return ctx.siteSettings?.[section]?.[key] || fallback;
}

function emptyText(ctx, key, fallback = '') {
  return siteText(ctx, 'empty_states', key, fallback);
}

function appNavText(ctx, key, fallback = '') {
  return ctx.siteSettings?.app?.nav_labels?.[key] || fallback;
}

function appHomeText(ctx, key, fallback = '') {
  return siteText(ctx, 'app_home', key, fallback);
}

function myText(ctx, key, fallback = '') {
  return siteText(ctx, 'my_apps', key, fallback);
}

function chatText(ctx, key, fallback = '') {
  return siteText(ctx, 'chat', key, fallback);
}

function formatTemplate(template, values = {}) {
  return String(template || '').replace(/\{(\w+)\}/g, (_, key) => values[key] ?? '');
}

export function favoritesPage() {
  return {
    user: null, points: 0, loading: false, cards: [], searchKeyword: '', siteSettings: null,
    async init() { injectLayout('favorites'); await loadSiteSettings(this); if (await loadUser(this)) await this.loadList(); },
    emptyText(key, fallback = '') { return emptyText(this, key, fallback); },
    appNavText(key, fallback = '') { return appNavText(this, key, fallback); },
    appHomeText(key, fallback = '') { return appHomeText(this, key, fallback); },
    async loadList() {
      this.loading = true;
      try {
        const r = await api.favorites({ page: 1, page_size: 60, q: this.searchKeyword });
        this.cards = r?.data?.apps || r?.data?.list || [];
      } finally { this.loading = false; }
    },
    async toggleFavorite(card, event) {
      if (event) event.preventDefault();
      const r = await api.toggleFavorite(card.id);
      if (!r?.data?.favorited) this.cards = this.cards.filter(c => c.id !== card.id);
    },
  };
}

export function historiesPage() {
  return {
    user: null, points: 0, loading: false, conversations: [], siteSettings: null,
    async init() { injectLayout('histories'); await loadSiteSettings(this); if (await loadUser(this)) await this.loadList(); },
    emptyText(key, fallback = '') { return emptyText(this, key, fallback); },
    appNavText(key, fallback = '') { return appNavText(this, key, fallback); },
    chatText(key, fallback = '') { return chatText(this, key, fallback); },
    async loadList() {
      this.loading = true;
      try {
        const r = await api.conversations();
        this.conversations = r?.data?.list || [];
      } finally { this.loading = false; }
    },
  };
}

export function workshopPage() {
  return {
    user: null, points: 0, stats: null, myApps: [], siteSettings: null,
    async init() {
      injectLayout('workshop');
      await loadSiteSettings(this);
      if (!(await loadUser(this))) return;
      const s = await api.homeStats().catch(() => null);
      this.stats = s?.data || null;
      const m = await api.myApps({ page: 1, page_size: 6 }).catch(() => null);
      this.myApps = m?.data?.list || [];
    },
    emptyText(key, fallback = '') { return emptyText(this, key, fallback); },
    appNavText(key, fallback = '') { return appNavText(this, key, fallback); },
    myText(key, fallback = '') { return myText(this, key, fallback); },
    syncedLibraryText() {
      const prefix = this.emptyText('workshop_library_prefix', '已同步');
      const suffix = this.emptyText('workshop_library_suffix', '张卡');
      return `${prefix} ${this.stats?.apps?.total || 0} ${suffix}`;
    },
  };
}

export function imageChatPage() {
  return {
    user: null, points: 0, prompt: '', filename: '', previewName: '', sending: false, replies: [], siteSettings: null,
    async init() { injectLayout('image'); await loadSiteSettings(this); await loadUser(this); },
    emptyText(key, fallback = '') { return emptyText(this, key, fallback); },
    appNavText(key, fallback = '') { return appNavText(this, key, fallback); },
    pickFile(e) {
      const f = e?.target?.files?.[0];
      this.filename = f ? f.name : '';
      this.previewName = this.filename;
    },
    async send() {
      if ((!this.prompt.trim() && !this.filename) || this.sending) return;
      this.sending = true;
      try {
        const r = await api.imageChat({ prompt: this.prompt.trim(), filename: this.filename });
        this.replies.unshift(r?.data || {});
        this.prompt = '';
        this.filename = '';
        this.previewName = '';
      } finally { this.sending = false; }
    },
  };
}

export function rewardsPage() {
  return {
    user: null,
    points: 0,
    balance: { free_points: 0, paid_points: 0, reward_points: 0, points: 0 },
    rewards: null,
    deposit: null,
    redeemInput: '',
    redemptions: [],
    message: '',
    messageType: 'info',
    busy: false,
    siteSettings: null,
    async init() {
      injectLayout('rewards');
      await loadSiteSettings(this);
      if (await loadUser(this)) {
        await Promise.all([this.loadRewards(), this.loadRedemptions()]);
      }
    },
    setMessage(text, type = 'info') {
      this.message = text;
      this.messageType = type;
      if (text) setTimeout(() => { if (this.message === text) this.message = ''; }, 3200);
    },
    emptyText(key, fallback = '') { return emptyText(this, key, fallback); },
    depositText(key, fallback = '') { return this.deposit?.[key] || siteText(this, 'deposit', key, fallback); },
    dashboardText(key, fallback = '') { return siteText(this, 'dashboard', key, fallback); },
    rewardsText(key, fallback = '') { return siteText(this, 'rewards', key, fallback); },
    normalizeBalance(data) {
      const b = data?.balance || data || {};
      return {
        free_points: parseInt(b.free_points || 0, 10),
        paid_points: parseInt(b.paid_points || b.normal_points || b.regular_points || 0, 10),
        reward_points: parseInt(b.reward_points || 0, 10),
        points: parseInt(b.points || b.total_points || 0, 10),
      };
    },
    async loadRewards() {
      const r = await api.rewards();
      this.rewards = r?.data || {};
      this.deposit = this.rewards.deposit || null;
      this.balance = this.normalizeBalance(this.rewards.balance || this.rewards);
      this.points = this.balance.points;
    },
    async loadRedemptions() {
      const r = await api.redemptions({ page: 1, page_size: 20 }).catch(() => null);
      this.redemptions = r?.data?.list || [];
    },
    openAifadian() {
      const url = this.deposit?.aifadian_url;
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
      } else {
        this.setMessage(this.dashboardText('aifadian_missing_text', this.deposit?.support_text || '暂未配置爱发电购买链接，请联系站长获取兑换码。'), 'error');
      }
    },
    paymentNote() {
      if (this.deposit?.payment_available) {
        return this.deposit?.payment_note_available || '爱发电购买完成后，使用站长发放的兑换码在本页到账。';
      }
      return this.deposit?.payment_note_unavailable || '暂未配置购买链接，请联系站长获取兑换码。';
    },
    async redeemNow() {
      const code = String(this.redeemInput || '').trim();
      if (!code || this.busy) {
        this.setMessage(this.dashboardText('redeem_empty_text', '请输入兑换码'), 'error');
        return;
      }
      this.busy = true;
      try {
        const r = await api.redeemCode(code);
        const data = r?.data || {};
        this.balance = this.normalizeBalance(data.balance || {});
        this.points = this.balance.points;
        this.redeemInput = '';
        this.setMessage(
          formatTemplate(this.dashboardText('redeem_success_detail_template', '兑换成功，到账 {points} 星月币'), { points: data.points_added || 0 }),
          'success',
        );
        await Promise.all([this.loadRewards(), this.loadRedemptions()]);
      } catch (err) {
        this.setMessage(err.message || this.dashboardText('redeem_failed_text', '兑换失败'), 'error');
      } finally {
        this.busy = false;
      }
    },
    packagePoints(pkg) {
      return Number(pkg?.points || 0).toLocaleString('zh-CN');
    },
    dailyPoints() {
      return parseInt(this.rewards?.daily?.points || 10, 10);
    },
    dailyClaimText() {
      if (this.rewards?.daily?.claimed) return this.rewardsText('daily_claimed_text', '今日已领取');
      return formatTemplate(this.rewardsText('daily_claim_template', '领取 +{points}'), { points: this.dailyPoints() });
    },
    formatTime(ts) {
      if (!ts) return '-';
      return new Date(ts > 1e12 ? ts : ts * 1000).toLocaleString('zh-CN', { hour12: false });
    },
    async claimDaily() {
      if (this.busy) return;
      this.busy = true;
      try {
        const r = await api.claimDailyReward();
        if (r?.data?.balance) this.balance = this.normalizeBalance(r.data.balance);
        if (r?.data) this.points = parseInt(r.data.points || this.balance.points || this.points, 10);
        await this.loadRewards();
        const added = parseInt(r?.data?.points_added || 0, 10);
        this.setMessage(
          added > 0
            ? formatTemplate(this.dashboardText('checkin_reward_success_template', '今日奖励已领取，到账 {points} 星月币'), { points: added })
            : this.dashboardText('checkin_repeat_text', '今日已经签到过了'),
          added > 0 ? 'success' : 'info',
        );
      } catch (err) {
        this.setMessage(err.message || this.dashboardText('claim_failed_text', '领取失败'), 'error');
      } finally { this.busy = false; }
    },
  };
}

export function logsPage() {
  return {
    user: null, points: 0, loading: false, logs: [], siteSettings: null,
    async init() { injectLayout('logs'); await loadSiteSettings(this); if (await loadUser(this)) await this.loadList(); },
    emptyText(key, fallback = '') { return emptyText(this, key, fallback); },
    appNavText(key, fallback = '') { return appNavText(this, key, fallback); },
    dashboardText(key, fallback = '') { return siteText(this, 'dashboard', key, fallback); },
    async loadList() {
      this.loading = true;
      try {
        const r = await api.logs({ page: 1, page_size: 80 });
        this.logs = r?.data?.list || [];
      } finally { this.loading = false; }
    },
  };
}

export function infoPage() {
  return {
    user: null, points: 0, stats: null, siteSettings: null,
    async init() {
      injectLayout('info');
      if (!(await loadUser(this))) return;
      const [s, settings] = await Promise.all([
        api.homeStats().catch(() => null),
        loadPublicSiteSettings().catch(() => null),
      ]);
      this.stats = s?.data || null;
      this.siteSettings = settings || null;
    },
    infoValue(key, fallback = '') {
      return this.siteSettings?.app?.[key] || fallback;
    },
  };
}

window.favoritesPage = favoritesPage;
window.historiesPage = historiesPage;
window.workshopPage = workshopPage;
window.imageChatPage = imageChatPage;
window.rewardsPage = rewardsPage;
window.logsPage = logsPage;
window.infoPage = infoPage;
