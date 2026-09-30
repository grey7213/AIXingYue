// A small editor for Memory Books records. All writes go through the real plugin.
const node=(tag,cls,text)=>{const e=document.createElement(tag);e.className=cls;if(text)e.textContent=text;return e;};
export function memoryManager(panel) {
    let snapshot, editing=null, busy=false, serial=0;
    const api=()=>window.HomerMemoryBooks?.memories;
    const note=node('p','homer-memory-note');note.setAttribute('role','status');
    const list=node('div','homer-memory-records');
    const retry=node('button','homer-memory-row','重新读取');retry.type='button';retry.onclick=()=>load();retry.hidden=true;
    panel.append(note,list,retry);
    function render() {
        editing=null; list.replaceChildren();
        note.textContent=snapshot.items.length?`共 ${snapshot.items.length} 条记忆 · 点击可编辑`:'还没有记忆。返回后点“立即总结”，把聊天中的重要内容记下来。';
        let shown=0;
        const more=node('button','homer-memory-row','显示更多记忆');more.type='button';
        const append=()=>{
            more.remove();
            for(const item of snapshot.items.slice(shown,shown+40)) {
                const button=node('button','homer-memory-record');button.type='button';
                button.append(node('strong','',item.title),node('p','',item.content),node('small','',item.disabled?'已停用':'用于后续对话'));
                button.onclick=()=>edit(item);list.append(button);
            }
            shown+=40;if(shown<snapshot.items.length)list.append(more);
        };
        more.onclick=append;append();
    }
    function edit(item) {
        editing=item;note.textContent='只编辑这条对话记忆，不会修改角色设定或聊天原文。';list.replaceChildren();
        const form=node('form','homer-memory-editor');
        const title=node('input','text_pole');title.value=item.title;title.maxLength=500;title.required=true;title.setAttribute('aria-label','记忆标题');
        const content=node('textarea','text_pole');content.value=item.content;content.maxLength=100000;content.required=true;content.setAttribute('aria-label','记忆内容');
        const enabled=node('input','');enabled.type='checkbox';enabled.checked=!item.disabled;
        const label=node('label','homer-memory-auto-toggle','在后续对话中使用');label.append(enabled);
        const actions=node('div','homer-memory-editor-actions');
        const cancel=node('button','','取消'),save=node('button','homer-memory-save','保存记忆'),remove=node('button','homer-memory-delete','删除这条记忆');
        cancel.type=remove.type='button';save.type='submit';
        const dirty=()=>title.value!==item.title||content.value!==item.content||enabled.checked===item.disabled;
        const confirm=node('div','homer-memory-delete-confirm');confirm.hidden=true;
        const yes=node('button','homer-memory-delete','确认删除'),no=node('button','','保留');yes.type=no.type='button';
        confirm.append(node('p','','删除后这条记忆将不再用于对话；聊天原文保留。'),no,yes);
        no.onclick=()=>confirm.hidden=true;remove.onclick=()=>{confirm.hidden=false;no.focus();};
        const write=async changes=>{
            if(busy)return;busy=true;const ticket=++serial;
            for(const e of form.elements)e.disabled=true;
            note.textContent='正在保存记忆…';
            try{await api().update(snapshot,item,changes);if(ticket!==serial)return;await load();}
            catch(error){if(ticket===serial){note.textContent=error.message||'保存失败，内容已保留，请重试。';for(const e of form.elements)e.disabled=false;}}
            finally{busy=false;}
        };
        form.onsubmit=e=>{e.preventDefault();if(form.reportValidity())void write({title:title.value,content:content.value,disabled:!enabled.checked});};
        yes.onclick=()=>void write({remove:true});cancel.onclick=()=>render();
        actions.append(cancel,save);form.append(title,content,label,actions,remove,confirm);list.append(form);
        // A cancelled editor intentionally keeps the original record; no auto-save on Back.
        editing={item,dirty,discard:()=>render()};
    }
    async function load(){
        const ticket=++serial;retry.hidden=true;editing=null;list.replaceChildren();note.textContent='正在读取已保存的记忆…';
        try{if(!api())throw Error('记忆管理暂不可用，请重新打开长记忆。');const result=await api().list();if(ticket!==serial||!panel.isConnected)return;snapshot=result;render();}
        catch(error){if(ticket===serial){note.textContent=error.message||'读取失败，请重试。';retry.hidden=false;}}
    }
    function back(){
        if(busy){note.textContent='正在保存，请稍候。';return true;}
        if(editing){render();return true;}
        ++serial;return false;
    }
    return {load,back};
}
