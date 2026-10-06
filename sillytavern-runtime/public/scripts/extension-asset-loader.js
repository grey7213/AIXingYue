// Keep one load operation per element. A second caller must join the first,
// not receive a promise with no load/error listeners and wait forever.
const loads = new WeakMap();

// Diagnostic only: never record an asset URL, query, account or conversation.
// A missing/blocked Performance API must not change a load's promise semantics.
function markExtensionAsset(phase, kind, id) {
    try {
        const safeId = typeof id === 'string' && /^[A-Za-z0-9_./-]{1,160}$/.test(id) ? id : 'unknown';
        const safeKind = kind === 'script' || kind === 'style' ? kind : 'unknown';
        globalThis.performance?.mark?.(`homer-extension-asset-${phase}:${safeKind}:${safeId}`);
    } catch { /* optional diagnostic */ }
}

export function loadExtensionAsset({ document, id, url, kind }) {
    const existing = document.getElementById(id);
    if (existing && loads.has(existing)) return loads.get(existing);
    if (existing?.dataset.extensionLoad === 'ready') return Promise.resolve();
    if (existing?.dataset.extensionLoad === 'error') existing.remove();
    const element = existing?.dataset.extensionLoad !== 'error' && existing
        ? existing : document.createElement(kind === 'script' ? 'script' : 'link');
    const promise = new Promise((resolve, reject) => {
        element.addEventListener('load', () => {
            element.dataset.extensionLoad = 'ready';
            markExtensionAsset('load', kind, id);
            resolve();
        }, { once: true });
        element.addEventListener('error', () => {
            element.dataset.extensionLoad = 'error';
            loads.delete(element);
            markExtensionAsset('error', kind, id);
            reject(new Error(`Extension ${kind} failed to load: ${id}`));
        }, { once: true });
        if (!existing || existing.dataset.extensionLoad === 'error') {
            element.id = id;
            element.dataset.extensionLoad = 'loading';
            if (kind === 'script') {
                element.type = 'module';
                element.async = true;
                element.src = url;
                markExtensionAsset('append', kind, id);
                document.body.appendChild(element);
            } else {
                element.rel = 'stylesheet';
                element.href = url;
                markExtensionAsset('append', kind, id);
                document.head.appendChild(element);
            }
        } else if (kind === 'style' && element.sheet) {
            element.dataset.extensionLoad = 'ready';
            markExtensionAsset('available', kind, id);
            resolve();
        }
    });
    loads.set(element, promise);
    return promise;
}
