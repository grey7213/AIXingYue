// This is a single CHAT_CHANGED -> CHAT_LOADED transaction, not a rendered-card
// cache. EJS, world-info and public events still run normally on every restore.
const element = value => value?.nodeType === 1;

function wrapperSource(wrapper) {
    const pre = wrapper.querySelector(':scope > pre');
    if (!pre) return null;
    return Array.from(pre.querySelectorAll('code'), node => node.textContent).join('');
}

export function createMessageIframeRenderBatch({ getScope, getSettings } = {}) {
    let batch = null;
    let snapshots = new WeakMap();
    const cleanups = new Set();

    function snapshotIdentity() {
        try {
            const scope = getScope();
            const settings = JSON.stringify(getSettings());
            return typeof scope === 'string' && scope !== '' && typeof settings === 'string'
                ? { scope, settings } : null;
        } catch { return null; }
    }

    function invalidate() {
        for (const cleanup of cleanups) cleanup();
        cleanups.clear();
        snapshots = new WeakMap();
    }

    function begin() {
        invalidate();
        batch = {};
    }

    function captureSource(wrapper, source) {
        if (!batch || !element(wrapper) || typeof source !== 'string') return;
        const identity = snapshotIdentity();
        if (!identity) return;
        snapshots.set(wrapper, { batch, ...identity, source, frame: null, failed: false });
    }

    function mounted(wrapper, frame) {
        const state = snapshots.get(wrapper);
        if (!state || state.batch !== batch || !element(frame) || frame.tagName !== 'IFRAME') return;
        state.frame = frame;
        const failed = () => { state.failed = true; };
        frame.addEventListener('error', failed);
        cleanups.add(() => frame.removeEventListener('error', failed));
    }

    function disposed(wrapper, frame) {
        const state = snapshots.get(wrapper);
        if (state?.frame === frame) { state.failed = true; state.frame = null; }
    }

    function reusable(wrapper, identity) {
        const state = snapshots.get(wrapper);
        if (!state || state.batch !== batch || state.failed || state.scope !== identity.scope
            || state.settings !== identity.settings || !wrapper.isConnected || !state.frame?.isConnected
            || !wrapper.contains(state.frame) || wrapper.querySelector(':scope > iframe') !== state.frame) return false;
        try {
            return state.frame.contentWindow != null && wrapperSource(wrapper) === state.source;
        } catch { return false; }
    }

    function consume(existing, fresh) {
        const identity = batch && snapshotIdentity();
        try {
            if (!identity || !Array.isArray(existing) || !Array.isArray(fresh)) return fresh;
            return fresh.map(next => {
                const previous = existing.find(row => row.message_id === next.message_id);
                return previous && Array.isArray(previous.elements) && Array.isArray(next.elements) && previous.elements.length > 0
                    && previous.elements.length === next.elements.length
                    && next.elements.every((wrapper, index) => wrapper === previous.elements[index] && reusable(wrapper, identity))
                    ? previous : next;
            });
        } catch {
            return fresh;
        } finally {
            batch = null;
            invalidate();
        }
    }

    return { begin, captureSource, mounted, disposed, invalidate, consume };
}
