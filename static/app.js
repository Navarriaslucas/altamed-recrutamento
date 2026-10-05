// menu móvel
document.querySelectorAll('[data-toggle]').forEach(b=>b.addEventListener('click',()=>{
  const t=document.querySelector(b.dataset.toggle);t.classList.toggle('open');b.setAttribute('aria-expanded',t.classList.contains('open'))}));
// DISC: sem repetir nota na mesma pergunta + progresso
const disc=document.querySelectorAll('.disc-q');
function checarDisc(){let ok=0;disc.forEach(q=>{const vs=[...q.querySelectorAll('select')].map(s=>s.value).filter(Boolean);
  const dup=new Set(vs).size!==vs.length;q.classList.toggle('erro',dup);if(vs.length===4&&!dup)ok++});
  const p=document.querySelector('#disc-prog');if(p){p.style.width=(100*ok/disc.length)+'%';document.querySelector('#disc-count').textContent=ok+' de '+disc.length}}
document.querySelectorAll('.disc-q select').forEach(s=>s.addEventListener('change',checarDisc));checarDisc();
// Kanban
const csrf=document.querySelector('meta[name=csrf]')?.content;let drag=null;
document.querySelectorAll('.kcard').forEach(c=>{
  c.addEventListener('dragstart',e=>{drag=c;c.classList.add('dragging');e.dataTransfer.setData('text/plain',c.dataset.id)});
  c.addEventListener('dragend',()=>{c.classList.remove('dragging');drag=null})});
document.querySelectorAll('.col').forEach(col=>{
  col.addEventListener('dragover',e=>{e.preventDefault();col.classList.add('over')});
  col.addEventListener('dragleave',()=>col.classList.remove('over'));
  col.addEventListener('drop',async e=>{e.preventDefault();col.classList.remove('over');if(!drag)return;
    const from=drag.parentElement,card=drag;col.querySelector('.lista').appendChild(card);
    const r=await fetch('/admin/candidatos/'+card.dataset.id+'/etapa',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF':csrf},body:JSON.stringify({etapa:col.dataset.etapa})});
    if(!r.ok){from.appendChild(card);alert('Não foi possível mover o candidato. Tente novamente.')}
    document.querySelectorAll('.col').forEach(c=>c.querySelector('.n').textContent=c.querySelectorAll('.kcard').length)})});
