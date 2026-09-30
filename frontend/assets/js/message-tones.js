// Presentation only. The stored message and the model prompt are never rewritten.
export function decorateMessage(root) {
 if(!root || root.querySelector('iframe,style,script,table,button,form,canvas,svg'))return;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
 for(const text of nodes){
  if(text.parentElement.closest('code,pre,a,[data-message-tone],[style],.is-user'))continue;
  // Do not recolor creator-authored containers with their own classes.
  let parent=text.parentElement,custom=false;
  while(parent&&parent!==root){if(parent.className||!['P','EM','STRONG','SPAN','BLOCKQUOTE'].includes(parent.tagName)){custom=true;break;}parent=parent.parentElement;}
  if(custom)continue;
  const thought=text.parentElement.closest('em');
  if(thought){const span=document.createElement('span');span.dataset.messageTone='thought';span.textContent=text.data;text.replaceWith(span);continue;}
  const pattern=/“[^”\n]+”|「[^」\n]+」|『[^』\n]+』|"[^"\n]+"|\*[^*\n]+\*|（(?:心想|内心)[^）\n]*）/g;
  const matches=[...text.data.matchAll(pattern)];if(!matches.length)continue;
  const fragment=document.createDocumentFragment();let offset=0;
  for(const match of matches){fragment.append(text.data.slice(offset,match.index));const span=document.createElement('span');span.dataset.messageTone=/^[*（]/.test(match[0])?'thought':'speech';span.textContent=match[0];fragment.append(span);offset=match.index+match[0].length;}
  fragment.append(text.data.slice(offset));text.replaceWith(fragment);
 }
}
export function installMessageTones(){
 if(window.__homerMessageTones)return;window.__homerMessageTones=true;
 const css=document.createElement('link');css.rel='stylesheet';css.href='/assets/css/message-tones.css';document.head.append(css);
 const selector='.mes[is_user="false"] .mes_text,.preview-message:not(.is-user)';
 const pending=new Set();let frame;
 const queue=node=>{if(node.nodeType===3)node=node.parentElement;if(!(node instanceof Element))return;const root=node.closest(selector);if(root)pending.add(root);node.querySelectorAll(selector).forEach(e=>pending.add(e));if(!frame)frame=requestAnimationFrame(()=>{frame=0;for(const el of pending)decorateMessage(el);pending.clear();});};
 new MutationObserver(records=>{for(const r of records){queue(r.target);for(const n of r.addedNodes)queue(n);}}).observe(document.body,{subtree:true,childList:true,characterData:true});queue(document.body);
}
