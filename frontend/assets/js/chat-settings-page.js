// Preserve the existing controls, event handlers and dialog cancellation while
// giving long settings tasks a page layout rather than a floating form.
function notifySurface(clear = false) {
    try {
        const bridge = window.HomerNative || window.parent?.HomerNative;
        const open = !clear && document.querySelector('dialog.homer-settings-page[open]');
        bridge?.setSettingsSurface?.(open ? (document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) : '');
    } catch { /* Browser previews and older clients have no native surface API. */ }
}
window.addEventListener('pagehide', () => notifySurface(true));
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => notifySurface());
function modelOverview(content) {
    const group=content.querySelector('.homer-model-fields');if(!group)return;
    const title=document.createElement('h3');title.className='homer-settings-section-title';title.textContent='生成偏好';group.before(title);
    // Direct controls: values and help stay visible, no four extra disclosure taps.
    for(const field of group.children) field.classList.add('homer-parameter-direct');
    const select=content.querySelector('.homer-model-select');
    if(select){
        // Keep the bound select (and the shared searchable picker) as the input,
        // but let its visual value wrap. Native selects clip long names/prices.
        const choice=document.createElement('div');choice.className='homer-model-choice';
        const copy=document.createElement('span');copy.className='homer-model-choice-copy';copy.setAttribute('aria-hidden','true');
        const name=document.createElement('strong'),info=document.createElement('small');info.className='homer-model-choice-detail';copy.append(name,info);
        select.before(choice);choice.append(select,copy);select.setAttribute('aria-label','当前模型');
        const update=()=>{const [label,...detail]=(select.selectedOptions[0]?.textContent||'请选择模型').split(' · ');name.textContent=label;info.textContent=detail.join(' · ');info.hidden=!detail.length;};
        select.addEventListener('change',update);new MutationObserver(update).observe(select,{childList:true,subtree:true});update();
    }
}
function modFilters(content){
    const list=content.querySelector('.homer-mod-list');if(!list)return;
    const search=document.createElement('input');search.type='search';search.placeholder='查找 Mod';search.setAttribute('aria-label','查找 Mod');search.className='homer-settings-search';
    const toolbar=document.createElement('div');toolbar.className='homer-mod-filter';const all=document.createElement('button'),enabled=document.createElement('button');
    all.type=enabled.type='button';all.textContent='全部';enabled.textContent='已启用';let onlyEnabled=false;
    const empty=document.createElement('p');empty.className='homer-mod-no-results';empty.textContent='没有匹配的 Mod，试试其他关键词。';empty.hidden=true;empty.setAttribute('role','status');
    const filter=()=>{let shown=0;for(const row of list.querySelectorAll('.homer-mod-row')){row.hidden=!row.textContent.toLowerCase().includes(search.value.trim().toLowerCase())||(onlyEnabled&&!row.querySelector('input').checked);if(!row.hidden)shown++;}empty.hidden=shown>0||!list.querySelector('.homer-mod-row');all.setAttribute('aria-pressed',String(!onlyEnabled));enabled.setAttribute('aria-pressed',String(onlyEnabled));};
    all.onclick=()=>{onlyEnabled=false;filter();};enabled.onclick=()=>{onlyEnabled=true;filter();};search.oninput=filter;list.addEventListener('change',filter);
    toolbar.append(all,enabled);list.before(search,toolbar);list.after(empty);filter();
}
export function settingsPage(dialog, { shell = dialog, head, footer, title, close } = {}) {
    dialog.classList.add('homer-settings-page');
    shell.classList.add('homer-settings-page__shell');
    head.classList.add('homer-settings-page__head');
    const heading = head.querySelector('h2') || document.createElement('h2');
    heading.textContent = title;
    heading.tabIndex = -1; heading.setAttribute('autofocus', '');
    const buttons = footer ? [...footer.querySelectorAll('button')] : [];
    const cancel = buttons.find(b => b.textContent.trim() === '取消');
    const save = buttons.find(b => b.textContent.trim() === '保存');
    const existingBack = cancel || close || head.querySelector('button');
    const back = existingBack || document.createElement('button');
    back.type = 'button'; back.textContent = cancel ? '取消' : '返回'; back.classList.add('homer-settings-page__back');
    if (!back.getAttribute('aria-label')) back.setAttribute('aria-label', cancel ? '取消' : `返回对话（${title}）`);
    if (!existingBack) back.addEventListener('click', () => {
        if (dialog.dispatchEvent(new Event('cancel', { cancelable: true }))) dialog.close();
    });
    head.replaceChildren(back, heading, document.createElement('span'));
    // Reset is a secondary header action. Keep one clear save action at the
    // bottom, without three equally prominent pills fighting for space.
    const reset = buttons.find(b => b.textContent === '恢复默认');
    if (save) { save.classList.add('homer-settings-page__save'); head.lastElementChild.replaceWith(save); }
    const content = document.createElement('div'); content.className = 'homer-settings-page__content';
    for (const child of [...shell.children]) if (child !== head && child !== footer) content.append(child);
    head.classList.add('is-scrolled');
    if (reset) { reset.setAttribute('aria-label', '恢复默认'); reset.classList.add('homer-settings-page__reset'); content.append(reset); }
    modelOverview(content);modFilters(content);
    const updateRanges = () => {
        for (const range of content.querySelectorAll('.homer-model-field__range')) {
            const min = Number(range.min), max = Number(range.max);
            range.style.setProperty('--range-progress', `${Math.max(0, Math.min(100, (Number(range.value) - min) / (max - min) * 100))}%`);
            const output=range.closest('.homer-parameter')?.querySelector('output');if(output)output.textContent=range.closest('.homer-model-field').querySelector('input[type=number]').value;
        }
    };
    content.addEventListener('input', updateRanges);reset?.addEventListener('click', updateRanges);
    new MutationObserver(() => { updateRanges(); notifySurface();if(dialog.open)content.querySelector('.homer-settings-search')?.dispatchEvent(new Event('input')); }).observe(dialog, { attributes:true, attributeFilter:['open'] });updateRanges();
    if (footer) footer.classList.add('homer-settings-page__footer');
    shell.replaceChildren(head, content, ...(footer ? [footer] : []));
    dialog.setAttribute('aria-label', title);
    return content;
}
