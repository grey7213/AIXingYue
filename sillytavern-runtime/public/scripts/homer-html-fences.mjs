// Preserve complete HTML frontends as opaque code until TavernHelper renders
// them. Markdown indentation/quote repair must not split a document into partly
// rendered HTML plus an indented source block. Ordinary code is untouched.
const escapeCode = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
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
