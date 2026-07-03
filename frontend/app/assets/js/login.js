import { api, setToken, ApiError } from '/app/assets/js/app-core.js';
import { loadPublicSiteSettings } from '/app/assets/js/layout.js?v=20260703-fengyue-ui2';

function loginPage() {
  return {
    view: 'login',
    loading: false,
    toast: null,
    toastTimer: null,
    loginForm: { email: '', password: '' },
    registerForm: { email: '', code: '', name: '', password: '' },
    sendingCode: false,
    codeCountdown: 0,
    countdownTimer: null,
    siteSettings: null,

    init() {
      // 已登录直接跳转
      const token = localStorage.getItem('ai_xingyue_token');
      if (token) {
        const next = new URLSearchParams(location.search).get('next') || '/app/';
        location.replace(next);
      }
      this.loadSiteSettings();
    },

    async loadSiteSettings() {
      this.siteSettings = await loadPublicSiteSettings().catch(() => null);
    },

    authText(key, fallback = '') {
      return this.siteSettings?.auth?.[key] || fallback;
    },

    showToast(message, type = 'info', duration = 2800) {
      if (this.toastTimer) clearTimeout(this.toastTimer);
      this.toast = { message, type };
      this.toastTimer = setTimeout(() => { this.toast = null; }, duration);
    },

    goNext() {
      const next = new URLSearchParams(location.search).get('next') || '/app/';
      location.replace(next);
    },

    async doLogin() {
      this.loading = true;
      try {
        const r = await api.login(this.loginForm.email.trim(), this.loginForm.password);
        const token = (r && (r.data || r));
        if (typeof token !== 'string') throw new Error(this.authText('login_invalid_response_text', '登录响应无效'));
        setToken(token);
        this.showToast(this.authText('login_success_text', '登录成功'), 'success');
        setTimeout(() => this.goNext(), 600);
      } catch (err) {
        this.showToast(err.message || this.authText('login_failed_text', '登录失败'), 'error');
      } finally { this.loading = false; }
    },

    async sendCode() {
      const email = this.registerForm.email.trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
        this.showToast(this.authText('invalid_email_text', '请输入正确的邮箱地址'), 'error');
        return;
      }
      this.sendingCode = true;
      try {
        await api.sendEmailCode(email);
        this.showToast(this.authText('code_sent_text', '验证码已发送，请查收邮件'), 'success');
        this.codeCountdown = 60;
        this.countdownTimer = setInterval(() => {
          this.codeCountdown--;
          if (this.codeCountdown <= 0) clearInterval(this.countdownTimer);
        }, 1000);
      } catch (err) {
        this.showToast(err.message || this.authText('send_failed_text', '发送失败'), 'error');
      } finally { this.sendingCode = false; }
    },

    async doRegister() {
      this.loading = true;
      try {
        const r = await api.register(
          this.registerForm.email.trim(),
          this.registerForm.password,
          this.registerForm.code.trim(),
          this.registerForm.name.trim()
        );
        const token = r && (r.data || r);
        if (typeof token !== 'string') throw new Error(this.authText('register_invalid_response_text', '注册响应无效'));
        setToken(token);
        this.showToast(this.authText('register_success_text', '注册成功，欢迎来到 AI星月'), 'success');
        setTimeout(() => this.goNext(), 700);
      } catch (err) {
        this.showToast(err.message || this.authText('register_failed_text', '注册失败'), 'error');
      } finally { this.loading = false; }
    },
  };
}

window.loginPage = loginPage;
document.addEventListener('alpine:init', () => {
  if (window.Alpine?.data) window.Alpine.data('loginPage', loginPage);
});
