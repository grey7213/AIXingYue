// Keep one load operation per element. A second caller must join the first,
// not receive a promise with no load/error listeners and wait forever.
const loads = new WeakMap();

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
            resolve();
        }, { once: true });
        element.addEventListener('error', () => {
            element.dataset.extensionLoad = 'error';
            loads.delete(element);
            reject(new Error(`Extension ${kind} failed to load: ${id}`));
        }, { once: true });
        if (!existing || existing.dataset.extensionLoad === 'error') {
            element.id = id;
            element.dataset.extensionLoad = 'loading';
            if (kind === 'script') {
                element.type = 'module';
                element.async = true;
                element.src = url;
                document.body.appendChild(element);
            } else {
                element.rel = 'stylesheet';
                element.href = url;
                document.head.appendChild(element);
            }
        } else if (kind === 'style' && element.sheet) {
            element.dataset.extensionLoad = 'ready';
            resolve();
        }
    });
    loads.set(element, promise);
    return promise;
}
