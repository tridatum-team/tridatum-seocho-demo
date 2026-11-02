const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function fetchJSON(path){const r=await fetch(path);const data=await r.json();if(!r.ok)throw new Error(data.error||'목록을 불러오지 못했습니다.');return data;}
(async()=>{
  try{
    const config=await fetchJSON('/api/config');
    const records=await fetchJSON('/api/records');
    const latest=new Map(records.map(r=>[r.case_id,r]));
    document.querySelector('#system').textContent=`${config.network_blocked?'외부 통신 차단 확인':'외부 통신 차단 미확인'} · ${config.model_available?'로컬 모델 준비':'로컬 모델 미준비'}`;
    document.querySelector('#casecount').textContent=`전체 ${config.cases.length}건`;
    document.querySelector('#cases').innerHTML=config.cases.map(c=>{
      const b=config.bundles[c.id],r=latest.get(c.id);
      return `<tr><td>SYN-CLM-${esc(c.id)}</td><td>${esc(b.customer)}</td><td><a class="request-title" href="/review?case=${encodeURIComponent(c.id)}">${esc(b.title)}</a><small>${esc(b.purpose)}</small></td><td>${c.documents}개</td><td>${r?esc(r.state)+(r.saved_at?' · 기록 저장':''):'미검토'}</td><td><a href="/review?case=${encodeURIComponent(c.id)}" aria-label="${esc(b.title)} 검토">검토 ↗</a></td></tr>`;
    }).join('');
    document.querySelectorAll('#cases tr').forEach(row=>row.addEventListener('click',event=>{if(!event.target.closest('a')&&!window.getSelection().toString())location.href=row.querySelector('a').href;}));
    document.querySelector('#storage-note').textContent=config.public?'방문자 세션별 기록 · 1시간 미사용 시 초기화':'이 실행 세션의 검토 상태 표시';
    document.querySelector('#notice').textContent='';
  }catch(error){document.querySelector('#notice').textContent=error.message;document.querySelector('#notice').classList.add('error');}
})();
