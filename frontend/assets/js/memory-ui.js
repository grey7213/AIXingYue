import { settingsPage } from './chat-settings-page.js';
import { memoryManager } from './memory-manager.js';
// Reorganize existing Memory Books controls without replacing its save/generate handlers.
function el(tag,cls,text) {const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e;}
function enhance(popup) {
    const content=popup.querySelector('.popup-content');
    if(!content?.querySelector('#stmb-profile-select')||content.querySelector('.homer-memory-layout'))return;
    const automatic=content.querySelector('#homer-memory-auto-controls');
    const original=[...content.children].filter(child=>child!==automatic);
    const layout=el('div','homer-memory-layout');
    const title=el('h2','','长记忆');
    const header=el('header');header.append(title);
    const step=(name)=>{const s=el('section','homer-memory-step');s.append(el('h3','',name));layout.append(s);return s;};
    const range=step('1 · 选择要记住的对话');
    const scene=content.querySelector('#stmb-scene')||content.querySelector('.info-block.warning');
    if(scene){
        if(scene.matches('.warning')){scene.hidden=true;range.append(scene);}
        else{const preview=el('details','homer-memory-preview');preview.append(el('summary','','查看所选对话摘要'),scene);range.append(preview);}
    }
    const ids=[...document.querySelectorAll('#chat .mes[mesid]')].map(e=>Number(e.getAttribute('mesid'))).filter(Number.isInteger);
    const form=el('div','homer-memory-range homer-memory-custom-range');form.hidden=true;const inputs=[];
    for(const [label,id,initial] of [['从','homer-memory-from',ids[0]],['到','homer-memory-to',ids.at(-1)]]) {
        const wrap=el('label','',label),input=document.createElement('input');input.type='number';input.min=String((ids[0]??0)+1);input.max=String((ids.at(-1)??0)+1);input.value=String((initial??0)+1);input.id=id;input.className='text_pole';input.setAttribute('aria-label',label==='从'?'起始消息':'结束消息');wrap.append(input);form.append(wrap);inputs.push(input);
    }
    const choose=el('button','','使用此范围');choose.type='button';const feedback=el('p','homer-memory-selection','选择需要整理的对话');feedback.setAttribute('role','status');
    choose.onclick=()=>{
        const [a,b]=inputs.map(e=>Number(e.value)-1);
        if(!Number.isInteger(a)||!Number.isInteger(b)||a>b||!ids.includes(a)||!ids.includes(b)){feedback.textContent='请输入当前已显示消息内有效的起止序号，结束不能早于开始。';return;}
        const start=document.querySelector(`#chat .mes[mesid="${a}"] .mes_stmb_start`),end=document.querySelector(`#chat .mes[mesid="${b}"] .mes_stmb_end`);
        if(!start||!end){feedback.textContent='记忆模块尚未准备好，请稍后重新打开。';return;}
        if(!start.classList.contains('on'))start.click();
        if(!end.classList.contains('on'))end.click();
        feedback.textContent=`已选择第 ${a+1}–${b+1} 条消息 · 共 ${ids.filter(id=>id>=a&&id<=b).length} 条`;
        if(scene?.matches('.warning'))scene.hidden=true;
    };form.append(choose);
    const shortcuts=el('div','homer-memory-shortcuts');
    const selectShortcut=button=>{for(const b of shortcuts.children)b.setAttribute('aria-pressed',String(b===button));};
    for(const [label,count] of [['最近 20 条',20],['全部已加载对话',ids.length]]){
        const button=el('button','',label==='全部已加载对话'?'全部对话':label);button.setAttribute('aria-label',label);button.setAttribute('aria-pressed','false');button.type='button';button.disabled=!ids.length;
        button.onclick=()=>{selectShortcut(button);form.hidden=true;inputs[0].value=String((ids[Math.max(0,ids.length-count)]??0)+1);inputs[1].value=String((ids.at(-1)??0)+1);choose.click();};
        shortcuts.append(button);
    }
    const custom=el('button','','自定义');custom.type='button';custom.setAttribute('aria-label','自定义');custom.setAttribute('aria-pressed','false');custom.disabled=!ids.length;custom.onclick=()=>{selectShortcut(custom);form.hidden=false;};shortcuts.append(custom);
    range.append(shortcuts,form,feedback);
    const preview=range.querySelector('.homer-memory-preview');if(preview)range.append(preview);
    const progress=content.querySelector('#stmb-memory-status');
    if(progress){progress.querySelector('[data-i18n="STMemoryBooks_SinceVersion"]')?.remove();const details=el('details','homer-memory-progress');details.append(el('summary','','记忆进度与提示'),progress);range.append(details);}
    const storage=step('2 · 确认记忆保存位置');
    const location=content.querySelector('#stmb-active-lorebook')?.closest('.info-block');if(location)storage.append(location);
    const badge=storage.querySelector('#stmb-mode-badge');if(badge)badge.textContent=content.querySelector('#stmb-manual-mode-enabled')?.checked?'手动选择记忆书':'跟随当前对话';
    const auto=content.querySelector('#stmb-auto-create-lorebook')?.closest('.world_entry_form_control');if(auto)storage.append(auto);
    const profile=step('3 · 选择整理方式');const profileRow=content.querySelector('#stmb-profile-select')?.closest('.world_entry_form_control');if(profileRow)profile.append(profileRow);
    profile.append(el('p','homer-memory-intro','生成将使用此配置，已有记忆不会被覆盖。'));
    const advanced=el('details','homer-memory-advanced');advanced.append(el('summary','','高级设置 · 模板、模型与自动整理'));
    for(const child of original) {
        if(child.tagName==='H2' || layout.contains(child))continue;
        advanced.append(child);
    }
    // The plugin retains all change/save handlers; sections no longer form one
    // long mixed settings modal. Switch pages without discarding input values.
    const nav=el('nav','homer-memory-tabs');nav.setAttribute('aria-label','长记忆分区');
    const main=el('section','homer-memory-tab');
    const welcome=el('section','homer-memory-welcome');
    welcome.append(el('h3','','让角色记住重要的事'),el('p','','把一段聊天整理成简短记忆，供后续对话参考。先选范围，再点“生成记忆”；聊天原文会保留。'));
    const cost=el('p','homer-memory-cost','生成记忆会调用当前整理模型，可能消耗积分。选择范围不会开始生成。');
    main.append(welcome,range,cost);
    const storagePage=el('section','homer-memory-tab');storagePage.append(profile,storage);
    const advancedPage=el('section','homer-memory-tab');advancedPage.append(...[...advanced.children].filter(e=>e.tagName!=='SUMMARY'));
    let advancedGroup;
    for(const child of [...advancedPage.children]) {
        if(child.matches('.stmb-section-title') || !advancedGroup){advancedGroup=el('section','homer-memory-advanced-group');advancedPage.append(advancedGroup);}
        advancedGroup.append(child);
    }
    const overview=el('section','homer-memory-tab homer-memory-home');
    overview.append(el('p','homer-memory-note','记下重要经历，让角色在后续对话中记得。'));
    const quick=el('div','homer-memory-quick');
    const action=(name,description,handler)=>{
        const b=el('button','homer-memory-row');b.type='button';b.append(el('span','',name),el('small','',description),el('span','homer-memory-chevron','›'));b.onclick=handler;return b;
    };
    quick.append(action('我的记忆','查看与编辑',()=>{showPanel(4);void manager.load();}),action('立即总结','选择范围并确认生成',()=>showPanel(1)));
    overview.append(quick);
    if(automatic){
        overview.append(automatic);
        const enabled=automatic.querySelector('#stmb-auto-summary-enabled'),interval=automatic.querySelector('#stmb-auto-summary-interval');
        const sync=()=>{interval.disabled=!enabled.checked;};enabled.addEventListener('change',sync);sync();
        interval.addEventListener('change',()=>{if(!interval.checkValidity()){interval.value=String(Math.max(10,Math.min(200,Number(interval.value)||50)));interval.dispatchEvent(new Event('change',{bubbles:true}));}});
    }
    overview.append(el('p','homer-memory-note','自动总结会调用模型并消耗积分。每个对话完成首次手动总结后生效。'));
    const options=el('div','homer-memory-quick');options.append(action('总结设置','模型与保存位置',()=>showPanel(2)),action('高级设置','指令、压缩与追踪',()=>showPanel(3)));overview.append(options);
    const records=el('section','homer-memory-tab');records.setAttribute('aria-label','我的记忆');
    const manager=memoryManager(records);
    const panels=[overview,main,storagePage,advancedPage,records];
    let activePanel=0;
    const showPanel=i=>{
        activePanel=i;panels.forEach((p,j)=>p.hidden=i!==j);if(controls)controls.hidden=i!==1;
        const text=['长记忆','立即总结','保存设置','高级设置','我的记忆'][i];
        for(const title of popup.querySelectorAll('.homer-settings-page__title,.homer-settings-page__head h2'))title.textContent=text;
        const scroller=popup.querySelector('.homer-settings-page__content');if(scroller)scroller.scrollTop=0;
    };
    ['整理记忆','保存设置','高级设置'].forEach((name,i)=>{
        const b=el('button','',name);b.type='button';b.setAttribute('aria-pressed',String(i===0));
        b.setAttribute('aria-label',name);if(i===0)b.hidden=true;
        panels[i+1].setAttribute('aria-label',name);
        if(i>0){b.textContent='';b.append(el('strong','',i===1?'整理与保存设置':'自动整理与高级设置'),el('small','',i===1?'更换整理模型、选择记忆保存位置':'模板、触发条件与其他专业选项'));}
        b.onclick=()=>showPanel(i+1);nav.append(b);
    });
    storage.querySelector('h3').textContent='记忆保存位置';range.querySelector('h3').textContent='选择对话范围';profile.querySelector('h3').textContent='整理方式';
    main.append(nav);layout.append(...panels);content.replaceChildren(layout);
    const controls=popup.querySelector('.popup-controls');
    if(!popup.querySelector('.homer-settings-page__head')) {
        popup.prepend(header);
        settingsPage(popup,{head:header,footer:controls,title:'长记忆'});
    }
    const goBack=event=>{if(activePanel!==0){event.preventDefault();event.stopImmediatePropagation();if(activePanel===4&&manager.back())return;showPanel(0);}};
    popup.addEventListener('cancel',goBack,true);
    popup.querySelector('.homer-settings-page__back').addEventListener('click',goBack,true);
    // Presentation only: retain plugin values and original click/save handlers.
    for(const option of popup.querySelectorAll('option'))if(/SillyTavern|Current ST/i.test(option.textContent))option.textContent='当前对话模型';
    for(const button of popup.querySelectorAll('.popup-controls .menu_button')){
        if(/^(关闭|Close)$/i.test(button.textContent.trim())){button.textContent='关闭';button.dataset.memoryClose='true';}
        if(/清除场景|Clear Scene/.test(button.textContent)){button.textContent='取消范围选择';button.title='只取消起止消息标记，不删除聊天记录或记忆';}
        else if(/创建记忆|Create Memory/i.test(button.textContent)){button.textContent='生成记忆';button.dataset.memoryGenerate='true';}
        else if(/整合记忆|Consolidate Memories/i.test(button.textContent)){button.textContent='合并整理已有记忆';button.title='已有记忆太多时再使用，不会生成新的聊天记录';storagePage.append(button);}
    }
    // No generation on entry. Select a useful default range through the original marker handlers.
    const initialStart=document.querySelector('#chat .mes_stmb_start.on')?.closest('.mes');
    const initialEnd=document.querySelector('#chat .mes_stmb_end.on')?.closest('.mes');
    if(initialStart&&initialEnd){feedback.textContent=`已选择第 ${Number(initialStart.getAttribute('mesid'))+1}–${Number(initialEnd.getAttribute('mesid'))+1} 条消息`;selectShortcut(custom);}
    else if(ids.length)shortcuts.firstElementChild.click();
    else{feedback.textContent='还没有可整理的对话。先和角色聊几句，再回来生成记忆。';popup.querySelector('[data-memory-generate]')?.setAttribute('disabled','');}
    showPanel(0);
}
let installed=false;
const boundaryButtons=new WeakSet();
function enhanceBoundaryButton(button) {
    if(boundaryButtons.has(button))return;
    boundaryButtons.add(button);
    button.setAttribute('aria-label','跳转到尚未整理记忆的对话');
    const clamp=()=>{
        if(!button.isConnected)return;
        const rect=button.getBoundingClientRect();
        if(!rect.width||!rect.height)return;
        const left=Math.max(8,Math.min(rect.left,innerWidth-rect.width-8));
        const top=Math.max(56,Math.min(rect.top,innerHeight-rect.height-80));
        // The upstream draggable button assumes a 36px square. Use its actual
        // rendered size after Homer adds a label, without replacing drag handlers.
        if(Math.abs(left-rect.left)>1)button.style.left=`${left}px`;
        if(Math.abs(top-rect.top)>1)button.style.top=`${top}px`;
    };
    // Dragging can change several style properties in one frame. Measure once
    // before painting, not synchronously after every plugin DOM mutation.
    let scheduled=false;
    const schedule=()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;clamp();});};
    const observer=new MutationObserver(schedule);
    observer.observe(button,{attributes:true,attributeFilter:['style']});
    new ResizeObserver(schedule).observe(button);
    window.addEventListener('resize',schedule);
    schedule();
}
function refreshMemoryLabels(popup){
    // Preserve actual plugin nodes/listeners, including DIV-based controls.
    for(const group of popup.querySelectorAll('#stmb-profile-buttons,#stmb-extra-function-buttons,#stmb-prompt-manager-buttons,#stmb-manual-lorebook-buttons')){
        group.classList.add('homer-memory-actions');
        for(const b of group.querySelectorAll('.menu_button')){
            const original=b.textContent.replace(/^[^\p{L}\p{N}]+/u,'').trim();
            const names={'设为默认':'设为默认整理方案','编辑配置文件':'编辑整理方案','新配置文件':'新建整理方案','删除配置文件':'删除整理方案','导出配置文件':'导出整理方案','导入配置文件':'导入整理方案','通用设置':'显示与操作设置','自动记忆':'自动整理的触发条件','摘要提示管理器':'整理记忆使用的指令','整合提示管理器':'合并记忆使用的指令','追踪器 & 侧边提示':'持续追踪与补充提示','上下文设置':'整理时可读取的内容','压缩':'压缩已有记忆','主题摘录':'按主题提取记忆'};
            const clean=names[original]||original;
            if(b.textContent!==clean)b.textContent=clean;
            if(b.tagName!=='BUTTON'&&!b.dataset.homerAccessible){b.dataset.homerAccessible='1';b.setAttribute('role','button');b.tabIndex=0;b.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();b.click();}});}
        }
    }
    const labels=[[/创建记忆|Create Memory/i,'生成记忆'],[/整合记忆|整合已有记忆|Consolidate Memories/i,'合并整理已有记忆'],[/清除场景|Clear Scene/i,'取消范围选择'],[/^(关闭|Close)$/i,'关闭']];
    for(const button of popup.querySelectorAll('.popup-controls .menu_button'))for(const [pattern,label] of labels){
        if(pattern.test(button.textContent)&&button.textContent!==label){button.textContent=label;if(label==='取消范围选择')button.title='只取消起止标记，不删除聊天或记忆';}
        if(button.textContent===label){
            if(label==='关闭')button.dataset.memoryClose='true';
            if(label==='生成记忆')button.dataset.memoryGenerate='true';
            if(label==='合并整理已有记忆')popup.querySelector('.homer-memory-tab[aria-label="保存设置"]')?.append(button);
        }
    }
    for(const option of popup.querySelectorAll('option'))if(/SillyTavern|Current ST/i.test(option.textContent))option.textContent='当前对话模型';
}
export function installMemoryUi() {
    if(installed)return;installed=true;
    const css=document.createElement('link');css.rel='stylesheet';css.href='/assets/css/memory-controls.css';document.head.append(css);
    const scan=node=>{if(!(node instanceof Element))return;const parent=node.closest('.stmb-popup');if(parent){enhance(parent);refreshMemoryLabels(parent);}node.querySelectorAll('.stmb-popup').forEach(p=>{enhance(p);refreshMemoryLabels(p);});if(node.id==='stmb-memory-boundary-jump')enhanceBoundaryButton(node);node.querySelectorAll('#stmb-memory-boundary-jump').forEach(enhanceBoundaryButton);};
    new MutationObserver(records=>{
        const roots=new Set(),popups=new Set();
        for(const record of records){
            const popup=record.target instanceof Element?record.target.closest('.stmb-popup'):null;
            if(popup)popups.add(popup);
            for(const node of record.addedNodes)if(node instanceof Element)roots.add(node);
        }
        for(const node of roots){
            if(!node.isConnected)continue;
            let parent=node.parentElement;while(parent&&!roots.has(parent))parent=parent.parentElement;
            if(!parent)scan(node);
        }
        for(const popup of popups)if(popup.isConnected){enhance(popup);refreshMemoryLabels(popup);}
    }).observe(document.body,{childList:true,subtree:true});
    document.querySelectorAll('.stmb-popup').forEach(enhance);
    document.querySelectorAll('#stmb-memory-boundary-jump').forEach(enhanceBoundaryButton);
}
