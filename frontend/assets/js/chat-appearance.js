import { settingsPage } from './chat-settings-page.js';
import { installMessageTones } from './message-tones.js';
// Personal appearance is local and scoped to an account + conversation.
const defaults = { assistant: '#29485f', user: '#4c4c4c', background: '#212121', image: '' };
let scopeReader = () => ({}), activeKey = '', dialog;
const keyFor = () => { const s=scopeReader();return s.owner && s.conversation ? `homer.chat-appearance.v1:${encodeURIComponent(s.owner)}:${encodeURIComponent(s.conversation)}` : ''; };
const color = (value, fallback) => /^#[\da-f]{6}$/i.test(value || '') ? value : fallback;
export function readableText(hex) {
    const rgb=hex.slice(1).match(/../g).map(n=>parseInt(n,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);
    return (.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]) > .179 ? '#000000' : '#ffffff';
}
function readableTint(background,tint){
 const luminance=hex=>{const c=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
 const bg=luminance(background),target=readableText(background)==='#ffffff'?255:0;
 for(let step=0;step<=10;step++){const hex='#'+tint.slice(1).match(/../g).map(v=>Math.round(parseInt(v,16)*(1-step/10)+target*step/10).toString(16).padStart(2,'0')).join('');const fg=luminance(hex);if((Math.max(bg,fg)+.05)/(Math.min(bg,fg)+.05)>=4.5)return hex;}
 return readableText(background);
}
function read() { try { return JSON.parse(localStorage.getItem(activeKey)) || {}; } catch { return {}; } }
function apply(value={}) {
    installMessageTones();
    const s=document.body.style;
    for (const [key,variable] of [['assistant','--tavo-assistant-bubble'],['user','--tavo-user-bubble'],['background','--chat-bg']]) {
        const v=color(value[key],defaults[key]);s.setProperty(variable,v);s.setProperty(`--homer-${key}-text`,readableText(v));
    }
    const dark=readableText(color(value.assistant,defaults.assistant))==='#ffffff';
    s.setProperty('--homer-speech-color',readableTint(color(value.assistant,defaults.assistant),dark?'#b4e8ff':'#005179'));
    s.setProperty('--homer-thought-color',readableTint(color(value.assistant,defaults.assistant),dark?'#f6c6eb':'#713164'));
    const picture = /^data:image\/(jpeg|png|webp);base64,[\da-z+/=]+$/i.test(value.image || '') ? value.image : '';
    s.setProperty('--homer-bg-image',picture ? `url("${picture}")` : 'none');
    document.body.classList.toggle('homer-personal-background',!!value.background || !!picture);
}
function sync() {
    const next = keyFor();
    if (dialog?.open) {
        if (next === activeKey) return;
        // An in-flight account/conversation change cannot keep an editor for
        // another scope alive, even when a background image is still decoding.
        dialog.close();
    }
    activeKey = next;
    apply(activeKey ? read() : {});
}
function node(tag,cls,text) { const e=document.createElement(tag);e.className=cls||'';if(text)e.textContent=text;return e; }
async function imageValue(file) {
    if (!file.type.startsWith('image/')) throw Error('请选择相册中的图片');
    if (file.size>20*1024*1024) throw Error('图片超过 20 MB，请换一张较小的图片');
    const url=URL.createObjectURL(file);
    try {
        const img=new Image();img.src=url;await img.decode();
        const scale=Math.min(1,1600/Math.max(img.width,img.height));
        const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.width*scale));canvas.height=Math.max(1,Math.round(img.height*scale));
        const ctx=canvas.getContext('2d');ctx.fillStyle='#212121';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
        const data=canvas.toDataURL('image/jpeg',.8);
        if(data.length>1800000)throw Error('这张图片过于复杂，请选择较小的图片');
        return data;
    } finally { URL.revokeObjectURL(url); }
}
export function bindChatAppearance(getScope) { scopeReader=getScope;sync();return { refresh:sync, open:openChatAppearance }; }
export function openChatAppearance() {
    sync();if(dialog?.open)return;
    const savedKey=activeKey,original=read();let draft={...defaults,...original},reading=false;
    const currentDialog=node('dialog','homer-appearance-dialog');dialog=currentDialog;dialog.setAttribute('aria-labelledby','homer-appearance-title');
    const head=node('header'),title=node('h2','','界面设置');title.id='homer-appearance-title';
    const close=node('button','','×');close.type='button';close.setAttribute('aria-label','关闭界面设置');close.onclick=()=>dialog.close();head.append(title,close);
    const note=node('p','homer-appearance-note','仅保存在这台设备的当前会话，不改变角色卡。调色可即时预览，点保存后生效。');
    const preview=node('div','homer-appearance-preview');preview.setAttribute('aria-label','当前外观预览');
    preview.append(node('span','homer-appearance-preview__caption','效果预览'),node('div','homer-appearance-preview__assistant','故事从这里继续。'),node('div','homer-appearance-preview__user','准备好了，我们出发吧。'));
    const refreshPreview=()=>{
        preview.style.backgroundColor=color(draft.background,defaults.background);
        preview.style.backgroundImage=draft.image ? `url("${draft.image}")` : 'none';
        for(const key of ['assistant','user']){const bubble=preview.querySelector(`.homer-appearance-preview__${key}`);const c=color(draft[key],defaults[key]);bubble.style.backgroundColor=c;bubble.style.color=readableText(c);}
        for(const row of fields.children){const input=row.querySelector('input');for(const swatch of row.querySelectorAll('button'))swatch.setAttribute('aria-pressed',String(swatch.style.getPropertyValue('--swatch')===input.value));}
    };
    const fields=node('div','homer-appearance-fields');
    const tabs=node('nav','homer-appearance-targets');tabs.setAttribute('aria-label','选择要调整的外观');
    let selectedTarget='assistant';
    const selectTarget=key=>{selectedTarget=key;[...fields.children].forEach((row,i)=>row.hidden=['assistant','user','background'][i]!==key);[...tabs.children].forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.target===key)));pictures.hidden=key!=='background';};
    for (const [key,label] of [['assistant','角色气泡'],['user','我的气泡'],['background','纯色背景']]) {
        const target=node('button','',label);target.type='button';target.dataset.target=key;target.onclick=()=>selectTarget(key);tabs.append(target);
        const row=node('label','homer-appearance-color'),input=document.createElement('input');input.type='color';input.value=color(draft[key],defaults[key]);input.setAttribute('aria-label',label);
        const swatches=node('span','homer-appearance-swatches');
        for(const hex of ['#29485f','#4c4c4c','#ede6fa','#f7e9df','#ffffff','#212121']) {
            const swatch=node('button');swatch.type='button';swatch.style.setProperty('--swatch',hex);swatch.setAttribute('aria-label',`${label} ${hex}`);
            swatch.onclick=e=>{e.preventDefault();input.value=hex;input.dispatchEvent(new Event('input'));};swatches.append(swatch);
        }
        input.oninput=()=>{draft[key]=input.value;if(key==='background')draft.image='';apply(draft);refreshPreview();};row.append(node('strong','',label),input,swatches);fields.append(row);
    }
    const pictures=node('div','homer-appearance-pictures'),file=document.createElement('input');file.type='file';file.accept='image/*';file.hidden=true;
    const choose=node('button','','从相册选择背景'),remove=node('button','','移除背景图片');choose.type=remove.type='button';choose.onclick=()=>file.click();
    const status=node('p','homer-appearance-status');status.setAttribute('role','status');
    file.onchange=async()=>{const picked=file.files?.[0];file.value='';if(!picked)return;reading=true;save.disabled=true;choose.disabled=true;status.textContent='正在读取图片…';try { draft.image=await imageValue(picked);if(dialog===currentDialog&&currentDialog.open){apply(draft);status.textContent='图片已预览，保存后保留。';} }catch(e){status.textContent=e.message;}finally{reading=false;save.disabled=!savedKey;choose.disabled=false;}};
    remove.onclick=()=>{draft.image='';apply(draft);refreshPreview();status.textContent='已改为纯色背景，保存后保留。';};pictures.append(choose,remove,file);
    new MutationObserver(refreshPreview).observe(status,{childList:true});
    const footer=node('footer'),reset=node('button','','恢复默认'),cancel=node('button','','取消'),save=node('button','is-primary','保存');
    for(const b of [reset,cancel,save])b.type='button';
    reset.onclick=()=>{draft={...defaults};fields.querySelectorAll('input').forEach((input,i)=>input.value=defaults[['assistant','user','background'][i]]);apply(draft);status.textContent='已预览默认外观，保存后保留。';};cancel.onclick=()=>dialog.close();
    save.disabled=!savedKey;if(!savedKey)status.textContent='当前会话尚未就绪，请稍后重新打开。';
    save.onclick=()=>{if(reading||!savedKey)return;if(keyFor()!==savedKey){currentDialog.close();return;}try {localStorage.setItem(savedKey,JSON.stringify(draft));currentDialog.close();}catch{status.textContent='本地空间不足，未保存。可以移除背景图片后重试。';}};
    footer.append(reset,cancel,save);dialog.append(head,note,preview,tabs,fields,pictures,status,footer);document.body.append(dialog);refreshPreview();selectTarget(selectedTarget);
    settingsPage(dialog, { head, footer, title: '界面设置' });
    dialog.addEventListener('close',()=>{currentDialog.remove();sync();},{once:true});dialog.showModal();
}
window.addEventListener('storage',e=>{if(e.key===activeKey)sync();});
window.addEventListener('homer-account-cleared', () => { dialog?.close(); sync(); });
