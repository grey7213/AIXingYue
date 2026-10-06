// Presentation bytes only: no script execution, stylesheet activation, card
// mounting or private API reads. Keep URLs identical to the real consumers.
// Only hint assets owned by the bounded-retry presentation loader. Chromium
// can retain a failed preload even after its link is removed; optional picker
// scripts and imported styles without that recovery must not be hinted.
export const STATIC_DIALOGUE_UI_RESOURCES = Object.freeze([
    { href: '/assets/vendor/tavo/dist/css/bundle.min.css', as: 'style' },
    { href: '/assets/vendor/tavo/dist/js/bundle.min.js', as: 'script' },
    { href: '/assets/css/tavo-chat-ui.css', as: 'style' },
].map(resource => Object.freeze(resource)));

// Fixed per-document metadata, not a response/body cache. Weak ownership lets
// a retired runtime document and all its records be collected together.
const documents = new WeakMap();
const marker = 'data-homer-static-ui-preload';
const result = (started = 0, reused = 0, failed = 0, unsupported = false) =>
    Object.freeze({ started, reused, failed, unsupported });

export function preloadStaticDialogueUi(doc = globalThis.document) {
    const prototype = (doc?.defaultView?.Document || globalThis.Document)?.prototype;
    if (!doc || !prototype?.createElement || !prototype.querySelectorAll
        || !doc.head || doc.head.ownerDocument !== doc) return result(0, 0, 0, true);
    let origin, candidates, probe;
    try {
        const base = new URL(doc.URL);
        if (!['http:', 'https:'].includes(base.protocol)) return result(0, 0, 0, true);
        origin = base.origin;
        // Do not use the bridge's instance lookup shim: a parent's preload or
        // similarly named link cannot prepare resources in this document.
        candidates = Array.from(prototype.querySelectorAll.call(doc, `link[${marker}]`));
        probe = prototype.createElement.call(doc, 'link');
        if (!probe.relList?.supports?.('preload')) return result(0, 0, 0, true);
    } catch {
        return result(0, 0, 0, true);
    }
    let records = documents.get(doc);
    if (!records) { records = new Map(); documents.set(doc, records); }
    let started = 0, reused = 0, failed = 0;
    for (const resource of STATIC_DIALOGUE_UI_RESOURCES) {
        const href = new URL(resource.href, origin + '/').href;
        const key = resource.as + '\u0000' + href;
        const previous = records.get(key);
        if (previous?.link.isConnected && previous.link.ownerDocument === doc
            && previous.link.rel === 'preload' && previous.link.as === resource.as && previous.link.href === href
            && previous.link.getAttribute(marker) === resource.href) { reused++; continue; }
        if (previous) { previous.cleanup(); records.delete(key); }
        let link = candidates.find(candidate => candidate.ownerDocument === doc && candidate.isConnected
            && candidate.rel === 'preload' && candidate.as === resource.as && candidate.href === href
            && candidate.getAttribute(marker) === resource.href);
        const adopted = Boolean(link);
        if (!link) {
            link = probe || prototype.createElement.call(doc, 'link'); probe = null;
            link.rel = 'preload'; link.as = resource.as; link.href = href;
            link.setAttribute(marker, resource.href);
            // No consumer IDs, crossorigin changes or rel=stylesheet/script:
            // actual activation retains its own ordering and failure policy.
        }
        let record;
        const cleanup = () => {
            link.removeEventListener('load', loaded);
            link.removeEventListener('error', errored);
        };
        const loaded = () => { cleanup(); };
        const errored = () => {
            cleanup();
            if (records.get(key) === record) records.delete(key);
            // An external component may have subsequently repurposed/moved
            // the node. Remove only this document's still-exact preload hint.
            if (link.ownerDocument === doc && link.rel === 'preload' && link.as === resource.as
                && link.href === href && link.getAttribute(marker) === resource.href) link.remove();
        };
        record = { link, cleanup };
        records.set(key, record);
        link.addEventListener('load', loaded, { once: true });
        link.addEventListener('error', errored, { once: true });
        try {
            if (adopted) reused++;
            else { doc.head.append(link); started++; }
        } catch {
            errored(); failed++;
        }
    }
    return result(started, reused, failed);
}
