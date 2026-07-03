import { api, requireAuth, getCachedUser, setCachedUser, clearAuth, formatDateTime, ApiError } from '/app/assets/js/app-core.js';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260627-logo';

function mePage() {
  return {
    user: null,
    points: 0,
    sidebarOpen: false,
    loading: false,
    toast: null,
    toastTimer: null,
    balance: { free_points: 0, paid_points: 0, reward_points: 0, points: 0 },
    deposit: null,
    redeemCode: '',
    profileForm: { display_id: '', avatar_url: '' },
    savingProfile: false,
    uploadingAvatar: false,
    persona: { name: '', description: '' },
    savingPersona: false,
    siteSettings: null,

    async init() {
      injectLayout('me');
      this.siteSettings = await loadPublicSiteSettings().catch(() => null);
      if (!requireAuth()) return;
      const cached = getCachedUser();
      if (cached) {
        this.user = cached;
        this.syncProfileForm(cached);
      }
      try {
        const profile = await api.profile();
        this.applyProfile(profile);
        await this.refreshPoints();
        await this.loadPersona();
      } catch (err) {
        if (err instanceof ApiError && err.code === 401) {
          clearAuth();
          location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname));
        }
      }
    },

    applyProfile(profile) {
      this.user = profile || null;
      if (profile) {
        this.syncProfileForm(profile);
        setCachedUser(profile);
      }
    },

    syncProfileForm(profile = this.user) {
      const p = profile || {};
      this.profileForm = {
        display_id: p.display_id || p.public_id || p.custom_id || '',
        avatar_url: p.avatar_url || p.avatar || '',
      };
    },

    profileAvatar() {
      return this.profileForm.avatar_url || this.user?.avatar_url || this.user?.avatar || '/assets/img/apk/default_avatar.png?v=20260627-logo';
    },

    profileDisplayId() {
      return this.user?.display_id || this.user?.public_id || this.user?.custom_id || '';
    },

    onAvatarError(event) {
      if (event?.target) event.target.src = '/assets/img/apk/default_avatar.png?v=20260627-logo';
    },

    async onAvatarChange(event) {
      const file = event.target.files?.[0];
      if (!file) return;
      this.uploadingAvatar = true;
      try {
        const dataUrl = await fileToDataUrl(file);
        const r = await api.uploadAvatar(dataUrl, file.name);
        const data = r?.data || r;
        this.profileForm.avatar_url = data.url || data.path || '';
        await this.saveProfile({ successMessage: this.accountText('avatar_saved_text', '头像已更新') });
      } catch (err) {
        this.showToast(err.message || this.accountText('avatar_upload_failed_text', '头像上传失败'), 'error');
      } finally {
        this.uploadingAvatar = false;
        if (event?.target) event.target.value = '';
      }
    },

    async saveProfile(options = {}) {
      this.savingProfile = true;
      try {
        const r = await api.updateProfile({
          display_id: String(this.profileForm.display_id || '').trim(),
          avatar_url: String(this.profileForm.avatar_url || '').trim(),
        });
        const profile = r?.data || r || {};
        this.applyProfile(profile);
        this.showToast(options.successMessage || this.accountText('profile_saved_text', '资料已保存'), 'success');
      } catch (err) {
        this.showToast(err.message || this.accountText('profile_save_failed_text', '资料保存失败'), 'error');
      } finally {
        this.savingProfile = false;
      }
    },

    clearAvatar() {
      this.profileForm.avatar_url = '';
    },

    async loadPersona() {
      try {
        const r = await api.getPersona();
        const data = r?.data || r || {};
        this.persona = { name: data.name || '', description: data.description || '' };
      } catch { /* noop */ }
    },

    async savePersona() {
      this.savingPersona = true;
      try {
        const r = await api.setPersona(this.persona.name || '', this.persona.description || '');
        const data = r?.data || r || {};
        this.persona = { name: data.name || '', description: data.description || '' };
        this.showToast(this.accountText('persona_saved_text', '人设已保存，聊天时将以此身份与角色互动'), 'success');
      } catch (err) {
        this.showToast(err.message || this.accountText('save_failed_text', '保存失败'), 'error');
      } finally {
        this.savingPersona = false;
      }
    },

    showToast(message, type = 'info', duration = 2800) {
      if (this.toastTimer) clearTimeout(this.toastTimer);
      this.toast = { message, type };
      this.toastTimer = setTimeout(() => { this.toast = null; }, duration);
    },

    siteText(section, key, fallback = '') {
      return this.siteSettings?.[section]?.[key] || fallback;
    },

    dashboardText(key, fallback = '') {
      return this.siteText('dashboard', key, fallback);
    },

    accountText(key, fallback = '') {
      return this.siteText('account', key, fallback);
    },

    formatTemplate(template, values = {}) {
      return String(template || '').replace(/\{(\w+)\}/g, (_, key) => values[key] ?? '');
    },

    depositText(key, fallback = '') {
      return this.deposit?.[key] || this.siteText('deposit', key, fallback);
    },

    dailyCheckinText() {
      const points = parseInt(this.siteSettings?.rewards?.daily_points || 10, 10);
      return this.formatTemplate(this.accountText('daily_checkin_template', '每日签到 +{points}'), { points });
    },

    paymentNote() {
      return this.deposit?.aifadian_url
        ? this.depositText('payment_note_available', '兑换码只可使用一次，请确认登录的是当前账号。')
        : this.depositText('payment_note_unavailable', '购买链接暂未配置，可以联系站长手动获取兑换码。');
    },

    formatDate(ts) {
      if (!ts) return '-';
      return formatDateTime(ts).split(' ')[0];
    },

    async refreshPoints() {
      try {
        const r = await api.credits().catch(() => api.points());
        const data = r.data || r;
        this.balance = this.normalizeBalance(data.balance || data);
        this.deposit = data.deposit || this.deposit;
        this.points = this.balance.points;
      } catch (err) {
        this.showToast(this.dashboardText('points_failed_text', '获取积分失败'), 'error');
      }
    },

    normalizeBalance(data) {
      const b = data || {};
      return {
        free_points: parseInt(b.free_points || 0, 10),
        paid_points: parseInt(b.paid_points || b.normal_points || b.regular_points || 0, 10),
        reward_points: parseInt(b.reward_points || 0, 10),
        points: parseInt(b.points || b.total_points || 0, 10),
      };
    },

    openAifadian() {
      const url = this.deposit?.aifadian_url;
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
      } else {
        this.showToast(this.dashboardText('aifadian_missing_text', this.depositText('support_text', '暂未配置爱发电购买链接，请联系站长获取兑换码')), 'error');
      }
    },

    async doDailyCheckin() {
      this.loading = true;
      try {
        const r = await api.claimDaily();
        const p = r.points || r.data?.points;
        if (p !== undefined) this.points = parseInt(p, 10);
        await this.refreshPoints();
        const added = parseInt(r.data?.points_added || 0, 10);
        this.showToast(
          added > 0
            ? this.formatTemplate(this.dashboardText('checkin_success_template', '签到成功 +{points} 积分'), { points: added })
            : this.dashboardText('checkin_repeat_text', '今日已经签到过了'),
          added > 0 ? 'success' : 'info',
        );
      } catch (err) {
        this.showToast(err.message || this.dashboardText('checkin_failed_text', '签到失败'), 'error');
      } finally { this.loading = false; }
    },

    async redeemNow() {
      const code = String(this.redeemCode || '').trim();
      if (!code) {
        this.showToast(this.dashboardText('redeem_empty_text', '请输入兑换码'), 'error');
        return;
      }
      this.loading = true;
      try {
        const r = await api.redeemCode(code);
        const data = r.data || r;
        this.balance = this.normalizeBalance(data.balance || {});
        this.points = this.balance.points;
        this.redeemCode = '';
        this.showToast(this.formatTemplate(this.dashboardText('redeem_success_template', '兑换成功 +{points} 星月币'), { points: data.points_added || 0 }), 'success');
      } catch (err) {
        this.showToast(err.message || this.dashboardText('redeem_failed_text', '兑换失败'), 'error');
      } finally { this.loading = false; }
    },

    doLogout() {
      clearAuth();
      this.showToast(this.dashboardText('logout_success_text', '已退出登录'), 'info');
      setTimeout(() => location.replace('/app/login.html'), 600);
    },
  };
}

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('read file failed'));
    reader.readAsDataURL(file);
  });
}

window.mePage = mePage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('mePage', mePage);
});
