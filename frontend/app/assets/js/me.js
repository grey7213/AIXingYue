import { api, requireAuth, getCachedUser, setCachedUser, clearAuth, formatDateTime, ApiError } from '/app/assets/js/app-core.js?v=20260917-r8';
import { injectLayout, loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260917-r8';
import { clearPageCache, readPageCache, writePageCache } from '/app/assets/js/page-cache.js?v=20260917-r8';

const ME_CACHE_SCOPE = 'me';
import {readPreferences,writePreferences} from './recommendations.js';
import {confirmAction} from '/assets/js/dialogs.js';

function mePage() {
  return {
    panel: ['settings','profile','persona','preferences'].includes(new URLSearchParams(location.search).get('panel')) ? new URLSearchParams(location.search).get('panel') : '',
    preferences: {enabled:false,interests:[],dislikedTags:[],hiddenTags:[],signals:[]},interestDraft:'',hiddenDraft:'',dislikedDraft:'',
    async savePreferences(){
      const interests=this.interestDraft.split(/[,，\n]/).map(t=>t.trim()).filter(Boolean),hiddenTags=this.hiddenDraft.split(/[,，\n]/).map(t=>t.trim()).filter(Boolean),dislikedTags=this.dislikedDraft.split(/[,，\n]/).map(t=>t.trim()).filter(Boolean);
      if([interests,hiddenTags,dislikedTags].some(tags=>tags.length>40||tags.some(t=>t.length>40))){this.showToast('每类最多填写 40 个标签，每个不超过 40 字','error');return;}
      const next={...readPreferences(this.user),enabled:this.preferences.enabled,interests,hiddenTags,dislikedTags};
      if(writePreferences(this.user,next)){this.preferences=readPreferences(this.user);this.showToast('偏好已保存，下次刷新推荐时生效','success');}else this.showToast('保存失败，请检查本机存储空间','error');
    },
    async resetRecommendations(){if(!await confirmAction('清除本机学习到的浏览和收藏偏好？你手动选择的兴趣和原始收藏不会删除。',{title:'重置推荐',confirmText:'清除学习记录'}))return;const next={...readPreferences(this.user),signals:[]};if(writePreferences(this.user,next)){this.preferences=next;this.showToast('学习记录已清除','success');}else this.showToast('清除失败，请重试','error');},
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
    adminVerified: false,
    profileError: '',
    profileRefreshing: false,

    async init() {
      injectLayout('me');
      void loadPublicSiteSettings().then(settings => { this.siteSettings = settings; }).catch(() => null);
      if (!requireAuth()) return;
      const cached = getCachedUser();
      if (cached) {
        this.user = cached;
        this.preferences=readPreferences(cached);this.interestDraft=this.preferences.interests.join('，');this.hiddenDraft=this.preferences.hiddenTags.join('，');this.dislikedDraft=this.preferences.dislikedTags.join('，');
        this.syncProfileForm(cached);
        this.restoreSnapshot(cached);
      }
      // Account authority must never wait for unrelated wallet/persona requests.
      void this.refreshPoints();
      void this.loadPersona();
      await this.refreshProfile();
    },

    async refreshProfile() {
      if (this.profileRefreshing) return;
      this.profileRefreshing = true;
      this.profileError = '';
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      try {
        const response = await api.profile({ signal: controller.signal });
        const profile = response?.data || response;
        if (!profile?.id) throw new Error('账户资料无效');
        this.applyProfile(profile);
      } catch (err) {
        this.adminVerified = false;
        if (err instanceof ApiError && err.code === 401) {
          clearAuth();
          location.replace('/app/login.html?next=' + encodeURIComponent(location.pathname));
        } else {
          this.profileError = '账户权限暂未确认，请重试。';
        }
      } finally {
        clearTimeout(timeout);
        this.profileRefreshing = false;
      }
    },

    applyProfile(profile) {
      this.user = profile || null;
      // Never grant a management entry from the persisted profile alone.
      this.adminVerified = profile?.is_admin === true || profile?.is_env_admin === true || profile?.role === 'admin';
      if (profile) {
        this.syncProfileForm(profile);
        setCachedUser(profile);
        this.persistSnapshot();
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
      return this.profileForm.avatar_url || this.user?.avatar_url || this.user?.avatar || '/assets/img/apk/default_avatar.png?v=20260901-persistent-pages';
    },

    profileDisplayId() {
      return this.user?.display_id || this.user?.public_id || this.user?.custom_id || '';
    },

    onAvatarError(event) {
      if (event?.target) event.target.src = '/assets/img/apk/default_avatar.png?v=20260901-persistent-pages';
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
        this.persistSnapshot();
      } catch { /* noop */ }
    },

    async savePersona() {
      this.savingPersona = true;
      try {
        const r = await api.setPersona(this.persona.name || '', this.persona.description || '');
        const data = r?.data || r || {};
        this.persona = { name: data.name || '', description: data.description || '' };
        this.persistSnapshot();
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

    paymentAvailable() {
      return !!(this.deposit?.payment_available && this.deposit?.mode !== 'closed');
    },

    paymentNote() {
      return this.paymentAvailable()
        ? this.depositText('payment_note_available', '兑换码只可使用一次，请确认登录的是当前账号。')
        : this.depositText('payment_note_unavailable', '充值通道暂时关闭，恢复后会重新开放购买和兑换。');
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
        this.persistSnapshot();
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

    openPayments() {
      if (this.paymentAvailable()) {
        window.location.href = '/app/rewards.html';
      } else {
        this.showToast(this.depositText('support_text', this.dashboardText('payment_missing_text', '充值通道暂时关闭')), 'error');
      }
    },

    async redeemNow() {
      if (!this.paymentAvailable()) {
        this.showToast(this.paymentNote(), 'error');
        return;
      }
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
        this.showToast(this.formatTemplate(this.dashboardText('redeem_success_template', '兑换成功 +{points} 惑梦币'), { points: data.points_added || 0 }), 'success');
      } catch (err) {
        this.showToast(err.message || this.dashboardText('redeem_failed_text', '兑换失败'), 'error');
      } finally { this.loading = false; }
    },

    async doLogout() {
      // 先请求后端清除 HttpOnly 登录 Cookie，再清理本地标记
      try { await api.logout(); } catch {}
      clearPageCache(ME_CACHE_SCOPE, this.user);
      clearAuth();
      this.showToast(this.dashboardText('logout_success_text', '已退出登录'), 'info');
      setTimeout(() => location.replace('/app/login.html'), 600);
    },

    restoreSnapshot(user = this.user) {
      const state = readPageCache(ME_CACHE_SCOPE, user);
      if (!state) return false;
      this.balance = this.normalizeBalance(state.balance || {});
      this.points = this.balance.points;
      this.deposit = state.deposit || null;
      this.persona = {
        name: String(state.persona?.name || ''),
        description: String(state.persona?.description || ''),
      };
      return true;
    },

    persistSnapshot() {
      if (!this.user) return;
      writePageCache(ME_CACHE_SCOPE, this.user, {
        balance: this.balance,
        deposit: this.deposit,
        persona: this.persona,
      });
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
