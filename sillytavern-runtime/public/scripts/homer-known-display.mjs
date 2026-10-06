// Only these callers' known CSS display values are written. Unlike jQuery
// show/toggle, this path never needs a computed-display/layout read.
export function setHostChromeDisplay(elements, visible, visibleDisplay, doc = globalThis.document) {
    if (!doc?.documentElement?.classList.contains('homer-host-chrome')) return false;
    for (const element of elements) {
        if (element.ownerDocument !== doc) continue;
        element.style.display = visible ? visibleDisplay : 'none';
    }
    return true;
}

const expressionWrapperIds = new Set(['expression-wrapper', 'visual-novel-wrapper']);

// Only the two native expression wrappers have an authoritative host-hidden
// state. Other elements (including card content) keep their original behavior.
export function setHostExpressionWrapperDisplay(elements, visible, doc = globalThis.document) {
    if (!doc?.documentElement?.classList.contains('homer-host-chrome')) return false;
    const local = [...elements];
    if (local.some(element => element.ownerDocument !== doc || !expressionWrapperIds.has(element.id))) return false;
    for (const element of local) element.style.setProperty('display', visible ? 'flex' : 'none', visible ? '' : 'important');
    return true;
}

// Inline `none` alone is insufficient: a stylesheet could override it with
// !important. Only our authoritative hidden wrappers can skip geometry.
// Unknown/visible controls still use the original check, with no state cache.
export function isHostChromeInlineHidden(elements, doc = globalThis.document) {
    if (!doc?.documentElement?.classList.contains('homer-host-chrome')) return false;
    let count = 0;
    for (const element of elements) {
        if (element.ownerDocument !== doc || !expressionWrapperIds.has(element.id)
            || element.style.display !== 'none' || element.style.getPropertyPriority('display') !== 'important') return false;
        count++;
    }
    return count > 0;
}
