import {
    changeMainAPI,
    eventSource,
    event_types,
    getRequestHeaders,
    messageEdit,
    isGenerating,
    saveSettingsDebounced,
    setOnlineStatus,
    activateCharacterForChat,
    prepareCharacterRead,
    prepareCharacterChatMirrorRead,
    scrollChatToBottom,
    scrollOnMediaLoad,
} from '../../../script.js';
import { oai_settings } from '../../openai.js';
import { prefetchPersonaAvatarsForConversation, prefetchPersonaAvatarsForCurrentChat } from '../../personas.js';
import { greetingSwipes, restoreCanonicalGreeting } from '../../homer-greeting-swipes.mjs';
import { refreshSettledAvatarImages } from '../../homer-avatar-refresh.mjs';
import { messagePreview } from '/assets/js/message-preview.js';
import { publicModel, fillModelSelect } from '/assets/js/model-catalog.js';
import { messageActionIcon, positionChatMenu } from '/assets/js/chat-menu.js';
import { createDeferredListCovers } from '/assets/js/deferred-list-covers.mjs';
import { allowScopedScripts, getRegexScripts, getRegexedString, regex_placement } from '../regex/engine.js';
import { extension_settings, writeExtensionField } from '../../extensions.js';
import { getContext } from '../../st-context.js';
import { accountStorage } from '../../util/AccountStorage.js';
import {
    convertCharacterBook,
    saveWorldInfo,
    updateWorldInfoList,
    world_names,
} from '../../world-info.js';
import { loadApprovedExtensions } from './extension-host.js';
import { installRoleplayHubCompatibility } from './roleplayhub-compat.js';
import { installCardStageRuntime, closeCardStageOverlay } from './card-stage.js';
import { installKeywordInjector } from './keyword-injector.js';
import { openChatTool } from '/assets/js/chat-tools.js';
import { bindChatAppearance } from '/assets/js/chat-appearance.js';
import { installMemoryUi } from '/assets/js/memory-ui.js';
import { settingsPage } from '/assets/js/chat-settings-page.js';
import { controlCenter } from '/assets/js/chat-control-center.js';
import { apiText } from '/assets/js/api-transport.js';
import { officialDisplayRules, setOfficialDisplayRules } from '../../homer-official-regex.mjs';
import { generationFailure, safeDiagnostic } from '../../homer-generation-diagnostics.mjs';
import { activateModelScope, confirmModelChange, mountModelGate } from '../../homer-model-gate.mjs';
import { adminWorkspace } from './admin-workspace.js';
import { chatImages } from '/assets/js/chat-images.js';
import { loadTavoUi, decorateTavoMessage, mountTavoComposer, refreshTavoUi, setTavoHostInsets, installTavoComposerFocusRelay } from '/assets/js/tavo-chat-ui.js';
import { captureCloudSync, canApplyCloudSync, createCloudSyncQueue } from '../../homer-cloud-sync.mjs';
import { createCardPreparationCache } from '../../homer-stable-template.mjs';
import { createChatOutbox } from '../../homer-chat-outbox.mjs';
import { requestSessionCard } from '../../homer-card-transport.mjs';
import { clearCardTransportMemory } from '../../homer-card-transport-cache.mjs';
import { holdLargeSourceLayout } from '../../homer-source-layout.mjs';
import { preloadStaticDialogueUi } from '../../homer-static-ui-preload.mjs';
import { capturePromptMessageState, prepareAcknowledgedPromptStates, restoreAcknowledgedPromptStates, samePromptMessageSource, clearPromptMessageState } from '../../homer-prompt-message-state.mjs';

const cardPreparations = createCardPreparationCache();
const chatOutbox = createChatOutbox();
const storageRequests = new Set();
let storageAccountEpoch = 0;
let verifiedStorageOwner = '';
let storageOwner = authenticatedStorageOwner();
let outboxReplay = null;
let extensionSettingsReplayWork = Promise.resolve();
const sessionReadFences = new WeakMap();
const acknowledgedPromptTickets = new WeakMap();
const storageAckStamps = new Map();

function storageAckKey(scope, kind = 'chat') { return JSON.stringify([scope, kind]); }
function storageAckStamp(scope, kind = 'chat') {
    const key = storageAckKey(scope, kind);
    if (!storageAckStamps.has(key)) storageAckStamps.set(key, { version: 0 });
    const stamp = storageAckStamps.get(key);
    storageAckStamps.delete(key); storageAckStamps.set(key, stamp);
    while (storageAckStamps.size > 64) storageAckStamps.delete(storageAckStamps.keys().next().value);
    return stamp;
}
async function acknowledgeStorage(committed, response) {
    const acknowledgement = await chatOutbox.cloudACK(committed, response);
    if (acknowledgement.applied) storageAckStamp(committed.scope, committed.kind).version++;
    return acknowledgement;
}

function authenticatedStorageOwner() {
    try {
        if (localStorage.getItem('ai_xingyue_logged_in') !== '1') return verifiedStorageOwner;
        const user = JSON.parse(localStorage.getItem('ai_xingyue_user') || 'null');
        return String(user?.id || user?.user_id || '').trim() || verifiedStorageOwner;
    } catch { return verifiedStorageOwner; }
}

function invalidateStorageAccount() {
    clearCardTransportMemory();
    verifiedStorageOwner = ''; storageOwner = ''; storageAccountEpoch++;
    for (const controller of storageRequests) controller.abort();
    cardPreparations.clear(); sessionPrefetchCache.clear(); storageAckStamps.clear();
    sessionPrefetchPeer = null;
    preparedAdminLaunch = null; scopeDrafts.clear();
}

function acceptVerifiedSessionOwner(payload, requestOwner, requestEpoch) {
    const userId = String(payload?.user?.id || payload?.user?.user_id || '').trim();
    const currentOwner = reconcileStorageAccount();
    if (!userId || requestEpoch !== storageAccountEpoch
        || (requestOwner && requestOwner !== userId) || (currentOwner && currentOwner !== userId)) {
        throw new Error('会话账号已切换，请重新进入');
    }
    // A successful authenticated server session, not a local login flag,
    // establishes the initial owner for a cookie-only login. No credentials
    // are copied and a logout epoch can never be revived by an old response.
    if (!currentOwner) { verifiedStorageOwner = userId; storageOwner = userId; }
}

function reconcileStorageAccount() {
    const owner = authenticatedStorageOwner();
    if (owner !== storageOwner) {
        clearCardTransportMemory();
        storageOwner = owner; storageAccountEpoch++;
        for (const controller of storageRequests) controller.abort();
        cardPreparations.clear();
        sessionPrefetchCache.clear();
        sessionPrefetchPeer = null;
        storageAckStamps.clear();
        preparedAdminLaunch = null; scopeDrafts.clear();
    }
    return owner;
}

async function requestScopedStorage(snapshot, kind, options = {}) {
    const owner = JSON.parse(snapshot.scope)[0];
    if (!owner || reconcileStorageAccount() !== owner
        || owner !== String(session?.user?.id || session?.user?.user_id || '')) {
        throw new Error('会话账号已切换');
    }
    const epoch = storageAccountEpoch;
    const current = await chatOutbox.fence(snapshot.scope, kind);
    if (reconcileStorageAccount() !== owner || epoch !== storageAccountEpoch
        || owner !== String(session?.user?.id || session?.user?.user_id || '')) throw new Error('会话账号已切换');
    if (!current || current.commitId !== snapshot.committed?.commitId || current.revision !== snapshot.committed?.revision) {
        throw new Error('本机存档已更新，等待最新版本同步');
    }
    const controller = new AbortController();
    storageRequests.add(controller);
    try {
        const result = await requestJson(kind === 'chat' ? '/api/homer/sync' : '/api/homer/runtime-state', {
            method: 'POST', body: snapshot.body, ...options, signal: controller.signal,
        });
        if (reconcileStorageAccount() !== owner || epoch !== storageAccountEpoch) throw new Error('会话账号已切换');
        if (kind === 'chat' && !Array.isArray(result?.messages)) throw new Error('云端未确认聊天记录');
        return result;
    } finally { storageRequests.delete(controller); }
}

const extensionSyncQueue = createCloudSyncQueue(async (snapshot, options) => {
    const epoch = storageAccountEpoch;
    const result = await requestScopedStorage(snapshot, 'extension-settings', options);
    await acknowledgeStorage(snapshot.committed, result);
    if (JSON.parse(snapshot.scope)[0] !== reconcileStorageAccount() || epoch !== storageAccountEpoch) throw new Error('会话账号已切换');
    return result;
});

async function replayPendingStorage() {
    const owner = reconcileStorageAccount();
    if (!owner || owner !== String(session?.user?.id || session?.user?.user_id || '')) return;
    if (outboxReplay) return outboxReplay;
    outboxReplay = (async () => {
        for (const committed of await chatOutbox.pending(owner)) {
            if (reconcileStorageAccount() !== owner) break;
            // Read back after listing: a live edit may have committed a newer
            // version while another scope was uploading. Never replay that old
            // listed body over the new one.
            const latest = await chatOutbox.read(committed.scope, committed.kind);
            if (!latest?.pending) continue;
            const snapshot = captureCloudSync(latest.scope, latest.payload);
            snapshot.committed = latest;
            try {
                await (latest.kind === 'chat' ? cloudSyncQueue : extensionSyncQueue).enqueue(snapshot);
            } catch { break; } // Retain the failed and remaining durable rows.
        }
    })().catch(() => {
        console.warn(`${MODULE_ID}: local chat replay remains pending`);
    }).finally(() => { outboxReplay = null; });
    return outboxReplay;
}

window.addEventListener('storage', event => {
    if (!event.key || (event.key === 'ai_xingyue_user' && event.newValue === null)
        || (event.key === 'ai_xingyue_logged_in' && event.newValue !== '1')) invalidateStorageAccount();
    else if (['ai_xingyue_user', 'ai_xingyue_logged_in'].includes(event.key)) reconcileStorageAccount();
});
window.addEventListener('homer-account-cleared', invalidateStorageAccount);

let tavoComposer = null;
let tavoUiReady;
let chatAppearance = null;
function prepareTavoConversationUi() {
    if (!tavoUiReady) tavoUiReady = loadTavoUi().catch(error => { tavoUiReady = null; throw error; });
    return tavoUiReady;
}

function setComposerDraft(value) {
    const composer = document.querySelector('#send_textarea');
    if (!(composer instanceof HTMLTextAreaElement)) return;
    composer.value = String(value || '').slice(0, 10_000);
    composer.dispatchEvent(new Event('input', { bubbles: true }));
    const key = scopeDraftKey();
    if (key) scopeDrafts.set(key, composer.value);
}

function openComposerFullscreen() {
    const source = document.querySelector('#send_textarea');
    if (!source || loadingLaunch) return;
    const scope = scopeDraftKey();
    document.querySelector('#homer-composer-fullscreen')?.remove();
    const dialog = createElement('dialog', 'homer-composer-fullscreen');
    dialog.id = 'homer-composer-fullscreen'; dialog.setAttribute('aria-label', '编辑消息');
    const head = createElement('header');
    const cancel = createElement('button', '', '取消'), save = createElement('button', '', '完成');
    cancel.type = save.type = 'button';
    const editor = createElement('textarea'); editor.value = source.value; editor.maxLength = 10_000;
    editor.setAttribute('aria-label', '消息正文');
    cancel.addEventListener('click', () => dialog.close());
    save.addEventListener('click', () => {
        if (scopeDraftKey() !== scope) { dialog.close(); return; }
        setComposerDraft(editor.value); tavoComposer?.refresh(); dialog.close();
    });
    head.append(cancel, createElement('strong', '', '编辑消息'), save); dialog.append(head, editor);
    dialog.addEventListener('close', () => dialog.remove(), { once: true });
    document.body.append(dialog); dialog.showModal(); editor.focus();
}

async function installTavoConversationUi() {
    await prepareTavoConversationUi();
    const container = document.querySelector('#form_sheld');
    if (!container) throw new Error('对话输入区域未就绪');
    if (!tavoComposer) {
        tavoComposer = await mountTavoComposer({
            container,
            inputSizing: () => !(canNotifyHost() && document.documentElement.classList.contains('homer-host-chrome')),
            getState: () => ({ scope: scopeDraftKey(), text: document.querySelector('#send_textarea')?.value || '',
                generating: Boolean(isGenerating() || generationBusy), disabled: Boolean(loadingLaunch || rollbackBusy || conversationRecoveryBlocked) }),
            onText: text => setComposerDraft(text),
            onSubmit: text => {
                if (isGenerating() || generationBusy || rollbackBusy || loadingLaunch || conversationRecoveryBlocked || !text.trim()) return;
                assertCanonicalConversationScope();
                setComposerDraft(text);
                const send = document.querySelector('#send_but');
                if (send && !send.matches(':disabled')) send.click();
            },
            onStop: () => { getContext().stopGeneration(); scheduleHostStateNotify(0, 'stop-requested'); },
            onPlus: text => { setComposerDraft(text); openHostRequestedSettings('attachments'); },
            onFullscreen: text => { setComposerDraft(text); openComposerFullscreen(); },
        });
        const canonicalInput = document.querySelector('#send_textarea');
        canonicalInput?.addEventListener('input', () => tavoComposer?.refresh());
    }
    tavoComposer.refresh(); queueMessageMenuRender();
}

const imageGenerationUi = chatImages({
    request: requestJson,
    scope: () => launch ? { user: session?.user?.id || '', conversation: launch.conversation_id, preview: !!launch.admin_preview } : null,
    prepare: async target => {
        await syncCloudChat();
        return cloudHomerMessageId(resolveMessageMenuTarget(target)?.message);
    },
    notice: showHostNotice,
    messages: () => [...document.querySelectorAll('#chat .mes')].map(element => ({
        element, id: cloudHomerMessageId(getContext().chat[messageIndexFromElement(element)]),
    })),
});

let adminConversationDraft = {};
let adminConversationConfig = null;

async function refreshAdminConfiguration(modelId = '', draft = adminConversationDraft) {
    const config = await requestJson('/api/homer/admin-configuration', {
        method: 'POST', body: JSON.stringify({ app_id: launch.app_id,
            model: modelId || conversationModelSettings().model_id || '', draft,
            include_library: !adminConversationConfig?.library }),
    });
    adminConversationConfig = { ...config, library: config.library || adminConversationConfig?.library };
    officialRegexState = setOfficialDisplayRules(config.display_regex);
    return config;
}

const administratorEditor = adminWorkspace({
    getConfig: () => adminConversationConfig,
    getDraft: () => adminConversationDraft,
    busy: () => isGenerating(),
    notice: (...args) => showHostNotice(...args),
    apply: async draft => {
        if (!launch?.admin_preview || !session?.user?.is_admin || isGenerating()) throw new Error('不可修改');
        const config = await refreshAdminConfiguration('', draft);
        // Store only explicitly changed sections, so untouched sections keep following
        // live model bindings and saved global changes on subsequent generations.
        adminConversationDraft = Object.fromEntries(Object.keys(draft).map(key => [key, config[key]]));
    },
    saveGlobal: async (kind, value) => {
        if (!launch?.admin_preview || !session?.user?.is_admin) throw new Error('没有权限');
        await requestJson(`/api/homer/admin-presets/${kind}/${encodeURIComponent(value.id)}`, { method: 'POST', body: JSON.stringify({ preset: value }) });
        adminConversationConfig.library = null;
        await refreshAdminConfiguration();
    },
});

const MODULE_ID = 'homer-bridge';
const urlParams = new URLSearchParams(window.location.search);
const adminPreviewRequested = urlParams.get('homer_admin_preview') === '1';
let officialRegexState = { count: 0, errors: [] };
let lastGenerationDiagnostic = null;
let requestedAppId = String(urlParams.get('homer_app_id') || urlParams.get('app_id') || '').trim();
let requestedConversationId = String(
    urlParams.get('homer_conversation_id')
    || urlParams.get('conversation_id')
    || urlParams.get('conv_id')
    || '',
).trim();
const requestedSiteOrigin = String(urlParams.get('homer_site_origin') || '').trim();
const requestedHostChannel = String(urlParams.get('homer_host_channel') || '').trim();
const requestedEmbed = String(urlParams.get('homer_embed') || '').trim();
// Presentation capability only. It neither establishes an owner nor grants
// card access, and administrator/older hosts retain the original transport.
const requestedIdleHostDisplay = urlParams.get('homer_idle_host_display') === '1';
const HOST_CHANNEL = 'homer:dialogue-host:v1';
const prewarmOnly = urlParams.get('homer_prewarm') === '1';
// Correlation only. Capture once so a new host name cannot relabel an old
// document. This identifier never grants account or card access.
const hostBootstrapEngineToken = normalizeBootstrapToken(String(window.name || '').startsWith('homer-bootstrap:')
    ? String(window.name).slice('homer-bootstrap:'.length) : '');
const hostBootstrapDocumentToken = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
if (hostBootstrapEngineToken) document.documentElement.dataset.homerBootstrapDocument = hostBootstrapDocumentToken;
let boundBootstrapToken = '';
if (urlParams.get('homer_host_chrome') === '1') {
    document.documentElement.classList.add('homer-host-chrome');
    installTavoComposerFocusRelay();
}
let coreAvailable = false;
let preparedAdminLaunch = null;
let adminBinding = false;
// Drafts belong to a verified scope, never to the reused DOM/composer itself.
// Memory-only and bounded; the native host is discarded on account changes.
const scopeDrafts = new Map();
function scopeDraftKey() {
    if (!launch?.conversation_id) return '';
    return JSON.stringify([session?.user?.id || session?.user?.user_id, Boolean(launch.admin_preview), launch.app_id, launch.conversation_id]);
}
function retainScopeDraft() {
    const key = scopeDraftKey();
    if (!key) return;
    scopeDrafts.set(key, document.querySelector('#send_textarea')?.value || '');
    if (scopeDrafts.size > 12) scopeDrafts.delete(scopeDrafts.keys().next().value);
}
function restoreScopeDraft() {
    const composer = document.querySelector('#send_textarea');
    if (!composer) return;
    const draft = scopeDrafts.get(scopeDraftKey()) || '';
    // Re-announcing an unchanged draft is not an input change. The normal
    // ready/state notifications still refresh model, busy and layout state.
    if (composer.value === draft) return;
    composer.value = draft;
    composer.dispatchEvent(new Event('input', { bubbles: true }));
}

function prepareAdminLaunch(appId) {
    if (!appId) return null;
    const owner = reconcileStorageAccount(), epoch = storageAccountEpoch;
    if (preparedAdminLaunch?.appId === appId && preparedAdminLaunch.owner === owner
        && preparedAdminLaunch.epoch === epoch && Date.now() - preparedAdminLaunch.created < 15000) return preparedAdminLaunch.promise;
    const promise = Promise.all([fetchSession(appId, '', true), requestJson('/api/homer/models')]).then(async ([preview, models]) => {
        acceptVerifiedSessionOwner(preview, owner, epoch);
        const enabled = payloadList(models).filter(item => item?.enabled !== false);
        const model = String(models?.default_id || enabled.find(item => item?.is_default)?.id || enabled[0]?.id || '');
        const config = await requestJson('/api/homer/admin-configuration', {
            method: 'POST', body: JSON.stringify({ app_id: appId, model, draft: {}, include_library: true }),
        });
        acceptVerifiedSessionOwner(preview, owner, epoch);
        // Memory-only, single-consumption data. Generation still refreshes the
        // authoritative configuration; no old draft or account cache is reused.
        return { ...preview, adminStartupData: { models, config } };
    });
    // Preload failures are surfaced on explicit bind, never unhandled rejections.
    promise.catch(() => { if (preparedAdminLaunch?.promise === promise) preparedAdminLaunch = null; });
    preparedAdminLaunch = { appId, owner, epoch, created: Date.now(), promise };
    return promise;
}

let initialized = false;
let bridgeStartScheduled = false;
let launchSessionPreloadPromise = null;
// Shared work that is safe to perform before a conversation is bound.  Keep
// this separate from the session preload: the latter contains account/card
// state and must never run for the empty prewarm page.
let administratorExtensionsPromise = null;
let prewarmBootstrapPromise = null;
let applicationReady = false;
let resolveApplicationReady;
const applicationReadyPromise = new Promise(resolve => {
    resolveApplicationReady = resolve;
});
let postApplicationReadyWork = Promise.resolve();
let loadingLaunch = false;
// A failed activation must never expose a previous launch over another
// character's canonical chat, or permit that chat to be saved/generated.
let conversationRecoveryBlocked = false;
let pendingCardScriptCharacter = null;
let launch = null;
let session = null;
let runtimeVariables = {};
let presetSearchQuery = '';
let syncTimer = null;
let tokenRefreshTimer = null;
let generationSettleTimer = null;
let suppressSync = false;
let generationBusy = false;
let generationSnapshot = null;
let generationRecoveryChain = Promise.resolve();
let rollbackBusy = false;
let lastSyncSignature = '';
const cloudSyncQueue = createCloudSyncQueue(async (snapshot, options) => {
    const epoch = storageAccountEpoch;
    const result = await requestScopedStorage(snapshot, 'chat', options);
    await acknowledgeStorage(snapshot.committed, result);
    if (JSON.parse(snapshot.scope)[0] !== reconcileStorageAccount() || epoch !== storageAccountEpoch) throw new Error('会话账号已切换');
    return result;
});
let eventHandlersInstalled = false;
let dialogueEventLogMuted = 0;
let messageMenuObserver = null;
let messageMenuRenderQueued = false;
let activeMessageMenuTarget = null;
let messageSelection = null;
let messagePressTimer = null;
let messagePressStart = null;
let messagePressTarget = null;
let suppressMessageClickUntil = 0;
let suppressMessageMenuPressRelease = false;
let hostOverlayActive = false;
let hostOverlaySignature = '';
let hostOverlayObserver = null;
let hostOverlaySyncQueued = false;
let presentationModeBridgeInstalled = false;
const MESSAGE_LONG_PRESS_DELAY = 500;
const MESSAGE_LONG_PRESS_MOVE_TOLERANCE = 10;
let extensionSettingsBridgeInstalled = false;
let embeddedDocumentLookupBridgeInstalled = false;
let extensionSettingsBaseline = null;
let conversationExtensionSettings = null;
let reaffirmExtensionSettingsAfterReady = false;
let extensionSettingsHydrating = false;
let extensionSettingsReplayInProgress = false;
let extensionSettingsPersistTimer = null;
let extensionSettingsPersistChain = Promise.resolve();
let extensionSettingsPersistWaiters = [];
let lastExtensionSettingsScope = '';
let lastExtensionSettingsSignature = '';
let productSurfaceBoundaryInstalled = false;
let upstreamNoticeObserver = null;
const pendingHostNotices = [];
let runtimeUiData = {
    conversations: [],
    models: [],
    modelDefaultId: '',
    mods: [],
    activeModIds: [],
};
let managedConversation = null;
const SESSION_PREFETCH_LIMIT = 2;
const SESSION_CACHE_TTL_MS = 30_000;
const sessionPrefetchCache = new Map();
let sessionPrefetchTimer = null;
let sessionPrefetchPeer = null;
let hostStateNotifyTimer = null;
let hostStateNotifyToken = null;

const DEFAULT_MODEL_SETTINGS = Object.freeze({
    model_id: '',
    temperature: 1,
    top_p: 1,
    frequency_penalty: 0,
    presence_penalty: 0,
});

function unwrap(payload) {
    if (payload && typeof payload === 'object' && payload.data !== undefined) {
        return payload.data;
    }
    return payload;
}

function runtimeGate() {
    return document.querySelector('#homer-runtime-gate');
}

function installEmbeddedComposerPolicy() {
    if (requestedEmbed !== '1' || document.documentElement.dataset.homerComposerPolicy === '1') {
        return;
    }
    document.documentElement.dataset.homerComposerPolicy = '1';
    const style = document.createElement('style');
    style.dataset.homerComposerPolicy = '1';
    style.textContent = [
        '#send_textarea ~ .autoComplete-wrap',
        '#send_textarea + .autoComplete-wrap',
        '.autoComplete-wrap:has(+ #send_textarea)',
        '.slashCommandBrowser',
    ].join(',') + '{display:none !important;visibility:hidden !important;pointer-events:none !important;}';
    (document.head || document.documentElement).append(style);
    const updateComposer = () => {
        const composer = document.querySelector('#send_textarea');
        if (composer instanceof HTMLTextAreaElement && composer.placeholder !== '随便聊聊...') {
            composer.placeholder = '随便聊聊...';
        }
    };
    const hideAutocomplete = (root) => {
        if (!(root instanceof Element)) return;
        const selector = '.autoComplete-wrap,.slashCommandBrowser';
        const nodes = [...root.querySelectorAll(selector)];
        if (root.matches(selector)) nodes.push(root);
        nodes.forEach(node => {
            node.style.setProperty('display', 'none', 'important');
            node.setAttribute('aria-hidden', 'true');
        });
    };
    hideAutocomplete(document.body);
    updateComposer();
    new MutationObserver(records => {
        // Inspect only new subtrees, not both full runtime and host documents
        // on every plugin mutation. Placeholder changes need no selector walk.
        const added = new Set();
        let composerChanged = false;
        for (const record of records) {
            if (record.type === 'attributes') composerChanged ||= record.target.id === 'send_textarea';
            for (const node of record.addedNodes) if (node instanceof Element) added.add(node);
        }
        for (const node of added) {
            if (!node.isConnected) continue;
            let parent = node.parentElement;
            while (parent && !added.has(parent)) parent = parent.parentElement;
            if (parent) continue;
            hideAutocomplete(node);
            composerChanged ||= node.id === 'send_textarea' || !!node.querySelector('#send_textarea');
        }
        if (composerChanged) updateComposer();
    }).observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['placeholder'],
    });
}

function setRuntimeGate(title, detail, { error = false } = {}) {
    const gate = runtimeGate();
    if (!gate) {
        return;
    }
    gate.classList.toggle('is-error', Boolean(error));
    gate.setAttribute('aria-busy', String(!error));
    const titleElement = gate.querySelector('.homer-runtime-gate__title');
    const detailElement = gate.querySelector('.homer-runtime-gate__detail');
    if (titleElement && title) {
        titleElement.textContent = String(title);
    }
    if (detailElement && detail) {
        detailElement.textContent = String(detail);
    }
}

async function releaseRuntimeGate() {
    // The host keeps this iframe covered until we report readiness. Do not
    // wait for frames here: a covered/background WebView can throttle them.
    // loadCloudChat has already completed rendering before this is called.
    const gate = runtimeGate();
    document.documentElement.classList.remove('homer-runtime-pending');
    gate?.classList.add('is-ready');
    gate?.setAttribute('aria-busy', 'false');
    // The embedded host reveals a genuinely ready conversation. Do not reveal
    // a fading launch card for another 260 ms after its readiness message.
    if (requestedEmbed === '1') gate?.remove();
    else window.setTimeout(() => gate?.remove(), 260);
}

function failRuntimeGate(error) {
    const message = String(error?.message || '对话服务暂时不可用，请稍后重试。');
    document.documentElement.classList.add('homer-runtime-pending');
    setRuntimeGate('对话暂时无法连接', message, { error: true });
}

async function requestJson(url, options = {}) {
    const method = String(options.method || 'GET').toUpperCase();
    const headers = {
        ...getRequestHeaders(),
        ...(options.headers || {}),
    };
    const { response, text } = await apiText(url, {
        ...options,
        method,
        headers,
        cache: 'no-store',
    });
    let payload = {};
    try {
        payload = JSON.parse(text);
    } catch {
        payload = {};
    }
    if (!response.ok || payload?.result === 'failure') {
        const message = payload?.error?.message || payload?.message || payload?.error || `HTTP ${response.status}`;
        // 只抛，不在这里弹持久错误条。requestJson 有 26 个调用点，很多是
        // 探测性/可容错的（例如 fetchSession 的嵌入式端点失败后还有回退），
        // 在最底层弹条会把这些正常回退渲染成一条不消失的「对话服务连接失败」。
        // 需要提示的调用点自己走 showHostNotice。
        throw new Error(String(message));
    }
    return unwrap(payload);
}

function queryString(appId, conversationId = '') {
    const params = new URLSearchParams({ app_id: appId });
    if (conversationId) {
        params.set('conversation_id', conversationId);
    }
    return params.toString();
}

function clampNumber(value, minimum, maximum, fallback) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.min(maximum, Math.max(minimum, parsed)) : fallback;
}

function cloneJsonObject(value) {
    try {
        const cloned = JSON.parse(JSON.stringify(value));
        return cloned && typeof cloned === 'object' && !Array.isArray(cloned) ? cloned : {};
    } catch {
        return {};
    }
}

function isJsonObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value);
}

function isPlainRuntimeTree(value, ancestors = new Set()) {
    if (value === null || typeof value === 'string' || typeof value === 'boolean') {
        return true;
    }
    if (typeof value === 'number') {
        return Number.isFinite(value);
    }
    if (typeof value !== 'object' || ancestors.has(value)) {
        return false;
    }

    const array = Array.isArray(value);
    const prototype = Object.getPrototypeOf(value);
    if (
        (array && prototype !== Array.prototype)
        || (!array && prototype !== Object.prototype && prototype !== null)
        || !Object.isExtensible(value)
    ) {
        return false;
    }

    ancestors.add(value);
    try {
        for (const key of Reflect.ownKeys(value)) {
            if (array && key === 'length') {
                continue;
            }
            if (typeof key === 'symbol' || (array && !/^(0|[1-9]\d*)$/.test(key))) {
                return false;
            }
            const descriptor = Object.getOwnPropertyDescriptor(value, key);
            if (
                !descriptor
                || !Object.hasOwn(descriptor, 'value')
                || !descriptor.enumerable
                || !descriptor.configurable
                || !descriptor.writable
                || !isPlainRuntimeTree(descriptor.value, ancestors)
            ) {
                return false;
            }
        }
        return true;
    } finally {
        ancestors.delete(value);
    }
}

function cloneJsonValue(value) {
    return JSON.parse(JSON.stringify(value));
}

function synchronizeJsonContainer(target, source, options = {}) {
    if (options.preserveUnsafeNamespaces) {
        if (!isJsonObject(target) || !isJsonObject(source)) {
            return target;
        }
        // A conversation snapshot is an overlay. Card-script sandboxes may
        // expose and save only part of extensionSettings, so an absent
        // top-level namespace must retain its native/baseline value rather than
        // being deleted (regex, TTS and expressions require their defaults).
        for (const [key, value] of Object.entries(source)) {
            const current = target[key];
            if (current === undefined) {
                if (isPlainRuntimeTree(value)) {
                    target[key] = cloneJsonValue(value);
                }
                continue;
            }
            // Some extensions hydrate their JSON settings into class instances
            // and retain references to them. A generic JSON restore cannot
            // recreate those prototypes, so preserve the live namespace and let
            // its owning extension manage deserialization.
            if (!isPlainRuntimeTree(current) || !isPlainRuntimeTree(value)) {
                continue;
            }
            if (
                (Array.isArray(current) && Array.isArray(value))
                || (isJsonObject(current) && isJsonObject(value))
            ) {
                synchronizeJsonContainer(current, value);
            } else {
                target[key] = cloneJsonValue(value);
            }
        }
        return target;
    }

    if (!isPlainRuntimeTree(target) || !isPlainRuntimeTree(source)) {
        return target;
    }
    if (Array.isArray(target) && Array.isArray(source)) {
        target.splice(0, target.length, ...cloneJsonValue(source));
        return target;
    }
    if (isJsonObject(target) && isJsonObject(source)) {
        for (const key of Object.keys(target)) {
            if (!Object.hasOwn(source, key)) {
                delete target[key];
            }
        }
        for (const [key, value] of Object.entries(source)) {
            const current = target[key];
            if (
                (Array.isArray(current) && Array.isArray(value))
                || (isJsonObject(current) && isJsonObject(value))
            ) {
                synchronizeJsonContainer(current, value);
            } else {
                target[key] = cloneJsonValue(value);
            }
        }
        return target;
    }
    return source;
}

function replaceExtensionSettings(value) {
    extensionSettingsHydrating = true;
    try {
        // Real extensions keep long-lived references to their nested settings
        // objects. Mutate those containers in place so a conversation restore
        // cannot leave an extension writing through a stale object reference.
        // Runtime-owned class instances are deliberately preserved because a
        // JSON snapshot cannot reconstruct their methods or custom prototypes.
        synchronizeJsonContainer(extension_settings, cloneJsonObject(value), {
            preserveUnsafeNamespaces: true,
        });
        ensureHomerExtensionSettingDefaults();
    } finally {
        extensionSettingsHydrating = false;
    }
}

function ensureHomerExtensionSettingDefaults() {
    if (!requestedAppId || !requestedConversationId) {
        return;
    }
    const disabledExtensions = new Set(
        Array.isArray(extension_settings.disabledExtensions)
            ? extension_settings.disabledExtensions
            : [],
    );
    disabledExtensions.add('third-party/st-yuzi-phone');
    extension_settings.disabledExtensions = [...disabledExtensions];
    const memoryBooks = extension_settings.STMemoryBooks ||= {};
    const moduleSettings = memoryBooks.moduleSettings ||= {};
    // Homer owns the chat header. Memory Books remains fully available from
    // the settings drawer, but its optional TopInfoBar install notice would
    // otherwise cover the first model-settings interaction.
    moduleSettings.dismissMissingTopInfoBarJobsNotice = true;
}

function captureExtensionSettingsBaseline() {
    ensureHomerExtensionSettingDefaults();
    extensionSettingsBaseline = cloneJsonObject(extension_settings);
    Object.defineProperty(globalThis, '__homerNativeExtensionSettingsSnapshot', {
        configurable: true,
        value: () => cloneJsonObject(extensionSettingsBaseline),
    });
}

function extensionSettingsScope(appId = launch?.app_id, conversationId = launch?.conversation_id) {
    return `${String(appId || '')}\u0000${String(conversationId || '')}`;
}

function extensionSettingsSnapshot() {
    const value = cloneJsonObject(extension_settings);
    return {
        value,
        signature: JSON.stringify(value),
    };
}

function captureExtensionStorage(options = {}) {
    if (launch?.admin_preview) return null;
    if (extensionSettingsHydrating || conversationRecoveryBlocked || !hasCanonicalConversationScope()
        || !launch?.app_id || !launch?.conversation_id) {
        return null;
    }
    const appId = String(launch.app_id);
    const conversationId = String(launch.conversation_id);
    const scope = extensionSettingsScope(appId, conversationId);
    const snapshot = extensionSettingsSnapshot();
    if (!options.force && scope === lastExtensionSettingsScope && snapshot.signature === lastExtensionSettingsSignature) {
        return null;
    }
    return {
        snapshot: captureCloudSync(cloudSyncScope(), {
            app_id: appId, conversation_id: conversationId, extension_settings: snapshot.value,
        }), scope, signature: snapshot.signature,
    };
}

async function persistExtensionSettingsSnapshot(options = {}, captured = captureExtensionStorage(options)) {
    if (!captured) return false;
    captured.snapshot.committed = await chatOutbox.prepare(captured.snapshot, 'extension-settings');
    const acknowledgement = await extensionSyncQueue.enqueue(captured.snapshot, {
        keepaliveOnly: Boolean(options.keepalive),
    });
    if (acknowledgement.deferred) return false;
    if (acknowledgement.skipped) {
        await acknowledgeStorage(captured.snapshot.committed, acknowledgement.response);
    }
    if (captured.scope === extensionSettingsScope()) {
        lastExtensionSettingsScope = captured.scope;
        lastExtensionSettingsSignature = captured.signature;
    }
    return true;
}

function flushExtensionSettingsPersist(options = {}) {
    window.clearTimeout(extensionSettingsPersistTimer);
    extensionSettingsPersistTimer = null;
    const waiters = extensionSettingsPersistWaiters;
    extensionSettingsPersistWaiters = [];
    if (!waiters.length && !options.force) {
        return extensionSettingsPersistChain;
    }
    // Capture now, not when a previous remote write eventually finishes. A
    // later cloud response must never capture the newly selected card instead.
    const captured = captureExtensionStorage(options);
    // The storage queue already orders transports. Do not defer even the local
    // prepare behind an older cloud request: it could land after a newer leave
    // snapshot and reintroduce the old settings as the newest revision.
    extensionSettingsPersistChain = persistExtensionSettingsSnapshot(options, captured);
    extensionSettingsPersistChain.then(
        value => waiters.forEach(waiter => waiter.resolve(value)),
        error => waiters.forEach(waiter => waiter.reject(error)),
    );
    return extensionSettingsPersistChain;
}

function saveConversationExtensionSettings() {
    if (extensionSettingsHydrating || extensionSettingsReplayInProgress) {
        return Promise.resolve(false);
    }
    if (!launch?.app_id || !launch?.conversation_id) {
        saveSettingsDebounced();
        return Promise.resolve(false);
    }
    // If a card helper changes settings during the short core-ready →
    // APP_READY overlap, the post-ready replay must use that newest state,
    // not the snapshot captured at launch. This keeps early interactivity and
    // conversation isolation compatible with extensions that save immediately.
    conversationExtensionSettings = cloneJsonObject(extension_settings);
    window.clearTimeout(extensionSettingsPersistTimer);
    const promise = new Promise((resolve, reject) => {
        extensionSettingsPersistWaiters.push({ resolve, reject });
    });
    // Card helpers commonly `await saveSettingsDebounced()` and immediately
    // refresh the parent page. The upstream debounce returns before its one-
    // second timer runs, so use a zero-delay coalescing queue whose promise only
    // resolves after the current conversation snapshot reaches Homer.
    extensionSettingsPersistTimer = window.setTimeout(() => {
        const replayScope = cloudSyncScope();
        extensionSettingsReplayWork = (async () => {
            // Card helpers can mutate the public extensionSettings object while
            // an extension still holds the previous value in module-local UI
            // state. Replay the standard load event before persisting so that
            // a later native debounce cannot write the stale value back over
            // the card's change.
            const intended = cloneJsonObject(conversationExtensionSettings || extension_settings);
            extensionSettingsReplayInProgress = true;
            try {
                if (replayScope !== cloudSyncScope()) return;
                replaceExtensionSettings(intended);
                await eventSource.emit(event_types.SETTINGS_LOADED);
                if (replayScope !== cloudSyncScope()) return;
                replaceExtensionSettings(intended);
                conversationExtensionSettings = cloneJsonObject(extension_settings);
            } finally {
                extensionSettingsReplayInProgress = false;
            }
            // This chain tracks local settings reconciliation only. Remote
            // persistence remains separately awaitable by extension callers.
            void flushExtensionSettingsPersist().catch(() => {
                console.warn(`${MODULE_ID}: extension settings save remains pending`);
            });
        })().catch(error => {
            console.warn(`${MODULE_ID}: extension settings reconciliation failed`, error);
            void flushExtensionSettingsPersist().catch(() => {});
        });
    }, 0);
    return promise;
}

function installExtensionSettingsPersistenceBridge() {
    if (extensionSettingsBridgeInstalled) {
        return;
    }
    const compatibilityApiName = ['Silly', 'Tavern'].join('');
    const compatibilityApi = globalThis[compatibilityApiName];
    if (!compatibilityApi || typeof compatibilityApi.getContext !== 'function') {
        return;
    }
    const nativeGetContext = compatibilityApi.getContext.bind(compatibilityApi);
    compatibilityApi.getContext = () => ({
        ...nativeGetContext(),
        saveSettingsDebounced: saveConversationExtensionSettings,
    });
    Object.defineProperties(compatibilityApi, {
        extensionSettings: {
            configurable: true,
            get: () => extension_settings,
        },
        extension_settings: {
            configurable: true,
            get: () => extension_settings,
        },
        saveSettingsDebounced: {
            configurable: true,
            value: saveConversationExtensionSettings,
        },
    });
    extensionSettingsBridgeInstalled = true;
}

function installEmbeddedDocumentLookupBridge() {
    if (embeddedDocumentLookupBridgeInstalled || requestedEmbed !== '1') {
        return;
    }
    let hostDocument = null;
    try {
        hostDocument = window.top !== window ? window.top.document : null;
    } catch {
        hostDocument = null;
    }
    if (!hostDocument || hostDocument === document) {
        return;
    }

    const nativeGetElementById = document.getElementById.bind(document);
    const nativeQuerySelector = document.querySelector.bind(document);
    const nativeQuerySelectorAll = document.querySelectorAll.bind(document);
    // In an ordinary top-level dialogue runtime, a card-script iframe sees the
    // same document through both window.parent and window.top. Homer's neutral
    // website shell adds one same-origin frame, so a script may mount a dialog
    // in top.document and then look it up through parent.document. Fall back to
    // the host only when the runtime document has no match, preserving normal
    // local selectors while restoring the upstream browsing-context contract.
    Object.defineProperties(document, {
        getElementById: {
            configurable: true,
            value: id => nativeGetElementById(id) || hostDocument.getElementById(id),
        },
        querySelector: {
            configurable: true,
            value: selector => nativeQuerySelector(selector) || hostDocument.querySelector(selector),
        },
        querySelectorAll: {
            configurable: true,
            value: selector => {
                const local = nativeQuerySelectorAll(selector);
                return local.length ? local : hostDocument.querySelectorAll(selector);
            },
        },
    });
    embeddedDocumentLookupBridgeInstalled = true;
}

function conversationModelSettings() {
    const saved = runtimeVariables.homer_model_settings;
    const raw = saved && typeof saved === 'object' ? saved : {};
    return {
        model_id: selectRuntimeModelId(runtimeVariables, runtimeUiData.models, runtimeUiData.modelDefaultId),
        temperature: clampNumber(raw.temperature, 0, 2, DEFAULT_MODEL_SETTINGS.temperature),
        top_p: clampNumber(raw.top_p, 0, 1, DEFAULT_MODEL_SETTINGS.top_p),
        frequency_penalty: clampNumber(
            raw.frequency_penalty,
            -2,
            2,
            DEFAULT_MODEL_SETTINGS.frequency_penalty,
        ),
        presence_penalty: clampNumber(
            raw.presence_penalty,
            -2,
            2,
            DEFAULT_MODEL_SETTINGS.presence_penalty,
        ),
    };
}

function selectRuntimeModelId(variables, models, defaultId = '') {
    const requested = String(variables?.homer_model_settings?.model_id || '').trim();
    return models.some(item => String(item?.id || '') === requested) ? requested
        : String(defaultId || models.find(item => item?.is_default)?.id || models[0]?.id || '');
}

function selectedModel() {
    const modelId = conversationModelSettings().model_id;
    return runtimeUiData.models.find(item => String(item?.id || '') === modelId) || null;
}

function safeSiteOrigin() {
    if (!requestedSiteOrigin) {
        return '';
    }
    try {
        const url = new URL(requestedSiteOrigin);
        if (!['http:', 'https:'].includes(url.protocol)) {
            return '';
        }
        return url.origin === window.location.origin ? url.origin : '';
    } catch {
        return '';
    }
}

function canNotifyHost() {
    return requestedEmbed === '1'
        && requestedHostChannel === HOST_CHANNEL
        && safeSiteOrigin() === window.location.origin
        && window.parent !== window;
}

function notifyHost(type, payload = {}) {
    if (type === 'navigate') {
        setDrawerOpen();
        setPanelOpen(false);
    }
    if (!canNotifyHost()) {
        return;
    }
    window.parent.postMessage({
        channel: HOST_CHANNEL,
        version: 1,
        type,
        ...payload,
    }, window.location.origin);
}

const HOST_OVERLAY_SELECTOR = 'dialog,[role="dialog"][aria-modal="true"],.popup,#homerCardExperienceRoot';
const HOST_ANCHORED_OVERLAY_SELECTOR = '#homer-message-menu-dialog,#homer-preset-panel';
function fullRuntimeOverlayOpen(element) {
    if (element.matches('#homerCardExperienceRoot')) return element.getAttribute('data-homer-overlay-active') === 'true';
    if (element.matches(HOST_ANCHORED_OVERLAY_SELECTOR)) return false;
    if (element instanceof HTMLDialogElement) return element.open;
    return !element.hidden && !element.closest('[hidden],[aria-hidden="true"]')
        && element.getAttribute('data-state') !== 'closed'
        && element.style.display !== 'none' && element.style.visibility !== 'hidden'
        && !element.classList.contains('hidden') && !element.classList.contains('is-hidden');
}

function syncHostOverlayState() {
    hostOverlayActive = Boolean(messageSelection)
        || [...document.querySelectorAll(HOST_OVERLAY_SELECTOR)].some(fullRuntimeOverlayOpen);
    if (!canNotifyHost() || !launch?.conversation_id) return;
    const payload = {
        active: hostOverlayActive,
        admin_preview: Boolean(launch.admin_preview),
        app_id: String(launch.app_id || '').slice(0, 160),
        conversation_id: String(launch.conversation_id || '').slice(0, 160),
    };
    const signature = JSON.stringify(payload);
    if (signature === hostOverlaySignature) return;
    hostOverlaySignature = signature;
    notifyHost('overlay-state', payload);
}

function installHostOverlayTracking() {
    if (hostOverlayObserver) return;
    const isOverlayNode = node => node instanceof Element && (
        node.matches(HOST_OVERLAY_SELECTOR + ',#homer-message-selection')
        || Boolean(node.querySelector(HOST_OVERLAY_SELECTOR + ',#homer-message-selection')));
    hostOverlayObserver = new MutationObserver(records => {
        const relevant = records.some(record => record.type === 'attributes'
            ? record.target instanceof Element && record.target.matches(HOST_OVERLAY_SELECTOR)
                && !record.target.matches(HOST_ANCHORED_OVERLAY_SELECTOR)
            : [...record.addedNodes, ...record.removedNodes].some(isOverlayNode));
        if (!relevant || hostOverlaySyncQueued) return;
        hostOverlaySyncQueued = true;
        queueMicrotask(() => { hostOverlaySyncQueued = false; syncHostOverlayState(); });
    });
    hostOverlayObserver.observe(document.body, {
        subtree: true, childList: true, attributes: true,
        attributeFilter: ['open', 'hidden', 'aria-hidden', 'data-state', 'class', 'style', 'data-homer-overlay-active'],
    });
    document.addEventListener('close', event => {
        if (event.target instanceof Element && event.target.matches(HOST_OVERLAY_SELECTOR)
            && !event.target.matches(HOST_ANCHORED_OVERLAY_SELECTOR)) syncHostOverlayState();
    }, true);
    syncHostOverlayState();
}

function currentRoleName() {
    return String(
        launch?.card?.data?.name
        || launch?.card?.name
        || launch?.conversation?.app_name
        || '角色对话',
    ).trim().slice(0, 120);
}

function normalizeBootstrapToken(value) {
    return typeof value === 'string' && /^[A-Za-z0-9._:-]{1,80}$/.test(value) ? value : '';
}

function notifyHostConversation(type = 'ready', transition = {}) {
    restoreScopeDraft();
    const idleDisplay = type === 'ready' && requestedIdleHostDisplay && canNotifyHost()
        && !launch?.admin_preview && !conversationRecoveryBlocked && hasCanonicalConversationScope();
    if (idleDisplay) syncHostOverlayState();
    const controlState = idleDisplay ? hostControlState() : null;
    const payload = {
        admin_preview: Boolean(launch?.admin_preview),
        app_id: String(launch?.app_id || '').slice(0, 160),
        conversation_id: String(launch?.conversation_id || '').slice(0, 160),
        role_name: currentRoleName(),
        ...transition,
    };
    notifyHost('title', payload);
    notifyHost('conversation', payload);
    // Schedule the fresh state before acknowledging it to capable hosts.
    // Older hosts may still request state explicitly through the same channel.
    scheduleHostStateNotify(0, type, { idleDisplay });
    if (type === 'ready') {
        notifyHost('ready', { ...payload, state_scheduled: true,
            ...(controlState ? { control_state: controlState } : {}) });
    } else notifyHost(type, type === 'conversation-switch-failed'
        ? { ...payload, state_scheduled: true } : payload);
}

function notifyHostLoading(message) {
    notifyHost('loading', {
        message: String(message || '正在准备对话…').trim().slice(0, 160),
    });
}

function notifyHostError(bootstrapToken = '') {
    notifyHost('error', {
        code: 'DIALOGUE_START_FAILED',
        message: '对话准备失败，请重试。',
        ...(normalizeBootstrapToken(bootstrapToken) ? { bootstrap_token: bootstrapToken } : {}),
    });
}

function canonicalDisplayTexts() {
    const result = new Map();
    for (const row of document.querySelectorAll('#chat .mes[mesid]')) {
        const index = Number(row.getAttribute('mesid'));
        const content = row.querySelector('.mes_text');
        // Interactive cards retain their live runtime. Never persist source
        // HTML, script code, hidden controls, or an iframe's document as text.
        if (!Number.isSafeInteger(index) || index < 0 || !content || content.querySelector('iframe,object,embed,canvas,video,audio')) continue;
        const walker = document.createTreeWalker(content, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
            acceptNode(node) {
                if (node.nodeType === Node.ELEMENT_NODE && (
                    node.matches('script,style,template,noscript,button,input,textarea,select,[hidden],[aria-hidden="true"],.homer-message-actions,.tav-action-bar')
                    || node.style.display === 'none' || node.style.visibility === 'hidden')) return NodeFilter.FILTER_REJECT;
                return NodeFilter.FILTER_ACCEPT;
            },
        });
        let value = '', node;
        while ((node = walker.nextNode())) {
            if (node.nodeType === Node.TEXT_NODE) value += node.textContent;
            else if (node.matches('br,p,div,li,blockquote,pre,h1,h2,h3,h4,h5,h6') && value && !value.endsWith('\n')) value += '\n';
            if (value.length >= 60_000) break;
        }
        result.set(index, value.slice(0, 60_000).trim());
    }
    return result;
}

function hostMessageSnapshot(message, index, displayTexts) {
    const swipes = Array.isArray(message?.swipes) ? message.swipes.map(item => String(item)) : [];
    const swipeIndex = Math.max(0, Math.min(Number(message?.swipe_id || 0), Math.max(0, swipes.length - 1)));
    const content = String(swipes.length ? swipes[swipeIndex] : message?.mes || '').slice(0, 60_000);
    const rawCreatedAt = message?.extra?.homer_created_at || message?.send_date || 0;
    const parsedCreatedAt = typeof rawCreatedAt === 'number'
        ? rawCreatedAt
        : Date.parse(String(rawCreatedAt || ''));
    return {
        id: String(
            message?.extra?.homer_message_id
            || message?.extra?.homer_sync_id
            || `${launch?.conversation_id || 'conversation'}-${index}`,
        ).slice(0, 180),
        role: message?.is_user ? 'user' : 'assistant',
        content,
        ...(displayTexts?.has(index) ? { display_text: displayTexts.get(index) } : {}),
        hidden: Boolean(message?.extra?.homer_hidden),
        collapsed: Boolean(message?.extra?.homer_collapsed),
        created_at: Number.isFinite(parsedCreatedAt) ? parsedCreatedAt : 0,
        // This is a display notification; complete swipes stay in serializeChat.
        swipe_index: swipeIndex,
    };
}

function hostConversationSnapshot(conversation) {
    return {
        id: String(conversation?.id || conversation?.conversation_id || '').slice(0, 160),
        app_id: String(conversation?.app_id || '').slice(0, 160),
        title: String(conversation?.title || conversation?.app_name || '角色对话').slice(0, 120),
        app_name: String(conversation?.app_name || conversation?.title || '角色对话').slice(0, 120),
        app_icon: String(conversation?.app_icon || '').slice(0, 2_000),
        last_message: String(conversation?.last_message || '').slice(0, 240),
        updated_at: Number(conversation?.updated_at || 0),
        pinned: Boolean(conversation?.pinned),
    };
}

function hostControlState() {
    const conversation = currentConversationRecord() || launch?.conversation || {};
    return {
        admin_preview: Boolean(launch?.admin_preview),
        app_id: String(launch?.app_id || '').slice(0, 160),
        conversation_id: String(launch?.conversation_id || '').slice(0, 160),
        title: currentRoleName(),
        avatar: String(launch?.conversation?.app_icon || '').slice(0, 2_000),
        conversation: hostConversationSnapshot(conversation),
        conversations: runtimeUiData.conversations.slice(0, 100).map(hostConversationSnapshot),
        models: runtimeUiData.models.map(publicModel),
        model_default_id: String(runtimeUiData.modelDefaultId || '').slice(0, 160),
        model_settings: { ...conversationModelSettings() },
        generating: Boolean(generationBusy || rollbackBusy),
        overlay_active: hostOverlayActive,
        draft: String(document.querySelector('#send_textarea')?.value || '').slice(0, 10_000),
    };
}

function cancelHostStateNotify(timer = hostStateNotifyTimer, token = hostStateNotifyToken) {
    if (timer === null) return;
    if (token?.idle) window.cancelIdleCallback(timer);
    else window.clearTimeout(timer);
}

function notifyHostState(reason = 'update') {
    const pendingTimer = hostStateNotifyTimer;
    const pendingToken = hostStateNotifyToken;
    tavoComposer?.refresh();
    if (!canNotifyHost() || !launch?.conversation_id) return;
    if (conversationRecoveryBlocked || !hasCanonicalConversationScope()) return;
    syncHostOverlayState();
    const context = getContext();
    const chat = Array.isArray(context?.chat) ? context.chat : [];
    const displayTexts = generationBusy || rollbackBusy || isGenerating() ? null : canonicalDisplayTexts();
    notifyHost('state', {
        reason: String(reason || 'update').slice(0, 40),
        state: {
            ...hostControlState(),
            messages: chat
                .map((message, index) => ({ message, index }))
                .filter(({ message }) => !message?.is_system || message?.extra?.homer_hidden)
                .slice(-120)
                .map(({ message, index }) => hostMessageSnapshot(message, index, displayTexts)),
        },
    });
    // A successful immediate reply also satisfies the old scheduled snapshot.
    // Capture before refresh/posting: reentrant edits may schedule newer work.
    // Keep the original timer on an ineligible reply or a thrown snapshot.
    if (pendingTimer !== null && hostStateNotifyTimer === pendingTimer && hostStateNotifyToken === pendingToken) {
        cancelHostStateNotify(pendingTimer, pendingToken);
        hostStateNotifyTimer = null;
        hostStateNotifyToken = null;
    }
}

function scheduleHostStateNotify(delay = 80, reason = 'update', { idleDisplay = false } = {}) {
    if (!canNotifyHost()) return;
    idleDisplay = idleDisplay === true && reason === 'ready' && requestedIdleHostDisplay
        && !launch?.admin_preview && !conversationRecoveryBlocked && hasCanonicalConversationScope();
    // Launch/switch completion promises one fresh state with its final ready
    // (or restored-failure) ACK. Do not read all message DOM during the adapter
    // await just to repeat that optional display snapshot at the final ACK.
    if (reason === 'chat-loaded' && loadingLaunch) return;
    cancelHostStateNotify();
    const token = {};
    if (idleDisplay) {
        // Keep only correlation identity, never message/DOM snapshots. The
        // optional read uses the current live DOM only after this fence holds.
        token.owner = reconcileStorageAccount();
        token.epoch = storageAccountEpoch;
        token.launch = launch;
        token.appId = String(launch?.app_id || '');
        token.conversationId = String(launch?.conversation_id || '');
        token.engineToken = hostBootstrapEngineToken;
        token.documentToken = hostBootstrapDocumentToken;
        token.idle = typeof window.requestIdleCallback === 'function'
            && typeof window.cancelIdleCallback === 'function';
    }
    hostStateNotifyToken = token;
    const callback = () => {
        if (hostStateNotifyToken !== token) return;
        hostStateNotifyTimer = null;
        hostStateNotifyToken = null;
        if (idleDisplay && (!token.owner || reconcileStorageAccount() !== token.owner
            || storageAccountEpoch !== token.epoch || launch !== token.launch
            || String(launch?.app_id || '') !== token.appId || String(launch?.conversation_id || '') !== token.conversationId
            || launch?.admin_preview
            || hostBootstrapEngineToken !== token.engineToken || hostBootstrapDocumentToken !== token.documentToken
            || (token.engineToken && document.documentElement?.dataset.homerBootstrapDocument !== token.documentToken))) return;
        notifyHostState(reason);
    };
    hostStateNotifyTimer = token.idle
        ? window.requestIdleCallback(callback, { timeout: 500 })
        : window.setTimeout(callback, idleDisplay ? 32 : Math.max(0, Number(delay) || 0));
}

function openHostRequestedSettings(section) {
    const target = String(section || 'drawer');
    if (target === 'drawer') {
        setDrawerOpen('right');
        return;
    }
    returnToDesktopNavigation();
    if (target === 'new-chat') {
        document.querySelector('#homer-new-chat-dialog')?.showModal();
        return;
    }
    if (target === 'attachments') {
        document.querySelector('#homer-attachment-dialog')?.showModal();
        return;
    }
    if (target === 'generation') {
        document.querySelector('#homer-generation-dialog')?.showModal();
        return;
    }
    if (target === 'model') {
        document.querySelector('#homer-model-dialog')?.showModal();
        return;
    }
    if (target === 'preset') {
        setPanelOpen(true);
        return;
    }
    if (target === 'memory') {
        openMemoryBooks();
        return;
    }
    if (target === 'mod') {
        document.querySelector('#homer-mod-dialog')?.showModal();
    }
}

async function receiveHostCommand(event) {
    if (!canNotifyHost() || event.origin !== window.location.origin || event.source !== window.parent) {
        return;
    }
    const message = event.data;
    if (!message || message.channel !== HOST_CHANNEL || message.version !== 1) {
        return;
    }
    if (message.type === 'prepare-conversation') {
        prepareColdConversation(message);
        return;
    }
    if (message.type === 'prepare-history-conversations') {
        prepareColdHistoryConversations(message);
        return;
    }
    if (['prepare-admin-preview', 'bind-admin-preview'].includes(message.type)) {
        const appId = String(message.app_id || '').trim().slice(0, 160);
        if (!appId) return;
        if (message.type === 'prepare-admin-preview') { prepareAdminLaunch(appId); return; }
        if (!coreAvailable || adminBinding || loadingLaunch || isGenerating() || generationBusy || rollbackBusy) {
            notifyHost('command-error', { message: '请先停止当前生成，再切换角色' }); return;
        }
        adminBinding = true;
        performance.mark('homer-admin-bind-start');
        try {
            // This is a request for a mode, not an authorization. Fetch the
            // signed preview from the server before changing any live scope.
            const next = await prepareAdminLaunch(appId);
            performance.mark('homer-admin-bind-authorized');
            preparedAdminLaunch = null;
            if (isGenerating() || generationBusy || rollbackBusy) throw new Error('请先停止当前生成，再切换角色');
            notifyHost('conversation-switching', {
                admin_preview: true,
                app_id: String(next?.launch?.app_id || appId),
                conversation_id: String(next?.launch?.conversation_id || ''),
                from_app_id: String(launch?.app_id || ''),
                from_conversation_id: String(launch?.conversation_id || ''),
                role_name: String(next?.launch?.card?.data?.name || next?.launch?.card?.name || '角色对话'),
            });
            await flushExtensionSettingsPersist();
            await syncCloudChat();
            performance.mark('homer-admin-bind-flushed');
            retainScopeDraft();
            window.clearTimeout(syncTimer);
            window.clearTimeout(sessionPrefetchTimer);
            sessionPrefetchCache.clear();
            sessionPrefetchPeer = null;
            requestedAppId = appId; requestedConversationId = '';
            adminConversationDraft = {}; adminConversationConfig = null; runtimeVariables = {};
            lastGenerationDiagnostic = null; generationSnapshot = null;
            if (!bridgeStartScheduled) {
                bridgeStartScheduled = true;
                launchSessionPreloadPromise = Promise.resolve(next);
                await startHomerBridge();
            } else {
                await bootstrapLaunch(next, prewarmBootstrapPromise || ensureAdministratorExtensions());
            }
        } finally { adminBinding = false; }
        return;
    }
    if (message.type === 'bind-conversation' && prewarmOnly && !bridgeStartScheduled) {
        const appId = String(message.app_id || '').trim().slice(0, 160);
        const conversationId = String(message.conversation_id || '').trim().slice(0, 160);
        if (!appId || !conversationId) return;
        performance.mark('homer-bind-received');
        requestedAppId = appId;
        requestedConversationId = conversationId;
        boundBootstrapToken = normalizeBootstrapToken(message.bootstrap_token);
        if (coreAvailable) {
            bridgeStartScheduled = true;
            void startHomerBridge();
        }
        return;
    }
    if (message.type === 'request-state') {
        notifyHostState('requested');
        return;
    }
    if (message.type === 'open-settings') {
        openHostRequestedSettings(message.section);
        return;
    }
    if(message.type==='memory-selection'){
        const ctx=getContext(),ids=Array.isArray(message.ids)?message.ids:[];
        const indices=ids.map(id=>ctx.chat.findIndex(m=>stableHomerMessageId(m)===id||cloudHomerMessageId(m)===id));
        if(indices.some(i=>i<0)){showHostNotice('所选消息尚未同步，请重新选择范围','warning');return;}
        openMemoryEngineSettings(indices);return;
    }
    if (message.type === 'model-settings') {
        await persistModelSettings(message.settings || {});
        buildRuntimeUi();
        notifyHostState('model-settings');
        return;
    }
    if (message.type === 'switch-conversation') {
        await switchConversation({
            id: String(message.conversation_id || ''),
            app_id: String(message.app_id || ''),
        }, normalizeBootstrapToken(message.bootstrap_token));
        return;
    }
    if (message.type === 'message-action') {
        assertCanonicalConversationScope();
        const context = getContext();
        const messageId = String(message.message_id || '');
        const index = context.chat.findIndex(item => stableHomerMessageId(item) === messageId
            || cloudHomerMessageId(item) === messageId);
        const target = index >= 0 ? messageMenuTargetForIndex(index) : null;
        if (target) await handleMessageMenuAction(String(message.action || ''), target);
        else showHostNotice('消息尚未同步完成，请稍后重新长按操作', 'warning');
        return;
    }
    if (message.type === 'host-insets') {
        setTavoHostInsets({ top: message.top, bottom: message.bottom });
        return;
    }
    if (message.type === 'refresh-appearance') {
        chatAppearance?.refresh();
        refreshTavoUi();
        return;
    }
    if (message.type === 'stop') {
        getContext().stopGeneration();
        scheduleHostStateNotify(0, 'stop-requested');
        return;
    }
    if (message.type === 'composer-text') {
        setComposerDraft(String(message.content || ''));
        tavoComposer?.refresh();
        return;
    }
    if (message.type !== 'draft') return;
    const content = String(message.content || '').slice(0, 10_000);
    if (!content) return;
    const composer = document.querySelector('#send_textarea');
    if (!(composer instanceof HTMLTextAreaElement)) return;
    composer.value = content;
    composer.dispatchEvent(new Event('input', { bubbles: true }));
    if (message.submit === true) {
        requestAnimationFrame(() => {
            if (conversationRecoveryBlocked || loadingLaunch || !hasCanonicalConversationScope()) return;
            const sendButton = document.querySelector('#send_but');
            if (sendButton instanceof HTMLElement && !sendButton.matches(':disabled')) {
                sendButton.click();
            }
        });
    }
}

window.addEventListener('message', event => {
    void receiveHostCommand(event).catch(error => {
        console.warn(`${MODULE_ID}: host command failed`, error);
        notifyHost('command-error', { message: String(error?.message || '操作失败').slice(0, 200) });
    });
});

const TECHNICAL_NOTICE_PATTERN = /(?:\bMVU\b|\bSillyTavern\b|\bTavern Helper\b|脚本加载|扩展加载|插件加载|构建信息|build\s*(?:info|version)|extension\s+(?:loaded|installed))/i;

function normalizeHostNotice(message) {
    const value = String(message || '').replace(/\s+/g, ' ').trim();
    if (!value || TECHNICAL_NOTICE_PATTERN.test(value)) {
        return '';
    }
    return value.slice(0, 240);
}

function showHostNotice(message, level = 'info') {
    const text = normalizeHostNotice(message);
    if (!text || requestedEmbed !== '1') {
        return;
    }
    const root = document.querySelector('#homer-runtime-root');
    if (!root) {
        pendingHostNotices.push({ text, level });
        if (pendingHostNotices.length > 4) {
            pendingHostNotices.shift();
        }
        return;
    }
    let stack = root.querySelector('#homer-notice-stack');
    if (!stack) {
        stack = createElement('div', 'homer-notice-stack');
        stack.id = 'homer-notice-stack';
        stack.setAttribute('aria-live', 'polite');
        stack.setAttribute('aria-atomic', 'false');
        root.append(stack);
    }
    stack.replaceChildren();
    const notice = createElement('div', 'homer-notice', text);
    notice.dataset.level = ['success', 'warning', 'error'].includes(level) ? level : 'info';
    stack.append(notice);
    window.setTimeout(() => notice.remove(), 4200);
}

function flushHostNotices() {
    const notices = pendingHostNotices.splice(0);
    for (const notice of notices) {
        showHostNotice(notice.text, notice.level);
    }
}

function mirrorUpstreamToast(toast) {
    if (!(toast instanceof HTMLElement) || toast.dataset.homerNoticeHandled === '1') {
        return;
    }
    toast.dataset.homerNoticeHandled = '1';
    const title = String(toast.querySelector('.toast-title')?.textContent || '').trim();
    const message = String(toast.querySelector('.toast-message')?.textContent || toast.textContent || '').trim();
    const text = [title, message].filter(Boolean).join('：');
    const level = toast.classList.contains('toast-error')
        ? 'error'
        : toast.classList.contains('toast-warning')
            ? 'warning'
            : toast.classList.contains('toast-success')
                ? 'success'
                : 'info';
    showHostNotice(text, level);
}

function installProductSurfaceBoundary() {
    if (productSurfaceBoundaryInstalled || requestedEmbed !== '1') {
        return;
    }
    productSurfaceBoundaryInstalled = true;
    document.documentElement.classList.add('homer-embedded-runtime', 'homer-runtime-pending');

    const parking = createElement('div', 'homer-internal-parking');
    parking.id = 'homer-internal-parking';
    parking.hidden = true;
    parking.inert = true;
    parking.setAttribute('aria-hidden', 'true');
    document.body.append(parking);
    for (const selector of ['#top-bar', '#top-settings-holder']) {
        const panel = document.querySelector(selector);
        if (panel) {
            parking.append(panel);
        }
    }

    upstreamNoticeObserver = new MutationObserver(records => {
        for (const record of records) {
            for (const node of record.addedNodes) {
                if (!(node instanceof Element)) {
                    continue;
                }
                if (node.matches('.toast')) {
                    window.queueMicrotask(() => mirrorUpstreamToast(node));
                }
                node.querySelectorAll?.('.toast').forEach(toast => {
                    window.queueMicrotask(() => mirrorUpstreamToast(toast));
                });
            }
        }
    });
    upstreamNoticeObserver.observe(document.documentElement, { childList: true, subtree: true });
}

function siteUrl(pathname) {
    const origin = safeSiteOrigin();
    return origin ? new URL(pathname, `${origin}/`).href : pathname;
}

function siteAssetUrl(rawUrl) {
    const value = String(rawUrl || '').trim();
    if (!value) {
        return '';
    }
    try {
        const origin = safeSiteOrigin();
        const url = new URL(value, origin ? `${origin}/` : window.location.href);
        return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch {
        return '';
    }
}

function proxyExtensionAssetUrl(rawUrl) {
    const value = String(rawUrl || '').trim();
    if (!value) {
        return '';
    }
    try {
        const parsed = new URL(value, safeSiteOrigin() || window.location.origin);
        const marker = '/console/api/web/dialogue/extensions/';
        const markerIndex = parsed.pathname.indexOf(marker);
        if (markerIndex < 0) {
            return value;
        }
        const suffix = parsed.pathname.slice(markerIndex + marker.length);
        return `/api/homer/extensions/${suffix}`;
    } catch {
        return value;
    }
}

async function loadAdministratorExtensions() {
    const registry = await requestJson('/api/homer/extensions');
    const list = (Array.isArray(registry) ? registry : registry?.list || []).map(item => ({
        ...item,
        js_url: proxyExtensionAssetUrl(item?.js_url),
        css_url: proxyExtensionAssetUrl(item?.css_url),
    }));
    return loadApprovedExtensions(list);
}

function administratorExtensionFailure(error) {
    console.warn(`${MODULE_ID}: administrator extensions failed`, error);
    window.__homerDialogueExtensions = {
        result: {
            loaded: [],
            skipped: [],
            failed: [{ id: 'registry', reason: String(error?.message || error) }],
        },
        list: [],
    };
    return window.__homerDialogueExtensions;
}

function ensureAdministratorExtensions() {
    if (!administratorExtensionsPromise) {
        administratorExtensionsPromise = loadAdministratorExtensions().catch(administratorExtensionFailure);
    }
    return administratorExtensionsPromise;
}

function beginSharedPrewarm() {
    if (!prewarmOnly || prewarmBootstrapPromise) {
        return prewarmBootstrapPromise;
    }
    performance.mark('homer-prewarm-start');
    preloadStaticDialogueUi();
    // Activate the fixed empty presentation in this host-owned document, not
    // merely its downloaded bytes. The ordinary installer shares this promise;
    // neither core-ready nor extension readiness waits for this optional work.
    // Do not mount the conversation composer or construct account/card UI here.
    if (canNotifyHost() && hostBootstrapEngineToken && !requestedAppId && !launch && !bridgeStartScheduled) {
        void prepareTavoConversationUi().catch(() => {});
    }
    // The established approved-extension registry is independent of the empty
    // presentation. No launch, card, world book or cloud messages are requested.
    prewarmBootstrapPromise = ensureAdministratorExtensions().then(result => {
        performance.mark('homer-prewarm-shared-ready');
        return result;
    });
    return prewarmBootstrapPromise;
}

async function preferLocalSession(payload, appId, conversationId, fence) {
    const userId = String(payload?.user?.id || payload?.user?.user_id || '');
    if (!payload?.launch || !userId || userId !== reconcileStorageAccount()) throw new Error('会话账号已切换，请重新进入');
    const epoch = storageAccountEpoch;
    const scope = JSON.stringify([userId, String(payload.launch.app_id), String(payload.launch.conversation_id)]);
    if (appId && String(payload.launch.app_id) !== String(appId)) throw new Error('会话角色信息不一致');
    if (conversationId && String(payload.launch.conversation_id) !== String(conversationId)) throw new Error('会话存档信息不一致');
    acknowledgedPromptTickets.delete(payload.launch);
    const ticket = sessionReadFences.get(payload);
    const local = await chatOutbox.read(scope, 'chat', fence);
    if (userId !== reconcileStorageAccount() || epoch !== storageAccountEpoch) throw new Error('会话账号已切换，请重新进入');
    if (!local && ticket && (ticket.stamp !== storageAckStamps.get(storageAckKey(scope))
        || ticket.version !== ticket.stamp?.version)) {
        // A very large acknowledged row may have been evicted by the byte
        // budget during this GET. Refetch instead of accepting its older body.
        const error = new Error('云端存档已更新，正在重新读取');
        error.code = 'HOMER_STALE_STORAGE_READ';
        throw error;
    }
    if (!local?.preferred) {
        // Fresh cloud messages/order remain authoritative. Retain only a
        // versioned, fully ACKed per-swipe Prompt Template tuple whose exact
        // canonical source also matches both that ACK and the fresh response.
        if (local && !local.pending && local.kind === 'chat' && local.owner === userId && local.scope === scope
            && Number.isSafeInteger(local.revision) && local.revision > 0 && local.ackRevision === local.revision
            && local.payload?.app_id === String(payload.launch.app_id)
            && local.payload?.conversation_id === String(payload.launch.conversation_id)) {
            const states = prepareAcknowledgedPromptStates(payload.launch.messages, local.payload.messages, local.ackPayload?.messages);
            if (states.some(Boolean)) acknowledgedPromptTickets.set(payload.launch, { owner: userId, epoch, scope, states });
        }
        return payload;
    }
    const messages = cloneJsonValue(local.payload.messages);
    if (local.ackRevision === local.revision && Array.isArray(local.ackPayload?.messages)) {
        local.ackPayload.messages.forEach((saved, index) => {
            if (!messages[index]) return;
            messages[index].extra = { ...(messages[index].extra || {}),
                homer_message_id: String(saved.id || ''), homer_sync_id: String(saved.id || messages[index].extra?.homer_sync_id || ''),
                homer_created_at: Number(saved.created_at || messages[index].extra?.homer_created_at || Date.now()),
            };
        });
    }
    // Retain complete canonical messages (including hidden/swipe/extension
    // metadata), not the clipped plain-text first-screen preview.
    payload.launch.local_chat = messages;
    payload.launch.local_pending = local.pending;
    payload.launch.messages = messages.map(message => ({
        id: String(message.extra?.homer_message_id || message.extra?.homer_sync_id || ''),
        role: message.is_system && !message.extra?.homer_hidden ? 'system' : message.is_user ? 'user' : 'assistant',
        content: String(message.mes || ''), created_at: Number(message.extra?.homer_created_at || Date.now()),
        swipes: message.swipes || [], swipe_index: Number(message.swipe_id || 0),
    }));
    return payload;
}

async function fetchSession(appId = '', conversationId = '', adminPreview = false, storageRetry = 0, { deferLocalMerge = false } = {}) {
    const owner = reconcileStorageAccount();
    const requestEpoch = storageAccountEpoch;
    if (adminPreview) {
        const preview = await requestJson(`/api/homer/admin-preview?app_id=${encodeURIComponent(appId)}`);
        if (!preview?.user?.is_admin || !preview?.launch?.admin_preview || !preview.launch.bridge_token) throw new Error('管理员试聊不可用，请检查服务端版本与权限');
        acceptVerifiedSessionOwner(preview, owner, requestEpoch);
        return preview;
    }
    const params = new URLSearchParams();
    if (appId) {
        params.set('app_id', appId);
    }
    if (conversationId) {
        params.set('conversation_id', conversationId);
    }
    // `URLSearchParams.prototype.size` only exists from Chrome 113. Android
    // WebView lags well behind that (the API 33 system image ships 109), and on
    // those builds `params.size` is undefined, so the query string was silently
    // dropped: the backend then answered without a `launch` payload and the app
    // died on "没有可启动的角色会话". Deriving the suffix from the serialized
    // string works on every engine.
    const query = params.toString();
    const suffix = query ? `?${query}` : '';
    const readScope = owner && appId && conversationId ? JSON.stringify([owner, String(appId), String(conversationId)]) : '';
    const stamp = readScope ? storageAckStamp(readScope) : null;
    const version = stamp?.version;
    const fence = owner && appId && conversationId
        ? await chatOutbox.fence(JSON.stringify([owner, String(appId), String(conversationId)])) : null;
    let embedded;
    try {
        embedded = await requestSessionCard(`/api/homer/session${suffix}`, {
            owner, appId, conversationId, request: requestJson,
            validate: payload => acceptVerifiedSessionOwner(payload, owner, requestEpoch),
            isCurrent: () => storageAccountEpoch === requestEpoch
                && (!owner || reconcileStorageAccount() === owner),
        });
    } catch (error) {
        // 嵌入式端点失败是预期路径之一，下面还有站点侧回退，这里只记日志。
        console.debug(`${MODULE_ID}: embedded session endpoint unavailable, falling back`, error);
    }
    const finalize = async payload => {
        acceptVerifiedSessionOwner(payload, owner, requestEpoch);
        if (appId && String(payload?.launch?.app_id) !== String(appId)) throw new Error('会话角色信息不一致');
        if (conversationId && String(payload?.launch?.conversation_id) !== String(conversationId)) throw new Error('会话存档信息不一致');
        const payloadScope = JSON.stringify([String(payload?.user?.id || payload?.user?.user_id || ''), String(payload?.launch?.app_id), String(payload?.launch?.conversation_id)]);
        const payloadStamp = stamp || storageAckStamp(payloadScope);
        sessionReadFences.set(payload, { fence, stamp: payloadStamp, version: stamp ? version : payloadStamp.version,
            raw: deferLocalMerge === true, owner: reconcileStorageAccount(), epoch: storageAccountEpoch, scope: payloadScope });
        // Read-only peer preparation retains the unprojected cloud response.
        // Its original GET fence is checked against a fresh local read once at
        // consumption, not by parsing/merging the same large row twice.
        if (deferLocalMerge === true) return payload;
        try { return await preferLocalSession(payload, appId, conversationId, fence); }
        catch (error) {
            if (error.code === 'HOMER_STALE_STORAGE_READ' && storageRetry < 1) return fetchSession(appId, conversationId, false, storageRetry + 1);
            throw error;
        }
    };
    if (embedded?.launch?.card && embedded.launch.bridge_token) return finalize(embedded);
    // Only use the site fallback when the embedded endpoint really failed or
    // omitted its launch. Never fetch a second complete large card on success.
    const fallback = await requestJson(`/console/api/web/dialogue/session${suffix}`);
    if (!fallback?.launch?.card || !fallback.launch.bridge_token) throw new Error('会话数据不完整，请重试连接');
    return finalize(fallback);
}

function sessionCacheKey(appId = '', conversationId = '') {
    return `${String(appId).trim()}::${String(conversationId).trim()}`;
}

// An explicit user target wins for the lifetime of this empty engine, even
// before bind/core-ready. Rejected messages must never set this latch.
let coldHistoryPreparationSelected = false;

function discardColdCharacterPreparation(entry) {
    if (entry?.characterPreparation) entry.characterPreparation.cancelled = true;
}

function prepareColdCharacterRead(appId, conversationId, expiresAt = undefined) {
    const key = sessionCacheKey(appId, conversationId), entry = sessionPrefetchCache.get(key);
    const owner = reconcileStorageAccount(), epoch = storageAccountEpoch;
    const scope = JSON.stringify([owner, String(appId), String(conversationId)]);
    if (!owner || !entry?.promise || entry.expiresAt <= Date.now()) return null;
    const retained = entry.characterPreparation;
    if (retained?.scope === scope && retained.owner === owner && retained.epoch === epoch
        && !retained.cancelled && retained.expiresAt > Date.now()) {
        if (Number.isFinite(expiresAt)) retained.expiresAt = Math.min(retained.expiresAt, expiresAt);
        return retained;
    }
    discardColdCharacterPreparation(entry);
    const safeKey = String(appId).replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80) || 'character';
    const preparation = { owner, epoch, scope, appId: String(appId), conversationId: String(conversationId),
        avatar: `homer-${safeKey}.png`, expiresAt: Number.isFinite(expiresAt) ? Math.min(entry.expiresAt, expiresAt) : entry.expiresAt,
        cancelled: false, claimed: false, payload: null, read: null };
    const isCurrent = () => !preparation.cancelled && preparation.expiresAt > Date.now()
        && reconcileStorageAccount() === owner && storageAccountEpoch === epoch
        && !adminPreviewRequested && !adminBinding
        && (!requestedAppId || (String(requestedAppId) === preparation.appId
            && String(requestedConversationId) === preparation.conversationId))
        && (!preparation.claimed || (session === preparation.targetSession && launch === preparation.targetLaunch));
    preparation.isCurrent = isCurrent;
    preparation.headerScope = JSON.stringify([owner, epoch, String(appId), String(conversationId)]);
    preparation.headerStamp = storageAckStamp(scope);
    preparation.headerVersion = preparation.headerStamp.version;
    const headerCurrent = () => isCurrent() && preparation.headerStamp === storageAckStamp(scope)
        && preparation.headerVersion === preparation.headerStamp.version;
    // This API refuses unknown/old servers, active/saving targets and invalid
    // scopes. The ticket contains only an existing mirror header, not prompts.
    try { preparation.headerRead = prepareCharacterChatMirrorRead(preparation.avatar,
        `Homer-${String(conversationId).replace(/[^a-zA-Z0-9_-]/g, '')}`, {
            owner, scope: preparation.headerScope, expiresAt: preparation.expiresAt, isCurrent: headerCurrent,
        }); } catch { /* Optional; the actual selected read remains authoritative. */ }
    // This endpoint authenticates the current account and reads only its
    // existing mirror. Prepare beside the session, without publishing it; the
    // separately authenticated session and original save/read fence must still
    // settle before this exact payload can receive a one-use handoff.
    try { preparation.read = prepareCharacterRead(preparation.avatar, { cacheOwner: owner, isCurrent }); }
    catch { /* Optional preparation cannot fail an ordinary selected read. */ }
    preparation.pending = entry.promise.then(async payload => {
        const fence = sessionReadFences.get(payload);
        if (!isCurrent() || sessionPrefetchCache.get(key) !== entry
            || fence?.raw !== true || fence.owner !== owner || fence.epoch !== epoch || fence.scope !== scope
            || String(payload?.user?.id || payload?.user?.user_id || '') !== owner
            || String(payload?.launch?.app_id || '') !== preparation.appId
            || String(payload?.launch?.conversation_id || '') !== preparation.conversationId
            || !payload?.launch?.card || !payload.launch.bridge_token || payload.launch.admin_preview) return null;
        preparation.payload = payload;
        return preparation.read ? await preparation.read.pending : null;
    }).then(value => ({ value }), error => ({ error }));
    // Only the existing two retained session/resource peers own this holder.
    // Its current check deliberately survives takePrefetchedSession's deletion
    // so an authenticated, same-payload one-use handoff remains valid.
    entry.characterPreparation = preparation;
    return preparation;
}

function prepareColdConversation(message) {
    if (!prewarmOnly || adminPreviewRequested || bridgeStartScheduled || requestedAppId || launch
        || !hostBootstrapEngineToken || message.engine_token !== hostBootstrapEngineToken
        || message.document_token !== hostBootstrapDocumentToken) return;
    const owner = reconcileStorageAccount();
    const appId = String(message.app_id || '').trim();
    const conversationId = String(message.conversation_id || '').trim();
    if (!owner || message.owner !== owner || !appId || !conversationId || appId.length > 160 || conversationId.length > 160) return;
    coldHistoryPreparationSelected = true;
    // One selected target only. Evicted in-flight requests cannot publish into
    // a live chat; consumption retains the existing account/outbox read fences.
    const key = sessionCacheKey(appId, conversationId);
    for (const retained of sessionPrefetchCache.keys()) if (retained !== key) {
        discardColdCharacterPreparation(sessionPrefetchCache.get(retained));
        sessionPrefetchCache.delete(retained);
    }
    void prefetchSession(appId, conversationId).catch(() => {});
    prepareColdCharacterRead(appId, conversationId);
    prepareConversationResources(appId, conversationId);
    performance.mark('homer-cold-target-read-start');
}

function prepareColdHistoryConversations(message) {
    if (!prewarmOnly || adminPreviewRequested || adminBinding || bridgeStartScheduled
        || requestedAppId || requestedConversationId || launch || coldHistoryPreparationSelected
        || !hostBootstrapEngineToken || message.engine_token !== hostBootstrapEngineToken
        || message.document_token !== hostBootstrapDocumentToken) return;
    const now = Date.now();
    if (!Number.isFinite(message.expires_at) || message.expires_at <= now
        || message.expires_at > now + SESSION_CACHE_TTL_MS
        || !Array.isArray(message.targets) || !message.targets.length
        || message.targets.length > SESSION_PREFETCH_LIMIT) return;
    const owner = reconcileStorageAccount(), epoch = storageAccountEpoch;
    if (!owner || message.owner !== owner) return;
    const targets = new Map();
    // Validate the entire batch before pruning or issuing any private request.
    // IDs originate in the host's fresh authorized list, not a cached preview;
    // fetchSession still performs the actual per-conversation authorization.
    for (const target of message.targets) {
        if (!target || typeof target !== 'object' || Array.isArray(target)
            || typeof target.app_id !== 'string' || typeof target.conversation_id !== 'string') return;
        const appId = target.app_id.trim(), conversationId = target.conversation_id.trim();
        if (!appId || !conversationId || appId.length > 160 || conversationId.length > 160) return;
        const key = sessionCacheKey(appId, conversationId), previous = targets.get(key);
        // The legacy cache-key separator must not merge distinct scoped pairs.
        if (previous && (previous.appId !== appId || previous.conversationId !== conversationId)) return;
        targets.set(key, { appId, conversationId });
    }
    if (reconcileStorageAccount() !== owner || storageAccountEpoch !== epoch
        || Date.now() >= message.expires_at) return;
    // One atomic bounded retention decision: calling the single-target helper
    // twice would evict the first peer and defeat the shared one-use promises.
    for (const retained of sessionPrefetchCache.keys()) if (!targets.has(retained)) {
        discardColdCharacterPreparation(sessionPrefetchCache.get(retained));
        sessionPrefetchCache.delete(retained);
    }
    for (const { appId, conversationId } of targets.values()) {
        if (reconcileStorageAccount() !== owner || storageAccountEpoch !== epoch || coldHistoryPreparationSelected) return;
        void prefetchSession(appId, conversationId).catch(() => {});
        prepareColdCharacterRead(appId, conversationId, message.expires_at);
        prepareConversationResources(appId, conversationId);
    }
    performance.mark('homer-cold-history-read-start');
}

function invalidateCachedSession(appId = '', conversationId = '') {
    sessionPrefetchCache.delete(sessionCacheKey(appId, conversationId));
}

function prefetchSession(appId = '', conversationId = '') {
    const key = sessionCacheKey(appId, conversationId);
    if (!appId || !conversationId) {
        return Promise.resolve(null);
    }
    const cached = sessionPrefetchCache.get(key);
    if (cached && cached.expiresAt > Date.now()) {
        return cached.promise;
    }
    sessionPrefetchCache.delete(key);
    const promise = fetchSession(appId, conversationId, false, 0, { deferLocalMerge: true }).catch(error => {
        if (sessionPrefetchCache.get(key)?.promise === promise) sessionPrefetchCache.delete(key);
        throw error;
    });
    sessionPrefetchCache.set(key, {
        promise,
        expiresAt: Date.now() + SESSION_CACHE_TTL_MS,
    });
    return promise;
}

async function takePrefetchedSession(appId = '', conversationId = '') {
    const key = sessionCacheKey(appId, conversationId);
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const promise = prefetchSession(appId, conversationId);
    try {
        const payload = await promise;
        const currentOwner = reconcileStorageAccount();
        const ticket = sessionReadFences.get(payload);
        if (epoch !== storageAccountEpoch || (owner && owner !== currentOwner)
            || (ticket?.raw === true && (ticket.owner !== currentOwner || ticket.epoch !== storageAccountEpoch))) {
            throw new Error('会话账号已切换，请重新进入');
        }
        const scope = JSON.stringify([currentOwner, String(appId), String(conversationId)]);
        if (ticket?.raw !== true || ticket.scope !== scope || !payload?.launch
            || Object.hasOwn(payload.launch, 'local_chat') || Object.hasOwn(payload.launch, 'local_pending')) {
            // A legacy/consumed/local-projected payload is not fresh cloud
            // input. Refetch instead of erasing fields from an already changed
            // message list or treating it as authoritative on a later take.
            return await fetchSession(appId, conversationId);
        }
        ticket.raw = false;
        try {
            const restored = await preferLocalSession(payload, appId, conversationId, ticket.fence);
            // A cookie-only first read had no pre-GET owner/fence. An ACK
            // before or during consumption can make its older cloud body look
            // authoritative once the local row stops being pending. Refetch
            // with the now verified owner; never invent a zero/local fence.
            if (ticket.fence === null && (ticket.stamp !== storageAckStamps.get(storageAckKey(scope))
                || ticket.version !== ticket.stamp?.version)) return await fetchSession(appId, conversationId);
            return restored;
        }
        catch (error) {
            if (error.code === 'HOMER_STALE_STORAGE_READ') return fetchSession(appId, conversationId);
            throw error;
        }
    } finally {
        // A prefetched payload contains private messages and can be large. Use
        // it once, then release it instead of keeping a second chat in memory.
        if (sessionPrefetchCache.get(key)?.promise === promise) sessionPrefetchCache.delete(key);
    }
}

function scheduleSessionPrefetch(preferredLaunch = null) {
    window.clearTimeout(sessionPrefetchTimer);
    sessionPrefetchTimer = null;
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const currentKey = sessionCacheKey(launch?.app_id, launch?.conversation_id);
    if (!owner || !launch?.app_id || !launch?.conversation_id || launch.admin_preview) {
        sessionPrefetchPeer = null;
        return;
    }
    if (preferredLaunch) {
        const appId = String(preferredLaunch.app_id || '').trim();
        const conversationId = String(preferredLaunch.conversation_id || '').trim();
        sessionPrefetchPeer = appId && conversationId && !preferredLaunch.admin_preview
            && sessionCacheKey(appId, conversationId) !== currentKey
            ? { owner, epoch, currentKey, appId, conversationId } : null;
    }
    const timer = window.setTimeout(() => {
        // A superseded timer or an account/scope change cannot start an old
        // scope's private read, even if the callback was already queued.
        if (sessionPrefetchTimer !== timer) return;
        sessionPrefetchTimer = null;
        if (reconcileStorageAccount() !== owner || storageAccountEpoch !== epoch
            || launch?.admin_preview || sessionCacheKey(launch?.app_id, launch?.conversation_id) !== currentKey) return;
        // Foreground hydration owns the critical path. Remember the preferred
        // peer above, but do not start/prune speculative reads while a switch
        // is in progress. The successful ready-tail reschedules after finally.
        if (loadingLaunch) return;
        const peer = sessionPrefetchPeer;
        const preferred = peer?.owner === owner && peer.epoch === epoch && peer.currentKey === currentKey
            ? [{ app_id: peer.appId, conversation_id: peer.conversationId }] : [];
        const candidates = [], keys = new Set();
        for (const item of [...preferred, ...runtimeUiData.conversations]) {
            const appId = String(item?.app_id || '').trim();
            const conversationId = String(item?.id || item?.conversation_id || '').trim();
            const key = sessionCacheKey(appId, conversationId);
            if (!appId || !conversationId || key === currentKey || keys.has(key)) continue;
            candidates.push({ appId, conversationId }); keys.add(key);
            if (candidates.length >= SESSION_PREFETCH_LIMIT) break;
        }
        // Retain at most the two chosen peers, not an accumulating copy of
        // every visited card. In-flight reads remain authenticated and fenced.
        for (const key of sessionPrefetchCache.keys()) if (!keys.has(key)) sessionPrefetchCache.delete(key);
        for (const { appId, conversationId } of candidates) {
            void prefetchSession(appId, conversationId).catch(() => {});
            // Prepare the same bounded peers' settings as well as their card.
            // Only read bytes here: no SETTINGS/CHAT events or card scripts.
            prepareConversationResources(appId, conversationId);
        }
    }, 0);
    sessionPrefetchTimer = timer;
}

function setAccessClasses(user) {
    const isAdmin = Boolean(user?.is_admin);
    document.body.classList.add('homer-runtime');
    document.body.classList.toggle('homer-admin', isAdmin);
    document.body.classList.toggle('homer-user', !isAdmin);
    document.documentElement.dataset.homerRole = isAdmin ? 'administrator' : 'user';
}

function enforceStreamingConfiguration() {
    const changed = oai_settings.stream_openai !== true;
    oai_settings.stream_openai = true;
    const toggle = document.querySelector('#stream_toggle');
    if (toggle instanceof HTMLInputElement && !toggle.checked) {
        toggle.checked = true;
    }
    document.documentElement.dataset.homerStreaming = 'true';
    return changed;
}

function applyConnectionConfiguration() {
    if (!session?.runtime || !launch?.bridge_token) {
        return;
    }
    const apiBase = String(
        session.runtime.dialogue_api_base_url
        || `${session.runtime.bridge_base_url || session.runtime.backend_base_url}/console/api/web/dialogue/v1`,
    ).replace(/\/+$/, '');
    const includeHeaders = [
        `Authorization: Bearer ${launch.bridge_token}`,
        'X-Homer-Module: dialogue-module',
    ].join('\n');

    const modelSettings = conversationModelSettings();
    const modelId = modelSettings.model_id || 'homer-cloud';
    activateModelScope(JSON.stringify([session?.user?.id || session?.user?.user_id, Boolean(launch.admin_preview), launch.app_id, launch.conversation_id || 'preview']), modelId);

    const sameConnectionConfiguration = getContext().mainApi === 'openai' && oai_settings.chat_completion_source === 'custom'
        && oai_settings.custom_url === apiBase && oai_settings.custom_model === modelId
        && oai_settings.temp_openai === modelSettings.temperature && oai_settings.top_p_openai === modelSettings.top_p
        && oai_settings.freq_pen_openai === modelSettings.frequency_penalty && oai_settings.pres_pen_openai === modelSettings.presence_penalty;
    if (sameConnectionConfiguration && oai_settings.custom_include_headers === includeHeaders) {
        enforceStreamingConfiguration(); setOnlineStatus(modelId); return;
    }
    if (sameConnectionConfiguration && oai_settings.bypass_status_check === true && oai_settings.stream_openai === true) {
        // A fresh session token is live authorization, not a changed persistent
        // provider configuration. Install it now without serializing/saving all
        // native settings or rewriting unrelated model controls on every switch.
        oai_settings.custom_include_headers = includeHeaders;
        $('#custom_include_headers').val(includeHeaders);
        reaffirmConversationConnection();
        return;
    }

    // A new bridge token is not an API/provider change. Re-running these UI
    // transitions forces layout across every native provider settings panel.
    if (getContext().mainApi !== 'openai') {
        $('#main_api').val('openai');
        changeMainAPI('openai');
    }
    const sourceChanged = oai_settings.chat_completion_source !== 'custom';
    oai_settings.chat_completion_source = 'custom';
    oai_settings.custom_url = apiBase;
    oai_settings.custom_model = modelId;
    oai_settings.custom_include_headers = includeHeaders;
    enforceStreamingConfiguration();
    oai_settings.bypass_status_check = true;
    oai_settings.temp_openai = modelSettings.temperature;
    oai_settings.top_p_openai = modelSettings.top_p;
    oai_settings.freq_pen_openai = modelSettings.frequency_penalty;
    oai_settings.pres_pen_openai = modelSettings.presence_penalty;
    $('#chat_completion_source').val('custom');
    if (sourceChanged) $('#chat_completion_source').trigger('change');
    $('#custom_api_url_text').val(apiBase);
    $('#custom_model_id').val(modelId);
    $('#custom_include_headers').val(includeHeaders);
    $('#temp_openai').val(modelSettings.temperature);
    $('#top_p_openai').val(modelSettings.top_p);
    $('#freq_pen_openai').val(modelSettings.frequency_penalty);
    $('#pres_pen_openai').val(modelSettings.presence_penalty);
    setOnlineStatus(modelId);
    const composer = document.querySelector('#send_textarea');
    if (composer instanceof HTMLTextAreaElement) {
        composer.disabled = false;
        composer.placeholder = '输入想发送的消息';
    }
    saveSettingsDebounced();
}

function reaffirmConversationConnection() {
    const modelId = conversationModelSettings().model_id || 'homer-cloud';
    enforceStreamingConfiguration();
    setOnlineStatus(modelId);
    const composer = document.querySelector('#send_textarea');
    if (composer instanceof HTMLTextAreaElement) {
        composer.disabled = false;
        composer.placeholder = '输入想发送的消息';
    }
}

async function refreshBridgeToken() {
    if (!launch?.app_id || !launch?.conversation_id) {
        return;
    }
    const refreshingLaunch = launch;
    try {
        const refreshed = await fetchSession(refreshingLaunch.app_id, refreshingLaunch.conversation_id, Boolean(refreshingLaunch.admin_preview));
        if (launch !== refreshingLaunch || adminBinding || loadingLaunch) return;
        if (refreshed?.launch?.bridge_token) {
            if (launch.admin_preview) {
                // Refresh authorization, not the ephemeral conversation identity.
                launch.bridge_token = refreshed.launch.bridge_token;
                session.user = refreshed.user;
            } else { session = refreshed; launch = refreshed.launch; }
            applyConnectionConfiguration();
            updateRuntimeStatus('已连接', 'online');
        }
    } catch (error) {
        if (launch !== refreshingLaunch || adminBinding || loadingLaunch) return;
        console.warn(`${MODULE_ID}: bridge token refresh failed`, error);
        updateRuntimeStatus('连接待刷新', 'warning');
    }
}

function installTokenRefresh() {
    window.clearInterval(tokenRefreshTimer);
    const ttl = Math.max(120, Number(launch?.bridge_token_ttl_seconds || 900));
    tokenRefreshTimer = window.setInterval(refreshBridgeToken, Math.max(60, ttl - 120) * 1000);
}

function cloneCardWithMarker(prepared) {
    const copy = JSON.parse(prepared.json);
    const cardSignature = prepared.signature;
    copy.spec = copy.spec || 'chara_card_v2';
    copy.spec_version = copy.spec_version || '2.0';
    copy.data = copy.data && typeof copy.data === 'object' ? copy.data : {};
    copy.data.extensions = copy.data.extensions && typeof copy.data.extensions === 'object'
        ? copy.data.extensions
        : {};
    copy.data.extensions.homer_bridge = {
        app_id: launch.app_id,
        source: 'homer-cloud',
        card_signature: cardSignature,
        imported_at: new Date().toISOString(),
    };
    copy.data.name = String(copy.data.name || copy.name || '惑梦角色');
    copy.name = copy.data.name;
    return copy;
}

async function waitForStableCharacterForm(timeoutMs = 5000) {
    const deadline = Date.now() + timeoutMs;
    let stableChecks = 0;
    while (Date.now() < deadline) {
        const runtimeShells = [...document.querySelectorAll('#sheld')];
        if (runtimeShells.length > 1) {
            const canonicalShell = runtimeShells.reduce((best, candidate) => {
                const rect = candidate.getBoundingClientRect();
                const area = rect.width * rect.height;
                const bestRect = best.getBoundingClientRect();
                return area >= bestRect.width * bestRect.height ? candidate : best;
            });
            for (const shell of runtimeShells) {
                if (shell !== canonicalShell) {
                    shell.remove();
                }
            }
        }
        const editorPanels = [...document.querySelectorAll('#rm_ch_create_block')];
        // Some extension UI transitions leave a hidden clone of the entire
        // character editor behind. Its fields still target form="form_create",
        // so submitting the canonical form would turn string values into
        // arrays. Keep SillyTavern's first editor and discard only duplicate
        // siblings inside the Homer runtime.
        for (const duplicatePanel of editorPanels.slice(1)) {
            duplicatePanel.remove();
        }
        const seenFormControlIds = new Set();
        const formControls = [...document.querySelectorAll('[id]')]
            .filter(element => element.form?.id === 'form_create');
        for (const control of formControls) {
            if (seenFormControlIds.has(control.id)) {
                control.remove();
                continue;
            }
            seenFormControlIds.add(control.id);
        }
        const formCount = document.querySelectorAll('#form_create').length;
        const formAnimating = $('#form_create:animated').length > 0;
        if (formCount === 1 && !formAnimating) {
            stableChecks += 1;
            if (stableChecks >= 2) {
                return;
            }
        } else {
            stableChecks = 0;
        }
        await new Promise(resolve => window.setTimeout(resolve, 100));
    }
    throw new Error('角色编辑器尚未完成初始化');
}

function enableEmbeddedCardCapabilities(character) {
    if (!character || typeof character !== 'object') {
        return;
    }
    // Homer launches cards chosen from its own library/import flow. Card-scoped
    // regex and TavernHelper scripts are therefore runtime content, not an
    // extension-install permission. Keep extension mutation admin-only while
    // allowing the selected card to behave exactly as it does in SillyTavern.
    allowScopedScripts(character);

    if (character.avatar && character?.data?.character_book) {
        accountStorage.setItem(`AlertWI_${character.avatar}`, 'true');
    }
}

function installCsrfAjaxBridge() {
    const jquery = window.jQuery;
    if (typeof jquery?.ajaxPrefilter !== 'function' || jquery.__homerCsrfPrefilterInstalled) {
        return;
    }
    // TavernHelper intentionally provides isolated jQuery contexts to card
    // scripts. Re-register the SillyTavern CSRF header on the currently active
    // root jQuery instance so legacy synchronous tokenizer calls keep working.
    jquery.ajaxPrefilter((_options, _originalOptions, xhr) => {
        const token = getRequestHeaders()['X-CSRF-Token'];
        if (token) {
            xhr.setRequestHeader('X-CSRF-Token', token);
        }
    });
    Object.defineProperty(jquery, '__homerCsrfPrefilterInstalled', {
        configurable: true,
        value: true,
    });
}

async function ensureEmbeddedWorldInfo(characterId, character) {
    const embeddedBook = character?.data?.character_book;
    if (!embeddedBook || typeof embeddedBook !== 'object') {
        return;
    }
    const bookName = String(embeddedBook.name || `${character?.name || 'Character'}'s Lorebook`).trim();
    if (!bookName) {
        return;
    }

    if (!world_names.includes(bookName)) {
        await updateWorldInfoList();
    }
    if (!world_names.includes(bookName)) {
        await saveWorldInfo(bookName, convertCharacterBook(embeddedBook), true);
        await updateWorldInfoList();
    }
    if (String(character?.data?.extensions?.world || '') !== bookName) {
        // Normal chat has no character-edit form. Triggering that control's
        // change event would save the previous card's stale hidden fields.
        // Preserve an existing user-edited book; bind only the extension field.
        await writeExtensionField(characterId, 'world', bookName);
    }
}

async function enableTavernHelperCardScripts(character) {
    const scripts = character?.data?.extensions?.tavern_helper?.scripts;
    if (!Array.isArray(scripts) || scripts.length === 0) {
        return;
    }
    const deadline = Date.now() + 5000;
    let toggle = null;
    while (Date.now() < deadline && !toggle) {
        const scriptTrees = [...document.querySelectorAll('[data-container-type]')];
        const characterTreeIndex = scriptTrees.findIndex(
            element => element.getAttribute('data-container-type') === 'character',
        );
        const toggles = [...document.querySelectorAll('input[id$="-script-enable-toggle"]')];
        if (characterTreeIndex >= 0 && toggles[characterTreeIndex] instanceof HTMLInputElement) {
            toggle = toggles[characterTreeIndex];
        }
        if (!toggle) {
            await new Promise(resolve => window.setTimeout(resolve, 100));
        }
    }
    if (!toggle) {
        throw new Error('TavernHelper 角色脚本开关尚未就绪');
    }
    if (toggle.checked) {
        return;
    }
    const avatar = String(character?.avatar || '').trim();
    const cardSignature = String(character?.data?.extensions?.homer_bridge?.card_signature || '').trim();
    const scriptSignature = cardSignature || scripts.map(script => [
        String(script?.id || ''),
        String(script?.name || ''),
        String(script?.content || '').length,
    ].join(':')).join('|');
    const trustKey = avatar ? `homer-card-script-ready:${avatar}` : '';
    const previouslyReady = Boolean(
        trustKey
        && scriptSignature
        && localStorage.getItem(trustKey) === scriptSignature,
    );
    toggle.click();

    const characterName = String(character.name || character.data?.name || '').trim();
    const promptDeadline = Date.now() + 5000;
    let checkedSince = 0;
    while (Date.now() < promptDeadline) {
        let confirmed = false;
        for (const dialog of document.querySelectorAll('dialog.popup[open]')) {
            const text = String(dialog.textContent || '');
            const isTavernHelperCardPrompt = text.includes(characterName)
                && (text.includes('酒馆助手') || text.includes('Tavern Helper'))
                && (text.includes('脚本') || text.toLowerCase().includes('script'));
            if (!isTavernHelperCardPrompt) {
                continue;
            }
            const confirm = dialog.querySelector('.popup-button-ok');
            if (confirm instanceof HTMLElement) {
                confirm.click();
                if (trustKey && scriptSignature) {
                    localStorage.setItem(trustKey, scriptSignature);
                }
                confirmed = true;
            }
        }
        if (confirmed) {
            return;
        }
        if (toggle.checked) {
            checkedSince ||= Date.now();
            // Some cards/accounts have already accepted the script policy, so
            // TavernHelper applies the toggle without opening a dialog. Do not
            // pay the full dialog timeout in that normal path; leave enough of
            // a settle window for a deferred confirmation popup to appear.
            const settleMs = previouslyReady ? 75 : 500;
            if (Date.now() - checkedSince >= settleMs) {
                if (trustKey && scriptSignature) {
                    localStorage.setItem(trustKey, scriptSignature);
                }
                return;
            }
        } else {
            checkedSince = 0;
        }
        await new Promise(resolve => window.setTimeout(resolve, 100));
    }
}

async function selectLaunchCharacter(context, characterId, options = {}) {
    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
        await context.selectCharacterById(characterId, options);
        // getContext() returns a snapshot. Re-read it after every attempted
        // switch; checking the launch-time snapshot falsely reports failure
        // even though selectCharacterById has already updated the live state.
        if (String(getContext().characterId) === String(characterId)) {
            return;
        }
        // SillyTavern intentionally ignores character switches while a local
        // chat save is settling. A rapid same-tab relaunch should wait and
        // retry, not continue with an undefined/previous character context.
        await new Promise(resolve => window.setTimeout(resolve, 100));
    }
    throw new Error('当前角色会话仍在保存，请稍后重试');
}

async function openLaunchCharacterChat(characterId, { reuseActiveCharacter = false, preparedHeader = null } = {}) {
    pendingCardScriptCharacter = null;
    const context = getContext();
    const localChatName = `Homer-${String(launch.conversation_id).replace(/[^a-zA-Z0-9_-]/g, '')}`;
    let character = context.characters?.[characterId];
    enableEmbeddedCardCapabilities(character);
    if (reuseActiveCharacter && String(context.characterId) === String(characterId)) {
        // Switching between two cloud conversations of the same card must not
        // re-select/unshallow the character, rescan its worldbook, or re-run
        // already enabled card scripts. Only bind the new local mirror; the
        // cloud payload replaces its messages immediately afterwards.
        installCsrfAjaxBridge();
        if (typeof context.bindCharacterChatWithoutLoad === 'function') {
            await context.bindCharacterChatWithoutLoad(localChatName, { ephemeral: Boolean(launch.admin_preview), preparedHeader });
        } else {
            await context.openCharacterChat(localChatName, { persistCharacter: false });
        }
        setOnlineStatus(conversationModelSettings().model_id || 'homer-cloud');
        return;
    }
    // Activate canonical chat state directly, not the hidden creation/editor
    // controls. Keep mirror integrity and itemized prompt storage validation.
    await activateCharacterForChat(characterId, {
        chatName: localChatName,
        ephemeral: Boolean(launch.admin_preview),
        preparedHeader,
    });
    performance.mark('homer-card-selected');
    character = getContext().characters?.[characterId];
    enableEmbeddedCardCapabilities(character);
    await ensureEmbeddedWorldInfo(characterId, character);
    performance.mark('homer-card-world-ready');
    installCsrfAjaxBridge();
    performance.mark('homer-card-mirror-ready');
    // The cloud payload is authoritative. Do not read, render and save a
    // provisional local greeting before replacing it with the cloud messages.
    // Enable scripts only after CHAT_CHANGED creates the character store.
    pendingCardScriptCharacter = character;
    // Updating the API source can animate the chat shell and briefly leave a
    // hidden duplicate. Broadcast the connected state again after the visible
    // canonical shell has been selected.
    setOnlineStatus(conversationModelSettings().model_id || 'homer-cloud');
}

function getManagedCoverUrl() {
    const raw = String(launch?.card?.data?.extensions?.homer_cover_url || '').trim();
    return siteAssetUrl(raw);
}

// 生成失败恢复。上游返回空回复时 SillyTavern 会留下一条空的 assistant 占位，
// 用户看到的是「发出去了但永远没有回复」。这里在 GENERATION_STARTED 时拍一份
// 快照，结束时若检测到空占位/多出的用户消息，就整轮回滚并明确提示。
function cloneGenerationMessages(messages) {
    try {
        return structuredClone(Array.isArray(messages) ? messages : []);
    } catch {
        try {
            return JSON.parse(JSON.stringify(Array.isArray(messages) ? messages : []));
        } catch {
            return [];
        }
    }
}

function isAssistantChatMessage(message) {
    return Boolean(message) && !message.is_user && !message.is_system
        && String(message.role || 'assistant').toLowerCase() !== 'user';
}

function selectedChatMessageContent(message) {
    if (!message) {
        return '';
    }
    const swipes = Array.isArray(message.swipes) ? message.swipes : [];
    if (swipes.length) {
        const swipeIndex = Math.max(0, Math.min(Number(message.swipe_id || 0), swipes.length - 1));
        return String(swipes[swipeIndex] ?? '');
    }
    return String(message.mes ?? message.content ?? '');
}

function isEmptyGeneratedAssistant(message) {
    if (!isAssistantChatMessage(message)) {
        return false;
    }
    const content = selectedChatMessageContent(message).replace(/​/g, '').trim();
    return ['', '...', '…'].includes(content);
}

function captureGenerationSnapshot(type) {
    const context = getContext();
    return {
        type: String(type || ''),
        chatId: String(context.chatId || ''),
        chat: cloneGenerationMessages(context.chat),
        launchMessages: cloneGenerationMessages(launch?.messages),
    };
}

function generationNeedsRecovery(snapshot, currentChat) {
    if (!snapshot || !Array.isArray(currentChat)) {
        return false;
    }
    const lastMessage = currentChat.at(-1);
    if (isEmptyGeneratedAssistant(lastMessage)) {
        return true;
    }
    if (currentChat.length > snapshot.chat.length && lastMessage?.is_user) {
        return true;
    }
    return ['regenerate', 'swipe'].includes(snapshot.type)
        && currentChat.length < snapshot.chat.length;
}

async function syncLaunchCharacterAvatar(character, force = false) {
    const capturedLaunch = launch;
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const appId = String(capturedLaunch?.app_id || '');
    const signature = String(character?.data?.extensions?.homer_bridge?.card_signature || '');
    const coverUrl = getManagedCoverUrl();
    const avatar = String(character?.avatar || '').trim();
    if (!coverUrl || !avatar || !owner || !appId || !signature) {
        return false;
    }
    const isSameRevision = () => {
        if (reconcileStorageAccount() !== owner || storageAccountEpoch !== epoch) return false;
        const current = getContext().characters?.find(item => String(item?.avatar || '') === avatar
            && String(item?.data?.extensions?.homer_bridge?.app_id || '') === appId);
        return String(current?.data?.extensions?.homer_bridge?.card_signature || '') === signature;
    };
    const isCurrent = () => isSameRevision() && String(launch?.app_id || '') === appId;
    if (!isSameRevision()) return false;
    const markerKey = `homer-avatar-sync:${appId}`;
    if (!force && accountStorage.getItem(markerKey) === coverUrl) {
        return false;
    }

    let coverBlob;
    try {
        const coverResponse = await fetch(coverUrl, {
            method: 'GET',
            cache: 'no-store',
            credentials: 'include',
        });
        if (!coverResponse.ok) {
            console.warn(`${MODULE_ID}: cover unavailable (HTTP ${coverResponse.status})`);
            return false;
        }
        coverBlob = await coverResponse.blob();
        if (!String(coverBlob.type || '').toLowerCase().startsWith('image/')) {
            console.warn(`${MODULE_ID}: cover response is not an image; keeping the card avatar`);
            return false;
        }
    } catch (error) {
        console.warn(`${MODULE_ID}: cover synchronization skipped`, error);
        return false;
    }

    // A handoff may leave this card in the retained catalog. Finish its exact
    // captured file upload there; never read a later launch for the target or
    // mark/upload after a revision, logout or same-owner relogin.
    if (!isSameRevision()) return false;
    const formData = new FormData();
    formData.append('avatar', new File([coverBlob], 'avatar.png', {
        type: coverBlob.type || 'image/png',
    }));
    formData.append('avatar_url', avatar);
    const uploadResponse = await fetch('/api/characters/edit-avatar', {
        method: 'POST',
        headers: getRequestHeaders({ omitContentType: true }),
        body: formData,
        cache: 'no-store',
    });
    if (!uploadResponse.ok) {
        console.warn(`${MODULE_ID}: avatar upload skipped (HTTP ${uploadResponse.status})`);
        return false;
    }
    if (!isSameRevision()) return false;
    accountStorage.setItem(markerKey, coverUrl);

    refreshSettledAvatarImages([...document.querySelectorAll('img')].filter(image => image instanceof HTMLImageElement), {
        avatar, stamp: Date.now(), baseUrl: window.location.href, isCurrent,
    });
    return true;
}

function reaffirmSelectedCardCapabilities() {
    const context = getContext();
    const character = context.characters?.[context.characterId];
    const selectedApp = character?.data?.extensions?.homer_bridge?.app_id;
    // APP_READY can replay an overlay captured BEFORE this card was selected.
    // Restore only the already-authorized active card's derived capabilities;
    // never trust a stale/previous card merely because it is in the catalog.
    if (!launch?.app_id || String(selectedApp ?? '') !== String(launch.app_id)) return;
    enableEmbeddedCardCapabilities(character);
}

async function importLaunchCardJson(card, preservedName) {
    const formData = new FormData();
    formData.append(
        'avatar',
        new File([JSON.stringify(card)], `${preservedName}.json`, { type: 'application/json' }),
    );
    formData.append('file_type', 'json');
    formData.append('user_name', String(session?.user?.name || 'Homer 用户'));
    formData.append('preserved_name', preservedName);
    const response = await fetch('/api/characters/import', {
        method: 'POST',
        body: formData,
        headers: getContext().getRequestHeaders({ omitContentType: true }),
        cache: 'no-store',
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || result?.error || !result?.file_name) {
        throw new Error('角色卡载入失败');
    }
    return `${String(result.file_name).replace(/\.png$/i, '')}.png`;
}

function prepareLaunchMirrorHeader(optionalPreparation = null) {
    const owner = reconcileStorageAccount(), epoch = storageAccountEpoch;
    const targetSession = session, targetLaunch = launch;
    if (!owner || !targetLaunch?.card || !targetLaunch.bridge_token || targetLaunch.admin_preview
        || adminPreviewRequested || adminBinding || !targetLaunch.app_id || !targetLaunch.conversation_id
        || owner !== String(targetSession?.user?.id || targetSession?.user?.user_id || '')
        || Object.hasOwn(targetLaunch, 'local_chat') || Object.hasOwn(targetLaunch, 'local_pending')) return null;
    const appId = String(targetLaunch.app_id), conversationId = String(targetLaunch.conversation_id);
    const sessionScope = JSON.stringify([owner, appId, conversationId]);
    const scope = JSON.stringify([owner, epoch, appId, conversationId]);
    const stamp = storageAckStamp(sessionScope), version = stamp.version;
    const current = () => reconcileStorageAccount() === owner && storageAccountEpoch === epoch
        && session === targetSession && launch === targetLaunch && !targetLaunch.admin_preview
        && String(targetSession?.user?.id || targetSession?.user?.user_id || '') === owner
        && String(targetLaunch.app_id) === appId && String(targetLaunch.conversation_id) === conversationId
        && !Object.hasOwn(targetLaunch, 'local_chat') && !Object.hasOwn(targetLaunch, 'local_pending')
        && storageAckStamp(sessionScope) === stamp && stamp.version === version;
    const avatar = `homer-${appId.replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80) || 'character'}.png`;
    if (optionalPreparation) {
        if (!optionalPreparation.headerRead || optionalPreparation.payload !== targetSession
            || optionalPreparation.owner !== owner || optionalPreparation.epoch !== epoch
            || optionalPreparation.scope !== sessionScope || optionalPreparation.avatar !== avatar
            || optionalPreparation.headerScope !== scope || optionalPreparation.headerStamp !== stamp
            || optionalPreparation.headerVersion !== version || !optionalPreparation.isCurrent()) return null;
        return { ticket: optionalPreparation.headerRead, owner, scope,
            isCurrent: () => current() && optionalPreparation.isCurrent() };
    }
    try {
        const ticket = prepareCharacterChatMirrorRead(avatar,
            `Homer-${conversationId.replace(/[^a-zA-Z0-9_-]/g, '')}`, {
                owner, scope, expiresAt: Date.now() + SESSION_CACHE_TTL_MS, isCurrent: current,
            });
        return ticket ? { ticket, owner, scope, isCurrent: current } : null;
    } catch { return null; }
}

function prepareInitialCharacterRead(optionalPreparation = null) {
    const targetOwner = reconcileStorageAccount(), targetEpoch = storageAccountEpoch;
    const targetLaunch = launch, targetSession = session;
    // Only an authenticated explicit initial selection is eligible. Empty
    // engine prewarm, existing characters and administrator previews stay out.
    if (!targetOwner || !targetLaunch?.card || targetLaunch.admin_preview
        || !targetLaunch.app_id || !targetLaunch.conversation_id
        || targetOwner !== String(targetSession?.user?.id || targetSession?.user?.user_id || '')) return null;
    const safeKey = String(targetLaunch.app_id || '').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80) || 'character';
    const avatar = `homer-${safeKey}.png`;
    if (getContext().characters.some(item => item?.avatar === avatar
        || String(item?.data?.extensions?.homer_bridge?.app_id || '') === String(targetLaunch.app_id))) return null;
    // A local merge/refetch may return a different payload. Never attach an
    // earlier peer's mirror read to it merely because the IDs still match.
    if (optionalPreparation && !optionalPreparation.claimed && optionalPreparation.read
        && optionalPreparation.payload === targetSession && optionalPreparation.owner === targetOwner
        && optionalPreparation.epoch === targetEpoch && optionalPreparation.avatar === avatar
        && optionalPreparation.scope === JSON.stringify([targetOwner, String(targetLaunch.app_id), String(targetLaunch.conversation_id)])
        && optionalPreparation.isCurrent()) {
        return { owner: targetOwner, epoch: targetEpoch, targetLaunch, targetSession, avatar,
            read: optionalPreparation.read, optionalPreparation };
    }
    const isCurrent = () => reconcileStorageAccount() === targetOwner && storageAccountEpoch === targetEpoch
        && launch === targetLaunch && session === targetSession
        && targetOwner === String(session?.user?.id || session?.user?.user_id || '');
    return { owner: targetOwner, epoch: targetEpoch, targetLaunch, targetSession, avatar,
        read: prepareCharacterRead(avatar, { cacheOwner: targetOwner, isCurrent }) };
}

async function importLaunchCharacter({ reuseActiveCharacter = false, initialRead = null, preparedHeader = null } = {}) {
    const targetOwner = reconcileStorageAccount(), targetEpoch = storageAccountEpoch;
    const targetLaunch = launch, targetSession = session;
    const isCurrent = () => reconcileStorageAccount() === targetOwner
        && storageAccountEpoch === targetEpoch && launch === targetLaunch && session === targetSession
        && targetOwner && targetOwner === String(session?.user?.id || session?.user?.user_id || '');
    const assertCurrent = () => {
        if (!isCurrent()) throw new Error('当前账号或会话已变化，请重新打开');
    };
    assertCurrent();
    const context = getContext();
    const prepared = cardPreparations.prepare(JSON.stringify([
        String(session?.user?.id || session?.user?.user_id || ''), String(launch.app_id),
    ]), launch.card);
    const safeKey = String(launch.app_id || '').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 80) || 'character';
    const preservedName = `homer-${safeKey}`;
    const expectedAvatar = `${preservedName}.png`;
    if (initialRead && (initialRead.owner !== targetOwner || initialRead.epoch !== targetEpoch
        || initialRead.targetLaunch !== targetLaunch || initialRead.targetSession !== targetSession
        || initialRead.avatar !== expectedAvatar)) {
        if (initialRead.optionalPreparation) initialRead = null;
        else throw new Error('角色读取票据与当前会话不一致');
    }
    const assertTargetCharacter = index => {
        assertCurrent();
        const character = context.characters[index];
        const marker = character?.data?.extensions?.homer_bridge;
        if (character?.avatar !== expectedAvatar
            || String(marker?.app_id ?? '') !== String(targetLaunch.app_id)
            || marker?.card_signature !== prepared.signature) {
            throw new Error('角色资料与当前会话不一致，请重新打开');
        }
    };
    let characterId = context.characters.findIndex(item => (
        String(item?.data?.extensions?.homer_bridge?.app_id || '') === String(launch.app_id)
        || item?.avatar === expectedAvatar
    ));
    if (characterId < 0) {
        // Cold embedded hosts have no whole-library catalog. Read the exact
        // persisted mirror, then verify its app/revision just like a warm card.
        // Only 404 means missing; auth/server failures must not cause an import.
        const optional = initialRead?.optionalPreparation;
        if (optional) {
            let expiryTimer;
            const outcome = await Promise.race([initialRead.read.pending, new Promise(resolve => {
                expiryTimer = setTimeout(() => resolve({ error: new Error('角色预读已过期') }),
                    Math.max(0, optional.expiresAt - Date.now()));
            })]).finally(() => clearTimeout(expiryTimer));
            assertCurrent();
            if (optional.claimed || optional.payload !== targetSession || !optional.isCurrent()
                || outcome.error || !outcome.value?.ok || outcome.value.getData?.avatar !== expectedAvatar) {
                optional.cancelled = true; initialRead = null;
            }
            else { optional.claimed = true; optional.targetLaunch = targetLaunch; optional.targetSession = targetSession; }
        }
        try {
            characterId = await context.getOneCharacter(expectedAvatar, { addIfMissing: true, missingOk: true, isCurrent,
                cacheOwner: targetLaunch.admin_preview ? '' : targetOwner, preparedRead: initialRead?.read || null });
        } catch (error) {
            assertCurrent();
            if (!optional || !initialRead) throw error;
            // Optional bytes never turn a recoverable read into a startup
            // failure. The normal selected read still enforces HTTP status,
            // avatar, account and revision rules (only a real 404 imports).
            characterId = await context.getOneCharacter(expectedAvatar, { addIfMissing: true, missingOk: true, isCurrent,
                cacheOwner: targetLaunch.admin_preview ? '' : targetOwner });
        }
        assertCurrent();
    }
    if (characterId >= 0) {
        const currentSignature = String(
            context.characters[characterId]?.data?.extensions?.homer_bridge?.card_signature || '',
        );
        const desiredSignature = prepared.signature;
        const currentAppId = context.characters[characterId]?.data?.extensions?.homer_bridge?.app_id;
        // Sanitizing/truncating an app ID into an avatar name is not injective.
        // Equal source JSON must never reuse another app's persisted marker.
        const metadataChanged = String(currentAppId ?? '') !== String(launch.app_id)
            || !currentSignature || currentSignature !== desiredSignature;
        if (metadataChanged) {
            const refreshedAvatar = await importLaunchCardJson(cloneCardWithMarker(prepared), preservedName);
            assertCurrent();
            if (refreshedAvatar !== expectedAvatar) throw new Error('角色导入结果与目标不一致');
            characterId = await context.getOneCharacter(refreshedAvatar, { addIfMissing: true, missingOk: true, isCurrent,
                cacheOwner: targetLaunch.admin_preview ? '' : targetOwner });
            assertCurrent();
            if (characterId < 0) {
                throw new Error('角色卡元数据刷新后未找到角色卡');
            }
        }
        assertTargetCharacter(characterId);
        // An unchanged imported card already owns the persisted avatar file.
        // Re-uploading the same multi-megabyte cover for every fresh browser
        // session was pure startup work and also forced another full character
        // list refresh. A changed card is re-imported and explicitly refreshed.
        if (metadataChanged) {
            // Cover pixels are independent of card scripts and message readiness.
            // Importing a PNG used to download/upload its multi-MB cover and
            // refresh every character before the user could read the greeting.
            void syncLaunchCharacterAvatar(context.characters[characterId], true)
                .catch(error => console.debug(`${MODULE_ID}: avatar refresh deferred`, error));
        }
        await openLaunchCharacterChat(characterId, {
            reuseActiveCharacter: reuseActiveCharacter && !metadataChanged,
            preparedHeader: metadataChanged ? null : preparedHeader,
        });
        assertCurrent();
        return;
    }

    const avatar = await importLaunchCardJson(cloneCardWithMarker(prepared), preservedName);
    assertCurrent();
    if (avatar !== expectedAvatar) throw new Error('角色导入结果与目标不一致');
    performance.mark('homer-card-json-imported');
    characterId = await context.getOneCharacter(avatar, { addIfMissing: true, missingOk: true, isCurrent,
        cacheOwner: targetLaunch.admin_preview ? '' : targetOwner });
    assertCurrent();
    performance.mark('homer-card-list-updated');
    if (characterId < 0) {
        throw new Error('导入后未找到角色卡');
    }
    assertTargetCharacter(characterId);
    void syncLaunchCharacterAvatar(context.characters[characterId], true)
        .catch(error => console.debug(`${MODULE_ID}: avatar refresh deferred`, error));
    await openLaunchCharacterChat(characterId);
    assertCurrent();
}

function normalizeOpeningMessage(message) {
    return restoreCanonicalGreeting(launch?.card, message,
        raw => getRegexedString(raw, regex_placement.AI_OUTPUT, { isMarkdown: true, depth: 0, deterministicReplay: true }),
        getRegexScripts({ allowedOnly: true }), { guardedReplay: true });
}

function cloudMessageToDialogue(message, index) {
    const role = String(message?.role || 'assistant');
    const isUser = role === 'user';
    const isSystem = role === 'system';
    const presentation = runtimeVariables.homer_message_presentation?.[String(message?.id || '')] || {};
    let content = String(message?.content || '');
    const createdAt = Number(message?.created_at || Date.now() + index);
    let swipes = Array.isArray(message?.swipes)
        ? message.swipes.map(item => String(item))
        : [];
    if (index === 0 && !isUser && !isSystem) {
        ({ mes: content, swipes } = normalizeOpeningMessage({
            mes: content, swipes, is_user: false, is_system: false,
        }));
        swipes = greetingSwipes(launch?.card, swipes, content);
    }
    const swipeId = Math.max(0, Math.min(Number(message?.swipe_index || 0), Math.max(0, swipes.length - 1)));
    return {
        name: isUser ? String(session?.user?.name || '你') : String(launch?.card?.data?.name || launch?.card?.name || '角色'),
        is_user: isUser,
        is_system: isSystem || Boolean(presentation.hidden),
        send_date: new Date(createdAt).toISOString(),
        mes: swipes.length ? swipes[swipeId] : content,
        swipes,
        swipe_id: swipeId,
        swipe_info: swipes.map(() => ({
            send_date: new Date(createdAt).toISOString(),
            gen_started: null,
            gen_finished: null,
            extra: {},
        })),
        extra: {
            homer_hidden: Boolean(presentation.hidden),
            homer_collapsed: Boolean(presentation.collapsed),
            homer_message_id: String(message?.id || ''),
            homer_sync_id: String(message?.id || `cloud-${index}`),
            homer_created_at: createdAt,
        },
    };
}

function initialGreetingMessage() {
    const card = launch?.card || {};
    const data = card.data || {};
    const text = String(data.first_mes || card.first_mes || '').trim();
    if (!text) {
        return null;
    }
    const swipes = greetingSwipes(card, [text]);
    return {
        name: String(data.name || card.name || '角色'),
        is_user: false,
        is_system: false,
        send_date: new Date().toISOString(),
        mes: text,
        swipes,
        swipe_id: 0,
        swipe_info: swipes.map(() => ({
            send_date: new Date().toISOString(),
            gen_started: null,
            gen_finished: null,
            extra: {},
        })),
        extra: {
            homer_sync_id: `greeting-${launch.conversation_id}`,
            homer_created_at: Date.now(),
        },
    };
}

async function loadCloudChat({ emitChatChanged = true } = {}) {
    const previousSuppressSync = suppressSync;
    const releaseSourceLayout = holdLargeSourceLayout();
    suppressSync = true;
    try {
    const context = getContext();
    const stateLaunch = launch;
    const promptTicket = acknowledgedPromptTickets.get(stateLaunch);
    acknowledgedPromptTickets.delete(stateLaunch);
    const messages = Array.isArray(launch.local_chat) ? cloneJsonValue(launch.local_chat) : Array.isArray(launch.messages)
        ? launch.messages.map(cloudMessageToDialogue)
        : [];
    if (Array.isArray(launch.local_chat) && messages.length) {
        const opening = messages[0];
        messages[0] = normalizeOpeningMessage(opening);
        if (!samePromptMessageSource(opening, messages[0])) clearPromptMessageState(messages[0]);
    } else if (promptTicket && launch === stateLaunch && promptTicket.owner === reconcileStorageAccount()
        && promptTicket.epoch === storageAccountEpoch
        && promptTicket.owner === String(session?.user?.id || session?.user?.user_id || '')
        && promptTicket.scope === JSON.stringify([promptTicket.owner, String(launch.app_id), String(launch.conversation_id)])) {
        // Projection has already normalized greetings/swipes. A changed source
        // cannot inherit a processed marker from its formerly rendered version.
        restoreAcknowledgedPromptStates(messages, promptTicket.states);
    }
    delete launch.local_chat;
    if (!messages.length) {
        const greeting = initialGreetingMessage();
        if (greeting) {
            messages.push(greeting);
        }
    }
    context.chat.splice(0, context.chat.length, ...messages);
    context.chatMetadata.homer_bridge = {
        user_id: String(session?.user?.id || session?.user?.user_id || ''),
        app_id: launch.app_id,
        conversation_id: launch.conversation_id,
        runtime: 'dialogue',
    };
    delete context.chatMetadata.homer_preset_overrides;
    context.chatMetadata.homer_model_settings = { ...conversationModelSettings() };
    // Launch a fresh, same-scope filename read before large DOM/iframe work,
    // not once those tasks are already occupying the main thread.
    prefetchPersonaAvatarsForCurrentChat();
    // The cloud conversation is authoritative. Paint it immediately; a fresh
    // embedded page must not block interactivity on two redundant writes to
    // SillyTavern's compatibility mirror. Normal generation/save hooks keep
    // that mirror current after the user actually changes the conversation.
    await context.printMessages({ scroll: false });
    if (emitChatChanged) {
        performance.mark('homer-switch-messages');
    }
    queueMessageMenuRender();
    if (emitChatChanged) {
        await eventSource.emit(event_types.CHAT_CHANGED, context.chatId);
    }
    if (pendingCardScriptCharacter) {
        const character = pendingCardScriptCharacter;
        pendingCardScriptCharacter = null;
        await enableTavernHelperCardScripts(character);
    }
    await eventSource.emit(event_types.CHAT_LOADED, context.chatId);
    } finally {
        suppressSync = previousSuppressSync;
        releaseSourceLayout();
    }
    // Do not force a viewport-sized layout of temporary 3MB source code
    // while the HTML frontend renderer is replacing it. Scroll the real DOM.
    scrollChatToBottom({ waitForFrame: true });
    // Preserve the normal late image/video/audio bottom-position watcher,
    // but attach it only after frontend conversion has finished.
    scrollOnMediaLoad();
    scheduleSync(100);
    scheduleHostStateNotify(0, 'chat-loaded');
}

function serializeChat() {
    const context = getContext();
    return context.chat.map((message, index) => {
        const swipes = Array.isArray(message?.swipes) ? message.swipes.map(item => String(item)) : [];
        const swipeId = Number(message?.swipe_id || 0);
        const promptState = capturePromptMessageState(message, { swipes, swipe_id: swipeId });
        const extra = { ...(message?.extra && typeof message.extra === 'object' ? message.extra : {}) };
        delete extra.homer_prompt_state;
        if (promptState) extra.homer_prompt_state = promptState.descriptor;
        return {
        name: String(message?.name || ''),
        is_user: Boolean(message?.is_user),
        // Hiding changes prompt participation, not the original cloud message role.
        is_system: Boolean(message?.is_system && !message?.extra?.homer_hidden),
        send_date: String(message?.send_date || ''),
        mes: String(message?.mes || ''),
        swipes,
        swipe_id: swipeId,
        ...(promptState?.values || {}),
        extra: {
            ...extra,
            homer_sync_id: String(
                message?.extra?.homer_sync_id
                || message?.extra?.homer_message_id
                || `${launch.conversation_id}-${message?.send_date || index}-${index}`,
            ),
        },
        };
    });
}

async function recoverFailedGeneration(snapshot) {
    const context = getContext();
    if (!snapshot || String(context.chatId || '') !== snapshot.chatId) {
        return false;
    }
    if (!generationNeedsRecovery(snapshot, context.chat)) {
        return false;
    }

    const previousSuppressSync = suppressSync;
    suppressSync = true;
    try {
        context.chat.splice(0, context.chat.length, ...cloneGenerationMessages(snapshot.chat));
        if (Array.isArray(launch?.messages)) {
            launch.messages.splice(
                0,
                launch.messages.length,
                ...cloneGenerationMessages(snapshot.launchMessages),
            );
        }
        try {
            await context.saveChat();
        } catch (error) {
            console.warn(`${MODULE_ID}: failed generation mirror was not saved locally`, error);
        }
        await context.printMessages();
        dialogueEventLogMuted += 1;
        try {
            await eventSource.emit(event_types.CHAT_LOADED, context.chatId);
        } finally {
            dialogueEventLogMuted = Math.max(0, dialogueEventLogMuted - 1);
        }
    } finally {
        suppressSync = previousSuppressSync;
    }

    lastSyncSignature = '';
    await syncCloudChat();
    const errorMessage = generationFailure({ error: { code: lastGenerationDiagnostic?.error_code || 'HM-G204' } }).message + '。本轮失败消息已撤回。';
    showHostNotice(errorMessage, 'error');
    updateRuntimeStatus('生成失败，消息已撤回', 'warning');
    queueMessageMenuRender();
    return true;
}

function cloudSyncScope() {
    return JSON.stringify([String(session?.user?.id || session?.user?.user_id || ''), launch?.app_id, launch?.conversation_id]);
}

function hasCanonicalConversationScope(context = getContext()) {
    const owner = String(session?.user?.id || session?.user?.user_id || '');
    const appId = String(launch?.app_id || '');
    const conversationId = String(launch?.conversation_id || '');
    const scope = context?.chatMetadata?.homer_bridge;
    const character = context?.characters?.[context.characterId];
    const mirror = `Homer-${conversationId.replace(/[^a-zA-Z0-9_-]/g, '')}`;
    return Boolean(owner && appId && conversationId
        && reconcileStorageAccount() === owner
        && String(scope?.user_id || '') === owner
        && String(scope?.app_id || '') === appId
        && String(scope?.conversation_id || '') === conversationId
        && scope?.runtime === 'dialogue'
        && String(character?.data?.extensions?.homer_bridge?.app_id || '') === appId
        && String(context?.chatId || '') === mirror);
}

function assertCanonicalConversationScope() {
    if (conversationRecoveryBlocked || !hasCanonicalConversationScope()) {
        throw new Error('当前会话未能完整恢复，请重新进入后再操作');
    }
}

function captureConversationRecovery() {
    assertCanonicalConversationScope();
    const context = getContext();
    return {
        owner: String(session.user.id || session.user.user_id),
        epoch: storageAccountEpoch,
        characterId: String(context.characterId),
        avatar: String(context.characters[context.characterId]?.avatar || ''),
        chatId: String(context.chatId),
        chat: cloneJsonValue(context.chat),
        chatMetadata: cloneJsonValue(context.chatMetadata),
        // References detect untouched preflight failures without moving live
        // message/iframe DOM or cloning the multi-megabyte character card.
        chatReference: context.chat,
        metadataReference: context.chatMetadata,
        messageReferences: context.chat.slice(),
    };
}

function assertRecoveryAccount(snapshot) {
    if (!snapshot || reconcileStorageAccount() !== snapshot.owner
        || storageAccountEpoch !== snapshot.epoch) {
        throw new Error('会话账号已切换，请重新进入');
    }
}

function canonicalRecoveryIsUntouched(snapshot) {
    const context = getContext();
    return Boolean(snapshot && hasCanonicalConversationScope(context)
        && String(context.characterId) === snapshot.characterId
        && String(context.chatId) === snapshot.chatId
        && context.chat === snapshot.chatReference
        && context.chatMetadata === snapshot.metadataReference
        && context.chat.length === snapshot.messageReferences.length
        && context.chat.every((message, index) => message === snapshot.messageReferences[index]));
}

async function restoreCanonicalConversation(snapshot, beforeRender) {
    assertRecoveryAccount(snapshot);
    const characterId = getContext().characters.findIndex(character => (
        String(character?.data?.extensions?.homer_bridge?.app_id || '') === String(launch.app_id)
        && String(character?.avatar || '') === snapshot.avatar
    ));
    if (characterId < 0) throw new Error('原角色资料未能恢复，请重新进入');
    pendingCardScriptCharacter = null;
    await activateCharacterForChat(characterId, {
        chatName: snapshot.chatId, ephemeral: Boolean(launch.admin_preview),
    });
    assertRecoveryAccount(snapshot);
    const context = getContext();
    const metadata = cloneJsonValue(snapshot.chatMetadata);
    for (const key of Object.keys(context.chatMetadata)) delete context.chatMetadata[key];
    Object.assign(context.chatMetadata, metadata);
    context.chat.splice(0, context.chat.length, ...cloneJsonValue(snapshot.chat));
    await beforeRender();
    assertRecoveryAccount(snapshot);
    await context.printMessages({ scroll: false });
    assertRecoveryAccount(snapshot);
    await eventSource.emit(event_types.CHAT_CHANGED, context.chatId);
    assertRecoveryAccount(snapshot);
    await enableTavernHelperCardScripts(getContext().characters[characterId]);
    assertRecoveryAccount(snapshot);
    await eventSource.emit(event_types.CHAT_LOADED, context.chatId);
    assertRecoveryAccount(snapshot);
    if (!hasCanonicalConversationScope()) throw new Error('原会话状态未能完整恢复，请重新进入');
    scrollChatToBottom({ waitForFrame: true });
    scrollOnMediaLoad();
    queueMessageMenuRender();
}

function blockConversationRecovery(error, bootstrapToken = '') {
    conversationRecoveryBlocked = true;
    pendingCardScriptCharacter = null;
    window.clearTimeout(syncTimer); syncTimer = null;
    window.clearTimeout(extensionSettingsPersistTimer); extensionSettingsPersistTimer = null;
    window.clearTimeout(hostStateNotifyTimer); hostStateNotifyTimer = null;
    hostStateNotifyToken = null;
    extensionSettingsPersistWaiters.splice(0).forEach(waiter => waiter.resolve(false));
    document.body.classList.add('homer-runtime-error');
    setOnlineStatus('no_connection');
    failRuntimeGate(error);
    tavoComposer?.refresh();
    notifyHostError(bootstrapToken);
}

function captureCurrentChatStorage() {
    assertCanonicalConversationScope();
    return captureCloudSync(cloudSyncScope(), {
        app_id: launch.app_id,
        conversation_id: launch.conversation_id,
        title: String(launch?.card?.data?.name || launch?.card?.name || '角色对话'),
        messages: serializeChat(),
    });
}

async function commitConversationBeforeSwitch() {
    const epoch = storageAccountEpoch;
    const leavingLaunch = launch;
    window.clearTimeout(syncTimer); syncTimer = null;
    window.clearTimeout(extensionSettingsPersistTimer); extensionSettingsPersistTimer = null;
    // A running zero-delay settings replay can still be changing canonical
    // objects. Wait for that local work, never its remote network chain.
    await extensionSettingsReplayWork;
    if (launch?.admin_preview) return;
    if (reconcileStorageAccount() !== JSON.parse(cloudSyncScope())[0]) throw new Error('请重新登录后再切换会话');
    const chatSnapshot = captureCurrentChatStorage();
    const extensionSnapshot = captureExtensionStorage({ force: true });
    if (!extensionSnapshot) throw new Error('当前会话设置仍在恢复，已保留当前会话，请稍后再试');
    try {
        [chatSnapshot.committed, extensionSnapshot.snapshot.committed] = await Promise.all([
            chatOutbox.prepare(chatSnapshot), chatOutbox.prepare(extensionSnapshot.snapshot, 'extension-settings'),
        ]);
    } catch {
        throw new Error('本机存档未保存成功，已保留当前会话，请腾出存储空间后重试');
    }
    if (JSON.parse(chatSnapshot.scope)[0] !== reconcileStorageAccount()
        || epoch !== storageAccountEpoch || launch !== leavingLaunch) throw new Error('会话账号已切换，请重新进入');
    // Both full snapshots have completed their local transactions. Uploads keep
    // captured identities and do not delay activating another conversation.
    void cloudSyncQueue.enqueue(chatSnapshot).catch(() => {});
    const waiters = extensionSettingsPersistWaiters.splice(0);
    extensionSyncQueue.enqueue(extensionSnapshot.snapshot).then(
        acknowledgement => waiters.forEach(waiter => waiter.resolve(!acknowledgement.deferred)),
        error => waiters.forEach(waiter => waiter.reject(error)),
    );
}

async function syncCloudChat({ keepaliveOnly = false, localOnly = false } = {}) {
    if (launch?.admin_preview || suppressSync || !launch?.app_id || !launch?.conversation_id) return false;
    if (conversationRecoveryBlocked || !hasCanonicalConversationScope()) {
        if (localOnly) assertCanonicalConversationScope();
        return false;
    }
    const epoch = storageAccountEpoch;
    const snapshot = captureCurrentChatStorage();
    try {
        snapshot.committed = await chatOutbox.prepare(snapshot);
        if (localOnly) {
            if (JSON.parse(snapshot.scope)[0] === reconcileStorageAccount()
                && epoch === storageAccountEpoch && canApplyCloudSync(snapshot, cloudSyncScope(), serializeChat())) launch.local_pending = snapshot.committed.pending;
            void syncCloudChatSnapshot(snapshot, { keepaliveOnly });
            return true;
        }
        return await syncCloudChatSnapshot(snapshot, { keepaliveOnly });
    } catch {
        if (JSON.parse(snapshot.scope)[0] === reconcileStorageAccount() && epoch === storageAccountEpoch
            && snapshot.scope === cloudSyncScope()) updateRuntimeStatus('本机存档未保存，请勿退出', 'warning');
        if (localOnly) throw new Error('本机存档未保存成功，请腾出存储空间后重试');
        return false;
    }
}

async function syncCloudChatSnapshot(snapshot, { keepaliveOnly = false } = {}) {
    const epoch = storageAccountEpoch;
    try {
        const acknowledgement = await cloudSyncQueue.enqueue(snapshot, { keepaliveOnly });
        if (acknowledgement.deferred) return false;
        if (acknowledgement.skipped) {
            await acknowledgeStorage(snapshot.committed, acknowledgement.response);
        }
        // No late account/chat response may mutate the new active chat. Even
        // in the same scope, an older version must not overwrite newer IDs.
        if (JSON.parse(snapshot.scope)[0] !== reconcileStorageAccount()
            || epoch !== storageAccountEpoch || !canApplyCloudSync(snapshot, cloudSyncScope(), serializeChat())) return true;
        const result = acknowledgement.response;
        const context = getContext();
        result.messages.forEach((message, index) => {
            if (!context.chat[index]) return;
            context.chat[index].extra = {
                ...(context.chat[index].extra || {}),
                homer_message_id: String(message?.id || ''),
                homer_sync_id: String(message?.id || context.chat[index].extra?.homer_sync_id || ''),
                homer_created_at: Number(message?.created_at || context.chat[index].extra?.homer_created_at || Date.now()),
            };
        });
        lastSyncSignature = JSON.stringify(serializeChat());
        launch.local_pending = false;
        queueMessageMenuRender();
        if (!cloudSyncQueue.pending(snapshot.scope)) updateRuntimeStatus('云端已同步', 'online');
        return true;
    } catch {
        console.warn(`${MODULE_ID}: chat cloud save remains pending`);
        if (JSON.parse(snapshot.scope)[0] === reconcileStorageAccount() && epoch === storageAccountEpoch
            && snapshot.scope === cloudSyncScope()) updateRuntimeStatus('等待同步', 'warning');
        return false;
    }
}

async function commitConfirmedCloudMutation() {
    const snapshot = captureCurrentChatStorage();
    snapshot.committed = await chatOutbox.prepare(snapshot);
    const messages = snapshot.payload.messages.map(message => ({
        id: String(message.extra?.homer_message_id || message.extra?.homer_sync_id || ''),
        role: message.is_system && !message.extra?.homer_hidden ? 'system' : message.is_user ? 'user' : 'assistant',
        content: String(message.mes || ''), created_at: Number(message.extra?.homer_created_at || 0),
        swipes: message.swipes || [], swipe_index: Number(message.swipe_id || 0),
    }));
    await acknowledgeStorage(snapshot.committed, { messages });
    launch.local_pending = false;
}

function scheduleSync(delay = 900) {
    if (suppressSync) {
        return;
    }
    window.clearTimeout(syncTimer);
    syncTimer = window.setTimeout(syncCloudChat, delay);
}

function confirmHomerAction({
    id = 'homer-confirm-dialog',
    eyebrow = '当前对话',
    title = '确认操作',
    notice = '',
    confirmLabel = '确认',
    danger = false,
} = {}) {
    const existing = document.querySelector(`#${id}`);
    existing?.close();
    existing?.remove();
    const dialog = createElement('dialog', 'homer-sheet-dialog homer-confirm-dialog');
    dialog.id = id;
    const shell = createElement('form', 'homer-sheet-dialog__shell');
    shell.method = 'dialog';
    const head = createElement('header', 'homer-sheet-dialog__head');
    const copy = createElement('div');
    copy.append(
        createElement('div', 'homer-preset-panel__eyebrow', eyebrow),
        createElement('h2', 'homer-sheet-dialog__title', title),
    );
    head.append(copy);
    shell.append(
        head,
        createElement('p', 'homer-sheet-dialog__notice', notice),
    );
    const actions = createElement('footer', 'homer-sheet-dialog__actions');
    const cancel = createElement('button', 'homer-secondary-button', '取消');
    cancel.type = 'submit';
    cancel.value = 'cancel';
    const confirm = createElement(
        'button',
        danger ? 'homer-primary-button homer-danger-button' : 'homer-primary-button',
        confirmLabel,
    );
    confirm.type = 'submit';
    confirm.value = 'confirm';
    actions.append(cancel, confirm);
    shell.append(actions);
    dialog.append(shell);
    document.body.append(dialog);
    return new Promise(resolve => {
        dialog.addEventListener('close', () => {
            const accepted = dialog.returnValue === 'confirm';
            dialog.remove();
            resolve(accepted);
        }, { once: true });
        dialog.showModal();
    });
}

function confirmRollback(messageIndex) {
    return confirmHomerAction({
        id: 'homer-rollback-dialog',
        title: '确认回溯',
        notice: `将移除第 ${messageIndex + 1} 条及之后的消息；当前页面会立即更新，无需刷新。`,
        confirmLabel: '确认回溯',
        danger: true,
    });
}

async function rollbackToMessage(target, { askConfirmation = true } = {}) {
    let resolved = resolveMessageMenuTarget(target);
    let index = resolved?.messageIndex ?? -1;
    let message = resolved?.message || null;
    let messageId = cloudHomerMessageId(message);
    if (!message || !messageId) {
        showHostNotice('这条消息仍在同步，请稍后再回溯', 'warning');
        return false;
    }
    if (rollbackBusy || generationBusy || loadingLaunch) {
        showHostNotice(generationBusy ? '回复生成完成后才能回溯' : '当前操作尚未完成，请稍候', 'warning');
        return false;
    }
    if (askConfirmation && !await confirmRollback(index)) {
        return false;
    }

    resolved = resolveMessageMenuTarget(target);
    index = resolved?.messageIndex ?? -1;
    message = resolved?.message || null;
    messageId = cloudHomerMessageId(message);
    if (!message || !messageId) {
        showHostNotice('目标消息已经变化，未执行回溯', 'warning');
        return false;
    }

    rollbackBusy = true;
    document.body.classList.add('homer-rollback-busy');
    queueMessageMenuRender();
    const previousSuppressSync = suppressSync;
    try {
        if (!await syncCloudChat()) throw new Error('当前消息尚未同步，请联网后再回溯');
        const result = await requestJson(
            siteUrl(`/console/api/web/messages/${encodeURIComponent(messageId)}/rollback`),
            { method: 'POST', body: '{}' },
        );
        const context = getContext();
        suppressSync = true;
        context.chat.splice(index);
        if (Array.isArray(launch?.messages)) {
            const launchIndex = launch.messages.findIndex(item => String(item?.id || '') === messageId);
            if (launchIndex >= 0) {
                launch.messages.splice(launchIndex);
            }
        }
        try {
            await context.saveChat();
        } catch (error) {
            console.warn(`${MODULE_ID}: rolled-back local mirror was not saved`, error);
        }
        await context.printMessages();
        dialogueEventLogMuted += 1;
        try {
            await eventSource.emit(event_types.MESSAGE_DELETED, context.chat.length);
            await eventSource.emit(event_types.CHAT_LOADED, context.chatId);
        } finally {
            dialogueEventLogMuted = Math.max(0, dialogueEventLogMuted - 1);
        }
        lastSyncSignature = JSON.stringify(serializeChat());
        await commitConfirmedCloudMutation();
        await logDialogueEvent('rewind', index, message);
        closeMessageMenu();
        queueMessageMenuRender();
        updateRuntimeStatus('云端已同步', 'online');
        showHostNotice(`已回溯，移除 ${Number(result?.deleted_count || 0)} 条消息`, 'success');
        return true;
    } catch (error) {
        console.error(`${MODULE_ID}: rollback failed`, error);
        showHostNotice(String(error?.message || '回溯失败，请重试'), 'error');
        return false;
    } finally {
        suppressSync = previousSuppressSync;
        rollbackBusy = false;
        document.body.classList.remove('homer-rollback-busy');
        queueMessageMenuRender();
    }
}

async function loadRuntimeState(preparedRead = null, modelCatalogWork = Promise.resolve(), preparedRegex = null) {
    if (launch?.admin_preview) {
        runtimeVariables = {};
        replaceExtensionSettings(cloneJsonObject(extensionSettingsBaseline || {}));
        await refreshOfficialRegex();
        return;
    }
    const scope = cloudSyncScope();
    const owner = reconcileStorageAccount();
    const stateLaunch = launch;
    const epoch = storageAccountEpoch;
    const assertScope = () => {
        if (owner !== reconcileStorageAccount() || epoch !== storageAccountEpoch || launch !== stateLaunch
            || scope !== cloudSyncScope() || owner !== JSON.parse(scope)[0]) throw new Error('会话已切换，未应用旧配置');
    };
    assertScope();
    let read = preparedRead || prepareRuntimeState(stateLaunch.app_id, stateLaunch.conversation_id);
    if (read.owner !== owner || read.epoch !== epoch || read.scope !== scope) {
        throw new Error('会话已切换，未应用旧配置');
    }
    // A click can wait at the durable-leave barrier. The peer's deadline is
    // checked again at consumption, not just when it was taken from the cache.
    if (read.expiresAt !== undefined && read.expiresAt <= Date.now()) read = prepareRuntimeState(stateLaunch.app_id, stateLaunch.conversation_id);
    let outcome = await read.pending;
    assertScope();
    if (read.expiresAt !== undefined && read.expiresAt <= Date.now()) {
        read = prepareRuntimeState(stateLaunch.app_id, stateLaunch.conversation_id);
        outcome = await read.pending;
    }
    assertScope();
    if (outcome.error) throw outcome.error;
    const { state, fence } = outcome.value;
    const local = await chatOutbox.read(scope, 'extension-settings', fence);
    assertScope();
    if (read.expiresAt !== undefined && read.expiresAt <= Date.now()) {
        return loadRuntimeState(prepareRuntimeState(stateLaunch.app_id, stateLaunch.conversation_id), modelCatalogWork);
    }
    if (local?.preferred) state.extension_settings = local.payload.extension_settings;
    const savedExtensionSettings = state?.extension_settings
        && typeof state.extension_settings === 'object'
        && !Array.isArray(state.extension_settings)
        ? state.extension_settings
        : {};
    const restoredExtensionSettings = cloneJsonObject(extensionSettingsBaseline || {});
    if (Object.keys(savedExtensionSettings).length) {
        synchronizeJsonContainer(restoredExtensionSettings, savedExtensionSettings);
    }
    conversationExtensionSettings = cloneJsonObject(restoredExtensionSettings || {});
    replaceExtensionSettings(conversationExtensionSettings);
    runtimeVariables = state?.variables && typeof state.variables === 'object'
        ? { ...state.variables }
        : {};
    delete runtimeVariables.homer_preset_overrides;
    // Extensions that mirror settings into controls or module-local state have
    // already handled the native global load by this point. Re-emit the normal
    // loaded signal after applying the conversation overlay so those mirrors do
    // not later write stale global values back into the active conversation.
    const settingsLoaded = eventSource.emit(event_types.SETTINGS_LOADED);
    let regexModelId = '';
    const regexLoaded = (async () => {
        // The first catalog may still be arriving alongside the state read.
        // Never select an empty/default model just to start its regex sooner.
        await modelCatalogWork;
        assertScope();
        regexModelId = String(conversationModelSettings().model_id || '');
        await refreshOfficialRegex(regexModelId, preparedRegex);
    })();
    await Promise.all([settingsLoaded, regexLoaded]);
    assertScope();
    // Some third-party extensions finalize module-local defaults on APP_READY.
    // When the embedded bridge starts from the earlier core-ready signal, one
    // post-ready replay is required so those defaults cannot overwrite the
    // conversation-scoped state that was just restored.
    reaffirmExtensionSettingsAfterReady = !applicationReady;
    const extensionSnapshot = extensionSettingsSnapshot();
    lastExtensionSettingsScope = extensionSettingsScope();
    lastExtensionSettingsSignature = extensionSnapshot.signature;
    // A settings listener may legitimately select a different effective model.
    // Its response guard rejects the earlier rules; read the matching set now.
    const currentModelId = String(conversationModelSettings().model_id || '');
    if (currentModelId !== regexModelId) {
        await refreshOfficialRegex(currentModelId);
        assertScope();
    }
}

function prepareRuntimeState(appId, conversationId) {
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const targetAppId = String(appId || '').trim();
    const targetConversationId = String(conversationId || '').trim();
    const scope = JSON.stringify([owner, targetAppId, targetConversationId]);
    const assertOwner = () => {
        if (!owner || !targetAppId || !targetConversationId || owner !== reconcileStorageAccount()
            || epoch !== storageAccountEpoch) throw new Error('会话账号已切换，请重新进入');
    };
    // Capture the same outbox read fence as an ordinary state load, but start
    // this cookie-authenticated GET beside the durable leave/session work.
    // Nothing is applied until loadRuntimeState verifies the new live scope.
    const pending = (async () => {
        assertOwner();
        const fence = await chatOutbox.fence(scope, 'extension-settings');
        assertOwner();
        const state = await requestJson(`/api/homer/runtime-state?${queryString(targetAppId, targetConversationId)}`);
        assertOwner();
        return { state, fence };
    })().then(value => ({ value }), error => ({ error }));
    // A failed leave/session can discard this read before it is consumed.
    // The settled outcome must not create an unhandled rejected Promise.
    return Object.freeze({ owner, epoch, scope, pending });
}

function prepareConversationResources(appId, conversationId) {
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const scope = JSON.stringify([owner, String(appId || '').trim(), String(conversationId || '').trim()]);
    const cached = sessionPrefetchCache.get(sessionCacheKey(appId, conversationId));
    const retained = cached?.resources;
    if (cached?.expiresAt > Date.now() && retained?.owner === owner
        && retained.epoch === epoch && retained.scope === scope) return retained;
    const expiresAt = cached?.expiresAt > Date.now() ? cached.expiresAt : undefined;
    const state = Object.freeze({ ...prepareRuntimeState(appId, conversationId), expiresAt });
    const models = Object.freeze({ ...prepareRuntimeModels(appId, conversationId), expiresAt });
    const regex = Object.freeze({ owner, epoch, scope, expiresAt, pending: (async () => {
        const [stateResult, modelResult] = await Promise.all([state.pending, models.pending]);
        if (stateResult.error) throw stateResult.error;
        if (modelResult.error) throw modelResult.error;
        if (!owner || owner !== reconcileStorageAccount() || epoch !== storageAccountEpoch) throw new Error('会话账号已切换');
        const modelList = payloadList(modelResult.value).filter(item => item?.enabled !== false);
        const modelId = selectRuntimeModelId(stateResult.value.state?.variables, modelList, modelResult.value?.default_id);
        const params = new URLSearchParams({ app_id: String(appId).trim(), conversation_id: String(conversationId).trim(), model: modelId });
        const payload = await requestJson(`/api/homer/regex?${params}`);
        if (owner !== reconcileStorageAccount() || epoch !== storageAccountEpoch) throw new Error('会话账号已切换');
        return { modelId, payload };
    })().then(value => ({ value }), error => ({ error })) });
    const resources = Object.freeze({ owner, epoch, scope, state, models, regex, character: cached?.characterPreparation || null });
    // Lifetime and eviction exactly follow the two one-use session peers.
    // Never create an unbounded second cache of per-conversation settings.
    if (cached && cached.expiresAt > Date.now()) cached.resources = resources;
    void regex.pending.then(outcome => {
        if (outcome.error && cached?.resources === resources) delete cached.resources;
    });
    return resources;
}

async function refreshOfficialRegex(modelId = '', preparedRead = null) {
    if (launch?.admin_preview) {
        // Fail closed: do not generate with silently stale admin settings.
        await refreshAdminConfiguration(modelId);
        return;
    }
    const regexLaunch = launch;
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const selectedId = String(modelId || conversationModelSettings().model_id || '');
    const current = () => launch === regexLaunch && owner === reconcileStorageAccount()
        && epoch === storageAccountEpoch && selectedId === String(conversationModelSettings().model_id || '');
    setOfficialDisplayRules({ scripts: [] });
    const params = new URLSearchParams({ app_id: launch.app_id, model: selectedId });
    if (!launch.admin_preview) params.set('conversation_id', launch.conversation_id);
    try {
        let prepared;
        if (preparedRead?.owner === owner && preparedRead.epoch === epoch
            && (preparedRead.expiresAt === undefined || preparedRead.expiresAt > Date.now())
            && preparedRead.scope === cloudSyncScope()) {
            const outcome = await preparedRead.pending;
            if (!current()) return;
            if (!outcome.error && outcome.value?.modelId === selectedId
                && (preparedRead.expiresAt === undefined || preparedRead.expiresAt > Date.now())) prepared = outcome.value.payload;
        }
        // Model edits, expiry, failed preparation and every generation use a
        // fresh authorized read; a peer's old model never supplies its rules.
        const payload = prepared || await requestJson(`/api/homer/regex?${params}`);
        if (!current()) return;
        officialRegexState = setOfficialDisplayRules(payload);
        if (officialRegexState.errors.length) showHostNotice(`[HM-R422] ${officialRegexState.errors.length} 条官方正则语法无效，请管理员检查`, 'error');
    } catch (error) {
        if (!current()) return;
        officialRegexState = { count: 0, errors: ['HM-R503'] };
        showHostNotice('[HM-R503] 官方展示规则读取失败，请重试或联系管理员更新服务', 'warning');
    }
}

async function persistRuntimeVariables() {
    if (launch?.admin_preview) return;
    const context = getContext();
    delete context.chatMetadata.homer_preset_overrides;
    context.chatMetadata.homer_model_settings = { ...conversationModelSettings() };
    await requestJson('/api/homer/runtime-state', {
        method: 'POST',
        body: JSON.stringify({
            app_id: launch.app_id,
            conversation_id: launch.conversation_id,
            variables: runtimeVariables,
        }),
    });
}

async function persistModelSettings(settings) {
    runtimeVariables = {
        ...runtimeVariables,
        homer_model_settings: {
            model_id: String(settings.model_id || ''),
            temperature: clampNumber(settings.temperature, 0, 2, 1),
            top_p: clampNumber(settings.top_p, 0, 1, 1),
            frequency_penalty: clampNumber(settings.frequency_penalty, -2, 2, 0),
            presence_penalty: clampNumber(settings.presence_penalty, -2, 2, 0),
        },
    };
    await persistRuntimeVariables();
    await refreshOfficialRegex(settings.model_id);
    confirmModelChange(settings.model_id);
    applyConnectionConfiguration();
    if (launch?.conversation_id && !launch.admin_preview) {
        launch.runtime_config = await requestJson(
            `/api/homer/conversations/${encodeURIComponent(launch.conversation_id)}/runtime-config`,
        );
        renderPresetLists(presetSearchQuery);
    }
    scheduleHostStateNotify(0, 'model-settings');
}

function payloadList(payload) {
    if (Array.isArray(payload)) {
        return payload;
    }
    return Array.isArray(payload?.list) ? payload.list : [];
}

function prepareRuntimeModels(appId, conversationId) {
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const scope = JSON.stringify([owner, String(appId || ''), String(conversationId || '')]);
    const assertOwner = () => {
        if (!owner || owner !== reconcileStorageAccount() || epoch !== storageAccountEpoch) {
            throw new Error('会话账号已切换，未应用旧模型目录');
        }
    };
    // Fresh cookie-authenticated catalog, not a stale/background replacement.
    // Start beside the durable leave; consume only after the target is bound.
    const pending = (async () => {
        assertOwner();
        const payload = await requestJson('/api/homer/models');
        assertOwner();
        return payload;
    })().then(value => ({ value }), error => ({ error }));
    return Object.freeze({ owner, epoch, scope, pending });
}

async function loadRuntimeUiData(preparedRead = null) {
    const stateLaunch = launch;
    const owner = reconcileStorageAccount();
    const epoch = storageAccountEpoch;
    const conversationId = String(launch?.conversation_id || '');
    const scope = JSON.stringify([owner, String(launch?.app_id || ''), conversationId]);
    let read = preparedRead || prepareRuntimeModels(launch?.app_id, conversationId);
    if (read.owner !== owner || read.epoch !== epoch || read.scope !== scope) {
        throw new Error('会话已切换，未应用旧模型目录');
    }
    // Optional Mod requests must not hold conversation startup hostage.
    void loadConversationMods();
    if (read.expiresAt !== undefined && read.expiresAt <= Date.now()) read = prepareRuntimeModels(stateLaunch.app_id, conversationId);
    let outcome = await read.pending;
    if (launch !== stateLaunch || owner !== reconcileStorageAccount() || epoch !== storageAccountEpoch) return;
    if (read.expiresAt !== undefined && read.expiresAt <= Date.now()) {
        read = prepareRuntimeModels(stateLaunch.app_id, conversationId);
        outcome = await read.pending;
    }
    if (launch !== stateLaunch || owner !== reconcileStorageAccount() || epoch !== storageAccountEpoch) return;
    // Keep the existing unavailable-catalog behavior; never adopt an old
    // request's model IDs after switching target or logging out/relogging in.
    const payload = outcome.error ? {} : outcome.value;
    runtimeUiData = { ...runtimeUiData, models: payloadList(payload).filter(item => item?.enabled !== false), modelDefaultId: String(payload?.default_id || '') };
}

let modLoadController;
async function loadConversationMods() {
    modLoadController?.abort();
    const controller = new AbortController();
    modLoadController = controller;
    const conversationId = String(launch?.conversation_id || '');
    runtimeUiData = { ...runtimeUiData, mods: [], activeModIds: [], modsLoading: true, modsError: '' };
    refreshModDialog();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
        const [library, active] = await Promise.all([
            requestJson('/api/homer/mods/library', { signal: controller.signal }),
            launch?.admin_preview ? Promise.resolve({ list: (adminConversationDraft.mod_ids || []).map(id => ({ id })) })
                : requestJson('/api/homer/mods/conversation/' + encodeURIComponent(conversationId), { signal: controller.signal }),
        ]);
        if (modLoadController !== controller || String(launch?.conversation_id || '') !== conversationId) return;
        runtimeUiData.mods = payloadList(library);
        runtimeUiData.activeModIds = payloadList(active).map(item => String(item?.id || item?.mod_id || '')).filter(Boolean);
    } catch {
        if (modLoadController !== controller || String(launch?.conversation_id || '') !== conversationId) return;
        runtimeUiData.modsError = 'Mod 暂时无法读取，请重试。现有配置没有更改。';
    } finally {
        clearTimeout(timeout);
        if (modLoadController === controller && String(launch?.conversation_id || '') === conversationId) {
            runtimeUiData.modsLoading = false;
            refreshModDialog();
        }
    }
}

function refreshModDialog() {
    const old = document.querySelector('#homer-mod-dialog');
    if (!old) return;
    const opened = old.open;
    old.close();
    const next = buildModDialog();
    old.replaceWith(next);
    if (opened) next.showModal();
    const summary = document.querySelector('#homer-mod-summary');
    if (summary) summary.textContent = runtimeUiData.modsLoading ? '正在读取' : runtimeUiData.modsError ? '读取失败，点此重试' : runtimeUiData.activeModIds.length + ' 个已启用';
}

async function loadConversationHistory() {
    if (launch?.admin_preview) return;
    try {
        const conversationsPayload = await requestJson('/api/homer/conversations');
        runtimeUiData = {
            ...runtimeUiData,
            conversations: payloadList(conversationsPayload),
        };
        populateHistoryList(
            document.querySelector('#homer-history-count'),
            document.querySelector('#homer-history-list'),
        );
        scheduleHostStateNotify(0, 'history');
        scheduleSessionPrefetch();
    } catch (error) {
        console.warn(`${MODULE_ID}: conversation history load failed`, error);
    }
}

function formatConversationTime(value) {
    const timestamp = Number(value || 0);
    if (!timestamp) {
        return '';
    }
    const delta = Date.now() - timestamp;
    if (delta < 60_000) {
        return '刚刚';
    }
    if (delta < 3_600_000) {
        return `${Math.max(1, Math.floor(delta / 60_000))} 分钟前`;
    }
    if (delta < 86_400_000) {
        return `${Math.max(1, Math.floor(delta / 3_600_000))} 小时前`;
    }
    return new Intl.DateTimeFormat('zh-CN', {
        month: 'numeric',
        day: 'numeric',
    }).format(new Date(timestamp));
}

function presetGroups() {
    const preset = launch?.runtime_config?.preset && typeof launch.runtime_config.preset === 'object'
        ? launch.runtime_config.preset
        : {};
    const current = preset.current_prompt || preset.prompt || {};
    const definitions = [{
        kind: String(current.kind || 'global_prompt'),
        label: '当前预设',
        description: '当前模型实际使用的唯一预设',
        config: current,
    }];
    return definitions.map(group => {
        const config = group.config && typeof group.config === 'object' ? group.config : {};
        const presetId = String(config.preset_id || '');
        const entries = Array.isArray(config.entries)
            ? config.entries.map((entry, index) => ({
                ...entry,
                id: String(entry?.id || ''),
                name: String(entry?.name || entry?.id || `条目 ${index + 1}`),
                role: String(entry?.role || 'system'),
                position: String(entry?.position || 'system_before'),
                enabled: Boolean(entry?.enabled),
                inheritedEnabled: Boolean(entry?.inherited_enabled),
                overridden: Boolean(entry?.overridden),
                locked: Boolean(entry?.locked || entry?.toggleable === false),
                toggleable: Boolean(entry?.toggleable && !entry?.locked),
                lockedReason: String(entry?.locked_reason || ''),
                kind: group.kind,
                groupLabel: group.label,
                presetId,
            })).filter(entry => entry.id)
            : [];
        return {
            ...group,
            presetId,
            name: String(config.name || group.label),
            enabled: Boolean(config.enabled),
            entries,
        };
    });
}

async function togglePreset(entry, enabled) {
    if (launch?.admin_preview) return;
    if (!entry?.toggleable || !entry?.presetId || !launch?.conversation_id) {
        return;
    }
    const result = await requestJson(
        `/api/homer/conversations/${encodeURIComponent(launch.conversation_id)}/preset-overrides`,
        {
            method: 'POST',
            body: JSON.stringify({
                preset_kind: entry.kind,
                preset_id: entry.presetId,
                items: [{ entry_id: entry.id, enabled: Boolean(enabled) }],
            }),
        },
    );
    if (result?.runtime_config && typeof result.runtime_config === 'object') {
        launch.runtime_config = result.runtime_config;
    } else {
        launch.runtime_config = await requestJson(
            `/api/homer/conversations/${encodeURIComponent(launch.conversation_id)}/runtime-config`,
        );
    }
    await refreshOfficialRegex();
    await getContext().printMessages();
    renderPresetLists(presetSearchQuery);
}

function createElement(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) {
        element.className = className;
    }
    if (text) {
        element.textContent = text;
    }
    return element;
}

function createPresetRow(entry) {
    const row = createElement('label', 'homer-preset-row');
    row.classList.toggle('is-locked', !entry.toggleable);
    const copy = createElement('span', 'homer-preset-row__copy');
    const title = createElement('span', 'homer-preset-row__name', entry.name);
    const positionLabel = entry.position === 'post_history' ? '历史后' : '系统提示';
    const stateLabel = entry.overridden ? '当前对话已调整' : '默认状态';
    const lockLabel = entry.toggleable ? '' : ` · ${entry.lockedReason || '只读条目'}`;
    const meta = createElement(
        'span',
        'homer-preset-row__meta',
        `${stateLabel}${lockLabel}`,
    );
    copy.append(title, meta);
    if (entry.toggleable) {
        const control = createElement('span', 'homer-switch');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = entry.enabled;
        input.setAttribute('aria-label', `${entry.name} ${entry.enabled ? '已开启' : '已关闭'}`);
        const slider = createElement('span', 'homer-switch__track');
        input.addEventListener('change', () => {
            const nextEnabled = input.checked;
            input.disabled = true;
            void togglePreset(entry, nextEnabled).catch(error => {
                input.checked = entry.enabled;
                showHostNotice(String(error?.message || '预设条目保存失败'), 'error');
            }).finally(() => {
                input.disabled = false;
            });
        });
        control.append(input, slider);
        row.append(copy, control);
    } else {
        row.append(copy, createElement('span', 'homer-preset-row__state', entry.enabled ? '已启用' : '已停用'));
    }
    return row;
}

function renderPresetContainer(container, groups, query, quick = false) {
    if (!container) {
        return;
    }
    const sections = [];
    for (const group of groups) {
        const matching = query
            ? group.entries.filter(item => `${item.name} ${item.role} ${item.lockedReason}`.toLocaleLowerCase().includes(query))
            : group.entries;
        if (query && !matching.length) {
            continue;
        }
        const section = createElement('section', 'homer-preset-group');
        const head = createElement('header', 'homer-preset-group__head');
        const copy = createElement('span', 'homer-preset-group__copy');
        copy.append(
            createElement('strong', '', group.label),
            createElement('small', '', `${group.name}${group.enabled ? '' : ' · 整体未启用'}`),
        );
        head.append(copy, createElement('span', 'homer-preset-group__count', `${matching.length} 条`));
        section.append(head);
        const values = matching;
        if (values.length) {
            const list = createElement('div', 'homer-preset-group__list');
            list.append(...values.map(createPresetRow));
            section.append(list);
            if (quick && matching.length > values.length) {
                section.append(createElement('div', 'homer-preset-group__more', `另有 ${matching.length - values.length} 条，请展开查看`));
            }
        } else {
            section.append(createElement(
                'div',
                'homer-empty',
                '当前预设没有向用户开放可切换条目',
            ));
        }
        sections.push(section);
    }
    container.replaceChildren(...sections);
    if (!sections.length) {
        container.append(createElement('div', 'homer-empty', '没有找到匹配的预设条目'));
    }
}

function renderPresetLists(filter = presetSearchQuery) {
    presetSearchQuery = String(filter || '').trim();
    const groups = presetGroups();
    const entries = groups.flatMap(group => group.entries);
    const query = String(filter || '').trim().toLocaleLowerCase();
    const quick = document.querySelector('#homer-preset-quick-list');
    const full = document.querySelector('#homer-preset-full-list');
    const count = document.querySelector('#homer-preset-count');
    const summary = document.querySelector('#homer-preset-summary');
    const toggleable = entries.filter(item => item.toggleable);
    const enabledCount = toggleable.filter(item => item.enabled).length;
    if (count) {
        count.textContent = `${enabledCount}/${toggleable.length} 可切换项已开启`;
    }
    if (summary) {
        summary.textContent = `${enabledCount}/${toggleable.length} 已开启 · 仅本次会话`;
    }
    renderPresetContainer(quick, groups, query, true);
    renderPresetContainer(full, groups, query, false);
}

function updateRuntimeStatus(text, state = 'online') {
    const status = document.querySelector('#homer-runtime-status');
    if (!status) {
        return;
    }
    status.textContent = text;
    status.dataset.state = state;
}

function setPanelOpen(open) {
    const panel = document.querySelector('#homer-preset-panel');
    if (panel) {
        panel.hidden = !open;
    }
    if (open) {
        renderPresetLists();
    }
}

function setFullDialogOpen(open) {
    const dialog = document.querySelector('#homer-preset-dialog');
    if (!dialog) {
        return;
    }
    if (open && !dialog.open) {
        dialog.showModal();
        renderPresetLists();
    } else if (!open && dialog.open) {
        dialog.close();
    }
}

function cloudHomerMessageId(message) {
    const extra = message?.extra && typeof message.extra === 'object' ? message.extra : {};
    return String(
        extra.homer_message_id
        || message?.homer_message_id
        || '',
    ).trim().slice(0, 160);
}

function stableHomerMessageId(message) {
    const extra = message?.extra && typeof message.extra === 'object' ? message.extra : {};
    return String(
        cloudHomerMessageId(message)
        || extra.homer_sync_id
        || '',
    ).trim().slice(0, 160);
}

function homerMessageId(message, index = -1) {
    return stableHomerMessageId(message) || (index >= 0 ? `message-${index}` : '');
}

async function logDialogueEvent(eventType, messageIndex = -1, messageOverride = null) {
    if (launch?.admin_preview) return;
    if (dialogueEventLogMuted || !launch?.app_id || !launch?.conversation_id) {
        return;
    }
    const context = getContext();
    const fallbackIndex = context.chat.length ? context.chat.length - 1 : -1;
    const index = Number.isInteger(Number(messageIndex)) && Number(messageIndex) >= 0
        ? Number(messageIndex)
        : fallbackIndex;
    const message = messageOverride || (index >= 0 ? context.chat[index] : null);
    const eventId = globalThis.crypto?.randomUUID?.()
        || `evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
    const payload = {
        event_id: eventId,
        event_type: String(eventType || ''),
        app_id: launch.app_id,
        conversation_id: launch.conversation_id,
        message_id: homerMessageId(message, index),
    };
    for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
            await requestJson('/api/homer/events', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            return;
        } catch (error) {
            if (attempt === 1) {
                console.warn(`${MODULE_ID}: dialogue event log failed`, eventType, error);
                return;
            }
            await new Promise(resolve => window.setTimeout(resolve, 350));
        }
    }
}

function messageIndexFromElement(element) {
    const raw = element?.getAttribute?.('mesid');
    const index = Number(raw);
    return Number.isInteger(index) && index >= 0 ? index : -1;
}

function messageMenuTargetForIndex(messageIndex, element = null, anchor = {}) {
    const context = getContext();
    const index = Number(messageIndex);
    const message = Number.isInteger(index) && index >= 0 ? context.chat[index] : null;
    if (!message || (message.is_system && !message.extra?.homer_hidden)) {
        return null;
    }
    return {
        messageIndex: index,
        messageId: stableHomerMessageId(message),
        messageRef: message,
        message,
        isUser: Boolean(message?.is_user),
        element: element || document.querySelector(`#chat .mes[mesid="${index}"]`),
        anchorX: Number.isFinite(Number(anchor?.x)) ? Number(anchor.x) : null,
        anchorY: Number.isFinite(Number(anchor?.y)) ? Number(anchor.y) : null,
    };
}

function messageMenuTargetFromElement(element, anchor = {}) {
    return messageMenuTargetForIndex(messageIndexFromElement(element), element, anchor);
}

function resolveMessageMenuTarget(target) {
    if ((typeof target === 'number' || typeof target === 'string') && Number.isInteger(Number(target))) {
        return messageMenuTargetForIndex(Number(target));
    }
    if (!target || typeof target !== 'object') {
        return null;
    }
    const context = getContext();
    const expectedId = String(target.messageId || '').trim();
    const matches = message => Boolean(
        message
        && (!message.is_system || message.extra?.homer_hidden)
        && (
            (target.messageRef && message === target.messageRef)
            || (expectedId && stableHomerMessageId(message) === expectedId)
        )
    );
    let index = Number(target.messageIndex);
    let message = Number.isInteger(index) && index >= 0 ? context.chat[index] : null;
    if (!matches(message)) {
        index = expectedId
            ? context.chat.findIndex(item => stableHomerMessageId(item) === expectedId)
            : -1;
        if (index < 0 && target.messageRef) {
            index = context.chat.indexOf(target.messageRef);
        }
        message = index >= 0 ? context.chat[index] : null;
    }
    if (!message || (message.is_system && !message.extra?.homer_hidden)) {
        return null;
    }
    const element = document.querySelector(`#chat .mes[mesid="${index}"]`);
    return {
        ...target,
        messageIndex: index,
        messageId: stableHomerMessageId(message),
        messageRef: message,
        message,
        isUser: Boolean(message?.is_user),
        element,
    };
}

async function truncateAfterMessage(target, actionLabel = '继续操作') {
    let resolved = resolveMessageMenuTarget(target);
    if (!resolved) {
        throw new Error('目标消息已经变化，请重新打开消息菜单');
    }
    const context = getContext();
    let trailingCount = context.chat.length - resolved.messageIndex - 1;
    if (trailingCount <= 0) {
        return true;
    }
    const confirmed = await confirmHomerAction({
        id: 'homer-timeline-confirm-dialog',
        title: `${actionLabel}前需要回溯`,
        notice: `将保留这条消息，并移除其后的 ${trailingCount} 条内容。当前页面会立即更新。`,
        confirmLabel: '回溯并继续',
        danger: true,
    });
    if (!confirmed) {
        return false;
    }
    resolved = resolveMessageMenuTarget(target);
    if (!resolved) {
        throw new Error('目标消息已经变化，未执行操作');
    }
    trailingCount = context.chat.length - resolved.messageIndex - 1;
    if (trailingCount <= 0) {
        return true;
    }
    const previousSuppressSync = suppressSync;
    suppressSync = true;
    dialogueEventLogMuted += 1;
    try {
        while (context.chat.length - 1 > resolved.messageIndex) {
            await context.deleteLastMessage();
        }
        await context.saveChat();
    } finally {
        dialogueEventLogMuted = Math.max(0, dialogueEventLogMuted - 1);
        suppressSync = previousSuppressSync;
    }
    if (!previousSuppressSync) {
        scheduleSync(0);
    }
    return true;
}

function messageMenuActions(resolved) {
    return [
        { id: 'image', label: '生图', icon: 'fa-regular fa-image' },
        { id: 'copy', label: '复制', icon: 'fa-regular fa-copy' },
        { id: 'edit', label: '改写', icon: 'fa-solid fa-pen' },
        { id: 'rollback', label: '回溯', icon: 'fa-solid fa-clock-rotate-left', cloud: true },
        { id: 'delete', label: '删除', icon: 'fa-regular fa-trash-can', cloud: true, danger: true },
        { id: 'hide', label: resolved?.message?.extra?.homer_hidden ? '取消隐藏' : '隐藏', icon: 'fa-regular fa-eye' },
        { id: 'select', label: '多选', icon: 'fa-solid fa-list-check' },
        { id: 'collapse', label: resolved?.message?.extra?.homer_collapsed ? '展开' : '折叠', icon: 'fa-solid fa-angles-down' },
        ...(!resolved?.isUser ? [
            { id: 'regenerate', label: '重写', icon: 'fa-solid fa-rotate-right' },
            { id: 'continue', label: '续写', icon: 'fa-solid fa-forward' },
        ] : []),
    ];
}

function ensureMessageMenuDialog() {
    let dialog = document.querySelector('#homer-message-menu-dialog');
    if (dialog) {
        return dialog;
    }
    dialog = createElement('dialog', 'homer-message-menu-dialog');
    dialog.id = 'homer-message-menu-dialog';
    dialog.setAttribute('aria-label', '消息操作');
    const shell = createElement('section', 'homer-message-menu__shell');
    const actions = createElement('div', 'homer-message-menu__actions');
    actions.setAttribute('role', 'menu');
    shell.append(actions);
    dialog.append(shell);
    // Opening a modal mid-touch makes Android send the original release click
    // to its backdrop (or a button underneath the finger). Consume only that
    // inherited click; a fresh pointerdown is an explicit new user action.
    dialog.addEventListener('pointerdown', () => {
        suppressMessageMenuPressRelease = false;
        suppressMessageClickUntil = 0;
    }, true);
    dialog.addEventListener('click', event => {
        if (!suppressMessageMenuPressRelease) return;
        suppressMessageMenuPressRelease = false;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    new ResizeObserver(() => {
        if (dialog.open && activeMessageMenuTarget) {
            positionMessageMenuDialog(dialog, resolveMessageMenuTarget(activeMessageMenuTarget));
        }
    }).observe(dialog);
    dialog.addEventListener('click', event => {
        if (event.target === dialog) {
            closeMessageMenu();
            return;
        }
        const button = event.target instanceof Element
            ? event.target.closest('[data-homer-message-menu-action]')
            : null;
        if (!button || button.disabled) {
            return;
        }
        const target = activeMessageMenuTarget;
        const action = String(button.dataset.homerMessageMenuAction || '');
        closeMessageMenu();
        void handleMessageMenuAction(action, target);
    });
    dialog.addEventListener('close', () => {
        activeMessageMenuTarget = null;
        suppressMessageMenuPressRelease = false;
        dialog.classList.remove('is-positioning');
        dialog.style.removeProperty('left');
        dialog.style.removeProperty('top');
        document.body.classList.remove('homer-message-menu-open');
    });
    document.body.append(dialog);
    return dialog;
}

function closeMessageMenu() {
    const dialog = document.querySelector('#homer-message-menu-dialog');
    if (dialog?.open) {
        dialog.close();
    } else {
        activeMessageMenuTarget = null;
        document.body.classList.remove('homer-message-menu-open');
    }
}

function positionMessageMenuDialog(dialog, resolved) {
    if (!dialog?.open) {
        dialog?.classList.remove('is-positioning');
        return;
    }
    const anchorElement = resolved?.element;
    const rect = anchorElement?.getBoundingClientRect?.();
    if (!rect) {
        dialog.classList.remove('is-positioning');
        return;
    }
    let header = document.querySelector('.homer-chat-header');
    let composer = document.querySelector('#form_sheld');
    if (document.documentElement.classList.contains('homer-host-chrome')) {
        // The visible controls belong to the permanent same-origin host, not
        // the offscreen canonical composer retained for engine event guards.
        header = composer = null;
        try {
            header = window.parent.document.querySelector('.preview-header');
            composer = window.parent.document.querySelector('#shared-composer');
        } catch { /* No cross-origin access is needed for standalone runtime. */ }
    }
    positionChatMenu(dialog, anchorElement, {
        header,
        composer,
        isUser: resolved?.isUser,
        pressY: resolved?.anchorY,
    });
    dialog.classList.remove('is-positioning');
}

function renderMessageMenuDialog() {
    const dialog = ensureMessageMenuDialog();
    if (!activeMessageMenuTarget) {
        return;
    }
    const resolved = resolveMessageMenuTarget(activeMessageMenuTarget);
    if (!resolved) {
        if (dialog.open) {
            closeMessageMenu();
        }
        return;
    }
    activeMessageMenuTarget = resolved;
    const actions = dialog.querySelector('.homer-message-menu__actions');
    const swipes = Array.isArray(resolved.message?.swipes) ? resolved.message.swipes : [];
    const swipeCount = Math.max(swipes.length, 1);
    const swipeIndex = Math.max(0, Math.min(Number(resolved.message?.swipe_id || 0), swipeCount - 1));
    dialog.dataset.messageIndex = String(resolved.messageIndex);
    dialog.dataset.messageId = cloudHomerMessageId(resolved.message) || resolved.messageId || '';
    dialog.dataset.messageRole = resolved.isUser ? 'user' : 'assistant';
    const busy = generationBusy || rollbackBusy || loadingLaunch;
    const cloudReady = Boolean(cloudHomerMessageId(resolved.message));
    const buttons = messageMenuActions(resolved).map(action => {
        const button = createElement(
            'button',
            `homer-message-menu__action${action.danger ? ' is-danger' : ''}`,
        );
        button.type = 'button';
        button.setAttribute('role', 'menuitem');
        button.dataset.homerMessageMenuAction = action.id;
        const disabledBySwipe = action.id === 'swipe-left' && swipeIndex <= 0;
        const disabled = (busy && action.id !== 'copy') || (action.cloud && !cloudReady) || disabledBySwipe;
        button.disabled = disabled;
        button.setAttribute('aria-disabled', String(disabled));
        if (action.cloud && !cloudReady) {
            button.title = '这条消息同步到云端后可用';
        }
        const icon = messageActionIcon(action.id);
        icon.classList.add('homer-message-menu__icon');
        button.append(
            icon,
            createElement('span', 'homer-message-menu__label', action.label),
        );
        return button;
    });
    actions.replaceChildren(...buttons);
    dialog.dataset.actionCount = String(buttons.length);
    if (dialog.open) {
        requestAnimationFrame(() => positionMessageMenuDialog(dialog, resolved));
    }
}

function openMessageMenu(target, { suppressRelease = false } = {}) {
    window.getSelection?.()?.removeAllRanges?.();
    const resolved = resolveMessageMenuTarget(target);
    if (!resolved) {
        showHostNotice('目标消息已经变化，请重新长按', 'warning');
        return;
    }
    const dialog = ensureMessageMenuDialog();
    suppressMessageMenuPressRelease = suppressRelease;
    activeMessageMenuTarget = resolved;
    dialog.classList.add('is-positioning');
    renderMessageMenuDialog();
    document.body.classList.add('homer-message-menu-open');
    if (!dialog.open) {
        dialog.showModal();
    }
    requestAnimationFrame(() => {
        renderMessageMenuDialog();
        dialog.querySelector('.homer-message-menu__action:not(:disabled)')?.focus({ preventScroll: true });
    });
}

function normalizeCharacterVersionLabel(value) {
    const raw = String(value || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    if (!raw) {
        return '';
    }
    if (/^version\s+/i.test(raw)) {
        return `v${raw.replace(/^version\s+/i, '')}`;
    }
    if (/^v\s*\d/i.test(raw)) {
        return raw.replace(/^v\s*/i, 'v');
    }
    if (/^\d+(?:\.\d+)*(?:\b|\s|·|-)/.test(raw)) {
        return `v${raw}`;
    }
    return raw;
}

function currentCharacterVersionLabel() {
    const data = launch?.card?.data && typeof launch.card.data === 'object'
        ? launch.card.data
        : {};
    const version = launch?.version && typeof launch.version === 'object'
        ? launch.version
        : {};
    const candidates = [
        data.character_version,
        version.version_name,
        version.label,
        Number(version.version_no) > 0 ? `v${Number(version.version_no)}` : '',
    ];
    for (const candidate of candidates) {
        const label = normalizeCharacterVersionLabel(candidate);
        if (label) {
            return label;
        }
    }
    return '';
}

function messageHeaderName(message) {
    const raw = String(
        message?.name
        || (message?.is_user ? session?.user?.name : currentRoleName())
        || (message?.is_user ? '你' : '角色'),
    ).replace(/\s+/g, ' ').trim().slice(0, 120);
    if (message?.is_user || /^《.+》/.test(raw)) {
        return raw;
    }
    return `《${raw}》`;
}

function createMessageHeaderTimeFormatter() {
    return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hourCycle: 'h23',
    });
}

function messageHeaderTime(message, getFormatter = createMessageHeaderTimeFormatter) {
    const raw = message?.send_date || message?.extra?.homer_created_at || '';
    let date;
    if (typeof raw === 'number' || /^\d+$/.test(String(raw))) {
        let timestamp = Number(raw || 0);
        if (timestamp > 0 && timestamp < 1_000_000_000_000) {
            timestamp *= 1000;
        }
        date = new Date(timestamp);
    } else {
        date = new Date(String(raw || ''));
    }
    if (!Number.isFinite(date.getTime())) {
        return '';
    }
    return getFormatter().format(date).replace(/\s+/g, ' ').trim();
}

function setTextIfChanged(element, text) {
    if (element && element.textContent !== text) {
        element.textContent = text;
    }
}

function decorateMessageHeader(messageElement, message, messageIndex, getTimeFormatter) {
    const header = messageElement.querySelector('.ch_name');
    const nameText = header?.querySelector('.name_text');
    const timestamp = header?.querySelector('.timestamp');
    const meta = nameText?.parentElement;
    if (!header || !nameText || !timestamp || !meta) {
        return;
    }

    setTextIfChanged(nameText, messageHeaderName(message));
    setTextIfChanged(timestamp, messageHeaderTime(message, getTimeFormatter));
    timestamp.setAttribute('aria-label', `消息时间：${timestamp.textContent || '未知'}`);

    let version = meta.querySelector('.homer-message-version');
    const versionLabel = message?.is_user ? '' : currentCharacterVersionLabel();
    if (versionLabel) {
        if (!version) {
            version = createElement('span', 'homer-message-version');
            timestamp.before(version);
        }
        setTextIfChanged(version, versionLabel);
        version.title = `当前角色版本：${versionLabel}`;
    } else {
        version?.remove();
    }

    let help = meta.querySelector('.homer-message-help');
    if (!help) {
        help = createElement('button', 'homer-message-help', '?');
        help.type = 'button';
        timestamp.after(help);
    }
    help.title = '查看这条消息的可用操作';
    help.setAttribute('aria-label', `查看第 ${messageIndex + 1} 条消息的操作帮助`);

    const more = header.querySelector('.extraMesButtonsHint');
    if (more) {
        more.classList.add('homer-message-more');
        more.title = '更多消息操作';
        more.tabIndex = 0;
        more.setAttribute('role', 'button');
        more.setAttribute('aria-label', `打开第 ${messageIndex + 1} 条消息的更多操作`);
    }
    const edit = header.querySelector('.mes_edit');
    if (edit) {
        edit.title = '编辑这条消息';
        edit.tabIndex = 0;
        edit.setAttribute('role', 'button');
        edit.setAttribute('aria-label', `编辑第 ${messageIndex + 1} 条消息`);
    }
    header.dataset.homerMessageHeader = 'true';
    header.dataset.homerMessageVersion = versionLabel;
}

function renderOpeningNavigation(element, message, index, editing) {
    const card = launch?.card?.data || launch?.card || {};
    const authored = Array.isArray(card.alternate_greetings) ? card.alternate_greetings : [];
    const swipes = Array.isArray(message?.swipes) ? message.swipes : [];
    const eligible = index === 0 && !message?.is_user && !message?.is_system && !editing
        && authored.length && swipes.length > 1
        && String(swipes[0]).trim() === String(card.first_mes || '').trim();
    let nav = element.querySelector('.homer-opening-nav');
    if (!eligible) { nav?.remove(); return; }
    if (!nav) {
        nav = createElement('nav', 'homer-opening-nav');
        nav.setAttribute('aria-label', '切换角色开场');
        const previous = createElement('button', '', '‹');
        const status = createElement('span'); status.setAttribute('aria-live', 'polite');
        const next = createElement('button', '', '›');
        for (const [button, direction, label] of [[previous, -1, '上一个开场'], [next, 1, '下一个开场']]) {
            button.type = 'button'; button.setAttribute('aria-label', label);
            button.addEventListener('click', event => {
                event.stopPropagation();
                const target = messageMenuTargetFromElement(element), current = target?.message;
                const nextIndex = Number(current?.swipe_id || 0) + direction;
                // Existing candidates only. Reaching the end must not generate
                // a paid reply or silently discard messages after this opening.
                if (!current || nextIndex < 0 || nextIndex >= current.swipes?.length) return;
                void handleMessageMenuAction(direction < 0 ? 'swipe-left' : 'swipe-right', target);
            });
        }
        nav.append(previous, status, next);
        (element.querySelector('.mes_block') || element).append(nav);
    }
    const selected = Number(message.swipe_id || 0), busy = generationBusy || rollbackBusy || loadingLaunch;
    nav.firstElementChild.disabled = busy || selected <= 0;
    nav.lastElementChild.disabled = busy || selected >= swipes.length - 1;
    setTextIfChanged(nav.children[1], `开场 ${selected + 1} / ${swipes.length}`);
}

function renderMessageMenuTargets() {
    const context = getContext();
    imageGenerationUi.render();
    // Only share within this synchronous pass; later passes resolve the current
    // locale/timezone again, and invalid dates never construct a formatter.
    let timeFormatter;
    const getTimeFormatter = () => timeFormatter ??= createMessageHeaderTimeFormatter();
    document.querySelectorAll('#chat .mes').forEach(messageElement => {
        messageElement.querySelector('.homer-message-actions')?.remove();
        const index = messageIndexFromElement(messageElement);
        const message = index >= 0 ? context.chat[index] : null;
        const eligible = Boolean(message && (!message.is_system || message.extra?.homer_hidden));
        messageElement.classList.toggle('homer-message-hidden', !!message?.extra?.homer_hidden);
        messageElement.classList.toggle('homer-message-collapsed', !!message?.extra?.homer_collapsed);
        const editing = eligible && Boolean(messageElement.querySelector('.edit_textarea'));
        renderOpeningNavigation(messageElement, message, index, editing);
        messageElement.classList.toggle('homer-message-menu-target', eligible);
        messageElement.classList.toggle('homer-message-editing', editing);
        if (!eligible) {
            messageElement.removeAttribute('tabindex');
            messageElement.removeAttribute('aria-haspopup');
            messageElement.removeAttribute('aria-controls');
            messageElement.removeAttribute('aria-label');
            delete messageElement.dataset.messageIndex;
            delete messageElement.dataset.homerMessageId;
            return;
        }
        decorateMessageHeader(messageElement, message, index, getTimeFormatter);
        decorateTavoMessage(messageElement, { id: stableHomerMessageId(message), isUser: !!message?.is_user,
            hidden: !!message?.extra?.homer_hidden, collapsed: !!message?.extra?.homer_collapsed });
        messageElement.tabIndex = 0;
        messageElement.setAttribute('aria-haspopup', 'dialog');
        messageElement.setAttribute('aria-controls', 'homer-message-menu-dialog');
        messageElement.setAttribute(
            'aria-label',
            `${message?.is_user ? '用户输入' : '角色回复'}，长按或右键打开操作菜单`,
        );
        messageElement.dataset.messageIndex = String(index);
        messageElement.dataset.homerMessageId = stableHomerMessageId(message);
    });
    renderMessageMenuDialog();
    renderMessageSelection();
}

function queueMessageMenuRender() {
    if (messageMenuRenderQueued) {
        return;
    }
    messageMenuRenderQueued = true;
    requestAnimationFrame(() => {
        messageMenuRenderQueued = false;
        renderMessageMenuTargets();
    });
}

function clearMessagePress() {
    window.clearTimeout(messagePressTimer);
    messagePressTimer = null;
    messagePressStart = null;
    messagePressTarget = null;
}

function eventMessageElement(event) {
    return event.target instanceof Element
        ? event.target.closest('#chat .mes.homer-message-menu-target')
        : null;
}

function isInteractiveMessageTarget(target) {
    return target instanceof Element && Boolean(target.closest(
        'button, a, input, textarea, select, option, iframe, [contenteditable="true"], .mes_buttons, .mes_edit_buttons',
    ));
}

async function copyMessageText(message) {
    const text = String(message?.mes || '');
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const textarea = createElement('textarea', 'homer-clipboard-fallback');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        document.body.append(textarea);
        textarea.select();
        const copied = document.execCommand('copy');
        textarea.remove();
        if (!copied) {
            throw new Error('复制失败');
        }
    }
    showHostNotice('已复制这条消息', 'success');
}

async function openNativeMessageEditor(target) {
    const resolved = resolveMessageMenuTarget(target);
    if (!resolved) {
        throw new Error('目标消息已经变化，无法编辑');
    }
    await messageEdit(resolved.messageIndex);
    requestAnimationFrame(() => {
        queueMessageMenuRender();
        resolved.element?.querySelector('.edit_textarea')?.focus({ preventScroll: true });
    });
}

async function deleteCloudMessage(target, alreadyConfirmed = false) {
    let resolved = resolveMessageMenuTarget(target);
    let messageId = cloudHomerMessageId(resolved?.message);
    if (!resolved || !messageId) {
        showHostNotice('这条消息仍在同步，请稍后再删除', 'warning');
        return false;
    }
    const confirmed = alreadyConfirmed || await confirmHomerAction({
        id: 'homer-delete-message-dialog',
        title: '确认删除',
        notice: '只删除这一条消息，其他上下文保留。对话摘要会同步失效并在后续重建。',
        confirmLabel: '删除消息',
        danger: true,
    });
    if (!confirmed) {
        return false;
    }
    resolved = resolveMessageMenuTarget(target);
    messageId = cloudHomerMessageId(resolved?.message);
    if (!resolved || !messageId) {
        showHostNotice('目标消息已经变化，未执行删除', 'warning');
        return false;
    }
    rollbackBusy = true;
    document.body.classList.add('homer-rollback-busy');
    queueMessageMenuRender();
    const previousSuppressSync = suppressSync;
    try {
        if (!await syncCloudChat()) throw new Error('当前消息尚未同步，请联网后再删除');
        const result = await requestJson(
            siteUrl(`/console/api/web/messages/${encodeURIComponent(messageId)}/delete`),
            { method: 'POST', body: '{}' },
        );
        if (result?.deleted !== true) {
            throw new Error('消息不存在或已被删除');
        }
        const context = getContext();
        const { messageIndex, message } = resolved;
        suppressSync = true;
        context.chat.splice(messageIndex, 1);
        if (Array.isArray(launch?.messages)) {
            const launchIndex = launch.messages.findIndex(item => String(item?.id || '') === messageId);
            if (launchIndex >= 0) {
                launch.messages.splice(launchIndex, 1);
            }
        }
        try {
            await context.saveChat();
        } catch (error) {
            console.warn(`${MODULE_ID}: deleted local mirror was not saved`, error);
        }
        await context.printMessages();
        dialogueEventLogMuted += 1;
        try {
            await eventSource.emit(event_types.MESSAGE_DELETED, context.chat.length);
            await eventSource.emit(event_types.CHAT_LOADED, context.chatId);
        } finally {
            dialogueEventLogMuted = Math.max(0, dialogueEventLogMuted - 1);
        }
        lastSyncSignature = JSON.stringify(serializeChat());
        await logDialogueEvent('message_delete', messageIndex, message);
        await commitConfirmedCloudMutation();
        updateRuntimeStatus(launch.local_pending ? '本机已保存，等待同步' : '云端已同步', launch.local_pending ? 'warning' : 'online');
        showHostNotice('已删除这条消息', 'success');
        queueMessageMenuRender();
        return true;
    } catch (error) {
        console.error(`${MODULE_ID}: message delete failed`, error);
        showHostNotice(String(error?.message || '删除失败，请重试'), 'error');
        return false;
    } finally {
        suppressSync = previousSuppressSync;
        rollbackBusy = false;
        document.body.classList.remove('homer-rollback-busy');
        queueMessageMenuRender();
    }
}

async function handleMessageMenuAction(action, target) {
    const resolved = resolveMessageMenuTarget(target);
    if (!resolved) {
        showHostNotice('目标消息已经变化，未执行操作', 'warning');
        return;
    }
    if ((generationBusy || rollbackBusy || loadingLaunch) && action !== 'copy') {
        showHostNotice('当前操作完成后再修改对话', 'warning');
        return;
    }
    try {
        if (action === 'copy') {
            await copyMessageText(resolved.message);
            return;
        }
        if (action === 'image') {
            await imageGenerationUi.open(target);
            return;
        }
        if (action === 'hide' || action === 'collapse') {
            await changeMessagePresentation([resolved], action, !resolved.message.extra?.[action === 'hide' ? 'homer_hidden' : 'homer_collapsed']);
            return;
        }
        if (action === 'select') { startMessageSelection(resolved); return; }
        if (action === 'edit') {
            await openNativeMessageEditor(resolved);
            return;
        }
        if (action === 'rollback') {
            await rollbackToMessage(resolved);
            return;
        }
        if (action === 'delete') {
            await deleteCloudMessage(resolved);
            return;
        }
        if (action === 'swipe-left' || action === 'swipe-right') {
            generationBusy = true;
            document.body.classList.add('homer-generating');
            queueMessageMenuRender();
            try {
                if (!await truncateAfterMessage(resolved, '切换候选回复')) {
                    return;
                }
                const current = resolveMessageMenuTarget(resolved);
                if (!current) {
                    throw new Error('目标消息已经变化');
                }
                dialogueEventLogMuted += 1;
                try {
                    const context = getContext();
                    if (action === 'swipe-left') {
                        await context.swipe.left();
                    } else {
                        await context.swipe.right();
                    }
                } finally {
                    dialogueEventLogMuted = Math.max(0, dialogueEventLogMuted - 1);
                }
                await logDialogueEvent('swipe', current.messageIndex, current.message);
                scheduleSync(100);
            } finally {
                generationBusy = false;
                document.body.classList.remove('homer-generating');
                queueMessageMenuRender();
                // MESSAGE_SWIPED fires while the temporary action lock is set.
                // Publish its release too, or the retained host refuses all
                // subsequent conversation navigation as "still generating".
                scheduleHostStateNotify(0, 'swipe-settled');
            }
            return;
        }
        if (['continue', 'regenerate', 'next'].includes(action)) {
            await runAction(action, { messageTarget: resolved });
        }
    } catch (error) {
        console.error(`${MODULE_ID}: message menu action failed`, action, error);
        showHostNotice(String(error?.message || '操作失败，请重试'), 'error');
    }
}

async function changeMessagePresentation(targets, action, enabled) {
    const context = getContext();
    const resolved = targets.map(resolveMessageMenuTarget).filter(Boolean);
    if (!resolved.length || generationBusy || rollbackBusy || loadingLaunch) return false;
    if (resolved.some(({ message }) => !cloudHomerMessageId(message))) {
        showHostNotice('这条消息仍在同步，请稍后再操作', 'warning');
        return false;
    }
    const old = resolved.map(({ message }) => ({ message, is_system: message.is_system, extra: { ...message.extra } }));
    const previousPresentation = runtimeVariables.homer_message_presentation;
    const presentation = { ...previousPresentation };
    rollbackBusy = true;
    queueMessageMenuRender();
    scheduleHostStateNotify(0, 'message-presentation-saving');
    try {
        for (const { message } of resolved) {
            const id = cloudHomerMessageId(message);
            presentation[id] = { ...presentation[id], [action === 'hide' ? 'hidden' : 'collapsed']: enabled };
            message.extra = { ...message.extra };
            if (action === 'hide') {
                message.extra.homer_hidden = enabled;
                message.is_system = enabled;
            } else message.extra.homer_collapsed = enabled;
        }
        runtimeVariables.homer_message_presentation = presentation;
        await persistRuntimeVariables();
        // The account-scoped conversation state is authoritative; mirror failures
        // must not roll back a successful cloud update only on this device.
        try { await context.saveChat(); } catch { showHostNotice('设置已保存，本地镜像稍后同步', 'warning'); }
        renderMessageMenuTargets();
        scheduleSync(0);
        scheduleHostStateNotify(0, 'message-presentation');
        showHostNotice(action === 'hide' ? (enabled ? '消息已从模型上下文中隐藏' : '消息已恢复到模型上下文') : (enabled ? '已折叠消息' : '已展开消息'), 'success');
        return true;
    } catch (error) {
        if (previousPresentation === undefined) delete runtimeVariables.homer_message_presentation;
        else runtimeVariables.homer_message_presentation = previousPresentation;
        for (const state of old) { state.message.is_system = state.is_system; state.message.extra = state.extra; }
        renderMessageMenuTargets();
        throw error;
    } finally {
        rollbackBusy = false;
        queueMessageMenuRender();
        scheduleHostStateNotify(0, 'message-presentation-saved');
    }
}

function closeMessageSelection() {
    messageSelection = null;
    document.body.classList.remove('homer-selecting-messages');
    document.querySelector('#homer-message-selection')?.remove();
    document.querySelectorAll('#chat .mes').forEach(el => { el.classList.remove('homer-message-selected'); el.removeAttribute('aria-selected'); });
    syncHostOverlayState();
}

function renderMessageSelection() {
    if (!messageSelection) return;
    const context = getContext();
    if (String(context.chatId || '') !== messageSelection.chatId) { closeMessageSelection(); return; }
    messageSelection.targets = messageSelection.targets.map(resolveMessageMenuTarget).filter(Boolean);
    const selected = new Set(messageSelection.targets.map(item => item.messageRef));
    document.querySelectorAll('#chat .mes').forEach(el => {
        const checked = selected.has(context.chat[messageIndexFromElement(el)]);
        el.classList.toggle('homer-message-selected', checked);
        el.setAttribute('aria-selected', String(checked));
    });
    const root = document.querySelector('#homer-message-selection');
    if (!root) return;
    const title = root.querySelector('[data-selection-count]');
    const text = '已选择 ' + selected.size + ' 条消息';
    if (title.textContent !== text) title.textContent = text;
    const hidden = messageSelection.targets.filter(item => item.message.extra?.homer_hidden).length;
    root.querySelector('[data-selection-hide]').disabled = selected.size === hidden;
    root.querySelector('[data-selection-show]').disabled = hidden === 0;
    root.querySelector('[data-selection-delete]').disabled = !selected.size || messageSelection.targets.some(item => !cloudHomerMessageId(item.message));
}

function startMessageSelection(target) {
    const resolved = resolveMessageMenuTarget(target);
    if (!resolved) return;
    closeMessageSelection();
    messageSelection = { chatId: String(getContext().chatId || ''), targets: [resolved] };
    document.body.classList.add('homer-selecting-messages');
    const root = createElement('section', 'homer-message-selection'); root.id = 'homer-message-selection';
    const head = createElement('header', 'homer-selection-head');
    const cancel = createElement('button', '', '取消'); cancel.type = 'button';
    cancel.dataset.homerCancelSelection = '';
    cancel.addEventListener('click', closeMessageSelection);
    const count = createElement('span'); count.dataset.selectionCount = ''; count.setAttribute('aria-live', 'polite');
    const all = createElement('button', '', '全选'); all.type = 'button';
    all.addEventListener('click', () => {
        messageSelection.targets = getContext().chat.map((_, index) => messageMenuTargetForIndex(index)).filter(Boolean);
        renderMessageSelection();
    });
    head.append(cancel, count, all);
    const foot = createElement('footer', 'homer-selection-footer');
    for (const [action, label, icon] of [['hide','隐藏','fa-eye'],['show','取消隐藏','fa-eye-slash'],['delete','删除','fa-trash-can']]) {
        const button = createElement('button'); button.type = 'button'; button.dataset['selection' + action[0].toUpperCase() + action.slice(1)] = '';
        const glyph = createElement('i', 'fa-regular ' + icon); glyph.setAttribute('aria-hidden', 'true');
        button.append(glyph, createElement('span', '', label));
        button.addEventListener('click', async () => {
            const selection = messageSelection;
            if (!selection) return;
            try {
                if (action === 'delete') {
                    const accepted = await confirmHomerAction({ id: 'homer-delete-selected-dialog', title: '删除所选消息', notice: '将删除所选的 ' + selection.targets.length + ' 条消息，其他消息保留。', confirmLabel: '确认删除', danger: true });
                    if (!accepted || messageSelection !== selection || selection.chatId !== String(getContext().chatId || '')) return;
                    for (const item of [...selection.targets].reverse()) {
                        if (selection.chatId !== String(getContext().chatId || '') || !await deleteCloudMessage(item, true)) break;
                    }
                } else await changeMessagePresentation(selection.targets, 'hide', action === 'hide');
                closeMessageSelection();
            } catch (error) { showHostNotice(error.message || '操作失败', 'error'); }
        });
        foot.append(button);
    }
    root.append(head, foot); document.body.append(root); renderMessageSelection();
    syncHostOverlayState();
}

function installMessageMenu() {
    const chat = document.querySelector('#chat');
    if (!chat) {
        window.setTimeout(installMessageMenu, 120);
        return;
    }
    if (chat.dataset.homerMessageMenuInstalled !== 'true') {
        chat.addEventListener('click', event => {
            if (!messageSelection) return;
            const element = event.target.closest?.('#chat .mes');
            if (!element) return;
            const target = messageMenuTargetFromElement(element);
            if (!target) return;
            event.preventDefault(); event.stopImmediatePropagation();
            const selected = messageSelection.targets.findIndex(item => item.messageRef === target.messageRef);
            if (selected >= 0) messageSelection.targets.splice(selected, 1);
            else messageSelection.targets.push(target);
            renderMessageSelection();
        }, true);
        chat.dataset.homerMessageMenuInstalled = 'true';
        // Native Android text handles otherwise outlive the modal and appear
        // above unrelated settings dialogs. Editable fields keep native selection.
        chat.addEventListener('selectstart', event => {
            if (event.target.closest?.('.mes_text') && !isInteractiveMessageTarget(event.target)) {
                event.preventDefault();
            }
        });
        const repositionMenu = () => {
            const dialog = document.querySelector('#homer-message-menu-dialog');
            if (dialog?.open && activeMessageMenuTarget) {
                positionMessageMenuDialog(dialog, resolveMessageMenuTarget(activeMessageMenuTarget));
            }
        };
        chat.addEventListener('scroll', closeMessageMenu, { passive: true });
        window.addEventListener('resize', repositionMenu, { passive: true });
        window.visualViewport?.addEventListener('resize', repositionMenu, { passive: true });
        chat.addEventListener('pointerdown', event => {
            if (messageSelection) return;
            const touchLike = event.pointerType === 'touch' || event.pointerType === 'pen';
            if ((!touchLike && event.button !== 0) || event.isPrimary === false || isInteractiveMessageTarget(event.target)) {
                return;
            }
            const element = eventMessageElement(event);
            if (!element) {
                return;
            }
            clearMessagePress();
            messagePressStart = {
                x: Number(event.clientX),
                y: Number(event.clientY),
                pointerId: event.pointerId,
            };
            messagePressTarget = messageMenuTargetFromElement(element, {
                x: messagePressStart.x,
                y: messagePressStart.y,
            });
            if (!messagePressTarget) {
                clearMessagePress();
                return;
            }
            messagePressTimer = window.setTimeout(() => {
                const target = messagePressTarget;
                if (target) {
                    suppressMessageClickUntil = Date.now() + 700;
                    window.getSelection?.()?.removeAllRanges?.();
                    openMessageMenu(target, { suppressRelease: true });
                }
                clearMessagePress();
            }, MESSAGE_LONG_PRESS_DELAY);
        }, { passive: true });
        chat.addEventListener('pointermove', event => {
            if (!messagePressStart || event.pointerId !== messagePressStart.pointerId) {
                return;
            }
            const distance = Math.hypot(
                Number(event.clientX) - messagePressStart.x,
                Number(event.clientY) - messagePressStart.y,
            );
            if (distance > MESSAGE_LONG_PRESS_MOVE_TOLERANCE) {
                clearMessagePress();
            }
        }, { passive: true });
        for (const eventName of ['pointerup', 'pointercancel', 'lostpointercapture']) {
            chat.addEventListener(eventName, clearMessagePress, { passive: true });
        }
        chat.addEventListener('contextmenu', event => {
            const element = eventMessageElement(event);
            if (!element || element.querySelector('.edit_textarea')) {
                return;
            }
            clearMessagePress();
            event.preventDefault();
            event.stopPropagation();
            openMessageMenu(messageMenuTargetFromElement(element, {
                x: event.clientX,
                y: event.clientY,
            }), { suppressRelease: suppressMessageMenuPressRelease });
        });
        chat.addEventListener('click', event => {
            const menuTrigger = event.target instanceof Element
                ? event.target.closest('.extraMesButtonsHint, .homer-message-help')
                : null;
            if (menuTrigger) {
                const element = menuTrigger.closest('#chat .mes.homer-message-menu-target');
                if (element) {
                    event.preventDefault();
                    event.stopImmediatePropagation();
                    openMessageMenu(messageMenuTargetFromElement(element));
                }
                return;
            }
            if (Date.now() >= suppressMessageClickUntil || !eventMessageElement(event)) {
                return;
            }
            event.preventDefault();
            event.stopImmediatePropagation();
        }, true);
        chat.addEventListener('keydown', event => {
            const headerTrigger = event.target instanceof Element
                ? event.target.closest('.extraMesButtonsHint, .homer-message-help, .mes_edit')
                : null;
            if (headerTrigger && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault();
                event.stopPropagation();
                if (headerTrigger.matches('.mes_edit')) {
                    headerTrigger.click();
                } else {
                    const element = headerTrigger.closest('#chat .mes.homer-message-menu-target');
                    if (element) {
                        openMessageMenu(messageMenuTargetFromElement(element));
                    }
                }
                return;
            }
            const keyboardMenu = event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10');
            if (!keyboardMenu) {
                return;
            }
            const element = eventMessageElement(event)
                || (document.activeElement instanceof Element
                    ? document.activeElement.closest('#chat .mes.homer-message-menu-target')
                    : null);
            if (!element) {
                return;
            }
            event.preventDefault();
            const rect = element.getBoundingClientRect();
            openMessageMenu(messageMenuTargetFromElement(element, {
                x: rect.left + rect.width / 2,
                y: rect.top + Math.min(rect.height / 2, 80),
            }));
        });
    }
    messageMenuObserver?.disconnect();
    messageMenuObserver = new MutationObserver(queueMessageMenuRender);
    messageMenuObserver.observe(chat, { childList: true, subtree: true });
    ensureMessageMenuDialog();
    queueMessageMenuRender();
}

async function runAction(type, options = {}) {
    if (generationBusy) {
        return;
    }
    const context = getContext();
    const target = options.messageTarget || (
        Number.isInteger(Number(options.messageIndex))
            ? messageMenuTargetForIndex(Number(options.messageIndex))
            : null
    );
    let resolved = target ? resolveMessageMenuTarget(target) : null;
    if (target && !resolved) {
        showHostNotice('目标消息已经变化，未执行生成', 'warning');
        return;
    }
    const logMessage = resolved?.message || null;
    generationBusy = true;
    document.body.classList.add('homer-generating');
    queueMessageMenuRender();
    try {
        if (resolved) {
            const label = type === 'regenerate' ? '重写' : type === 'next' ? '推进下一回' : '续写';
            if (!await truncateAfterMessage(resolved, label)) {
                return;
            }
            resolved = resolveMessageMenuTarget(resolved);
            if (!resolved) {
                throw new Error('目标消息已经变化');
            }
        }
        dialogueEventLogMuted += 1;
        try {
            enforceStreamingConfiguration();
            if (type === 'next') {
                await context.generate('normal', {
                    quiet_prompt: '自然推进到下一回合或下一段情节，保持角色设定与当前叙事连续。',
                    quietToLoud: true,
                });
            } else {
                await context.generate(type);
            }
        } finally {
            dialogueEventLogMuted = Math.max(0, dialogueEventLogMuted - 1);
        }
        await logDialogueEvent(
            type === 'next' ? 'continue_next' : type,
            resolved?.messageIndex ?? context.chat.length - 1,
            logMessage,
        );
    } catch (error) {
        console.error(`${MODULE_ID}: action failed`, error);
        showHostNotice(String(error?.message || '操作失败，请重试'), 'error');
    } finally {
        window.clearTimeout(generationSettleTimer);
        generationSettleTimer = null;
        generationBusy = false;
        document.body.classList.remove('homer-generating');
        scheduleSync(100);
        queueMessageMenuRender();
    }
}

function setDrawerOpen(side = '') {
    const root = document.querySelector('#homer-runtime-root');
    if (!root) {
        return;
    }
    const left = root.querySelector('#homer-left-drawer');
    const right = root.querySelector('#homer-right-drawer');
    const backdrop = root.querySelector('#homer-drawer-backdrop');
    const desktopLayout = window.matchMedia('(min-width: 761px)').matches;
    const leftOpen = side === 'left';
    const rightOpen = side === 'right';
    left?.classList.toggle('is-open', leftOpen);
    right?.classList.toggle('is-open', rightOpen);
    left?.setAttribute('aria-hidden', String(!leftOpen));
    right?.setAttribute('aria-hidden', String(!rightOpen));
    const desktopLeftOpen = leftOpen && desktopLayout;
    if (backdrop) {
        backdrop.hidden = (desktopLeftOpen && !rightOpen) || (!leftOpen && !rightOpen);
    }
    document.body.classList.toggle('homer-drawer-open', leftOpen || rightOpen);
    document.body.classList.toggle('homer-left-drawer-open', leftOpen);
    if (leftOpen) historyCoverLoader?.open();
    else historyCoverLoader?.close();
    if (leftOpen || rightOpen) {
        window.setTimeout(() => {
            (rightOpen ? right : left)?.querySelector('button, a, select, input')?.focus();
        }, 160);
    }
}

function returnToDesktopNavigation() {
    setDrawerOpen();
}

function createSettingButton(icon, label, description, id = '') {
    const button = createElement('button', 'homer-setting-row');
    button.type = 'button';
    if (id) {
        button.id = id;
    }
    button.append(
        createElement('span', 'homer-setting-row__icon', icon),
        createElement('span', 'homer-setting-row__copy'),
        createElement('span', 'homer-setting-row__chevron', '›'),
    );
    const copy = button.querySelector('.homer-setting-row__copy');
    copy.append(
        createElement('strong', 'homer-setting-row__label', label),
        createElement('small', 'homer-setting-row__description', description),
    );
    return button;
}

function createDialogHeader(eyebrow, title, closeLabel, closeHandler) {
    const head = createElement('header', 'homer-sheet-dialog__head');
    const copy = createElement('div');
    copy.append(
        createElement('div', 'homer-preset-panel__eyebrow', eyebrow),
        createElement('h2', 'homer-sheet-dialog__title', title),
    );
    const close = createElement('button', 'homer-icon-button', '×');
    close.type = 'button';
    close.setAttribute('aria-label', closeLabel);
    close.addEventListener('click', closeHandler);
    head.append(copy, close);
    return head;
}

function createRangeField({ key, label, hint, min, max, step, value }) {
    const field = createElement('label', 'homer-model-field');
    field.dataset.key = key;
    const head = createElement('span', 'homer-model-field__head');
    const title = createElement('span', 'homer-model-field__label', label);
    const number = document.createElement('input');
    number.className = 'homer-model-field__number';
    number.type = 'number';
    number.min = String(min);
    number.max = String(max);
    number.step = String(step);
    number.value = String(value);
    number.setAttribute('aria-label', label);
    head.append(title, number);
    const range = document.createElement('input');
    range.className = 'homer-model-field__range';
    range.type = 'range';
    range.min = String(min);
    range.max = String(max);
    range.step = String(step);
    range.value = String(value);
    range.setAttribute('aria-label', `${label}滑块`);
    const sync = (source, target) => {
        target.value = String(clampNumber(source.value, min, max, value));
    };
    range.addEventListener('input', () => sync(range, number));
    number.addEventListener('input', () => sync(number, range));
    field.append(head, range, createElement('small', 'homer-model-field__hint', hint));
    return field;
}

function openMemoryBooks(){
    // The plugin already owns range selection and the real conversation.
    // Never interpose a second page based on the host's lossy preview DOM.
    openMemoryEngineSettings();
}

function openMemoryEngineSettings(indices=[]) {
    returnToDesktopNavigation();
    const dialog = document.querySelector('#homer-memory-dialog');
    if (!dialog || dialog.open) return;
    const status = dialog.querySelector('[role=status]');
    const retry = dialog.querySelector('.homer-memory-card');
    const controller = new AbortController();
    let opened = false, started = false;
    status.textContent = '正在准备当前会话的记忆设置…';
    retry.hidden = true;
    const loadingDelay=setTimeout(()=>{if(!opened&&!controller.signal.aborted)dialog.showModal();},250);
    const timeout = setTimeout(() => {
        controller.abort();
        if (dialog.open) { status.textContent = '记忆模块暂未就绪，可以重试或关闭；不会在关闭后自动弹出。'; retry.hidden = false; }
    }, 15000);
    dialog.addEventListener('close', () => { clearTimeout(loadingDelay);clearTimeout(timeout); if (!opened) controller.abort(); }, { once: true });
    const open = async () => {
        if (started || controller.signal.aborted || !window.HomerMemoryBooks?.open) return;
        started = true;
        try {
            await window.HomerMemoryBooks.open({ signal: controller.signal, onReady: () => {
                if (controller.signal.aborted) return;
                opened = true; clearTimeout(loadingDelay);clearTimeout(timeout); dialog.close();
                if(indices.length){
                    const apply=()=>{const popup=document.querySelector('.stmb-popup[open]');if(!popup)return;const a=popup.querySelector('#homer-memory-from'),b=popup.querySelector('#homer-memory-to');if(a&&b){a.value=String(indices[0]+1);b.value=String(indices.at(-1)+1);popup.querySelector('.homer-memory-custom-range button')?.click();}};
                    requestAnimationFrame(apply);
                }
            } });
        } catch {
            clearTimeout(timeout);
            if (dialog.open) { status.textContent = '记忆设置读取失败，请重试。'; retry.hidden = false; }
        }
    };
    window.addEventListener('homer:memory-ready', open, { once: true, signal: controller.signal });
    void open();
}

function buildModelDialog() {
    const settings = conversationModelSettings();
    const dialog = createElement('dialog', 'homer-sheet-dialog');
    dialog.id = 'homer-model-dialog';
    const shell = createElement('form', 'homer-sheet-dialog__shell');
    shell.method = 'dialog';
    shell.append(createDialogHeader(
        '仅影响当前会话',
        '模型设置',
        '关闭模型设置',
        () => dialog.close(),
    ));
    shell.append(createElement(
        'p',
        'homer-sheet-dialog__notice',
        '这些参数只用于当前角色的当前对话。不同模型可能会忽略不支持的参数。',
    ));

    const modelField = createElement('label', 'homer-model-select-field');
    modelField.append(createElement('span', 'homer-model-field__label', '当前模型'));
    const select = document.createElement('select');
    select.id = 'homer-model-select';
    select.className = 'homer-model-select';
    fillModelSelect(select, runtimeUiData.models, settings.model_id);
    if (!select.options.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '使用网站默认模型';
        select.append(option);
    }
    modelField.append(select);
    shell.append(modelField);

    const fields = createElement('div', 'homer-model-fields');
    fields.append(
        createRangeField({
            key: 'temperature',
            label: '温度',
            hint: '数值越高越有变化，越低越稳定。',
            min: 0,
            max: 2,
            step: 0.05,
            value: settings.temperature,
        }),
        createRangeField({
            key: 'top_p',
            label: 'Top‑P',
            hint: '控制候选词范围，通常保持在 0.8–1。',
            min: 0,
            max: 1,
            step: 0.01,
            value: settings.top_p,
        }),
        createRangeField({
            key: 'frequency_penalty',
            label: '词频惩罚',
            hint: '降低已频繁出现词语再次出现的概率。',
            min: -2,
            max: 2,
            step: 0.05,
            value: settings.frequency_penalty,
        }),
        createRangeField({
            key: 'presence_penalty',
            label: '存在惩罚',
            hint: '鼓励模型尝试对话中尚未出现的新内容。',
            min: -2,
            max: 2,
            step: 0.05,
            value: settings.presence_penalty,
        }),
    );
    shell.append(fields);

    const actions = createElement('footer', 'homer-sheet-dialog__actions');
    const reset = createElement('button', 'homer-secondary-button', '恢复默认');
    reset.type = 'button';
    reset.addEventListener('click', () => {
        select.value = String(runtimeUiData.modelDefaultId || runtimeUiData.models[0]?.id || '');
        const defaults = DEFAULT_MODEL_SETTINGS;
        for (const field of fields.querySelectorAll('.homer-model-field')) {
            const key = field.dataset.key;
            const value = defaults[key];
            field.querySelector('.homer-model-field__range').value = String(value);
            field.querySelector('.homer-model-field__number').value = String(value);
        }
    });
    const cancel = createElement('button', 'homer-secondary-button', '取消');
    cancel.type = 'button';
    cancel.addEventListener('click', () => dialog.close());
    const save = createElement('button', 'homer-primary-button', '保存');
    save.setAttribute('aria-label', '保存到本次会话');
    save.type = 'button';
    save.addEventListener('click', async () => {
        if (!shell.reportValidity()) return;
        const next = {
            model_id: select.value,
        };
        for (const field of fields.querySelectorAll('.homer-model-field')) {
            next[field.dataset.key] = Number(field.querySelector('.homer-model-field__number').value);
        }
        save.disabled = true;
        try {
            await persistModelSettings(next);
            const model = selectedModel();
            const summary = document.querySelector('#homer-model-summary');
            if (summary) {
                summary.textContent = String(model?.name || model?.model || '网站默认模型');
            }
            dialog.close();
            showHostNotice('模型参数已保存到当前会话', 'success');
        } catch (error) {
            showHostNotice(String(error?.message || '模型设置保存失败'), 'error');
        } finally {
            save.disabled = false;
        }
    });
    actions.append(reset, cancel, save);
    shell.append(actions);
    dialog.append(shell);
    settingsPage(dialog, { shell, head: shell.querySelector('header'), footer: actions, title: '模型设置' });
    dialog.addEventListener('close', () => {
        const saved = conversationModelSettings();
        select.value = saved.model_id || runtimeUiData.modelDefaultId || '';
        for (const field of fields.querySelectorAll('.homer-model-field')) {
            field.querySelector('.homer-model-field__number').value = String(saved[field.dataset.key]);
            field.querySelector('.homer-model-field__range').value = String(saved[field.dataset.key]);
        }
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) {
            dialog.close();
        }
    });
    return dialog;
}

function buildModDialog() {
    const dialog = createElement('dialog', 'homer-sheet-dialog');
    dialog.id = 'homer-mod-dialog';
    const shell = createElement('div', 'homer-sheet-dialog__shell');
    shell.append(createDialogHeader(
        '当前对话独立生效',
        'Mod 管理',
        '关闭 Mod 管理',
        () => dialog.close(),
    ));
    shell.append(createElement(
        'p',
        'homer-sheet-dialog__notice',
        '选择用于当前对话的 Mod。保存后生效。',
    ));
    const list = createElement('div', 'homer-mod-list');
    const tools = createElement('div', 'homer-mod-tools');
    const count = createElement('span', 'homer-mod-count');
    const reorder = createElement('button', 'homer-mod-reorder', '调整顺序');reorder.type='button';reorder.setAttribute('aria-pressed','false');
    reorder.addEventListener('click',()=>{const on=list.classList.toggle('is-reordering');reorder.setAttribute('aria-pressed',String(on));reorder.textContent=on?'完成排序':'调整顺序';});
    const updateCount=()=>count.textContent=`已启用 ${list.querySelectorAll('input:checked').length} / ${runtimeUiData.mods.length}`;
    tools.append(count,reorder);shell.append(tools);
    for (const mod of runtimeUiData.mods) {
        const modId = String(mod?.id || mod?.mod_id || '');
        if (!modId) {
            continue;
        }
        const row = createElement('div', 'homer-mod-row');
        row.dataset.modId = modId;
        const label = createElement('label', 'homer-mod-row__main');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.checked = runtimeUiData.activeModIds.includes(modId);
        input.setAttribute('aria-label', `启用 ${String(mod?.name || 'Mod')}`);
        input.className = 'homer-mod-switch';input.addEventListener('change',updateCount);
        const copy = createElement('span', 'homer-mod-row__copy');
        copy.append(
            createElement('strong', '', String(mod?.name || '未命名 Mod')),
            createElement('small', '', String(mod?.summary || '没有说明')),
        );
        const track=createElement('span','homer-mod-switch-track');track.setAttribute('aria-hidden','true');
        label.append(copy, input, track);
        const order = createElement('span', 'homer-mod-row__order');
        const up = createElement('button', 'homer-mini-button', '↑');
        const down = createElement('button', 'homer-mini-button', '↓');
        up.type = down.type = 'button';
        up.setAttribute('aria-label', `上移 ${String(mod?.name || 'Mod')}`);
        down.setAttribute('aria-label', `下移 ${String(mod?.name || 'Mod')}`);
        up.addEventListener('click', () => {
            const previous = row.previousElementSibling;
            if (previous) {
                list.insertBefore(row, previous);
            }
        });
        down.addEventListener('click', () => {
            const next = row.nextElementSibling;
            if (next) {
                list.insertBefore(next, row);
            }
        });
        order.append(up, down);
        row.append(label, order);
        list.append(row);
    }
    if (runtimeUiData.modsLoading || runtimeUiData.modsError) {
        const status = createElement('p', 'homer-empty', runtimeUiData.modsLoading ? '正在读取 Mod…你可以关闭此窗口，读取会继续。' : runtimeUiData.modsError);
        status.setAttribute('role', 'status');
        list.append(status);
        if (runtimeUiData.modsError) {
            const retry = createElement('button', 'homer-secondary-button', '重试');
            retry.type = 'button';
            retry.addEventListener('click', () => { void loadConversationMods(); });
            list.append(retry);
        }
    } else if (!list.children.length) {
        list.append(createElement('div', 'homer-empty', '你的 Mod 收藏库还是空的'));
    }
    shell.append(list);
    updateCount();
    tools.hidden=Boolean(runtimeUiData.modsLoading||runtimeUiData.modsError||!runtimeUiData.mods.length);
    const actions = createElement('footer', 'homer-sheet-dialog__actions');
    const workshop = document.createElement('a');
    workshop.className = 'homer-secondary-button';
    workshop.href = siteUrl('/app/workshop.html');
    workshop.textContent = '获取更多 Mod';
    workshop.className='homer-mod-library-link';shell.append(workshop);
    const cancel = createElement('button', 'homer-secondary-button', '取消');
    cancel.type = 'button';
    cancel.addEventListener('click', () => dialog.close());
    const save = createElement('button', 'homer-primary-button', '保存');
    save.setAttribute('aria-label', '保存 Mod');
    save.type = 'button';
    save.disabled = Boolean(runtimeUiData.modsLoading || runtimeUiData.modsError);
    save.addEventListener('click', async () => {
        const modIds = [...list.querySelectorAll('.homer-mod-row')]
            .filter(row => row.querySelector('input')?.checked)
            .map(row => String(row.dataset.modId || ''))
            .filter(Boolean);
        save.disabled = true;
        try {
            if (launch?.admin_preview) {
                if (isGenerating()) throw new Error('请先停止生成再修改 Mod');
                await refreshAdminConfiguration('', { ...adminConversationDraft, mod_ids: modIds });
                adminConversationDraft.mod_ids = modIds;
            } else await requestJson(`/api/homer/mods/conversation/${encodeURIComponent(launch.conversation_id)}`, {
                method: 'POST',
                body: JSON.stringify({ mod_ids: modIds }),
            });
            runtimeUiData.activeModIds = modIds;
            const summary = document.querySelector('#homer-mod-summary');
            if (summary) {
                summary.textContent = `${modIds.length} 个已启用`;
            }
            dialog.close();
            showHostNotice('当前会话 Mod 已更新', 'success');
        } catch (error) {
            showHostNotice(String(error?.message || 'Mod 保存失败'), 'error');
        } finally {
            save.disabled = false;
        }
    });
    actions.append(cancel, save);
    shell.append(actions);
    dialog.append(shell);
    settingsPage(dialog, { shell, head: shell.querySelector('header'), footer: actions, title: 'Mod 管理' });
    dialog.addEventListener('close', () => {
        const rows = [...list.querySelectorAll('.homer-mod-row')];
        const order = [...runtimeUiData.activeModIds, ...runtimeUiData.mods.map(mod => String(mod.id || mod.mod_id || ''))];
        rows.sort((a,b) => order.indexOf(a.dataset.modId)-order.indexOf(b.dataset.modId));
        for (const row of rows) { row.querySelector('input').checked = runtimeUiData.activeModIds.includes(row.dataset.modId); list.append(row); }
        list.classList.remove('is-reordering');reorder.setAttribute('aria-pressed','false');reorder.textContent='调整顺序';updateCount();
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) {
            dialog.close();
        }
    });
    return dialog;
}

function currentConversationRecord() {
    return runtimeUiData.conversations.find(item => (
        String(item?.id || '') === String(launch?.conversation_id || '')
    )) || launch?.conversation || null;
}

function updateConversationTitle(title) {
    const clean = String(title || '').trim();
    if (!clean) return;
    if (launch?.conversation) launch.conversation.title = clean;
    const record = runtimeUiData.conversations.find(item => String(item?.id || '') === String(launch?.conversation_id || ''));
    if (record) record.title = clean;
    const role = document.querySelector('#homer-right-drawer .homer-drawer__role');
    if (role) role.textContent = clean;
    populateHistoryList(
        document.querySelector('#homer-history-count'),
        document.querySelector('#homer-history-list'),
    );
    notifyHost('title', { title: clean });
}

function updatePresentationModeControl(detail = {}) {
    const control = document.querySelector('#homer-presentation-mode-toggle');
    const button = control?.querySelector('button');
    if (!control || !button) return;
    const visualAvailable = detail.visualAvailable !== false;
    const mode = detail.mode === 'tavern' ? 'tavern' : 'visual_novel';
    control.dataset.mode = mode;
    control.hidden = !visualAvailable;
    const targetMode = mode === 'tavern' ? 'visual_novel' : 'tavern';
    const targetLabel = targetMode === 'tavern' ? '酒馆模式' : '视觉小说';
    button.dataset.presentationMode = targetMode;
    button.textContent = targetLabel;
    button.setAttribute('aria-label', `切换到${targetLabel}`);
    button.title = `切换到${targetLabel}`;
}

function installPresentationModeBridge() {
    if (presentationModeBridgeInstalled) return;
    presentationModeBridgeInstalled = true;
    document.addEventListener('homer-presentation-mode-state', event => {
        updatePresentationModeControl(event?.detail || {});
    });
}

function buildPresentationModeToggle() {
    const section = createElement('aside', 'homer-presentation-mode-toggle');
    section.id = 'homer-presentation-mode-toggle';
    section.dataset.mode = 'tavern';
    section.hidden = true;
    const button = createElement('button', '', '视觉小说');
    button.type = 'button';
    button.dataset.presentationMode = 'visual_novel';
    button.setAttribute('aria-label', '切换到视觉小说');
    button.addEventListener('click', () => {
        const mode = String(button.dataset.presentationMode || 'visual_novel');
        document.dispatchEvent(new CustomEvent('homer-presentation-mode-request', {
            detail: { mode },
        }));
    });
    section.append(button);
    window.setTimeout(() => {
        document.dispatchEvent(new CustomEvent('homer-presentation-mode-query'));
    }, 0);
    return section;
}

function openRenameDialog(conversation = currentConversationRecord()) {
    managedConversation = conversation;
    const dialog = document.querySelector('#homer-rename-dialog');
    const input = dialog?.querySelector('input');
    if (!(dialog instanceof HTMLDialogElement) || !(input instanceof HTMLInputElement)) return;
    input.value = String(conversation?.title || conversation?.app_name || '');
    dialog.showModal();
    window.setTimeout(() => input.select(), 60);
}

function buildRenameDialog() {
    const dialog = createElement('dialog', 'homer-site-dialog homer-rename-dialog');
    dialog.id = 'homer-rename-dialog';
    dialog.dataset.modal = 'rename';
    const form = createElement('form', 'homer-site-dialog__surface');
    form.method = 'dialog';
    const head = createElement('header', 'homer-rename-dialog__head');
    head.append(createElement('strong', '', '聊天名称'));
    const save = createElement('button', 'homer-primary-button', '保存');
    save.type = 'submit';
    save.value = 'save';
    head.append(save);
    const input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 80;
    input.placeholder = '给聊天取个名字';
    form.append(head, input);
    dialog.append(form);
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const conversation = managedConversation || currentConversationRecord();
        const title = input.value.replace(/\s+/g, ' ').trim();
        if (!title) {
            showHostNotice('请输入聊天名称', 'warning');
            return;
        }
        save.disabled = true;
        try {
            const result = await requestJson(`/api/homer/conversations/${encodeURIComponent(conversation.id)}/rename`, {
                method: 'POST',
                body: JSON.stringify({ title }),
            });
            conversation.title = result?.conversation?.title || title;
            if (String(conversation.id) === String(launch?.conversation_id || '')) {
                updateConversationTitle(conversation.title);
            }
            dialog.close();
            await loadConversationHistory();
            showHostNotice('聊天名称已保存', 'success');
        } catch (error) {
            showHostNotice(String(error?.message || '改名失败'), 'error');
        } finally {
            save.disabled = false;
        }
    });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) dialog.close();
    });
    return dialog;
}

async function exportConversation(conversation) {
    const result = await requestJson(`/api/homer/conversations/${encodeURIComponent(conversation.id)}/export`, {
        method: 'POST',
        body: '{}',
    });
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${String(conversation.title || conversation.app_name || '聊天').replace(/[\\/:*?"<>|]/g, '_')}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function deleteManagedConversation(conversation) {
    const accepted = await confirmHomerAction({
        id: 'homer-delete-conversation-dialog',
        eyebrow: '会话管理',
        title: '删除这段聊天？',
        notice: '删除后将无法恢复，其他历史会话不会受到影响。',
        confirmLabel: '删除',
        danger: true,
    });
    if (!accepted) return;
    await requestJson(`/api/homer/conversations/${encodeURIComponent(conversation.id)}/delete`, {
        method: 'POST', body: '{}',
    });
    const wasCurrent = String(conversation.id) === String(launch?.conversation_id || '');
    runtimeUiData.conversations = runtimeUiData.conversations.filter(item => String(item?.id || '') !== String(conversation.id));
    if (wasCurrent) {
        const next = runtimeUiData.conversations[0];
        if (next) await switchConversation(next);
        else await startNewConversation();
    } else {
        populateHistoryList(document.querySelector('#homer-history-count'), document.querySelector('#homer-history-list'));
    }
    showHostNotice('聊天已删除', 'success');
}

function buildConversationManagerDialog() {
    const dialog = createElement('dialog', 'homer-site-dialog homer-chat-manage-dialog');
    dialog.id = 'homer-chat-manage-dialog';
    dialog.dataset.modal = 'chat-manage';
    dialog.setAttribute('aria-label', '会话管理');
    const surface = createElement('section', 'homer-site-dialog__surface');
    const actions = createElement('div', 'homer-chat-manage__actions');
    const definitions = [
        ['pin', '置顶'], ['rename', '改名'], ['new', '开始新聊天'], ['copy', '复制聊天'], ['export', '导出'],
    ];
    for (const [action, label] of definitions) {
        const button = createElement('button', '', label);
        button.type = 'button';
        button.dataset.action = action;
        actions.append(button);
    }
    const remove = createElement('button', 'homer-chat-manage__danger', '删除');
    remove.type = 'button';
    remove.dataset.action = 'delete';
    surface.append(actions, remove);
    dialog.append(surface);
    dialog.addEventListener('click', async event => {
        if (event.target === dialog) {
            dialog.close();
            return;
        }
        const button = event.target instanceof Element ? event.target.closest('[data-action]') : null;
        if (!(button instanceof HTMLButtonElement) || !managedConversation) return;
        const conversation = managedConversation;
        const action = button.dataset.action;
        dialog.close();
        try {
            if (action === 'rename') return openRenameDialog(conversation);
            if (action === 'new') return void startNewConversation();
            if (action === 'pin') {
                const pinned = !Boolean(conversation.pinned);
                await requestJson(`/api/homer/conversations/${encodeURIComponent(conversation.id)}/pin`, {
                    method: 'POST', body: JSON.stringify({ pinned }),
                });
                await loadConversationHistory();
                showHostNotice(pinned ? '聊天已置顶' : '已取消置顶', 'success');
                return;
            }
            if (action === 'copy') {
                const result = await requestJson(`/api/homer/conversations/${encodeURIComponent(conversation.id)}/copy`, {
                    method: 'POST', body: '{}',
                });
                await loadConversationHistory();
                showHostNotice('聊天副本已创建', 'success');
                const copied = result?.conversation;
                if (copied) await switchConversation(copied);
                return;
            }
            if (action === 'export') {
                await exportConversation(conversation);
                showHostNotice('聊天已导出', 'success');
                return;
            }
            if (action === 'delete') await deleteManagedConversation(conversation);
        } catch (error) {
            showHostNotice(String(error?.message || '会话操作失败'), 'error');
        }
    });
    return dialog;
}

function openConversationManager(conversation) {
    managedConversation = conversation;
    const dialog = document.querySelector('#homer-chat-manage-dialog');
    const pin = dialog?.querySelector('[data-action="pin"]');
    if (pin) pin.textContent = conversation?.pinned ? '取消置顶' : '置顶';
    dialog?.showModal();
}

async function importConversationFile(file) {
    const text = await file.text();
    let payload;
    try {
        payload = JSON.parse(text);
    } catch {
        throw new Error('聊天文件不是有效的 JSON');
    }
    if (!payload || typeof payload !== 'object' || !Array.isArray(payload.messages)) {
        throw new Error('聊天文件缺少 messages 列表');
    }
    payload.conversation = {
        ...(payload.conversation || {}),
        app_id: payload?.conversation?.app_id || launch?.app_id || '',
        app_name: payload?.conversation?.app_name || launch?.conversation?.app_name || '',
        app_icon: payload?.conversation?.app_icon || launch?.conversation?.app_icon || '',
    };
    return requestJson('/api/homer/conversations/import', {
        method: 'POST', body: JSON.stringify(payload),
    });
}

function buildNewConversationMenu() {
    const dialog = createElement('dialog', 'homer-site-dialog homer-new-chat-dialog');
    dialog.id = 'homer-new-chat-dialog';
    dialog.dataset.modal = 'new-chat';
    const surface = createElement('section', 'homer-site-dialog__surface homer-new-chat-menu');
    const create = createElement('button', '', '创建聊天');
    const importButton = createElement('button', '', '导入聊天');
    create.type = importButton.type = 'button';
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    input.hidden = true;
    create.addEventListener('click', () => { dialog.close(); void startNewConversation(); });
    importButton.addEventListener('click', () => input.click());
    input.addEventListener('change', async () => {
        const file = input.files?.[0];
        if (!file) return;
        dialog.close();
        try {
            const result = await importConversationFile(file);
            await loadConversationHistory();
            const conversation = result?.conversation;
            if (conversation) await switchConversation(conversation);
            showHostNotice('聊天已导入', 'success');
        } catch (error) {
            showHostNotice(String(error?.message || '导入聊天失败'), 'error');
        } finally {
            input.value = '';
        }
    });
    surface.append(create, importButton, input);
    dialog.append(surface);
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    return dialog;
}

let continuationLayoutObserver;
let continuationLayoutFrame = 0;
function positionContinuationControl(defer = false) {
    const trigger = document.querySelector('#homer-continuation-trigger');
    // The app removed this floating action. Mirror its shipping CSS state
    // without a computed-style/layout read, including late resize callbacks.
    if (!trigger || trigger.hidden || document.body.classList.contains('homer-runtime')) return;
    const composer = document.querySelector('#send_form');
    if (!composer) return;
    if (defer === true) {
        if (continuationLayoutFrame) cancelAnimationFrame(continuationLayoutFrame);
        continuationLayoutFrame = requestAnimationFrame(() => {
            continuationLayoutFrame = 0;
            positionContinuationControl();
        });
        return;
    }
    trigger.style.bottom = `${Math.max(0, window.innerHeight - composer.getBoundingClientRect().top + 8)}px`;
}

function installContinuationControlLayout() {
    continuationLayoutObserver?.disconnect();
    continuationLayoutObserver = undefined;
    window.removeEventListener('resize', positionContinuationControl);
    if (continuationLayoutFrame) cancelAnimationFrame(continuationLayoutFrame);
    continuationLayoutFrame = 0;
    const trigger = document.querySelector('#homer-continuation-trigger');
    if (!trigger || trigger.hidden || document.body.classList.contains('homer-runtime')) return;
    const composer = document.querySelector('#send_form');
    if (!composer) return;
    continuationLayoutObserver = new ResizeObserver(positionContinuationControl);
    continuationLayoutObserver.observe(composer);
    window.addEventListener('resize', positionContinuationControl);
    positionContinuationControl(true);
}

function buildContinuationControls() {
    const controls = createElement('div');
    const trigger = createElement('button', 'homer-continuation-trigger');
    trigger.id = 'homer-continuation-trigger'; trigger.type = 'button'; trigger.setAttribute('aria-label', '生成操作');
    trigger.hidden = document.body.classList.contains('homer-runtime');
    trigger.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="m8 8 5 4-5 4Zm6 0 5 4-5 4Z" fill="currentColor" stroke="none"/></svg>';
    const dialog = createElement('dialog', 'homer-site-dialog'); dialog.id = 'homer-generation-dialog'; dialog.setAttribute('aria-label', '生成操作');
    const surface = createElement('section', 'homer-site-dialog__surface homer-generation-options');
    surface.append(createElement('h2', '', '生成操作'));
    for (const [action, label, description] of [['continue', '续写', '接着当前最后一条回复继续写'], ['regenerate', '重写', '重新生成最后一条回复'], ['next', '下回续', '保持当前设定，推进到下一回合']]) {
        const button = createElement('button'); button.type = 'button';
        button.append(createElement('strong', '', label), createElement('small', '', description));
        button.addEventListener('click', () => { dialog.close(); void runAction(action); }); surface.append(button);
    }
    const cancel = createElement('button', 'homer-secondary-button', '取消'); cancel.type = 'button'; cancel.addEventListener('click', () => dialog.close());
    surface.append(cancel); dialog.append(surface); controls.append(trigger, dialog);
    trigger.addEventListener('click', () => {
        if (generationBusy || loadingLaunch) { showHostNotice('请等待当前操作完成', 'warning'); return; }
        dialog.showModal();
    });
    return controls;
}

function buildAttachmentDialog() {
    const dialog = createElement('dialog', 'homer-site-dialog homer-attachment-dialog');
    dialog.id = 'homer-attachment-dialog';
    dialog.dataset.modal = 'attachments';
    dialog.setAttribute('aria-label', '添加内容');
    const surface = createElement('section', 'homer-site-dialog__surface');
    const grid = createElement('div', 'homer-attachment-grid');
    const definitions = [
        ['gallery', '▧', '相册'], ['camera', '◉', '拍照'], ['image', '◇', '生图'],
    ];
    for (const [action, icon, label] of definitions) {
        const button = createElement('button');
        button.type = 'button';
        button.dataset.action = action;
        button.append(createElement('span', 'homer-attachment-icon', icon), createElement('span', '', label));
        grid.append(button);
    }
    const ai = createElement('button', 'homer-ai-help', '◌  AI帮答');
    ai.type = 'button';
    ai.dataset.action = 'ai-help';
    surface.append(grid, ai);
    dialog.append(surface);
    dialog.addEventListener('click', event => {
        if (event.target === dialog) { dialog.close(); return; }
        const button = event.target instanceof Element ? event.target.closest('[data-action]') : null;
        if (!button) return;
        const action = button.dataset.action;
        dialog.close();
        if (action === 'gallery') {
            document.querySelector('#file_form_input')?.click();
        } else if (action === 'camera') {
            const camera = document.createElement('input');
            camera.type = 'file'; camera.accept = 'image/*'; camera.capture = 'environment';
            camera.addEventListener('change', () => {
                const target = document.querySelector('#file_form_input');
                if (target instanceof HTMLInputElement && camera.files?.length) {
                    try { target.files = camera.files; target.dispatchEvent(new Event('change', { bubbles: true })); } catch { target.click(); }
                }
            }, { once: true });
            camera.click();
        } else if (action === 'ai-help') {
            document.querySelector('#option_impersonate')?.click();
        } else {
            // Use the app's existing image workspace; searching all buttons by
            // their caption also found this very button and recursed indefinitely.
            const target = '/app/image-chat.html';
            if (canNotifyHost()) notifyHost('navigate', { target });
            else window.location.assign(siteUrl(target));
        }
    });
    return dialog;
}

function buildMemoryDialog() {
    const dialog = createElement('dialog', 'homer-site-dialog homer-memory-dialog');
    dialog.id = 'homer-memory-dialog';
    dialog.dataset.modal = 'memory-settings';
    const surface = createElement('section', 'homer-site-dialog__surface');
    surface.append(
        createDialogHeader('CURRENT CHAT', '长记忆', '关闭长记忆', () => dialog.close()),
        createElement('p', 'homer-sheet-dialog__notice', '记忆只绑定当前会话，不展示角色卡世界书正文。'),
    );
    const card = createElement('button', 'homer-memory-card');
    card.type = 'button';
    card.textContent = '重试';
    const status = createElement('p', 'homer-sheet-dialog__notice');
    status.setAttribute('role', 'status');
    surface.append(status);
    card.addEventListener('click', () => { dialog.close(); openMemoryBooks(); });
    surface.append(card);
    dialog.append(surface);
    dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    return dialog;
}

function bindComposerAttachmentButton() {
    const button = document.querySelector('#options_button');
    if (!(button instanceof HTMLElement) || button.dataset.homerAttachmentBound === '1') return;
    button.dataset.homerAttachmentBound = '1';
    button.setAttribute('aria-label', '添加内容');
    button.addEventListener('click', event => {
        event.preventDefault();
        event.stopImmediatePropagation();
        document.querySelector('#options')?.classList.remove('openDrawer');
        document.querySelector('#homer-attachment-dialog')?.showModal();
    }, { capture: true });
}

let historyCoverLoader = null;
let historyCoverList = null;

function disposeHistoryCoverLoader() {
    historyCoverLoader?.dispose();
    historyCoverLoader = null;
    historyCoverList = null;
}

function historyCoversFor(historyList) {
    if (historyCoverList !== historyList) disposeHistoryCoverLoader();
    if (!historyCoverLoader) {
        historyCoverList = historyList;
        const owner = storageOwner;
        const epoch = storageAccountEpoch;
        const appId = String(launch?.app_id || '');
        const conversationId = String(launch?.conversation_id || '');
        historyCoverLoader = createDeferredListCovers({
            list: historyList,
            isOpen: () => {
                const root = historyList.closest('#homer-runtime-root');
                const drawer = historyList.closest('#homer-left-drawer');
                // Image visibility is presentation-only. Keep a late observer
                // tied to the actual live root/scope without reading an account
                // bridge for every avatar or altering authentication state.
                return historyList.isConnected && root === document.querySelector('#homer-runtime-root')
                    && drawer?.classList.contains('is-open') && drawer.getAttribute('aria-hidden') === 'false'
                    && Boolean(owner) && owner === storageOwner && epoch === storageAccountEpoch
                    && owner === String(session?.user?.id || session?.user?.user_id || '')
                    && appId === String(launch?.app_id || '') && conversationId === String(launch?.conversation_id || '');
            },
            setCover: (node, url) => {
                node.style.backgroundImage = url ? `url("${url.replaceAll('"', '%22')}")` : '';
            },
        });
    }
    return historyCoverLoader;
}

function populateHistoryList(historyCount, historyList) {
    if (!(historyCount instanceof HTMLElement) || !(historyList instanceof HTMLElement)) {
        return;
    }
    historyCount.textContent = String(runtimeUiData.conversations.length);
    historyList.replaceChildren();
    const coverLoader = historyCoversFor(historyList);
    const covers = [];
    for (const conversation of runtimeUiData.conversations) {
        const item = createElement('div', 'homer-history-item');
        item.dataset.conversationId = String(conversation?.id || conversation?.conversation_id || '');
        item.dataset.appId = String(conversation?.app_id || '');
        item.classList.toggle(
            'is-active',
            String(conversation?.id || '') === String(launch?.conversation_id || ''),
        );
        const avatar = createElement('span', 'homer-history-item__avatar');
        const avatarUrl = siteAssetUrl(conversation?.app_icon)
            || siteUrl('/assets/img/apk/avatar.webp?v=20260831-silvercat-v1');
        coverLoader.set(avatar, avatarUrl);
        covers.push(avatar);
        const copy = createElement('span', 'homer-history-item__copy');
        const itemHead = createElement('span', 'homer-history-item__head');
        itemHead.append(
            createElement('strong', '', String(conversation?.title || conversation?.app_name || '未命名会话')),
            createElement('time', '', formatConversationTime(conversation?.updated_at)),
        );
        copy.append(
            itemHead,
            createElement('small', '', messagePreview(conversation?.last_message, 72) || '点击继续对话'),
        );
        const main = createElement('button', 'homer-history-item__main');
        main.type = 'button';
        main.append(avatar, copy);
        main.addEventListener('click', () => void switchConversation(conversation));
        const more = createElement('button', 'homer-history-item__more', '⋮');
        more.type = 'button';
        more.setAttribute('aria-label', `管理 ${String(conversation?.title || conversation?.app_name || '会话')}`);
        more.addEventListener('click', event => {
            event.stopPropagation();
            openConversationManager(conversation);
        });
        item.append(main, more);
        historyList.append(item);
    }
    if (!historyList.children.length) {
        historyList.append(createElement('div', 'homer-empty', '还没有历史会话'));
    }
    coverLoader.retain(covers);
}

let runtimeBackHandler = null;
function installRuntimeBackHandler() {
    if (window.HomerCloseOverlay === runtimeBackHandler && runtimeBackHandler) return;
    const previousCloseOverlay = window.HomerCloseOverlay;
    runtimeBackHandler = () => {
        if (typeof previousCloseOverlay === 'function' && previousCloseOverlay()) return true;
        if ([...document.querySelectorAll('dialog[open]')].some(el => el.getClientRects().length)) return false;
        if (closeCardStageOverlay()) return true;
        const root = document.querySelector('#homer-runtime-root');
        const panel = root?.querySelector('#homer-preset-panel');
        if (panel && !panel.hidden) { setPanelOpen(false); return true; }
        if (root?.querySelector('.homer-chat-drawer.is-open, #homer-left-drawer.is-open, #homer-right-drawer.is-open')) {
            setDrawerOpen(); return true;
        }
        return false;
    };
    window.HomerCloseOverlay = runtimeBackHandler;
}

function buildRuntimeUi() {
    installHostOverlayTracking();
    void prepareTavoConversationUi().catch(() => {});
    document.documentElement.classList.toggle('homer-admin-preview', Boolean(launch?.admin_preview));
    installMemoryUi();
    try { document.documentElement.toggleAttribute('data-homer-dark', localStorage.getItem('ai_xingyue_shell_theme') === 'dark'); } catch {}
    if (!document.querySelector('#homer-option-picker-script')) {
        const picker = document.createElement('script');
        picker.id = 'homer-option-picker-script';
        picker.src = siteUrl('/assets/js/option-picker.js?v=20260917-r8');
        document.head.append(picker);
    }
    if (!document.querySelector('#homer-chat-design')) {
        const stylesheet = document.createElement('link');
        stylesheet.id = 'homer-chat-design';
        stylesheet.rel = 'stylesheet';
        stylesheet.href = siteUrl('/assets/css/chat-design.css?v=20260917-r8');
        document.head.append(stylesheet);
    }
    const previousRoot = document.querySelector('#homer-runtime-root');
    const sameCard = previousRoot?.dataset.appId === String(launch?.app_id || '');
    const previousDrawer = sameCard && previousRoot?.querySelector('#homer-right-drawer.is-open') ? 'right'
        : sameCard && previousRoot?.querySelector('#homer-left-drawer.is-open') ? 'left' : '';
    disposeHistoryCoverLoader();
    previousRoot?.remove();
    const root = createElement('div', 'homer-runtime-root');
    root.id = 'homer-runtime-root';
    root.dataset.appId = String(launch?.app_id || '');

    const roleName = String(
        launch?.card?.data?.name
        || launch?.card?.name
        || launch?.conversation?.app_name
        || '角色对话',
    );
    const header = createElement('header', 'homer-chat-header');
    const menu = createElement('button', 'homer-header-button');
    menu.innerHTML = "<svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.7\" stroke-linecap=\"round\"><path d=\"M5 6h14M5 12h9M5 18h14\"/></svg>";
    menu.type = 'button';
    menu.setAttribute('aria-label', '打开导航与历史会话');
    menu.addEventListener('click', () => {
        const leftDrawer = document.querySelector('#homer-left-drawer');
        setDrawerOpen(leftDrawer?.classList.contains('is-open') ? '' : 'left');
    });
    const title = createElement('div', 'homer-chat-header__title', roleName);
    title.id = 'homer-conversation-title';
    const settingsButton = createElement('button', 'homer-header-button');
    settingsButton.innerHTML = '<i class="fa-solid fa-gear" aria-hidden="true"></i>';
    settingsButton.type = 'button';
    settingsButton.setAttribute('aria-label', '打开对话设置');
    settingsButton.addEventListener('click', () => setDrawerOpen('right'));
    header.append(menu, title, settingsButton);

    const backdrop = createElement('button', 'homer-drawer-backdrop');
    backdrop.id = 'homer-drawer-backdrop';
    backdrop.type = 'button';
    backdrop.hidden = true;
    backdrop.setAttribute('aria-label', '关闭侧栏');
    backdrop.addEventListener('click', () => {
        const rightIsOpen = document.querySelector('#homer-right-drawer')?.classList.contains('is-open');
        rightIsOpen ? returnToDesktopNavigation() : setDrawerOpen();
    });

    const leftDrawer = createElement('aside', 'homer-drawer homer-drawer--left');
    leftDrawer.id = 'homer-left-drawer';
    leftDrawer.setAttribute('aria-label', '导航与历史会话');
    leftDrawer.setAttribute('aria-hidden', 'true');
    const leftHead = createElement('header', 'homer-drawer__head');
    leftHead.classList.add('homer-drawer__head--left');
    const brand = createElement('div');
    brand.append(createElement('h2', 'homer-drawer__title', '惑梦（Homer）'));
    const leftClose = createElement('button', 'homer-icon-button', '×');
    leftClose.type = 'button';
    leftClose.setAttribute('aria-label', '关闭导航');
    leftClose.addEventListener('click', () => setDrawerOpen());
    leftHead.append(brand, leftClose);
    const navigation = createElement('nav', 'homer-main-navigation');
    const navigationItems = [
        ['⌂', '我的', '/app/me.html'],
        ['⌕', '探索', '/app/explore.html'],
        ['♡', '收藏', '/app/favorites.html'],
        ['✦', '创意工坊', '/app/workshop.html'],
    ];
    for (const [icon, label, path] of navigationItems) {
        const link = document.createElement('a');
        link.className = 'homer-main-navigation__item';
        link.href = siteUrl(path);
        // 在 APK / 站点 iframe 里让宿主换页，而不是在 iframe 内部整页跳转。宿主侧是
        // 常驻 WebView，收到 navigate 会原地切页并保留旧页面；直接在 iframe 里加载
        // 站点页也会被主站的 frame-ancestors 'none' 拒掉。
        link.addEventListener('click', event => {
            if (!canNotifyHost()) return;
            event.preventDefault();
            notifyHost('navigate', { target: path });
        });
        link.append(
            createElement('span', 'homer-main-navigation__icon', icon),
            createElement('span', '', label),
        );
        navigation.append(link);
    }
    const historySection = createElement('section', 'homer-history');
    const historyHead = createElement('div', 'homer-history__head');
    const historyMeta = createElement('span', 'homer-history__meta');
    const historyCount = createElement('span', '', '0');
    historyCount.id = 'homer-history-count';
    const newConversation = createElement('button', 'homer-history__new', '+');
    newConversation.id = 'homer-history-new';
    newConversation.type = 'button';
    newConversation.setAttribute('aria-label', '为当前角色新建对话');
    newConversation.addEventListener('click', () => {
        document.querySelector('#homer-new-chat-dialog')?.showModal();
    });
    historyMeta.append(historyCount, newConversation);
    historyHead.append(createElement('h3', '', '历史会话'), historyMeta);
    const historyList = createElement('div', 'homer-history__list');
    historyList.id = 'homer-history-list';
    populateHistoryList(historyCount, historyList);
    historySection.append(historyHead, historyList);
    leftDrawer.append(leftHead, navigation, historySection);

    const rightDrawer = createElement('aside', 'homer-drawer homer-drawer--right');
    rightDrawer.id = 'homer-right-drawer';
    rightDrawer.setAttribute('aria-label', '对话设置');
    rightDrawer.setAttribute('aria-hidden', 'true');
    const rightHead = createElement('header', 'homer-drawer__head');
    const settingCopy = createElement('div', 'homer-chat-identity');
    const portrait = document.createElement('img'); portrait.alt = ''; portrait.className = 'homer-chat-identity__avatar';
    const defaultPortrait = siteUrl('/assets/img/apk/avatar.webp');
    portrait.src = siteAssetUrl(launch?.conversation?.app_icon) || defaultPortrait;
    portrait.addEventListener('error', () => { if (portrait.src !== defaultPortrait) portrait.src = defaultPortrait; });
    settingCopy.append(portrait, createElement('h2', 'homer-drawer__title', roleName));
    const rightClose = createElement('button', 'homer-icon-button', '×');
    rightClose.type = 'button';
    rightClose.setAttribute('aria-label', '关闭设置');
    rightClose.addEventListener('click', returnToDesktopNavigation);
    rightHead.append(settingCopy, rightClose);
    const settingList = createElement('div', 'homer-setting-list');
    const currentModel = selectedModel();
    const modelButton = createSettingButton(
        '◉',
        '模型设置',
        String(currentModel?.name || currentModel?.model || '网站默认模型'),
        'homer-open-model-settings',
    );
    modelButton.querySelector('.homer-setting-row__description').id = 'homer-model-summary';
    modelButton.addEventListener('click', () => {
        returnToDesktopNavigation();
        document.querySelector('#homer-model-dialog')?.showModal();
    });
    const presetButton = createSettingButton(
        '☷',
        '预设开关',
        '仅作用于当前对话',
        'homer-open-preset-settings',
    );
    presetButton.querySelector('.homer-setting-row__description').id = 'homer-preset-summary';
    presetButton.addEventListener('click', () => {
        returnToDesktopNavigation();
        setFullDialogOpen(true);
    });
    const favoritesLink = document.createElement('a');
    favoritesLink.className = 'homer-setting-row';
    favoritesLink.href = siteUrl('/app/favorites.html');
    favoritesLink.append(
        createElement('span', 'homer-setting-row__icon', '♡'),
        createElement('span', 'homer-setting-row__copy'),
        createElement('span', 'homer-setting-row__chevron', '›'),
    );
    favoritesLink.querySelector('.homer-setting-row__copy').append(
        createElement('strong', 'homer-setting-row__label', '收藏'),
        createElement('small', 'homer-setting-row__description', '管理已收藏的角色卡'),
    );
    const memoryButton = createSettingButton(
        '∞',
        '长记忆',
        '整理与管理当前对话记忆',
        'homer-open-memory-books',
    );
    memoryButton.addEventListener('click', () => {
        returnToDesktopNavigation();
        openMemoryBooks();
    });
    const modButton = createSettingButton(
        '◇',
        'Mod',
        `${runtimeUiData.activeModIds.length} 个已启用`,
        'homer-open-mods',
    );
    modButton.querySelector('.homer-setting-row__description').id = 'homer-mod-summary';
    modButton.addEventListener('click', () => {
        returnToDesktopNavigation();
        document.querySelector('#homer-mod-dialog')?.showModal();
    });
    favoritesLink.addEventListener('click', event => {
        if (!canNotifyHost()) return;
        event.preventDefault(); notifyHost('navigate', { target: '/app/favorites.html' });
    });
    if (launch?.admin_preview) {
        settingList.append(modelButton);
        for (const [kind, label, symbol] of [['prompt', '预设', '☷'], ['worldbook', '世界书', '▤'], ['regex', '正则', '⌘']]) {
            const entry = createSettingButton(symbol, label, '选择、编辑与开关 · 本次会话', `homer-admin-${kind}`);
            entry.dataset.adminKind = kind;
            entry.addEventListener('click', () => administratorEditor.open(rightDrawer, kind));
            settingList.append(entry);
        }
        settingList.append(memoryButton, modButton);
        settingList.className = 'haw-setting-list';
        for (const entry of settingList.children) {
            entry.className = 'haw-setting-row';
            for (const [before, after] of [['icon', 'icon'], ['copy', 'copy'], ['label', 'label'], ['description', 'description'], ['chevron', 'arrow']]) {
                const part = entry.querySelector(`.homer-setting-row__${before}`);
                if (part) part.className = `haw-row-${after}`;
            }
        }
    } else settingList.append(modelButton, presetButton, memoryButton, modButton);
    const appearance = chatAppearance = bindChatAppearance(() => ({ owner: session?.user?.id || session?.user?.user_id, conversation: launch?.conversation_id }));
    const shortcuts = createElement('nav', 'homer-chat-shortcuts');
    shortcuts.setAttribute('aria-label', '对话快捷操作');
    for (const [action, label, icon] of [['appearance', '界面设置', 'fa-palette'], ['stats', '统计', 'fa-chart-simple'], ['search', '搜索', 'fa-magnifying-glass']]) {
        const button = createElement('button'); button.type = 'button'; button.setAttribute('aria-label', label);
        const mark = createElement('i', `fa-solid ${icon}`); mark.setAttribute('aria-hidden', 'true');
        button.append(mark, createElement('span', '', label));
        button.addEventListener('click', () => {
            returnToDesktopNavigation();
            if (action === 'appearance') appearance.open();
            else openChatTool(action, { container: document.querySelector('#chat'), selector: '.mes', isUser: element => element.getAttribute('is_user') === 'true', title: roleName });
        }); shortcuts.append(button);
    }
    rightDrawer.append(
        rightHead,
        settingList,
        createElement(
            'p',
            'homer-privacy-note',
            '角色卡世界书正文受创作者保护。你只能通过预设开关调整创作者允许开放的条目。',
        ),
        shortcuts,
    );

    if (launch?.admin_preview) {
        rightDrawer.classList.add('homer-admin-settings');
        rightDrawer.querySelector('.homer-privacy-note').textContent = '管理员会话工作区。调整仅用于本次会话；保存全局配置需要单独确认。';
    } else controlCenter(rightDrawer);
    const panel = createElement('section', 'homer-preset-panel');
    panel.id = 'homer-preset-panel';
    panel.hidden = true;
    const panelHead = createElement('header', 'homer-preset-panel__head');
    const heading = createElement('div');
    heading.append(
        createElement('div', 'homer-preset-panel__eyebrow', '当前模型绑定预设'),
        createElement('h2', 'homer-preset-panel__title', '本次会话开关'),
    );
    const close = createElement('button', 'homer-icon-button', '×');
    close.type = 'button';
    close.setAttribute('aria-label', '关闭预设面板');
    close.addEventListener('click', () => setPanelOpen(false));
    panelHead.append(heading, close);

    const statusGrid = createElement('div', 'homer-status-grid');
    const runtimeStatus = createElement('div', 'homer-status-pill');
    runtimeStatus.append(createElement('i', 'homer-status-dot'));
    const runtimeText = createElement('span', '', '会话能力已连接');
    runtimeText.id = 'homer-runtime-status';
    runtimeText.dataset.state = 'online';
    runtimeStatus.append(runtimeText);
    const count = createElement('div', 'homer-status-pill homer-status-pill--gold', '读取预设…');
    count.id = 'homer-preset-count';
    statusGrid.append(runtimeStatus, count);

    const notice = createElement(
        'p',
        'homer-preset-notice',
        '这里只显示当前模型实际使用的一个预设，以及后台明确允许用户切换的条目；不会展示提示词或世界书正文。',
    );
    const quickList = createElement('div', 'homer-preset-list');
    quickList.id = 'homer-preset-quick-list';
    const expand = createElement('button', 'homer-expand-button', '展开全部条目');
    expand.type = 'button';
    expand.addEventListener('click', () => setFullDialogOpen(true));
    const quickSearch = document.createElement('input');
    quickSearch.type = 'search'; quickSearch.className = 'homer-preset-search';
    quickSearch.placeholder = '搜索开关名称'; quickSearch.setAttribute('aria-label', '搜索会话开关');
    quickSearch.addEventListener('input', () => renderPresetLists(quickSearch.value));
    panel.append(panelHead, statusGrid, notice, quickSearch, quickList, expand);

    const dialog = createElement('dialog', 'homer-preset-dialog');
    dialog.id = 'homer-preset-dialog';
    const dialogShell = createElement('div', 'homer-preset-dialog__shell');
    const dialogHead = createElement('header', 'homer-preset-dialog__head');
    const dialogHeading = createElement('div');
    dialogHeading.append(
        createElement('div', 'homer-preset-panel__eyebrow', '当前模型唯一预设'),
        createElement('h2', 'homer-preset-dialog__title', '预设条目控制台'),
    );
    const dialogClose = createElement('button', 'homer-icon-button', '×');
    dialogClose.type = 'button';
    dialogClose.setAttribute('aria-label', '关闭全部条目');
    dialogClose.addEventListener('click', () => setFullDialogOpen(false));
    dialogHead.append(dialogHeading, dialogClose);
    const search = document.createElement('input');
    search.className = 'homer-preset-search';
    search.type = 'search';
    search.placeholder = '搜索当前预设条目';
    search.setAttribute('aria-label', '搜索预设条目');
    search.addEventListener('input', () => renderPresetLists(search.value));
    const fullList = createElement('div', 'homer-preset-list homer-preset-list--full');
    fullList.id = 'homer-preset-full-list';
    dialogShell.append(dialogHead, search, fullList);
    dialog.append(dialogShell);
    settingsPage(dialog, { shell: dialogShell, head: dialogHead, close: dialogClose, title: '预设开关' });
    dialog.addEventListener('click', event => {
        if (event.target === dialog) {
            setFullDialogOpen(false);
        }
    });

    root.append(
        header,
        backdrop,
        leftDrawer,
        rightDrawer,
        panel,
        dialog,
        buildModelDialog(),
        buildModDialog(),
        buildMemoryDialog(),
        buildRenameDialog(),
        buildConversationManagerDialog(),
        buildNewConversationMenu(),
        buildAttachmentDialog(),
        buildContinuationControls(),
        buildPresentationModeToggle(),
    );
    root.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            setDrawerOpen();
            setPanelOpen(false);
        }
    });
    document.body.append(root);
    // The native Back contract must include custom panels, not only HTML dialogs.
    installRuntimeBackHandler();
    // The runtime form shell may fill the viewport; anchor to the actual input
    // form's geometry only when a host actually exposes the floating control.
    installContinuationControlLayout();
    bindComposerAttachmentButton();
    renderPresetLists();
    flushHostNotices();
    // Navigation is a drawer on every viewport.  Opening it automatically on
    // desktop/landscape makes the background runtime visibly rearrange the
    // local first frame several seconds after launch.
    // Late hydration can rebuild the shell after it is already interactive.
    // Preserve an explicitly opened drawer on the same card, not an automatic
    // default. Conversation switching closes it before rebuilding.
    setDrawerOpen(previousDrawer);
}

async function startNewConversation() {
    if (launch?.admin_preview) return;
    if (loadingLaunch || generationBusy || !launch?.app_id) {
        showHostNotice(generationBusy ? '回复生成完成后才能新建对话' : '当前会话仍在准备，请稍候', 'warning');
        return;
    }
    loadingLaunch = true;
    document.body.classList.add('homer-switching-chat');
    try {
        const created = await requestJson('/api/homer/conversations/start', {
            method: 'POST',
            body: JSON.stringify({
                app_id: launch.app_id,
                app_name: launch?.conversation?.app_name || launch?.card?.data?.name || '',
                app_icon: launch?.conversation?.app_icon || '',
                version_id: launch?.conversation?.version_id || launch?.version_id || '',
            }),
        });
        const conversation = {
            ...created,
            id: created?.conversation_id,
            app_id: created?.app_id || launch.app_id,
            title: created?.app_name || '新对话',
        };
        loadingLaunch = false;
        await switchConversation(conversation);
        void loadConversationHistory();
    } catch (error) {
        console.error(`${MODULE_ID}: conversation create failed`, error);
        showHostNotice(String(error?.message || '新建对话失败'), 'error');
    } finally {
        loadingLaunch = false;
        document.body.classList.remove('homer-switching-chat');
        queueMessageMenuRender();
    }
}

async function switchConversation(conversation, bootstrapToken = '') {
    const bootstrapAcknowledgement = normalizeBootstrapToken(bootstrapToken)
        ? { bootstrap_token: bootstrapToken } : {};
    const targetConversationId = String(conversation?.id || conversation?.conversation_id || '').trim();
    const targetAppId = String(conversation?.app_id || '').trim();
    if (!targetConversationId || !targetAppId) {
        showHostNotice('这条历史会话缺少角色信息，暂时无法切换', 'error');
        return;
    }
    if (targetConversationId === String(launch?.conversation_id || '')) {
        setDrawerOpen();
        return;
    }
    if (loadingLaunch || adminBinding || generationBusy || rollbackBusy) {
        showHostNotice(rollbackBusy ? '当前消息保存后才能切换会话' : generationBusy ? '回复生成完成后才能切换会话' : '会话正在切换，请稍候', 'warning');
        if (!loadingLaunch) notifyHostConversation('conversation-switch-failed', {
            failed_app_id: targetAppId,
            failed_conversation_id: targetConversationId,
            ...bootstrapAcknowledgement,
        });
        return;
    }

    const previous = {
        session,
        launch,
        adminConversationDraft,
        adminConversationConfig,
        lastGenerationDiagnostic,
        runtimeVariables: { ...runtimeVariables },
        presetSearchQuery,
        runtimeUiData,
        extensionSettings: cloneJsonObject(extension_settings),
        extensionSettingsScope: lastExtensionSettingsScope,
        extensionSettingsSignature: lastExtensionSettingsSignature,
        conversationExtensionSettings,
        reaffirmExtensionSettingsAfterReady,
        officialRegexState,
        displayRules: officialDisplayRules().map(rule => ({ ...rule })),
        owner: reconcileStorageAccount(),
        epoch: storageAccountEpoch,
        canonical: null,
        configurationChanged: false,
    };
    retainScopeDraft();
    loadingLaunch = true;
    performance.mark('homer-switch-start');
    document.body.classList.add('homer-switching-chat');
    setDrawerOpen();
    notifyHostLoading('正在切换历史会话…');
    notifyHost('conversation-switching', {
        admin_preview: false,
        app_id: targetAppId.slice(0, 160),
        conversation_id: targetConversationId.slice(0, 160),
        from_app_id: String(previous.launch?.app_id || '').slice(0, 160),
        from_conversation_id: String(previous.launch?.conversation_id || '').slice(0, 160),
        role_name: String(conversation?.app_name || conversation?.title || '角色对话').slice(0, 120),
    });
    try {
        assertCanonicalConversationScope();
        const currentAppId = String(launch?.app_id || '');
        const currentConversationId = String(launch?.conversation_id || '');
        const sameCharacterCard = currentAppId === targetAppId;
        // Establish the same one-use session row before preparing resources.
        // Otherwise an uncached click prepares unattached settings and an
        // arriving prefetch can start a second read for the exact target.
        const nextSessionWork = takePrefetchedSession(targetAppId, targetConversationId);
        // Still await the original promise below; this observer only handles
        // rejection if synchronous resource preparation fails before that await.
        void nextSessionWork.catch(() => {});
        const preparedResources = prepareConversationResources(targetAppId, targetConversationId);
        const runtimeStateRead = preparedResources.state;
        const modelCatalogRead = preparedResources.models;
        const [, nextSession] = await Promise.all([
            commitConversationBeforeSwitch(),
            nextSessionWork,
        ]);
        // The durable leave barrier has settled. Capture only chat state,
        // never source card JSON, before any target activation can clear it.
        previous.canonical = captureConversationRecovery();
        assertRecoveryAccount(previous);
        invalidateCachedSession(currentAppId, currentConversationId);
        performance.mark('homer-switch-session');
        if (!nextSession?.launch) {
            throw new Error('没有找到目标历史会话');
        }
        previous.configurationChanged = true;
        session = nextSession;
        launch = nextSession.launch;
        const preparedHeader = prepareLaunchMirrorHeader();
        // Remember the actual previous peer after its durable leave barrier.
        // The scheduler defers its reads until foreground hydration is ready,
        // rather than preparing only whichever history rows happen to be first.
        if (!launch.admin_preview && !previous.launch?.admin_preview) {
            scheduleSessionPrefetch(previous.launch);
        }
        prefetchPersonaAvatarsForConversation({
            userId: session.user?.id || session.user?.user_id,
            appId: launch.app_id, conversationId: launch.conversation_id,
        });
        requestedAppId = targetAppId;
        requestedConversationId = targetConversationId;
        adminConversationDraft = {};
        adminConversationConfig = null;
        lastGenerationDiagnostic = null;
        generationSnapshot = null;
        runtimeVariables = {};
        presetSearchQuery = '';
        lastSyncSignature = '';
        setAccessClasses(session?.user);
        const modelCatalogWork = loadRuntimeUiData(modelCatalogRead);
        await Promise.all([loadRuntimeState(runtimeStateRead, modelCatalogWork, preparedResources.regex), modelCatalogWork]);
        assertRecoveryAccount(previous);
        performance.mark('homer-switch-hydrated');
        applyConnectionConfiguration();
        // Keep the website-owned shell visible while a large card and its
        // worldbook finish importing into the dialogue engine.
        await importLaunchCharacter({ reuseActiveCharacter: sameCharacterCard, preparedHeader });
        assertRecoveryAccount(previous);
        performance.mark('homer-switch-card');
        await loadCloudChat();
        assertRecoveryAccount(previous);
        performance.mark('homer-switch-cloud');
        buildRuntimeUi();
        installTokenRefresh();
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set('homer_app_id', launch.app_id);
        nextUrl.searchParams.set('homer_conversation_id', launch.conversation_id);
        nextUrl.searchParams.delete('app_id');
        nextUrl.searchParams.delete('conversation_id');
        nextUrl.searchParams.delete('conv_id');
        window.history.pushState({
            homer_app_id: launch.app_id,
            homer_conversation_id: launch.conversation_id,
        }, '', nextUrl);
        updateRuntimeStatus(launch.local_pending ? '本机已保存，等待同步' : '云端已同步', launch.local_pending ? 'warning' : 'online');
        reaffirmConversationConnection();
        window.setTimeout(reaffirmConversationConnection, 800);
        conversationRecoveryBlocked = false;
        document.body.classList.remove('homer-runtime-error');
        notifyHostConversation('ready', bootstrapAcknowledgement);
        scheduleSessionPrefetch();
        void replayPendingStorage();
        performance.mark('homer-switch-ready');
    } catch (error) {
        // Logout/relogin (even the same owner) invalidates this recovery. Never
        // resurrect an old account session, token, or message snapshot.
        if (reconcileStorageAccount() !== previous.owner || storageAccountEpoch !== previous.epoch) {
            blockConversationRecovery(new Error('会话账号已切换，请重新进入'), bootstrapToken);
            return;
        }
        session = previous.session;
        launch = previous.launch;
        adminConversationDraft = previous.adminConversationDraft;
        adminConversationConfig = previous.adminConversationConfig;
        lastGenerationDiagnostic = previous.lastGenerationDiagnostic;
        requestedAppId = String(launch?.app_id || '');
        requestedConversationId = String(launch?.conversation_id || '');
        runtimeVariables = previous.runtimeVariables;
        presetSearchQuery = previous.presetSearchQuery;
        runtimeUiData = previous.runtimeUiData;
        const previousSuppressSync = suppressSync;
        suppressSync = true;
        try {
            const restoreSettings = async () => {
                replaceExtensionSettings(previous.extensionSettings);
                await eventSource.emit(event_types.SETTINGS_LOADED);
                assertRecoveryAccount(previous);
                lastExtensionSettingsScope = previous.extensionSettingsScope;
                lastExtensionSettingsSignature = previous.extensionSettingsSignature;
                conversationExtensionSettings = previous.conversationExtensionSettings;
                reaffirmExtensionSettingsAfterReady = previous.reaffirmExtensionSettingsAfterReady;
                officialRegexState = setOfficialDisplayRules({
                    scripts: previous.displayRules, revision: previous.officialRegexState.revision,
                });
                officialRegexState = previous.officialRegexState;
                applyConnectionConfiguration();
            };
            if (previous.configurationChanged) {
                if (!canonicalRecoveryIsUntouched(previous.canonical)) {
                    await restoreCanonicalConversation(previous.canonical, restoreSettings);
                } else {
                    // GET/configuration failure before activation: preserve the
                    // existing DOM, focused editor, and live card iframes.
                    await restoreSettings();
                }
            }
            assertRecoveryAccount(previous);
            assertCanonicalConversationScope();
            pendingCardScriptCharacter = null;
            buildRuntimeUi();
            const restoredUrl = new URL(window.location.href);
            restoredUrl.searchParams.set('homer_app_id', launch.app_id);
            restoredUrl.searchParams.set('homer_conversation_id', launch.conversation_id);
            restoredUrl.searchParams.delete('app_id');
            restoredUrl.searchParams.delete('conversation_id');
            restoredUrl.searchParams.delete('conv_id');
            window.history.replaceState({}, '', restoredUrl);
            console.error(`${MODULE_ID}: conversation switch failed; previous canonical chat restored`, error);
            showHostNotice(String(error?.message || '历史会话切换失败'), 'error');
            notifyHostConversation('conversation-switch-failed', {
                failed_app_id: targetAppId,
                failed_conversation_id: targetConversationId,
                ...bootstrapAcknowledgement,
            });
        } catch (recoveryError) {
            // No false ready/state event: the canonical state is unavailable.
            blockConversationRecovery(recoveryError, bootstrapToken);
            console.error(`${MODULE_ID}: previous conversation recovery failed`, recoveryError);
        } finally {
            suppressSync = previousSuppressSync;
        }
    } finally {
        loadingLaunch = false;
        document.body.classList.remove('homer-switching-chat');
        queueMessageMenuRender();
    }
}

async function copyDiagnostic(value) {
    const text = JSON.stringify(safeDiagnostic(value), null, 2);
    try { await navigator.clipboard.writeText(text); }
    catch {
        const field = document.createElement('textarea'); field.value = text;
        document.body.append(field); field.select();
        const copied = document.execCommand('copy'); field.remove();
        if (!copied) { showHostNotice('复制失败，请允许剪贴板访问后重试', 'error'); return; }
    }
    showHostNotice('诊断日志已复制（不含正文与密钥）', 'success');
}

function renderDiagnosticButtons() {
    if (!session?.user?.is_admin) return;
    for (const element of document.querySelectorAll('#chat .mes')) {
        const message = getContext().chat[Number(element.getAttribute('mesid'))];
        const value = message?.extra?.homer_diagnostic;
        if (!value || element.querySelector('.homer-copy-diagnostic')) continue;
        const button = createElement('button', 'homer-copy-diagnostic', '复制诊断日志');
        button.type = 'button';
        button.addEventListener('click', () => copyDiagnostic(message.extra.homer_diagnostic));
        element.querySelector('.mes_block')?.append(button);
    }
    let failed = document.querySelector('#homer-failed-diagnostic');
    if (lastGenerationDiagnostic?.status === 'failed') {
        if (!failed) {
            failed = createElement('button', 'homer-copy-diagnostic', '复制本次失败日志');
            failed.type = 'button'; failed.id = 'homer-failed-diagnostic';
            failed.addEventListener('click', () => copyDiagnostic(lastGenerationDiagnostic));
            document.querySelector('#chat')?.append(failed);
        }
    } else failed?.remove();
}

function installEventHandlers() {
    if (eventHandlersInstalled) {
        return;
    }
    eventHandlersInstalled = true;
    mountModelGate();
    eventSource.on(event_types.MESSAGE_RECEIVED, () => window.setTimeout(renderDiagnosticButtons, 100));
    eventSource.on(event_types.CHAT_LOADED, () => window.setTimeout(renderDiagnosticButtons, 100));
    eventSource.on(event_types.MESSAGE_SENT, messageIndex => {
        scheduleSync();
        void logDialogueEvent('message_send', Number(messageIndex));
        queueMessageMenuRender();
        scheduleHostStateNotify(0, 'message-sent');
    });
    eventSource.on(event_types.MESSAGE_EDITED, messageIndex => {
        scheduleSync();
        void logDialogueEvent('message_edit', Number(messageIndex));
        queueMessageMenuRender();
        scheduleHostStateNotify(0, 'message-edited');
    });
    eventSource.on(event_types.MESSAGE_DELETED, messageIndex => {
        scheduleSync();
        void logDialogueEvent('message_delete', Number(messageIndex));
        queueMessageMenuRender();
        scheduleHostStateNotify(0, 'message-deleted');
    });
    eventSource.on(event_types.MESSAGE_SWIPED, messageIndex => {
        scheduleSync();
        void logDialogueEvent('swipe', Number(messageIndex));
        queueMessageMenuRender();
        scheduleHostStateNotify(0, 'message-swiped');
    });
    for (const event of [event_types.MESSAGE_RECEIVED, event_types.MESSAGE_UPDATED]) {
        eventSource.on(event, () => {
            scheduleSync();
            queueMessageMenuRender();
            scheduleHostStateNotify(60, 'message-updated');
        });
    }
    eventSource.on(event_types.CHAT_COMPLETION_SETTINGS_READY, async data => {
        if (!launch) return;
        assertCanonicalConversationScope();
        await refreshOfficialRegex(String(data.model || ''));
        assertCanonicalConversationScope();
        // Per-request only: never persist private admin drafts into account settings.
        if (launch.admin_preview) data.custom_include_body = JSON.stringify({ homer_preview: adminConversationDraft });
    });
    window.addEventListener('homer-generation-diagnostic', event => {
        // Summaries and extension calls are not replies in the visible chat.
        if (event.detail.generation_type === 'quiet') return;
        lastGenerationDiagnostic = { ...event.detail, display_regex_count: officialRegexState.count,
            display_regex_errors: officialRegexState.errors };
        if (event.detail.status === 'failed') {
            // The embedded shell hides the upstream stop button. Its computed
            // display guard can suppress GENERATION_ENDED on a failed stream.
            // Settle only this snapshot, after the real processor has stopped.
            const failedSnapshot = generationSnapshot;
            const settle = async (attempt = 0) => {
                if (!failedSnapshot || generationSnapshot !== failedSnapshot) return;
                if (isGenerating()) {
                    if (attempt < 100) window.setTimeout(() => void settle(attempt + 1), 50);
                    return;
                }
                generationSnapshot = null;
                generationRecoveryChain = generationRecoveryChain.then(async () => {
                    try { await recoverFailedGeneration(failedSnapshot); }
                    finally {
                        generationBusy = false; document.body.classList.remove('homer-generating');
                        renderDiagnosticButtons(); queueMessageMenuRender();
                    }
                }).catch(() => showHostNotice('失败消息恢复未完成，请重新进入会话', 'error'));
            };
            window.setTimeout(() => void settle(), 50);
        }
        if (session?.user?.is_admin) {
            const messages = getContext().chat;
            const reply = [...messages].reverse().find(message => !message.is_user && !message.is_system);
            if (reply && event.detail.status === 'complete') {
                reply.extra ||= {};
                reply.extra.homer_diagnostic = lastGenerationDiagnostic;
            }
            renderDiagnosticButtons();
        }
    });
    eventSource.on(event_types.GENERATION_STARTED, (type, _options, dryRun) => {
        enforceStreamingConfiguration();
        // SillyTavern and prompt extensions use dry-run generations to assemble or
        // count prompts. A dry run has no matching GENERATION_ENDED event, so it
        // must never put Homer message actions into a persistent busy state.
        if (dryRun) {
            return;
        }
        lastGenerationDiagnostic = null;
        window.clearTimeout(generationSettleTimer);
        generationSettleTimer = null;
        generationSnapshot = captureGenerationSnapshot(type);
        generationBusy = true;
        document.body.classList.add('homer-generating');
        queueMessageMenuRender();
        scheduleHostStateNotify(0, 'generation-started');
    });
    for (const event of [event_types.GENERATION_ENDED, event_types.GENERATION_STOPPED]) {
        eventSource.on(event, () => {
            window.clearTimeout(generationSettleTimer);
            generationSettleTimer = null;
            const snapshot = generationSnapshot;
            generationSnapshot = null;
            // 串成一条链，避免连点重生成时两次恢复互相踩。
            generationRecoveryChain = generationRecoveryChain.then(async () => {
                try {
                    const recovered = await recoverFailedGeneration(snapshot);
                    renderDiagnosticButtons();
                    if (!recovered) {
                        window.clearTimeout(syncTimer);
                        syncTimer = null;
                        await syncCloudChat({ localOnly: true });
                    }
                } catch (error) {
                    console.error(`${MODULE_ID}: failed generation recovery did not complete`, error);
                    showHostNotice('回复生成失败，请刷新当前会话后重试。', 'error');
                    updateRuntimeStatus('生成恢复失败', 'warning');
                }
                // Never await a shared timer that the next GENERATION_STARTED
                // clears: that leaves this recovery chain pending forever.
                generationBusy = isGenerating();
                document.body.classList.toggle('homer-generating', generationBusy);
                generationSettleTimer = null;
                queueMessageMenuRender();
                scheduleHostStateNotify(0, 'generation-ended');
            });
        });
    }
    eventSource.on(event_types.CHAT_CHANGED, () => {
        closeMessageMenu();
        window.setTimeout(renderPresetLists, 100);
        window.setTimeout(queueMessageMenuRender, 100);
    });
    eventSource.on(event_types.SETTINGS_UPDATED, () => {
        enforceStreamingConfiguration();
        void saveConversationExtensionSettings().catch(error => {
            console.warn(`${MODULE_ID}: extension settings persistence failed`, error);
        });
    });
    window.addEventListener('online', refreshBridgeToken);
    window.addEventListener('online', () => { void replayPendingStorage(); });
    window.addEventListener('pagehide', () => {
        // Stop delayed visibility work, retaining image registration for a
        // possible back/forward document restore. Root replacement disposes it.
        historyCoverLoader?.close();
        window.clearTimeout(sessionPrefetchTimer);
        sessionPrefetchTimer = null;
        sessionPrefetchCache.clear();
        sessionPrefetchPeer = null;
        window.clearTimeout(syncTimer);
        syncTimer = null;
        // Do not send oversized histories through the 64-KiB keepalive quota.
        // Generation completion already awaits the ordinary storage ACK.
        void syncCloudChat({ keepaliveOnly: true });
        void flushExtensionSettingsPersist({ force: true, keepalive: true }).catch(() => {});
    });
}

async function bootstrapLaunch(preloadedSession = null, administratorExtensionsPromise = Promise.resolve(), bootstrapToken = '', preparedResources = null) {
    if (loadingLaunch || !requestedAppId) {
        if (!requestedAppId) {
            failRuntimeGate(new Error('缺少角色会话参数，请从惑梦角色页重新进入。'));
        }
        return;
    }
    loadingLaunch = true;
    // Direct/legacy entry may not have a shared prewarm document. Start the
    // same optional byte preparation beside hydration; never await a hint.
    preloadStaticDialogueUi();
    performance.mark('homer-bootstrap-start');
    performance.mark('homer-session-start');
    notifyHostLoading('正在同步当前会话…');
    try {
        setRuntimeGate('正在确认会话', '正在读取账号、角色与云端存档…');
        session = preloadedSession || await fetchSession(requestedAppId, requestedConversationId, Boolean(launch?.admin_preview || adminPreviewRequested));
        performance.mark('homer-session-ready');
        setAccessClasses(session?.user);
        if (!session?.launch) {
            throw new Error('没有可启动的角色会话');
        }
        launch = session.launch;
        const initialCharacterRead = prepareInitialCharacterRead(preparedResources?.character);
        const preparedHeader = prepareLaunchMirrorHeader(preparedResources?.character);
        prefetchPersonaAvatarsForConversation({
            userId: session.user?.id || session.user?.user_id,
            appId: launch.app_id, conversationId: launch.conversation_id,
        });
        setRuntimeGate('正在恢复配置', '同步模型、预设、扩展与当前对话设置…');
        notifyHostLoading('正在读取角色卡配置…');
        const startupData = launch.admin_preview && session.adminStartupData;
        delete session.adminStartupData;
        if (startupData) {
            runtimeVariables = {};
            replaceExtensionSettings(cloneJsonObject(extensionSettingsBaseline || {}));
            runtimeUiData = { ...runtimeUiData, models: payloadList(startupData.models).filter(item => item?.enabled !== false), modelDefaultId: String(startupData.models?.default_id || '') };
            adminConversationConfig = startupData.config;
            officialRegexState = setOfficialDisplayRules(startupData.config.display_regex);
            void loadConversationMods();
        } else {
            const modelCatalogWork = loadRuntimeUiData(preparedResources?.models);
            await Promise.all([loadRuntimeState(preparedResources?.state, modelCatalogWork, preparedResources?.regex), modelCatalogWork]);
        }
        performance.mark('homer-bootstrap-hydrated');
        applyConnectionConfiguration();
        // Render navigation/settings immediately so the user never falls
        // through to the inherited runtime UI during a large card import.
        buildRuntimeUi();
        setRuntimeGate('正在装载角色卡', '解析世界书、正则、脚本与角色资源…');
        notifyHostLoading('正在装载角色卡、世界书与扩展…');
        // Extension discovery can run beside session/UI hydration, but card
        // import must not start until every administrator-approved compatibility
        // hook is active.
        await administratorExtensionsPromise;
        performance.mark('homer-bootstrap-extensions');
        // The embedded client already has settings, extensions and characters
        // at core-ready. Do not keep the visible cloud conversation behind the
        // standalone runtime's remaining backgrounds/tokenizers/personas work.
        // Extensions that attach APP_READY-time listeners receive an explicit
        // state replay below once that non-critical initialization completes.
        performance.mark('homer-bootstrap-core-ready');
        await importLaunchCharacter({ reuseActiveCharacter: true, initialRead: initialCharacterRead, preparedHeader });
        performance.mark('homer-card-ready');
        setRuntimeGate('正在恢复对话', '载入云端消息并校准候选回复…');
        performance.mark('homer-bootstrap-card-imported');
        notifyHostLoading('正在恢复云端对话…');
        const needsApplicationReadyReplay = !applicationReady;
        await loadCloudChat();
        performance.mark('homer-bootstrap-cloud-loaded');
        // The same launch's shell is already mounted. Hydrate its lists in
        // place rather than reconstructing every dialog after message load.
        renderPresetLists(presetSearchQuery);
        queueMessageMenuRender();
        installEventHandlers();
        await installTavoConversationUi();
        installMessageMenu();
        installTokenRefresh();
        // Native startup may normalize the API selectors after the early
        // core-ready configuration. Reapply the conversation bridge once all
        // upstream initialization has finished so the first send uses Homer,
        // not an empty/default provider.
        applyConnectionConfiguration();
        const cleanUrl = new URL(window.location.href);
        cleanUrl.searchParams.set('homer_app_id', launch.app_id);
        cleanUrl.searchParams.set('homer_conversation_id', launch.conversation_id);
        cleanUrl.searchParams.delete('app_id');
        cleanUrl.searchParams.delete('conversation_id');
        cleanUrl.searchParams.delete('conv_id');
        window.history.replaceState({}, '', cleanUrl);
        updateRuntimeStatus(launch.local_pending ? '本机已保存，等待同步' : '云端已同步', launch.local_pending ? 'warning' : 'online');
        reaffirmConversationConnection();
        window.setTimeout(reaffirmConversationConnection, 800);
        setRuntimeGate('梦境已就绪', '正在呈现完整对话界面…');
        await releaseRuntimeGate();
        document.documentElement.classList.add('homer-runtime-ready');
        positionContinuationControl(true);
        performance.mark('homer-bootstrap-ready');
        notifyHostConversation('ready', normalizeBootstrapToken(bootstrapToken) ? { bootstrap_token: bootstrapToken } : {});
        void replayPendingStorage();
        if (needsApplicationReadyReplay) {
            const replayLaunch = launch;
            void applicationReadyPromise.then(async () => {
                await postApplicationReadyWork;
                if (launch !== replayLaunch) return;
                performance.mark('homer-bootstrap-app-ready');
                applyConnectionConfiguration();
                await eventSource.emit(event_types.CHAT_CHANGED, getContext().chatId);
                await eventSource.emit(event_types.CHAT_LOADED, getContext().chatId);
                reaffirmConversationConnection();
            }).catch(error => {
                console.warn(`${MODULE_ID}: post-ready extension replay failed`, error);
            });
        }
        // History can be large and is not part of the current conversation's
        // critical path. Populate only its existing drawer nodes after the
        // chat is interactive; do not rebuild or navigate the page.
        window.setTimeout(() => {
            void loadConversationHistory();
        }, 250);
    } catch (error) {
        console.error(`${MODULE_ID}: launch failed`, error);
        document.body.classList.add('homer-runtime-error');
        failRuntimeGate(error);
        showHostNotice(String(error?.message || '对话模块启动失败'), 'error');
        notifyHostError(bootstrapToken);
    } finally {
        loadingLaunch = false;
        tavoComposer?.refresh();
        queueMessageMenuRender();
    }
}

async function startHomerBridge() {
    installKeywordInjector({ active: Boolean(requestedAppId), persist: saveConversationExtensionSettings, logEvent: logDialogueEvent });
    runtimeGate()?.querySelector('.homer-runtime-gate__retry')?.addEventListener('click', () => {
        document.body.classList.remove('homer-runtime-error');
        setRuntimeGate('正在重新连接', '重新读取账号、角色卡与云端存档…');
        void bootstrapLaunch();
    });
    setRuntimeGate('正在连接惑梦', '确认登录状态、角色存档与对话扩展…');
    notifyHostLoading('正在初始化对话能力…');
    if (prewarmOnly) {
        performance.mark('homer-bind-start');
    }
    // Selection is now explicit. Start authorized read-only configuration
    // beside the session transfer, but do not apply it or execute the card
    // until fetchSession verifies this exact owner and launch below.
    const preparedResources = requestedAppId && requestedConversationId && !adminPreviewRequested
        && reconcileStorageAccount() ? prepareConversationResources(requestedAppId, requestedConversationId) : null;
    const selectedRead = prewarmOnly && !adminPreviewRequested && requestedAppId && requestedConversationId
        && sessionPrefetchCache.get(sessionCacheKey(requestedAppId, requestedConversationId));
    const launchSessionPromise = requestedAppId
        ? (launchSessionPreloadPromise ||= selectedRead
            ? takePrefetchedSession(requestedAppId, requestedConversationId)
            : fetchSession(requestedAppId, requestedConversationId, adminPreviewRequested))
        : fetchSession('', '', adminPreviewRequested);
    const administratorExtensionsPromise = prewarmBootstrapPromise || ensureAdministratorExtensions();
    try {
        const launchSession = await launchSessionPromise;
        session = launchSession;
        setAccessClasses(launchSession?.user);
        captureExtensionSettingsBaseline();
        installPresentationModeBridge();
        installRoleplayHubCompatibility();
        installCardStageRuntime();
        await bootstrapLaunch(launchSession, administratorExtensionsPromise, boundBootstrapToken, preparedResources);
    } catch (error) {
        console.error(`${MODULE_ID}: launch bootstrap failed`, error);
        failRuntimeGate(error);
        notifyHostError(boundBootstrapToken);
    }
}

export async function init() {
    if (initialized) {
        return;
    }
    initialized = true;
    if (prewarmOnly) notifyHost('bridge-available', hostBootstrapEngineToken ? {
        engine_token: hostBootstrapEngineToken, document_token: hostBootstrapDocumentToken,
    } : {});
    installProductSurfaceBoundary();
    installEmbeddedComposerPolicy();
    notifyHostLoading('正在准备对话…');
    ensureHomerExtensionSettingDefaults();
    installExtensionSettingsPersistenceBridge();
    installKeywordInjector({
        active: Boolean(requestedAppId),
        persist: saveConversationExtensionSettings,
        logEvent: logDialogueEvent,
    });
    // Built-in extensions activate while settings load, so the bridge cannot
    // start directly from this hook. The host runtime announces a narrower
    // core-ready point after settings/extensions/characters are available;
    // standalone initialization can then finish in parallel. APP_READY remains
    // a safe fallback for upstream runtimes that do not emit the early event.
    const scheduleBridgeStart = () => {
        coreAvailable = true;
        performance.mark('homer-prewarm-core-ready');
        if (prewarmOnly && !requestedAppId) {
            // Prepare the engine, not a user's previous card. No session is
            // opened, no card script runs, and no generation is requested.
            beginSharedPrewarm();
            notifyHost('core-ready', hostBootstrapEngineToken ? {
                engine_token: hostBootstrapEngineToken, document_token: hostBootstrapDocumentToken,
            } : {});
            return;
        }
        if (bridgeStartScheduled) {
            return;
        }
        bridgeStartScheduled = true;
        void startHomerBridge();
    };
    // Begin read-only session/UI/extension hydration at core-ready. The
    // bootstrap itself gates character selection and chat loading on APP_READY,
    // so third-party APP_READY-time CHAT_CHANGED subscriptions remain intact.
    window.addEventListener('homer:runtime-core-ready', () => {
        if (requestedAppId && !launchSessionPreloadPromise) {
            launchSessionPreloadPromise = fetchSession(requestedAppId, requestedConversationId, adminPreviewRequested);
        }
        scheduleBridgeStart();
    }, { once: true });
    eventSource.once(event_types.APP_READY, () => {
        applicationReady = true;
        resolveApplicationReady?.();
        // Do not widen the runtime document lookup surface while upstream
        // built-in extensions are still activating.  In particular, their
        // startup probes must only see the runtime DOM; falling through into
        // the website shell can make an unrelated host control look like an
        // upstream setting node and stall extension activation.  Card scripts
        // do not run before APP_READY, so installing the compatibility bridge
        // here preserves their parent/top lookup contract without extending
        // the critical startup path.
        installEmbeddedDocumentLookupBridge();
        scheduleBridgeStart();
        if (!reaffirmExtensionSettingsAfterReady || !conversationExtensionSettings) {
            return;
        }
        reaffirmExtensionSettingsAfterReady = false;
        postApplicationReadyWork = (async () => {
            replaceExtensionSettings(conversationExtensionSettings);
            reaffirmSelectedCardCapabilities();
            await eventSource.emit(event_types.SETTINGS_LOADED);
            const snapshot = extensionSettingsSnapshot();
            lastExtensionSettingsScope = extensionSettingsScope();
            lastExtensionSettingsSignature = snapshot.signature;
        })().catch(error => {
            console.warn(`${MODULE_ID}: post-ready conversation settings replay failed`, error);
        });
    });
}
