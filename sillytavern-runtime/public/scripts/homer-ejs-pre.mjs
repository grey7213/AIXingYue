// When code-block evaluation is disabled, protect the whole block through all
// EJS preprocessors. A JS-string wrapper alone is not opaque: a later reasoning
// pass can find literal <thinking> examples inside it and inject another wrapper.
export function protectPreContent(html) {
    const blocks = [];
    let prefix = 'HOMERLITERALPRE';
    while (html.includes(prefix)) prefix += 'X';
    const doc = new DOMParser().parseFromString(html, 'text/html');
    for (const pre of doc.querySelectorAll('pre')) {
        const token = `${prefix}${blocks.length}END`;
        blocks.push([token, pre.outerHTML]);
        pre.replaceWith(doc.createTextNode(token));
    }
    return { content: doc.body.innerHTML, restore(value) {
        if (typeof value !== 'string') return value;
        for (const [token, original] of blocks) value = value.replaceAll(token, original);
        return value;
    } };
}
