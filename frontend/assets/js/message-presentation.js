// Presentation metadata only. No message source, iframe parent or card DOM is rewritten.
const authorSelector = 'iframe,.homer-card-component,.homer-roleplayhub-documents';
const htmlCodeSelector = 'pre code.custom-language-html,pre code.language-html';
const proseSelector = 'p,blockquote,ul,ol,h1,h2,h3,h4,h5,h6';

function containsAuthorRegion(node) {
    if (node.nodeType !== 1) return false;
    if (node.matches(authorSelector) || node.querySelector(authorSelector)) return true;
    // Raw inline card panels also own their visual shell. Plain paragraphs,
    // emphasis, links and regular code blocks do not qualify as such a panel.
    const panels = [node, ...node.querySelectorAll('div,section,article,main,figure,table')];
    if (panels.some(panel => panel.matches('div,section,article,main,figure,table')
        && (panel.id || panel.hasAttribute('style') || panel.classList.length)
        && !panel.classList.contains('homer-prose-region'))) return true;
    // The Helper will replace these fences with a live iframe. Classify before
    // that async conversion, without hashing/scanning megabytes of script.
    return [...node.querySelectorAll(htmlCodeSelector)].some(code =>
        code.classList.contains('custom-language-html')
        || /<!doctype\s+html|<html[\s>]|<style[\s>]|<script[\s>]/i.test(code.textContent.slice(0, 512)));
}

export function updateMessagePresentation(root, isUser = root?.closest('.mes')?.getAttribute('is_user') === 'true') {
    if (!root) return 'plain';
    const branches = [...root.children];
    const rich = !isUser && branches.some(containsAuthorRegion);
    const mes = root.closest('.mes');
    root.classList.toggle('homer-author-content', rich);
    mes?.classList.toggle('homer-author-message', rich);
    // Only the software's plain siblings receive bubble styling. Do not wrap
    // or reparent them: even moving an ancestor can reload an existing iframe.
    for (const branch of branches) {
        const prose = rich && branch.matches(proseSelector) && !containsAuthorRegion(branch)
            && !branch.hasAttribute('style') && (!branch.className || branch.classList.contains('homer-prose-region'));
        branch.classList.toggle('homer-prose-region', prose);
    }
    return rich ? 'author' : 'plain';
}
