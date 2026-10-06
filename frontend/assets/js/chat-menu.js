// Original vector drawings shared by cached chat and the live runtime.
const paths = {
  image: 'M3 3h18v18H3z M3 17l6-6 5 5 3-3 4 4 M15 7h2v2h-2z',
  copy: 'M8 8h12v12H8z M16 8V4H4v12h4',
  edit: 'm4 16 12-12 4 4L8 20H4v-4 M14 6l4 4 M3 22h18',
  rollback: 'M3 4h18 M3 11h7 M3 18h7 M17 9l-4 4 4 4 M13 13h5a4 4 0 0 1 0 8',
  delete: 'M3 6h18 M9 6V3h6v3 M6 6l1 15h10l1-15 M10 11l4 5 M14 11l-4 5',
  hide: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M9 12a3 3 0 1 0 6 0 3 3 0 1 0-6 0',
  select: 'M3 5h18 M3 12h7 M3 19h7 M13 15l3 3 6-7',
  collapse: 'm7 9 5-5 5 5 M7 15l5 5 5-5',
  regenerate: 'M20 7V3l-3 3 M20 7a9 9 0 1 0 1 5 M20 7h-4',
  continue: 'M3 3h18v18H3z M7 8l5 4-5 4 M13 8l5 4-5 4',
};
export function messageActionIcon(action) {
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  for(const [name,value] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'square','stroke-linejoin':'miter','aria-hidden':'true'}))svg.setAttribute(name,value);
  const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',paths[action]||paths.copy);svg.append(path);
  return svg;
}

export function positionChatMenu(menu, anchor, {header, composer, isUser=false, pressY}={}) {
  if(!menu.open||!anchor)return;
  const v=window.visualViewport,edge=10,gap=10;
  const leftEdge=(v?.offsetLeft||0)+edge;
  const rightEdge=(v?.offsetLeft||0)+(v?.width||innerWidth)-edge;
  const topEdge=Math.max((v?.offsetTop||0)+edge,(header?.getBoundingClientRect().bottom||0)+gap);
  const bottomEdge=Math.min((v?.offsetTop||0)+(v?.height||innerHeight)-edge,(composer?.getBoundingClientRect().top||innerHeight)-gap);
  menu.style.setProperty('max-height',`${Math.max(48,bottomEdge-topEdge)}px`,'important');
  const rect=anchor.getBoundingClientRect(),width=menu.offsetWidth,height=menu.offsetHeight;
  let top=rect.top-height-gap;
  if(top<topEdge)top=rect.bottom+gap;
  if(top+height>bottomEdge)top=Number.isFinite(pressY)?pressY-height-gap:topEdge;
  menu.style.left=`${Math.max(leftEdge,Math.min(isUser?rect.right-width:rect.left,rightEdge-width))}px`;
  menu.style.top=`${Math.max(topEdge,Math.min(top,bottomEdge-height))}px`;
}
