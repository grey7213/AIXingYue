// When code-block evaluation is disabled, protect the whole block through all
// EJS preprocessors. A JS-string wrapper alone is not opaque: a later reasoning
// pass can find literal <thinking> examples inside it and inject another wrapper.
// This is a presence check, not a source read. CharacterData.length avoids
// allocating a multi-megabyte string merely to decide whether it is empty.
export function hasNonemptyDOMText(selection) {
    let result = null;
    try {
        if (selection && Number.isInteger(selection.length) && selection.length >= 0) {
            const nodes = [];
            let supported = true;
            for (let index = 0; index < selection.length; index++) {
                const node = selection[index];
                if (!node || ![1, 2, 3, 4, 7, 8, 9, 10, 11].includes(node.nodeType)) { supported = false; break; }
                if ([3, 4].includes(node.nodeType) && typeof node.length !== 'number') { supported = false; break; }
                if ([1, 9, 11].includes(node.nodeType)
                    && typeof (node.nodeType === 9 ? node : node.ownerDocument)?.createTreeWalker !== 'function') { supported = false; break; }
                nodes.push(node);
            }
            if (supported) {
                result = false;
                for (const node of nodes) {
                    if ([3, 4].includes(node.nodeType)) {
                        if (node.length) { result = true; break; }
                    } else if ([1, 9, 11].includes(node.nodeType)) {
                        const document = node.nodeType === 9 ? node : node.ownerDocument;
                        // TEXT | CDATA: excludes comments and does not enter
                        // template.content or shadow roots, just like .text().
                        const walker = document.createTreeWalker(node, 4 | 8);
                        let text;
                        while ((text = walker.nextNode())) {
                            if (typeof text.length !== 'number') throw new TypeError('Unsupported text node');
                            if (text.length) { result = true; break; }
                        }
                        if (result) break;
                    }
                }
            }
        }
    } catch {
        result = null;
    }
    // Keep the original receiver and exception behavior. Never catch/retry a
    // failing fallback call, or execute the collection's text method twice.
    return result === null ? Boolean(selection?.text()) : result;
}

export function protectPreContent(html, liveRoot = null) {
    const blocks = [];
    let prefix = 'HOMERLITERALPRE';
    while (html.includes(prefix)) prefix += 'X';
    // The render handler has already parsed this markup into a message DOM.
    // Avoid parsing multi-megabyte code a second time. Import into a separate
    // inert document, not the live document: cloneNode there could upgrade
    // custom elements and run constructors even without connecting the clone.
    let root;
    if (liveRoot?.nodeType === 1
        && liveRoot.namespaceURI === 'http://www.w3.org/1999/xhtml'
        && liveRoot.innerHTML === html
        && !/^(?:base|link|meta|title|script|style|noscript)$/i.test(liveRoot.firstElementChild?.localName || '')
        && !Array.from(liveRoot.children).some(node => /^(?:html|head|body|frameset|frame)$/i.test(node.localName))) {
        if (!liveRoot.querySelector('pre')) return { content: html, restore: value => value };
        const inertDocument = liveRoot.ownerDocument.implementation.createHTMLDocument('');
        root = inertDocument.importNode(liveRoot, true);
    } else {
        // String callers and head/document markup keep the previous parser
        // semantics; a stale or unrelated DOM snapshot can never win.
        root = new DOMParser().parseFromString(html, 'text/html').body;
    }
    for (const pre of root.querySelectorAll('pre')) {
        const token = `${prefix}${blocks.length}END`;
        blocks.push([token, pre.outerHTML]);
        pre.replaceWith(root.ownerDocument.createTextNode(token));
    }
    return { content: root.innerHTML, restore(value) {
        if (typeof value !== 'string') return value;
        for (const [token, original] of blocks) value = value.replaceAll(token, original);
        return value;
    } };
}

// Capture the current message synchronously, without serializing or deep-copying
// its potentially multi-megabyte PRE text twice. The existing string API above
// still validates stale snapshots; this API accepts only the current DOM itself.
export function capturePreContent(liveRoot) {
    if (liveRoot?.nodeType !== 1) throw new TypeError('A current message element is required');
    if (liveRoot.namespaceURI !== 'http://www.w3.org/1999/xhtml'
        || /^(?:base|link|meta|title|script|style|noscript)$/i.test(liveRoot.firstElementChild?.localName || '')
        || Array.from(liveRoot.children).some(node => /^(?:html|head|body|frameset|frame)$/i.test(node.localName))) {
        // Preserve the existing parser semantics for unsupported fragments.
        const rawHTML = liveRoot.innerHTML;
        return { rawHTML, ...protectPreContent(rawHTML), identityRestoresRaw: false };
    }
    const pres = Array.from(liveRoot.querySelectorAll('pre'));
    if (!pres.length) {
        const rawHTML = liveRoot.innerHTML;
        return { rawHTML, content: rawHTML, restore: value => value, identityRestoresRaw: true };
    }
    // querySelectorAll does not enter template.content, exactly like the old
    // API. Retain its PRE numbering even for programmatically nested PREs.
    const indices = new Map(pres.map((pre, index) => [pre, index]));
    const originals = pres.map(pre => pre.outerHTML);
    const placeholders = [];
    const inertDocument = liveRoot.ownerDocument.implementation.createHTMLDocument('');
    const root = inertDocument.importNode(liveRoot, false);
    function copy(node) {
        if (indices.has(node)) {
            // PRE markup separates its neighbours in the original serialized
            // input. A space keeps prefix scanning from falsely concatenating
            // those neighbours before the real token is selected.
            const placeholder = inertDocument.createTextNode(' ');
            placeholders.push([placeholder, indices.get(node)]);
            return placeholder;
        }
        // Templates keep their inert content intact. Deep-importing a template
        // here never exposes that content to our PRE walk or a live registry.
        const template = node.nodeType === 1
            && node.namespaceURI === 'http://www.w3.org/1999/xhtml'
            && node.localName === 'template';
        const clone = inertDocument.importNode(node, template);
        if (!template) for (const child of node.childNodes) clone.appendChild(copy(child));
        return clone;
    }
    for (const child of liveRoot.childNodes) root.appendChild(copy(child));
    const surrounding = root.innerHTML;
    let prefix = 'HOMERLITERALPRE';
    while (surrounding.includes(prefix) || originals.some(html => html.includes(prefix))) prefix += 'X';
    for (const [placeholder, index] of placeholders) placeholder.data = `${prefix}${index}END`;
    const content = root.innerHTML;
    function restoreBlocks(value) {
        if (typeof value !== 'string') return value;
        for (let index = 0; index < originals.length; index++) {
            value = value.replaceAll(`${prefix}${index}END`, originals[index]);
        }
        return value;
    }
    // The snapshot is complete above. Reconstruct from these immutable strings
    // only if a caller actually needs the raw HTML, never from a later live DOM.
    let rawHTML;
    function getRawHTML() {
        if (rawHTML === undefined) rawHTML = restoreBlocks(content);
        return rawHTML;
    }
    return { get rawHTML() { return getRawHTML(); }, content, identityRestoresRaw: true, restore(value) {
        return value === content ? getRawHTML() : restoreBlocks(value);
    } };
}
