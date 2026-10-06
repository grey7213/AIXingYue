// Preserve complete HTML frontends as opaque code until TavernHelper renders
// them. Markdown indentation/quote repair must not split a document into partly
// rendered HTML plus an indented source block. Ordinary code is untouched.
const escapeCode = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
// Official prose beautifiers must not rewrite JavaScript string literals inside
// a card's executable frontend. Split once at the card -> official boundary,
// not into sentinel tokens a catch-all rule could erase. This does NOT execute
// HTML or bypass Markdown/DOMPurify/Helper; the original formatter still runs.
export function createFrontendRuleBoundary(source) {
    const parts = [];
    let cursor = 0;
    const fences = /^[ \t]*(`{3,}|~{3,})[ \t]*(?:html)?[ \t]*\r?\n([\s\S]*?)^[ \t]*\1[ \t]*$/gim;
    for (const match of source.matchAll(fences)) {
        if (!/<body(?:\s[^>]*)?>[\s\S]*<\/body\s*>/i.test(match[2])) continue;
        // Preserve line separators so an official trim/catch-all cannot turn a
        // valid fenced document into inline prose when recombining the parts.
        let start = match.index, end = start + match[0].length;
        if (start > cursor && source[start - 1] === '\n') {
            start--;
            if (start > cursor && source[start - 1] === '\r') start--;
        }
        if (source[end] === '\r' && source[end + 1] === '\n') end += 2;
        else if (source[end] === '\n') end++;
        if (start > cursor) parts.push({ text: source.slice(cursor, start), frontend: false });
        parts.push({ text: source.slice(start, end), frontend: true });
        cursor = end;
    }
    if (cursor < source.length || !parts.length) parts.push({ text: source.slice(cursor), frontend: false });
    return { apply(transform) {
        for (const part of parts) if (!part.frontend && part.text) part.text = transform(part.text);
        return parts.map(part => part.text).join('');
    } };
}
export function protectFrontendFences(source) {
    const blocks = [];
    let prefix = 'HOMERFRONTENDOPAQUE';
    while (source.includes(prefix)) prefix += 'X';
    const markdown = source.replace(/^[ \t]*(`{3,}|~{3,})[ \t]*(?:html)?[ \t]*\r?\n([\s\S]*?)^[ \t]*\1[ \t]*$/gim, (whole, fence, html) => {
        if (!/<body(?:\s[^>]*)?>[\s\S]*<\/body\s*>/i.test(html)) return whole;
        const token = `${prefix}${blocks.length}END`;
        blocks.push({ token, html: `<pre><code class="language-html">${escapeCode(html.replace(/\r?\n$/, ''))}</code></pre>` });
        return `\n\n${token}\n\n`;
    });
    return { markdown, restore(rendered) {
        for (const { token, html } of blocks) rendered = rendered.replace(`<p>${token}</p>`, html).replaceAll(token, html);
        return rendered;
    } };
}
