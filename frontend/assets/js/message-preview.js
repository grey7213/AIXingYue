// Text-only history summaries. Never mount or evaluate card HTML / regex scripts.
export function messagePreview(value, limit = 160) {
    return String(value || '').slice(0, 100000)
        .replace(/<(think|thinking|analysis|inner_flow)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi, ' ')
        .replace(/```(?:html|javascript|js|css|json|xml|text)?\s*[\s\S]*?(?:```|$)/gi, ' ')
        .replace(/<(script|style|head|iframe|svg)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi, ' ')
        .replace(/<!doctype[^>]*>[\s\S]*/gi, ' ')
        .replace(/<[^>]*>/g, ' ')
        .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
        .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
        .replace(/&nbsp;|&#160;/gi, ' ').replace(/&amp;/gi, '&')
        .replace(/\s+/g, ' ').trim().slice(0, limit);
}
