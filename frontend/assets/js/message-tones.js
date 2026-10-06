import { updateMessagePresentation } from './message-presentation.js';
// Presentation only. Stored messages, prompts and creator scripts are untouched.
const snapshots = new WeakMap();
const allowed = new Set(['P','EM','STRONG','SPAN','BLOCKQUOTE','Q','B','I','U','S','SMALL','LI','UL','OL']);
const blocks = new Set(['P','BLOCKQUOTE','LI']);
const excluded = 'code,pre,a,iframe,style,script,table,button,form,canvas,svg,math,.katex,.MathJax,.homer-card-component,.homer-roleplayhub-documents,.is-user';

function proseRuns(root) {
    const runs = []; let run = [];
    const flush = () => { if (run.length) runs.push(run); run = []; };
    const walk = node => {
        if (node.nodeType === 3) { if (node.data) run.push(node); return; }
        if (node.nodeType !== 1) return;
        if (node.tagName === 'BR') { flush(); return; }
        if (node !== root && (node.matches(excluded) || node.hasAttribute('style')
            || !allowed.has(node.tagName)
            || (node.className && !node.classList.contains('homer-prose-region') && !node.hasAttribute('data-message-tone')))) { flush(); return; }
        const block = blocks.has(node.tagName);
        if (block) flush();
        for (const child of node.childNodes) walk(child);
        if (block) flush();
    };
    for (const child of root.childNodes) walk(child);
    flush(); return runs;
}

function snapshot(runs) { return runs.flat().map(node => [node, node.data]); }
function unchanged(before, after) { return before?.length === after.length && after.every(([node,text],i) => before[i][0] === node && before[i][1] === text); }

export function decorateMessage(root) {
    if (!root || root.closest('.mes')?.getAttribute('is_user') === 'true' || root.classList.contains('is-user')) return;
    updateMessagePresentation(root);
    let runs = proseRuns(root);
    if (unchanged(snapshots.get(root), snapshot(runs))) return;
    // Remove only our wrappers in eligible prose. Never normalize a card tree,
    // move media or resanitize markup while a live iframe is running.
    const wrappers = new Set(runs.flat().map(n => n.parentElement.closest('[data-message-tone]')).filter(Boolean));
    for (const wrapper of wrappers) wrapper.replaceWith(...wrapper.childNodes);
    runs = proseRuns(root);
    for (const nodes of runs) {
        const text = nodes.map(n => n.data).join('');
        // Matching continues across inline emphasis. Unfinished streamed text
        // is colored already, without waiting for its closing delimiter.
        const pattern = /“[^”\n]*(?:”|(?=\n)|$)|「[^」\n]*(?:」|(?=\n)|$)|『[^』\n]*(?:』|(?=\n)|$)|«[^»\n]*(?:»|(?=\n)|$)|＂[^＂\n]*(?:＂|(?=\n)|$)|"[^"\n]*(?:"|(?=\n)|$)|（[^）\n]*(?:）|(?=\n)|$)|\([^\)\n]*(?:\)|(?=\n)|$)/g;
        const ranges = [...text.matchAll(pattern)].map(m => ({ start:m.index, end:m.index+m[0].length, tone:/^[（(]/.test(m[0])?'aside':'speech' }));
        let position = 0;
        for (const node of nodes) {
            const start = position, end = start+node.data.length; position=end;
            const thought = !!node.parentElement.closest('em,i');
            const spans = ranges.filter(r => r.start < end && r.end > start);
            if (!thought && !spans.length) continue;
            const fragment = document.createDocumentFragment(); let offset=0;
            const append = (value,tone) => { if(!value)return; if(!tone){fragment.append(value);return;} const span=document.createElement('span');span.dataset.messageTone=tone;span.textContent=value;fragment.append(span); };
            for (const r of spans) {
                const from=Math.max(0,r.start-start), to=Math.min(node.data.length,r.end-start);
                append(node.data.slice(offset,from),thought?'thought':null);
                append(node.data.slice(from,to),r.tone); offset=to;
            }
            append(node.data.slice(offset),thought?'thought':null); node.replaceWith(fragment);
        }
    }
    snapshots.set(root,snapshot(proseRuns(root)));
}

export function installMessageTones() {
    if(window.__homerMessageTones)return;window.__homerMessageTones=true;
    const css=document.createElement('link');css.rel='stylesheet';css.href='/assets/css/message-tones.css';document.head.append(css);
    const selector='.mes[is_user="false"] .mes_text,.preview-message:not(.is-user)';
    const pending=new Set();let queued=false;
    const queue=node=>{
        if(node.nodeType===3)node=node.parentElement;if(!(node instanceof Element))return;
        const root=node.closest(selector);if(root)pending.add(root);
        else node.querySelectorAll(selector).forEach(e=>pending.add(e));
        // Microtask classification happens before paint, not a delayed frame
        // that briefly exposes a blue wrapper around the author's UI.
        if(!queued){queued=true;queueMicrotask(()=>{queued=false;for(const el of pending)if(el.isConnected)decorateMessage(el);pending.clear();});}
    };
    new MutationObserver(records=>{for(const r of records){queue(r.target);for(const n of r.addedNodes)queue(n);}}).observe(document.body,{subtree:true,childList:true,characterData:true});queue(document.body);
}
