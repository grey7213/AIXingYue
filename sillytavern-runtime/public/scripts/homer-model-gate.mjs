// A failed provider is paused only in its owning account/conversation scope.
const failures = new Map();
const providerCodes = new Set(['HM-G204', 'HM-G429', 'HM-G502', 'HM-G503', 'HM-G504', 'HM-GNET']);
let scope = '', selected = '', mounted = false;
export const currentModelScope = () => scope;
const key = value => `homer:model-pause:v1:${value}`;
function read(value) {
    if (failures.has(value)) return failures.get(value);
    try {
        const saved = JSON.parse(sessionStorage.getItem(key(value)) || 'null');
        if (saved && typeof saved.model === 'string' && providerCodes.has(saved.code)) failures.set(value, saved);
    } catch { /* Private browsing/storage errors must not block switching models. */ }
    return failures.get(value);
}
function save(value, failure) {
    if (failure) failures.set(value, failure); else failures.delete(value);
    try {
        if (failure) sessionStorage.setItem(key(value), JSON.stringify(failure));
        else sessionStorage.removeItem(key(value));
    } catch { /* Keep the in-memory gate. */ }
}
export function activateModelScope(value, model) {
    scope = String(value || ''); selected = String(model || ''); render();
}
export function confirmModelChange(model) {
    const failed = scope && read(scope);
    if (failed && String(model) !== failed.model) save(scope, null);
    selected = String(model || ''); render();
}
export function recordModelFailure(trace) {
    if (!trace?.scope || trace.status !== 'failed' || !providerCodes.has(trace.error_code)) return;
    save(trace.scope, { model: String(trace.model || ''), code: trace.error_code });
    render();
}
export function modelIsPaused(model = selected, value = scope) {
    return Boolean(value && read(value)?.model === String(model));
}
export function requireAvailableModel(model) {
    if (!modelIsPaused(model)) return;
    const error = new Error('当前模型繁忙或暂不可用，请更换模型后继续');
    error.code = 'HM-GLOCK'; throw error;
}
function render() {
    if (!mounted || typeof document === 'undefined') return;
    const paused = modelIsPaused();
    document.body.classList.toggle('homer-model-paused', paused);
    const button = document.querySelector('#send_but');
    if (button) {
        if (paused) button.setAttribute('aria-disabled', 'true');
        else button.removeAttribute('aria-disabled');
    }
    let notice = document.getElementById('homer-model-pause-notice');
    const form = document.querySelector('#send_form');
    if (!notice && form) {
        notice = document.createElement('small');
        notice.id = 'homer-model-pause-notice'; notice.setAttribute('role', 'status');
        form.insertAdjacentElement('beforebegin', notice);
    }
    if (notice) {
        notice.hidden = !paused;
        notice.textContent = paused ? `当前模型繁忙或暂不可用，请更换模型后继续。〔${read(scope).code}〕` : '';
    }
}
export function mountModelGate() {
    if (mounted) return;
    mounted = true;
    document.addEventListener('click', event => {
        if (modelIsPaused() && event.target.closest?.('#send_but')) {
            event.preventDefault(); event.stopImmediatePropagation(); render();
        }
    }, true);
    document.addEventListener('keydown', event => {
        if (modelIsPaused() && event.target.id === 'send_textarea' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault(); event.stopImmediatePropagation(); render();
        }
    }, true);
    render();
}
