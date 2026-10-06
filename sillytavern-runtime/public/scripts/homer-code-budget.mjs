// Syntax colour is optional presentation, never a reason to truncate source.
// Bound synchronous highlighting by UTF-16 length (the browser string size).
export const CODE_HIGHLIGHT_MAX_CHARS = 64 * 1024;

export function shouldHighlightCode(text) {
    return typeof text === 'string' && text.length <= CODE_HIGHLIGHT_MAX_CHARS;
}

// Read the live source, excluding only our own direct copy-control nodes.
// Highlight.js spans remain included and no rendered HTML is re-parsed.
export function readCopyableCodeText(code) {
    let text = '';
    for (const node of code.childNodes) {
        if (node.nodeType === 1 && node.classList?.contains('code-copy')) continue;
        text += node.textContent || '';
    }
    return text;
}
