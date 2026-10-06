// Equivalent to the renderer's case-sensitive Bk(jQuery(pre).text()) predicate.
// Inspect text only: comments, markup structure and template/shadow contents are
// not HTML source. No rendering, normalization, cache or author hook is skipped.
const markers = ['html>', '<head>', '<body'];
const tailLength = Math.max(...markers.map(marker => marker.length)) - 1;
const matches = text => markers.some(marker => text.includes(marker));

export function hasFrontendMarkupText(root, fallback) {
    // Callers retain their original jQuery collection in the fallback closure.
    // In particular, a multi-root collection must not silently become root[0].
    if (root?.nodeType !== 1 || typeof root.ownerDocument?.createTreeWalker !== 'function') return fallback();
    try {
        // SHOW_TEXT | SHOW_CDATA_SECTION: the same text node types contributing
        // to Element.textContent, including script/style and cross-element text.
        const walker = root.ownerDocument.createTreeWalker(root, 12);
        let tail = '';
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            const text = node.nodeValue;
            if (typeof text !== 'string') throw new TypeError('Unsupported text node');
            if (matches(text) || matches(tail + text.slice(0, tailLength))) return true;
            // Never concatenate the preceding tail with a multi-megabyte node.
            tail = text.length >= tailLength ? text.slice(-tailLength) : (tail + text).slice(-tailLength);
        }
        return false;
    } catch { /* Preserve the original receiver and its error behavior below. */ }
    return fallback();
}
