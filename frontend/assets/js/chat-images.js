// Clean-room implementation of the observed two-section image-generation sheet.
// No card instructions, worldbooks or messages are sent to the image provider.
export function chatImages({request, scope, prepare, notice, messages}) {
  let key = '', rows = [], timer, fetching = false, revision = 0, dialog, readFailures = 0;
  const loaded = new Map();
  const pendingImages = new WeakMap();
  const visibleImages = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      visibleImages.unobserve(entry.target);
      const load = pendingImages.get(entry.target); pendingImages.delete(entry.target); void load?.();
    }
  }, {rootMargin:'160px'});
  function styles() {
    if (document.getElementById('homer-image-style')) return;
    const link = document.createElement('link'); link.id = 'homer-image-style'; link.rel = 'stylesheet';
    link.href = new URL('../css/chat-images.css', import.meta.url).href; document.head.append(link);
  }
  function node(tag, text, cls) {
    const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e;
  }
  async function refresh() {
    const s = scope(); if (!s?.conversation || s.preview || fetching) return;
    const current = key, rev = revision; fetching = true;
    try {
      const data = await request('/api/homer/images/history?conversation_id=' + encodeURIComponent(s.conversation));
      if (current !== key || rev !== revision) return;
      readFailures = 0; rows = data.list || []; render();
    } catch {
      // History retrieval is independent from chat readiness. Retry on revisit
      // or while a known task is pending, not through a page-blocking overlay.
      if (current === key) readFailures++;
    } finally {
      fetching = false;
      if (current === key && (rows.some(r => r.status === 'running') || (readFailures > 0 && readFailures <= 3))) {
        clearTimeout(timer); timer = setTimeout(refresh, Math.min(15000, 3000 * Math.max(1, readFailures)));
      }
    }
  }
  function render() {
    styles();
    const s = scope(); const next = s && !s.preview ? `${s.user}:${s.conversation}` : '';
    if (next !== key) {
      key = next; revision++; rows = []; readFailures = 0; loaded.clear(); visibleImages.disconnect(); clearTimeout(timer);
      dialog?.close();
      // A previous request may still be finishing. Start a fresh scoped read.
      fetching = false; if (key) timer = setTimeout(refresh, 500);
    }
    for (const {element, id} of messages()) {
      const matches = rows.filter(r => r.message_id === id).slice().reverse();
      let box = element.querySelector('.homer-generated-images');
      const signature = JSON.stringify(matches.map(r => [r.id,r.status,r.error]));
      if (box?.dataset.signature === signature) continue;
      if (!matches.length) { box?.remove(); continue; }
      if (!box) { box = node('div',null,'homer-generated-images'); element.querySelector('.mes_block')?.append(box); }
      box.replaceChildren(); box.dataset.signature = signature;
      for (const row of matches) {
        const item = node('figure',null,'homer-generated-image');
        const caption = node('figcaption', row.status === 'running' ? '正在生成图片… · 成功后扣积分' : row.status === 'failed' ? row.error : `${row.provider_name} · ${row.cost} 积分`);
        caption.setAttribute('role','status'); item.append(caption);
        if (row.status === 'succeeded') {
          const img = node('img'); img.alt = '本条消息生成的图片'; img.loading = 'lazy';
          item.prepend(img);
          const retry = node('button','重新加载图片'); retry.type='button'; retry.hidden=true; item.append(retry);
          const owner = key;
          const load = async () => {
            retry.hidden=true;
            try {
              const result = loaded.get(row.id) || await request('/api/homer/images/content/' + encodeURIComponent(row.id));
              if (key !== owner || !item.isConnected) return;
              if (!/^data:image\/(jpeg|png|webp);base64,/.test(result.data_url || '')) throw new Error('invalid image');
              loaded.set(row.id,result);
              while (loaded.size > 4) loaded.delete(loaded.keys().next().value);
              img.src=result.data_url;
            } catch { if (item.isConnected) { retry.hidden=false; caption.textContent='图片暂未加载，生成结果已保存'; } }
          };
          retry.onclick=load; pendingImages.set(item,load); visibleImages.observe(item);
        }
        box.append(item);
      }
    }
  }
  async function open(target) {
    if (dialog?.open) return;
    styles();
    const start = scope();
    if (!start?.conversation || start.preview) { notice('请在已保存的会话中生图，临时管理测试会话不计入图片历史', 'warning'); return; }
    const owner = `${start.user}:${start.conversation}`;
    const previous = document.activeElement;
    dialog = node('dialog',null,'homer-image-sheet'); dialog.id='homer-image-sheet';
    dialog.setAttribute('aria-labelledby','homer-image-heading');
    const handle=node('div',null,'homer-image-handle'); handle.setAttribute('aria-hidden','true');
    const title=node('h2','生成图片'); title.id='homer-image-heading';
    const summary=node('p','UTF-8 长度：0 · 预计消耗：—', 'homer-image-summary');
    const hint=node('p','您可自行填写图片描述。生成完成后，图片会出现在这条消息下方。失败不扣积分。','homer-image-hint');
    const label=node('label','图片内容'); label.htmlFor='homer-image-prompt';
    const prompt=node('textarea'); prompt.id='homer-image-prompt'; prompt.placeholder='描述画面中的人物、场景和风格…'; prompt.rows=5;
    const details=node('details'); details.open=true; details.append(node('summary','图片模型'));
    const options=node('div',null,'homer-image-models'); details.append(options);
    const status=node('p','正在读取可用模型…','homer-image-status'); status.setAttribute('role','status');
    const retry=node('button','重新读取'); retry.type='button'; retry.hidden=true;
    const footer=node('footer'); const cancel=node('button','取消','homer-image-cancel'); cancel.type='button';
    const submit=node('button','生成','homer-image-submit'); submit.type='button'; submit.disabled=true; footer.append(cancel,submit);
    dialog.append(handle,title,summary,hint,label,prompt,details,status,retry,footer); document.body.append(dialog);
    const activeDialog=dialog;
    let models=[],selected='',busy=false,requestId=crypto.randomUUID();
    const validScope=()=>{const s=scope();return s && `${s.user}:${s.conversation}`===owner;};
    function update() {
      const bytes=new TextEncoder().encode(prompt.value.trim()).length;
      const model=models.find(m=>m.id===selected);
      summary.textContent=`UTF-8 长度：${bytes} / 12000 · 预计消耗：${model ? model.cost_points + ' 积分' : '—'}`;
      submit.disabled=busy || !model || !bytes || bytes>12000;
      prompt.disabled=busy;
      options.querySelectorAll('input').forEach(e=>e.disabled=busy);
      submit.textContent=busy ? '正在提交…' : '生成';
    }
    prompt.oninput=()=>{requestId=crypto.randomUUID();update();};
    async function read() {
      retry.hidden=true;status.textContent='正在读取可用模型…';
      try {
        const data=await request('/api/homer/images/providers');
        if(!activeDialog.open || !validScope()) return;
        models=data.list||[];selected=models[0]?.id||'';options.replaceChildren();
        for (const model of models) {
          const option=node('label',null,'homer-image-model'); const radio=node('input');radio.type='radio';radio.name='homer-image-provider';radio.value=model.id;radio.checked=model.id===selected;
          radio.onchange=()=>{selected=model.id;requestId=crypto.randomUUID();update();};
          const text=node('span');text.append(node('strong',model.name),node('small',model.memo || ''));option.append(radio,text,node('span',`${model.cost_points} 积分`));options.append(option);
        }
        status.textContent=models.length ? '' : '暂无可用生图模型，请联系管理员配置。';
      } catch {status.textContent='无法读取生图模型，请检查网络后重试。';retry.hidden=false;}
      update();
    }
    retry.onclick=read;
    cancel.onclick=()=>activeDialog.close();
    activeDialog.addEventListener('close',()=>{activeDialog.remove();previous?.focus?.();},{once:true});
    activeDialog.addEventListener('click',e=>{if(e.target===activeDialog){const r=activeDialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)activeDialog.close();}});
    submit.onclick=async()=>{
      if(submit.disabled || !validScope()) return;
      busy=true;update();status.textContent='';
      try {
        const messageId=await prepare(target);
        if(!validScope() || !activeDialog.open) return;
        if(!messageId) throw new Error('这条消息尚未保存，请稍后重试');
        const result=await request('/api/homer/images/tasks',{method:'POST',body:JSON.stringify({text:prompt.value.trim(),provider_id:selected,expected_cost:models.find(m=>m.id===selected)?.cost_points,conversation_id:start.conversation,message_id:messageId,request_id:requestId})});
        if(validScope()) {
          const model=models.find(m=>m.id===selected);
          rows=[...rows.filter(r=>r.id!==result.id),{id:result.id,message_id:messageId,status:result.status,provider_name:model.name,cost:model.cost_points,error:'任务未能完成，请重新生成'}];
          render();activeDialog.close();notice('图片任务已提交，结果会显示在对应消息下方','success');clearTimeout(timer);await refresh();
        }
      } catch(e) {status.textContent=e.message || '提交失败，请重试';}
      finally {busy=false;update();}
    };
    activeDialog.showModal(); void read();
  }
  document.addEventListener('visibilitychange',()=>{if(!document.hidden && key) {clearTimeout(timer);void refresh();}});
  window.addEventListener('online',()=>{if(key) {readFailures=0;clearTimeout(timer);void refresh();}});
  return {open,render};
}
