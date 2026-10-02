async function analyze(){
 const btn=document.querySelector('#analyze button'); const out=document.querySelector('#analyzeResult');
 const linkedin=document.querySelector('#linkedin').value.trim(), instagram=document.querySelector('#instagram').value.trim();
 if(!linkedin||!instagram){out.innerHTML='<div class="error">Both public URLs are required.</div>';return}
 btn.disabled=true;btn.textContent='Reading public sources…';out.innerHTML='';
 try{
  const r=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({linkedin,instagram})});
  const d=await r.json(); if(!r.ok) throw Error(d.error);
  out.innerHTML=`<div class="panel live-profile" style="margin-top:18px">
    <div class="eyebrow">PROFILE READY · ${escapeHtml(d.name)}</div>
    <h2>${escapeHtml(d.role)}</h2>
    <div class="live-grid"><div><div class="mini-label">NEEDS & VALUES</div>${d.needs.map(x=>`<div class="bullet">${escapeHtml(x)}</div>`).join('')}</div><div><div class="mini-label">INTERESTS</div><div class="big-chips">${d.interests.map(x=>`<span>${escapeHtml(x)}</span>`).join('')}</div></div></div>
    <div class="evidence"><div class="mini-label">SOURCE CHECK</div><div>↳ ${escapeHtml(d.evidence[0])}</div><div>↳ ${escapeHtml(d.evidence[1])}</div></div>
    <p class="live-note">${escapeHtml(d.source_policy)}</p>
    <div class="cta-row"><a class="btn primary" href="${d.profile_url}">Open agent profile →</a><a class="btn ghost" href="${d.ranking_url}">See matches →</a></div>
  </div>`
 }catch(e){out.innerHTML=`<div class="error">${escapeHtml(e.message)}</div>`}
 finally{btn.disabled=false;btn.textContent='Analyze person →'}
}
function escapeHtml(s){return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
