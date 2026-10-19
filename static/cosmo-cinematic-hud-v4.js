/* Cosmo HUD v4: reactor visual, safe shortcuts, actual service health */
(function(){
'use strict';
function addReactor(){
 const w=document.querySelector('#chat .welcome');
 if(!w||w.querySelector('.cosmo-reactor-wrap'))return;
 const el=document.createElement('div');el.className='cosmo-reactor-wrap';el.setAttribute('aria-hidden','true');
 el.innerHTML='<div class="cosmo-reactor"><div class="cosmo-reactor-orbit"></div><div class="cosmo-reactor-core">C</div></div><div class="cosmo-reactor-caption">COSMO NEURAL CORE <span>/ ONLINE</span></div>';
 const title=w.querySelector('#welcomeTitle')||w.querySelector('h1');if(title)w.insertBefore(el,title);else w.prepend(el);
}
function safeOpen(name){if(typeof window.cosmoOpenKnownSite==='function'){window.cosmoOpenKnownSite(name);return}const urls={youtube:'https://www.youtube.com/','github do cosmo':'https://github.com/kauplayon/kaubot'};if(urls[name])window.location.assign(urls[name])}
function addShortcuts(){
 const deck=document.querySelector('.cosmo-command-deck');if(!deck||deck.querySelector('.cosmo-shortcuts'))return;
 const row=document.createElement('div');row.className='cosmo-shortcuts';row.setAttribute('aria-label','Atalhos rápidos');
 [['▶ YOUTUBE',()=>safeOpen('youtube')],['⌘ GITHUB',()=>safeOpen('github do cosmo')],['◉ MODO VOZ',()=>{if(typeof window.openVoiceMode==='function')window.openVoiceMode()}],['↻ ATUALIZAR NOTÍCIAS',()=>document.getElementById('refreshCosmoNews')?.click()]].forEach(([label,action])=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.addEventListener('click',action);row.appendChild(b)});
 deck.appendChild(row);
}
async function updateStatus(){
 const cloud=document.getElementById('jarvisHudCloud'),state=document.getElementById('jarvisHudState');
 try{const r=await fetch('/health',{cache:'no-store',headers:{Accept:'application/json'}});if(!r.ok)throw Error('health');const d=await r.json();if(cloud)cloud.textContent=d.ai_configured?'IA CONECTADA':'IA NÃO CONFIGURADA';if(state&&!document.querySelector('.voice-mode-overlay:not([hidden])'))state.textContent=d.status==='ok'?'SISTEMA OPERACIONAL':'VERIFICAR SISTEMA';document.documentElement.dataset.cosmoAi=d.ai_configured?'online':'local';document.documentElement.dataset.cosmoStorage=d.persistent_storage_configured?'persistent':'local'}
 catch(_){if(cloud)cloud.textContent='STATUS INDISPONÍVEL';document.documentElement.dataset.cosmoAi='unknown'}
}
function init(){addReactor();addShortcuts();updateStatus();const chat=document.getElementById('chat');if(chat)new MutationObserver(addReactor).observe(chat,{childList:true,subtree:true});document.addEventListener('visibilitychange',()=>{if(!document.hidden)updateStatus()});window.addEventListener('online',updateStatus)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();