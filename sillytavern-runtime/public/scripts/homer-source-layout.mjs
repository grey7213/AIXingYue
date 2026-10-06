// A restored HTML frontend is initially present as literal PRE source. Laying
// out megabytes of that temporary source before its renderer replaces it can
// stall the WebView main thread. Defer only that intermediate layout, never
// its DOM/text, processing events, renderer or final fallback presentation.
const holds = new WeakMap();
export const SOURCE_LAYOUT_HOLD_CLASS = 'homer-preparing-source-layout';

// Keep at most one scroll request per live restore transaction. A microtask
// lets the normal post-finally scroll supersede this request without reading
// the temporary source layout or adding a second final scroll.
export function deferScrollUntilSourceLayoutRelease(root, callback) {
    const state = holds.get(root);
    if (!state || typeof callback !== 'function') return false;
    state.pendingScroll = callback;
    return true;
}

export function holdLargeSourceLayout(root = globalThis.document?.getElementById('chat')) {
    if (!root?.classList) return () => {};
    let state = holds.get(root);
    if (!state) {
        state = { count: 0, alreadyPresent: root.classList.contains(SOURCE_LAYOUT_HOLD_CLASS), pendingScroll: null };
        holds.set(root, state);
        root.classList.add(SOURCE_LAYOUT_HOLD_CLASS);
    }
    state.count++;
    let released = false;
    return () => {
        if (released) return;
        released = true;
        if (--state.count !== 0) return;
        holds.delete(root);
        if (!state.alreadyPresent) root.classList.remove(SOURCE_LAYOUT_HOLD_CLASS);
        const pendingScroll = state.pendingScroll;
        state.pendingScroll = null;
        if (pendingScroll) {
            // An optional scroll must never replace the original rendering
            // error thrown through the restore transaction's finally block.
            Promise.resolve().then(pendingScroll).catch(() => {
                console.warn('Deferred chat scroll failed after source layout release.');
            });
        }
    };
}
