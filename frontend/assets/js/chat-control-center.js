// Presentation adapter: move existing action nodes, never duplicate handlers or permissions.
const paths = {
 model:'M4 5h16v11H9l-5 4V5Z M8 9h8 M8 12h5',
 preset:'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
 memory:'M12 5C8 2 4 4 4 4v15s4-2 8 1c4-3 8-1 8-1V4s-4-2-8 1Z M12 5v15',
 mod:'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M17 14v6 M14 17h6',
 appearance:'M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h5a4 4 0 0 0 4-4c0-3-4-6-9-6Z M7 9h.01 M10 6h.01 M15 6h.01',
};
function icon(key){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');const p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',paths[key]);svg.append(p);return svg;}
export function controlCenter(root){
 if(!root||root.dataset.controlCenter)return;root.dataset.controlCenter='true';root.classList.add('homer-control-center');
 const head=root.querySelector('header'),list=root.querySelector('.homer-setting-list,.preview-setting-list'),shortcuts=root.querySelector('.homer-chat-shortcuts');
 const rows=[...list.children],appearance=shortcuts?.querySelector('[aria-label="界面设置"]');
 if(appearance)rows.push(appearance);
 list.className='homer-control-grid';
 const groups=['对话能力','扩展与外观'].map(title=>{const section=document.createElement('section'),heading=document.createElement('h3'),items=document.createElement('div');section.className='homer-control-group';heading.textContent=title;items.className='homer-control-group__items';section.append(heading,items);return section;});
 for(const [i,button] of rows.entries()){
  const key=['model','preset','memory','mod','appearance'][i];
  let copy=button.querySelector('.homer-setting-row__copy,.preview-setting-row__copy');
  if(!copy){copy=document.createElement('span');const name=document.createElement('strong');name.textContent='界面设置';const desc=document.createElement('small');desc.textContent='气泡与背景';copy.append(name,desc);}
  copy.className='homer-control-card__copy';for(const child of copy.children)child.className='';
  const arrow=document.createElement('span');arrow.className='homer-control-chevron';arrow.textContent='›';arrow.setAttribute('aria-hidden','true');
  button.className='homer-control-card';button.dataset.control=key;button.replaceChildren(icon(key),copy,arrow);groups[i<3?0:1].lastElementChild.append(button);
 }
 list.replaceChildren(...groups);
 const caption=document.createElement('p');caption.className='homer-control-caption';caption.textContent='对话设置';head.before(caption);
 if(shortcuts)shortcuts.classList.add('homer-control-utilities');
 const note=root.querySelector('.homer-privacy-note,.preview-privacy-note');if(note){note.className='homer-control-footnote';note.textContent='模型、预设与 Mod 仅影响当前对话。长记忆中的自动总结沿用账号设置。';root.append(note);}
}
