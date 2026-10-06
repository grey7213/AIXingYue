// Genuine APK presentation components; Homer remains the only conversation engine.
// Message chrome is built with EMPTY text. Ordinary .mes_text nodes are reused;
// interactive bodies receive chrome classes in-place without reparenting iframe.
import { updateMessagePresentation } from './message-presentation.js';
const VENDOR = '/assets/vendor/tavo';
let loading;
let activeComposer;
let themeSignature = '';
const decorated = new Map();
let cleanupObserver;
let canonicalFocusListenerInstalled = false;
const canonicalFocusControls = new WeakSet();
const presentationAssetRequests = new Map();

// Embedded card helpers deliberately fall back from runtime document lookups
// to the website host. Presentation resources and canonical controls must not:
// a host link cannot style the iframe, nor can a host input own engine state.
function localElementById(id) {
    const element = Document.prototype.getElementById.call(document, id);
    return element?.ownerDocument === document ? element : null;
}

function localQuerySelector(selector) {
    return Document.prototype.querySelector.call(document, selector);
}

// SillyTavern's hidden input remains its send state, not the visible editor.
// Keep its legacy instance-level .focus() calls from scrolling this iframe or
// opening a second keyboard. Other inputs and HTMLElement.prototype stay intact.
export function installTavoComposerFocusRelay() {
    if (!document.documentElement.classList.contains('homer-host-chrome') || window.parent === window) return;
    const forward = () => {
        try {
            const host = window.parent.document;
            const container = host.getElementById('shared-composer');
            const input = container?.querySelector('[data-tav-role="input"]');
            if (!(input instanceof window.parent.HTMLTextAreaElement) || input.disabled || !host.hasFocus()
                || host.body.classList.contains('has-runtime-overlay') || localQuerySelector('dialog[open]')
                || host.querySelector('dialog[open]') || !input.getClientRects().length
                || window.parent.getComputedStyle(container).visibility === 'hidden'
                || window.parent.getComputedStyle(input).visibility === 'hidden') return;
            input.focus({ preventScroll: true });
        } catch { /* No focus handoff outside the same-origin visible host. */ }
    };
    const canonical = localElementById('send_textarea');
    if (canonical instanceof HTMLTextAreaElement && !canonicalFocusControls.has(canonical)) {
        canonicalFocusControls.add(canonical);
        canonical.focus = forward;
    }
    if (!canonicalFocusListenerInstalled) {
        canonicalFocusListenerInstalled = true;
        document.addEventListener('focusin', event => {
            if (event.target !== localElementById('send_textarea')) return;
            event.target.blur();
            forward();
        }, true);
    }
}

const scaffoldMarkup = `<div class="tav-chat-container homer-tavo-scaffold">
<section class="tav-chat-composer tav-composer tavo-composer" data-tav-role="composer-root" hidden>
<div class="tav-chat-composer-attachments" data-tav-role="attachments" hidden></div>
<div class="tav-chat-composer-group-repliers" data-tav-role="group-repliers" hidden></div>
<div class="tav-chat-composer-shell tav-composer-shell tavo-composer-shell" data-tav-role="shell">
<button type="button" class="tav-composer-leading-button" data-tav-role="plus" aria-label="添加内容"><span class="tav-composer-add-icon tavo-composer-add-icon" data-tav-role="plus-icon" aria-hidden="true"></span></button>
<textarea class="tav-chat-composer-input tav-composer-input tavo-composer-input" data-tav-role="input" rows="1" aria-label="消息内容" maxlength="10000"></textarea>
<button type="button" data-tav-role="asr-cancel-recording" hidden><span></span></button>
<button type="button" class="tav-composer-trailing-button" data-tav-role="trailing" aria-label="发送"><span data-tav-role="trailing-icon" aria-hidden="true"></span></button>
</div><div class="tav-chat-composer-shortcuts" data-tav-role="shortcut-bar" hidden></div><div class="tav-chat-asr-overlay" data-tav-role="asr-overlay" hidden></div></section></div>
<button class="tav-scroll-top-button" hidden></button><button class="tav-scroll-bottom-button" hidden></button>
<button class="tav-selection-here-top-button" hidden><span class="tav-selection-here-label"></span></button>
<button class="tav-selection-here-bottom-button" hidden><span class="tav-selection-here-label"></span></button>`;

// These three fixed public assets are the only speculative presentation hints.
// A failed preload can poison the first actual consumer in Chromium. Consume
// that failure and retry the same URL once, within the original activation
// promise; never recreate the composer/scaffold or retry private API writes.
function presentationAsset(id, href, kind) {
    const existing = localElementById(id);
    if (kind === 'style' && existing?.sheet) return Promise.resolve();
    if (presentationAssetRequests.has(id)) return presentationAssetRequests.get(id);
    let start;
    const ready = new Promise((resolve, reject) => {
        const attempt = (remaining, previous = null) => {
            const node = previous || document.createElement(kind === 'style' ? 'link' : 'script');
            if (!previous) {
                node.id = id;
                if (kind === 'style') { node.rel = 'stylesheet'; node.href = href; }
                else node.src = href;
            }
            let settled = false;
            const cleanup = () => {
                clearTimeout(timer);
                node.removeEventListener('load', loaded);
                node.removeEventListener('error', failed);
            };
            const loaded = () => {
                if (settled) return;
                settled = true; cleanup(); presentationAssetRequests.delete(id); resolve();
            };
            const fail = retry => {
                if (settled) return;
                settled = true; cleanup(); node.remove();
                if (retry && remaining > 0) { attempt(remaining - 1); return; }
                presentationAssetRequests.delete(id);
                reject(new Error(kind === 'style' ? '对话样式未能加载' : '对话组件未能加载'));
            };
            const failed = () => fail(true);
            // Preserve the stylesheet deadline without doubling the wait.
            // Removing an in-flight classic script cannot guarantee execution
            // is cancelled. Keep its original load/error settlement so a slow
            // request cannot race a second initialization after a timeout.
            const timer = kind === 'style' ? setTimeout(() => fail(false), 15000) : null;
            node.addEventListener('load', loaded, { once: true });
            node.addEventListener('error', failed, { once: true });
            if (!previous) {
                try { document.head.append(node); } catch { fail(false); }
            }
        };
        start = () => attempt(1, existing);
    });
    presentationAssetRequests.set(id, ready);
    start();
    return ready;
}

function stylesheet(id, href) {
    return presentationAsset(id, href, 'style');
}

function response(requestId, value = null, error = null) {
    if (requestId) queueMicrotask(() => window.tav?.JSBridge?._handleFlutterResponse(requestId, value, error));
}

function dispatchOriginalCall(serialized) {
    let call;
    try { call = JSON.parse(serialized); } catch { return; }
    const params = call.params || {};
    if (call.method === 'loadItems') { response(call.requestId, { items: [], start: 0, end: 0, total: 0 }); return; }
    const telemetry = ['init', 'webViewReady', 'onScroll', 'messageRendered', 'messageHeightChanged'];
    if (telemetry.includes(call.method)) { response(call.requestId); return; }
    const controller = activeComposer;
    if (!controller || controller.disposed) { response(call.requestId, null, { code: 'HM-UI001', message: '会话已经切换' }); return; }
    const state = controller.options.getState() || {};
    const identity = controller.identity;
    if (call.method.startsWith('composer') && (params.navigationSession !== identity.navigationSession || params.conversationId !== identity.conversationId)) {
        response(call.requestId, null, { code: 'HM-UI002', message: '会话已经切换' }); return;
    }
    const method = {
        composerTextChanged: 'onText', composerSubmit: 'onSubmit', composerStop: 'onStop',
        composerOpenPlus: 'onPlus', composerOpenFullscreen: 'onFullscreen',
    }[call.method];
    if (!method) { response(call.requestId, null, { code: 'HM-UI003', message: '此操作不适用' }); return; }
    if (state.disabled && call.method !== 'composerTextChanged') { response(call.requestId, null, { code: 'HM-UI004', message: '当前会话不可修改' }); return; }
    if (call.method === 'composerSubmit' && state.generating) { response(call.requestId); return; }
    // Request-style calls always settle. Their callback executes the existing
    // engine command, not a parallel model request or a synthetic reply.
    const scope = String(state.scope || ''), navigationSession = identity.navigationSession;
    Promise.resolve().then(() => {
        if (activeComposer !== controller || controller.disposed || controller.identity.navigationSession !== navigationSession || String(controller.options.getState()?.scope || '') !== scope) throw new Error('会话已经切换');
        return controller.options[method]?.(String(params.text || '').slice(0, 10000), params);
    })
        .then(value => response(call.requestId, value ?? null), () => response(call.requestId, null, { code: 'HM-UI005', message: '操作未完成，请重试' }))
        .finally(() => { if (activeComposer === controller) controller.refresh(); });
}

function colorStyle(name, fallback) {
    const value = getComputedStyle(document.body).getPropertyValue(name).trim();
    return /^#[\da-f]{6}$/i.test(value) ? value : fallback;
}

export function refreshTavoUi() {
    if (!window.tav?.JSBridge || !window.tav.chatView) return;
    const character = colorStyle('--tavo-assistant-bubble', '#29485f');
    const user = colorStyle('--tavo-user-bubble', '#4c4c4c');
    const background = colorStyle('--chat-bg', '#212121');
    const font = { color: colorStyle('--homer-assistant-text', '#ffffff'), fontSize: 15, fontWeight: 400, toneHighlight: false, quoteHighlight: false };
    const avatar = { radius: 100, name: false, avatar: false };
    const config = {
        env: { os: 'Android', debug: false },
        i10n: { chat_bubble_reasoning: '思考过程', chat_select_message_here: '选到此处', plugin_last_message_actions_more: '更多' },
        settings: { safeTopHeight: 0, disableBlur: true, javaScriptExecutionMode: 'disabled', streamingOutputEffect: 'none', translationEnabled: false, mathRenderMode: 'disabled' },
        webViewport: { backgroundColor: background, backgroundImageUrl: '', backgroundImageOpacity: 0, disableTopFade: true, topFadeHeight: 0, topOverlayInset: 0, bottomContentInset: 0, nativeTopShadow: false, displayMode: 'chat', bottomOverlayColor: 'transparent' },
        theme: { fontFamily: '', colorScheme: { primary: '#b4a5dc', secondary: '#c6a6ff', onSurface: '#fff', onPrimary: '#fff', errorContainer: '#662222', onErrorContainer: '#fff' }, textTheme: { bodySmall: { color: '#fff', fontSize: 12, fontWeight: 400 }, labelLarge: { color: '#fff', fontSize: 14, fontWeight: 500 } }, actionBarButtonColor: '#444', bubbleLoadingColor: '#fff', bubbleMenuColor: '#333', consoleCursorColor: '#fff', consoleOverlayForFlatStyleColor: '#333', contextMenuButtonActiveColor: '#555', defaultAvatarBackgroundColor: '#444', defaultAvatarForegroundColor: '#fff', panelColor: '#333', partnerBalanceColor: '#fff', scrollTopBottomBackgroundColor: '#444', onErrorContainerLinkColor: '#fff', flatSplitterIcon: '' },
        chatTheme: { bubbleDisplayType: 'bubble', userBubbleStyle: { color: user, radius: 16, blur: 0, alignment: 'right' }, characterBubbleStyle: { color: character, radius: 16, blur: 0, alignment: 'left' }, userBubbleFontStyle: { ...font, color: colorStyle('--homer-user-text', '#ffffff') }, characterBubbleFontStyle: { ...font }, userAvatarStyle: { ...avatar }, characterAvatarStyle: { ...avatar }, groupUserAvatarStyle: { ...avatar }, groupCharacterAvatarStyle: { ...avatar }, consoleStyle: { color: '#656668', radius: 22, blur: 0, fontColor: '#fff', placeholderColor: '#ccc', sendColor: '#fff', fontSize: 16, fontWeight: 400 }, customCss: '' },
    };
    const signature = JSON.stringify(config);
    if (signature !== themeSignature || JSON.stringify(window.tav.config) !== signature) {
        // The synchronous original apply method avoids a second theme animation.
        window.tav.JSBridge._applyConfig(config); themeSignature = signature;
    }
}

function resetTavoDocumentViewport() {
    if (document.documentElement.classList.contains('homer-host-chrome') && (window.scrollX || window.scrollY)) {
        // Only the embedded page scroll is invalid. Keep canonical #chat's
        // own scroll position and any live card iframe completely untouched.
        window.scrollTo(0, 0);
    }
}

export function setTavoHostInsets({ top, bottom } = {}) {
    if (!document.documentElement.classList.contains('homer-host-chrome')) return;
    resetTavoDocumentViewport();
    const height = Math.max(1, window.innerHeight);
    const bounded = (value, fallback) => Number.isFinite(Number(value)) ? Math.max(0, Math.min(height, Number(value))) : fallback;
    const style = document.documentElement.style;
    const nextTop = `${bounded(top, 48)}px`, nextBottom = `${bounded(bottom, 72)}px`;
    if (style.getPropertyValue('--homer-host-top') === nextTop && style.getPropertyValue('--homer-host-bottom') === nextBottom) return;
    // Unchanged host measurements must not force layout of a large card while
    // its message/iframe DOM is being restored. Only an actual inset change
    // needs the old bottom position before updating the viewport variables.
    const chat = localElementById('chat');
    const atBottom = chat && chat.scrollHeight - chat.scrollTop - chat.clientHeight <= 8;
    style.setProperty('--homer-host-top', nextTop); style.setProperty('--homer-host-bottom', nextBottom);
    if (atBottom) chat.scrollTop = Math.max(0, chat.scrollHeight - chat.clientHeight);
}

export function loadTavoUi() {
    if (loading) return loading;
    if (new URLSearchParams(location.search).get('homer_host_chrome') === '1') document.documentElement.classList.add('homer-host-chrome');
    installTavoComposerFocusRelay();
    loading = (async () => {
        await stylesheet('homer-tavo-vendor-css', `${VENDOR}/dist/css/bundle.min.css`);
        if (!window.tav?.item?.MessageBubbleItem) {
            if (!localElementById('homer-tavo-scaffold')) {
                const scaffold = document.createElement('div'); scaffold.id = 'homer-tavo-scaffold';
                scaffold.setAttribute('aria-hidden', 'true'); scaffold.innerHTML = scaffoldMarkup;
                document.body.append(scaffold);
            }
            window.TavChannel = Object.freeze({ postMessage: dispatchOriginalCall });
            await presentationAsset('homer-tavo-vendor-js', `${VENDOR}/dist/js/bundle.min.js`, 'script');
        }
        window.tav.JSBridge.setConversation({ isGroup: false, characters: [{ id: 1, name: '角色' }] });
        refreshTavoUi();
        await stylesheet('homer-tavo-integration-css', '/assets/css/tavo-chat-ui.css');
        resetTavoDocumentViewport();
        document.body.classList.add('homer-tavo-ui');
        if (!cleanupObserver) {
            cleanupObserver = new MutationObserver(records => {
                if (!records.some(record => [...record.removedNodes].some(node => node instanceof Element && (node.matches('.mes,.homer-tavo-chrome') || node.querySelector('.mes,.homer-tavo-chrome'))))) return;
                for (const [element, record] of decorated) if (!element.isConnected) { record.view.dispose(); decorated.delete(element); }
            });
            cleanupObserver.observe(document.body, { subtree: true, childList: true });
        }
    })().catch(error => { loading = undefined; throw error; });
    return loading;
}

export function decorateTavoMessage(element, { id = '', isUser = false, hidden = false, collapsed = false } = {}) {
    if (!element || !window.tav?.item?.MessageBubbleItem) return false;
    const content = element.querySelector('.mes_text') || element;
    updateMessagePresentation(content, isUser);
    const existing = decorated.get(element);
    if (existing && existing.content === content && existing.chrome.isConnected) {
        existing.view.item.message.hidden = !!hidden;
        existing.chrome.classList.toggle('homer-tavo-hidden', !!hidden);
        existing.chrome.classList.toggle('homer-tavo-collapsed', !!collapsed);
        return true;
    }
    existing?.view.dispose();
    existing?.chrome.remove();
    const item = { type: 'message', isLast: false, isLastMessage: false, speakerName: '', candidate: { index: 0, size: 1 }, message: { id: String(id), characterId: isUser ? null : 1, isUser: !!isUser, content: '', reasoning: '', attachments: [], toolCards: [], hidden: !!hidden, translated: false, isTranslating: false, actionBarHidden: true, actionBarDisabled: true, bubbleLocked: false } };
    const view = new window.tav.item.MessageBubbleItem(item);
    // Homer owns menu/selection and the message body. Disable only these bridge
    // hooks, not the genuine bubble builder or original composer implementation.
    view._listenContextMenu = () => {};
    view.buildSelectionCheckbox = () => {};
    view._hydrateTavoContent = () => {};
    view._handleConfigChanged = () => {};
    // Homer CSS owns responsive widths (including live card bodies). The
    // vendor's empty-body viewport measurement cannot affect those !important
    // widths, but its per-message RAF forces layout while HTML cards convert.
    // Override only this instance; keep original components and the composer.
    view.setBubbleContentWidth = () => {};
    view.build();
    const body = view.el.querySelector('.tav-bubble-content-body');
    if (!body) { view.dispose(); return false; }
    if (content !== element && content.querySelector('iframe,video,audio,canvas')) {
        // Even a same-document appendChild reloads a live iframe browsing
        // context on old WebViews. Project genuine chrome classes in-place;
        // never reparent interactive card bodies or their existing parent.
        const originalMessage = view.el.querySelector('.tav-message');
        const wrapper = view.el.querySelector('.tav-bubble-wrapper');
        const bubble = view.el.querySelector('.tav-bubble');
        const bubbleContent = view.el.querySelector('.tav-bubble-content');
        element.classList.add('homer-tavo-message', 'homer-tavo-live-message', ...originalMessage.classList);
        const destination = content.parentElement;
        destination.classList.add(...wrapper.classList);
        content.classList.add('homer-tavo-live-content', ...bubble.classList, ...bubbleContent.classList);
        content.classList.toggle('homer-tavo-hidden', !!hidden); content.classList.toggle('homer-tavo-collapsed', !!collapsed);
        view.dispose();
        decorated.set(element, { view, content, chrome: content, live: true });
        return true;
    }
    const chrome = view.el; chrome.classList.add('homer-tavo-chrome');
    chrome.classList.toggle('homer-tavo-hidden', !!hidden); chrome.classList.toggle('homer-tavo-collapsed', !!collapsed);
    if (content === element) {
        // Cached shell callers give us an existing DOM text wrapper, not source
        // HTML. Wrap that same node; runtime always uses canonical .mes_text.
        const parent = element.parentNode;
        if (!parent) { view.dispose(); return false; }
        parent.insertBefore(chrome, element); body.replaceChildren(content);
    } else {
        const destination = element.querySelector('.mes_block') || element;
        body.replaceChildren(content); destination.append(chrome); element.classList.add('homer-tavo-message');
    }
    decorated.set(element, { view, content, chrome });
    return true;
}

export async function mountTavoComposer(options) {
    await loadTavoUi();
    if (!options?.container || typeof options.getState !== 'function') throw new Error('缺少会话输入区域');
    activeComposer?.dispose();
    let root = window.tav.chatComposer.root;
    window.tav.chatComposer.dispose();
    options.container.append(root); root.classList.add('homer-tavo-composer');
    window.tav.chatComposer = new window.tav.ChatComposer(root);
    let inputSizingSuppressed = false;
    if (options.inputSizing !== undefined) {
        // The host-owned runtime still needs this proxy's state and callbacks,
        // but its offscreen input need not measure layout. Leave the vendor
        // prototype, viewport behavior and default visible caller untouched.
        const composer = window.tav.chatComposer, resizeInput = composer._resizeInput;
        composer._resizeInput = function (...args) {
            if (this.disposed) return;
            if ((typeof options.inputSizing === 'function' ? options.inputSizing() : options.inputSizing) === false) {
                inputSizingSuppressed = true; return;
            }
            inputSizingSuppressed = false;
            return resizeInput.apply(this, args);
        };
    }
    let scope = '', chatStateSignature = '';
    const controller = {
        options, identity: { navigationSession: 0, conversationId: 1 }, disposed: false,
        element: root, input: root.querySelector('[data-tav-role="input"]'),
        refresh() {
            if (controller.disposed) return;
            const state = options.getState() || {};
            const nextScope = String(state.scope || '');
            if (nextScope !== scope) { scope = nextScope; controller.identity.navigationSession += 1; }
            refreshTavoUi();
            const composer = window.tav.chatComposer;
            const config = { ...controller.identity, platform: 'Android', placeholder: state.placeholder || '随便聊聊…', sendKey: state.sendKey || 'enter', maxLines: 5, actionsEnabled: !state.disabled, asrEnabled: false, labels: { cancel: '取消', holdToTalk: '按住说话' }, icons: { plus: `${VENDOR}/images/icon_plus.png`, send: `${VENDOR}/images/chat_console_send.png`, stop: `${VENDOR}/images/chat_console_stop.png`, asr: `${VENDOR}/images/chat_console_asr.png`, keyboard: `${VENDOR}/images/chat_console_keyboard.png` } };
            const snapshot = { ...controller.identity, text: String(state.text || '').slice(0, 10000), inputMode: 'text', chatState: state.generating ? 'generating' : 'idle', asrPhase: 'idle', asrVolume: 0, preparing: false, pluginActionPending: false, attachments: [], groupRepliers: [], showGroupRepliers: false, showGroupReplierNames: false, shortcuts: [] };
            // Compare the real vendor state, not just the last host input. Native
            // callbacks can change text, snapshots or controls before refresh.
            // Its configure() performs viewport layout even for identical input.
            if (JSON.stringify(composer.config) !== JSON.stringify(config)) {
                window.tav.JSBridge.configureComposer(config);
            }
            if (JSON.stringify(composer.snapshot) !== JSON.stringify(snapshot)
                || composer.input.value !== snapshot.text || composer.input.readOnly !== false) {
                window.tav.JSBridge.applyComposerSnapshot(snapshot);
            }
            const disabled = !config.actionsEnabled;
            const action = state.generating ? 'stop' : 'send';
            const controlsMatch = composer.input.value === snapshot.text
                && composer.input.disabled === disabled && composer.input.readOnly === false
                && composer.input.placeholder === config.placeholder
                && composer.input.enterKeyHint === (config.sendKey === 'enter' ? 'send' : 'enter')
                && composer.plus.disabled === disabled && composer.plus.hidden === false
                && composer.trailing.disabled === disabled && composer.trailing.dataset.action === action
                && composer.trailingIcon.className === `tav-composer-${action}-icon tavo-composer-${action}-icon`
                && root.hidden === Boolean(composer.selectionMode)
                && composer.inlineLoading.hidden === true && composer.inlineAsrWaveform.hidden === true;
            if (!controlsMatch) window.tav.JSBridge.configureComposer(config);
            const nextChatStateSignature = JSON.stringify([controller.identity, snapshot.chatState]);
            if (chatStateSignature !== nextChatStateSignature || window.tav.chatView.chatState !== snapshot.chatState) {
                window.tav.JSBridge.updateChatState(snapshot.chatState); chatStateSignature = nextChatStateSignature;
            }
            const label = state.generating ? '停止生成' : '发送';
            if (composer.trailing.getAttribute('aria-label') !== label) composer.trailing.setAttribute('aria-label', label);
            // A same-state refresh must restore input sizing if the proxy
            // becomes visible again, even when config/snapshot did not change.
            if (inputSizingSuppressed && (typeof options.inputSizing === 'function' ? options.inputSizing() : options.inputSizing) !== false) composer._resizeInput();
        },
        dispose() {
            if (controller.disposed) return; controller.disposed = true;
            if (activeComposer === controller) { window.tav.chatComposer.dispose(); activeComposer = undefined; }
            root.hidden = true;
        },
    };
    activeComposer = controller; controller.refresh();
    return controller;
}
