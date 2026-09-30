import { api } from './api.js?v=20260917-r8';
export function adminDialogue() {
    const channel = 'homer:dialogue-host:v1';
    return {
        usesSharedConversationHost() {
            try { return window.HomerNative?.supportsSharedConversationHost?.() === true; }
            catch { return false; }
        },
        previewSearch: '', previewCards: [], previewCard: '', previewUrl: '', previewError: '',
        previewBusy: false, previewPage: 1, previewTotal: 0, previewSetupOpen: true,
        previewStarted: false, previewStarting: false, previewCoreReady: false, previewBridgeAvailable: false, previewPendingCard: '', previewTimeout: null,
        preparePreviewRuntime() {
            // Android already owns one persistent, prewarmed conversation host.
            // Never start a second engine inside the management WebView.
            if (this.usesSharedConversationHost()) return;
            if (this.previewUrl) return;
            const query = new URLSearchParams({ homer_admin_preview: '1', homer_prewarm: '1', homer_embed: '1', homer_site_origin: location.origin, homer_host_channel: channel });
            this.previewUrl = '/module/dialogue/?' + query;
            window.addEventListener('message', event => {
                const frame = document.querySelector('#admin-dialogue-frame');
                if (event.origin !== location.origin || event.source !== frame?.contentWindow || event.data?.channel !== channel || event.data?.version !== 1) return;
                const message = event.data;
                if (message.type === 'bridge-available') {
                    this.previewBridgeAvailable = true;
                    if (this.previewPendingCard) this.sendPreviewCommand('prepare-admin-preview', this.previewPendingCard);
                    else this.preparePreviewCard();
                }
                if (message.type === 'core-ready') {
                    if (this.previewCoreReady) return;
                    this.previewCoreReady = true;
                    this.previewBridgeAvailable = true;
                    if (this.previewPendingCard) this.sendPreviewCommand('bind-admin-preview', this.previewPendingCard);
                    else this.preparePreviewCard();
                }
                if (message.type === 'ready' && String(message.app_id) === String(this.previewPendingCard)) {
                    this.previewPendingCard = ''; this.previewStarting = false; this.previewStarted = true; this.previewSetupOpen = false;
                    clearTimeout(this.previewTimeout); performance.mark('homer-admin-workspace-ready');
                }
                if (['error', 'command-error'].includes(message.type)) {
                    this.previewStarting = false; this.previewError = message.message || '会话连接失败，请重试';
                    this.previewPendingCard = ''; clearTimeout(this.previewTimeout);
                }
            });
        },
        sendPreviewCommand(type, appId) {
            document.querySelector('#admin-dialogue-frame')?.contentWindow?.postMessage({ channel, version: 1, type, app_id: String(appId) }, location.origin);
        },
        preparePreviewCard() {
            if (this.usesSharedConversationHost()) {
                if (this.previewCard) window.HomerNative.prepareAdminConversation(String(this.previewCard));
                return;
            }
            if (this.previewBridgeAvailable && this.previewCard && !this.previewStarting)
                this.sendPreviewCommand('prepare-admin-preview', this.previewCard);
        },
        async loadPreviewCards(page = 1) {
            if (this.previewBusy) return;
            this.previewBusy = true; this.previewError = '';
            try {
                const response = await api.admin.apps({ q: this.previewSearch.trim(), source: 'all', page, page_size: 30, lightweight: 1 });
                const data = response.data || response;
                this.previewCards = data.list || []; this.previewPage = page; this.previewTotal = data.total || 0;
                if (!this.previewCard && this.previewCards.length) this.previewCard = this.previewCards[0].id;
                this.preparePreviewCard();
            } catch (error) { this.previewError = error.message || '角色读取失败，请重试'; }
            finally { this.previewBusy = false; }
        },
        async openPreview() {
            this.activeTab = 'dialogue-preview';
            if (!this.previewCards.length) await this.loadPreviewCards();
        },
        async startPreview() {
            if (!this.previewCard || this.previewBusy || this.previewStarting) return;
            if (this.usesSharedConversationHost()) {
                const query = new URLSearchParams({ app_id: String(this.previewCard), admin_preview: '1' });
                location.assign('/app/chat.html?' + query);
                return;
            }
            if (this.previewStarted && !await this.confirmPreviewReset()) return;
            this.preparePreviewRuntime();
            this.previewError = '';
            performance.mark('homer-admin-workspace-click');
            this.previewStarting = true; this.previewPendingCard = String(this.previewCard);
            if (this.previewCoreReady) this.sendPreviewCommand('bind-admin-preview', this.previewPendingCard);
            else if (this.previewBridgeAvailable) this.sendPreviewCommand('prepare-admin-preview', this.previewPendingCard);
            clearTimeout(this.previewTimeout);
            this.previewTimeout = setTimeout(() => {
                this.previewStarting = false; this.previewPendingCard = '';
                this.previewError = '会话连接超时，请检查服务连接后重试。普通历史会话不受影响。';
            }, 30000);
        },
        async confirmPreviewReset() {
            const { confirmAction } = await import('./dialogs.js?v=20260917-r8');
            return confirmAction('当前测试消息不会保留，也不会影响普通历史会话。', { title: '重新开始试聊？', confirmText: '重新开始' });
        },
    };
}
