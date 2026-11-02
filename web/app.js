const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const titles={C01:['미사용 필터 반품','서초정비 · 이전 규정 적용 여부 확인'],C02:['전륜 패드 교환 요청','양재서비스 · 수령 제품 식별 확인'],C03:['분할 출고 재고 반품','서초정비 · 출고 및 기처리 이력 대조'],C04:['와이퍼 파손 접수','반포오토 · 제출 증빙 확인'],C05:['점화 플러그 대체 요청','양재서비스 · 고객 요청 및 매입처 의견'],C06:['패드 라벨 식별 요청','반포오토 · 판독 불확실 항목 확인']};
let config,cid=new URLSearchParams(location.search).get('case'),record=null,currentDoc='',busy=false,showText=false,documentData=null;
async function api(path,data){const r=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{});const obj=await r.json();if(!r.ok)throw new Error(obj.error||'요청 실패');return obj;}
function notice(text,error=false){$('#notice').textContent=text;$('#notice').classList.toggle('error',error);}
function tab(name){$$('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));$$('.tabcontent').forEach(p=>p.hidden=p.id!==name);}
function statusClass(state){return state==='통과'?'good':state==='자료 부족'?'warn':'bad';}
function docName(id){return config.documents.find(d=>d.id===id)?.title||id;}
function fieldsSchema(){return [['customer','거래처','text'],['request_date','접수일','date'],['part','요청 품번','text'],['quantity','요청 수량','number'],['unit','단위','text'],['label_part','수령 라벨 품번 · 공란은 미상','text'],['received_quantity','회수 수량 · 공란은 미상','number'],['vendor_quantity','매입처 인정 의견 수량','number'],['shipment_ids','참조 출고번호 · 쉼표로 구분','text'],['reason','접수 사유','text']];}
function fieldDoc(key){return ['label_part'].includes(key)?cid+'-LBL':['received_quantity'].includes(key)?cid+'-INS':['vendor_quantity'].includes(key)?cid+'-VND':cid+'-REQ';}
function selectCase(next){
if(busy)return;
cid=next;record=null;documentData=null;showText=false;toggleText();
$('#caseid').textContent=`접수번호 SYN-CLM-${cid}`;
$('#casetitle').textContent=titles[cid][0];
$('#casesub').textContent=titles[cid][1];
const docs=config.documents.filter(d=>d.case_id===cid);
$('#doccount').textContent=`${docs.length}개`;
$('#doclist').innerHTML=docs.map(d=>`<button data-doc="${d.id}">${esc(d.title)}</button>`).join('');
$$('[data-doc]').forEach(b=>b.onclick=()=>viewDoc(b.dataset.doc));
$('#step2').classList.remove('active');$('#step3').classList.remove('active');
$('#checks').innerHTML='<div class="empty"><h2>검토 대기</h2><p>제출 문서를 확인한 뒤 ‘문서 추출 · 대조 실행’을 누르세요.<br>추출값과 거래·규정 대조 결과가 이곳에 표시됩니다.</p></div>';
$('#fields').innerHTML='<p class="method-note">추출 후 값을 보정할 수 있습니다.</p>';
$('#draft').innerHTML='<div class="empty"><h2>회신 초안 대기</h2><p>검토 완료 후 로컬 모델로 초안을 작성할 수 있습니다.</p></div>';
renderBundle();notice('');tab('checks');
}
function renderBundle(){
const b=config.bundles[cid];
$('#bundlesummary').textContent=`접수 파일 묶음 · 제출 ${b.documents.length}개 / 규정 ${b.policies.length}개 / 원장 3개`;
$('#bundlecontent').innerHTML=`
  <div class="bundle-intro"><p>${esc(b.purpose)}</p><a href="/api/bundle?case_id=${encodeURIComponent(cid)}" download="${cid}_접수문서.zip">전체 묶음 ZIP 받기</a></div>
  <table class="bundle-table" aria-label="접수 파일 목록"><thead><tr><th scope="col">구분</th><th scope="col">제출 파일</th><th scope="col">대조·열람 범위</th></tr></thead><tbody>
    ${b.documents.map(d=>`<tr><td>${esc(d.role)}</td><td><button class="file-link" data-bundle-doc="${d.id}">${esc(d.id)} · ${esc(d.title)} ↗</button></td><td>${esc(d.use)}${d.sources.length?`<small>서식 참고: ${d.sources.map(id=>esc(config.sources.find(s=>s.id===id)?.title||id)).join(', ')}</small>`:''}</td></tr>`).join('')}
  </tbody></table>
  <div class="bundle-references"><b>업무 기준</b>${b.policies.map(id=>`<button class="file-link" data-bundle-doc="${id}">${esc(id)} 가상 규정 ↗</button>`).join('')}<b>구조화 원장</b>${['shipments.csv','completed_returns.csv','parts.csv'].map(name=>`<button class="file-link" data-bundle-csv="${name}">${name} ↗</button>`).join('')}</div>
  ${b.missing_submission.length?`<p class="bundle-missing">미제출 자료: ${b.missing_submission.map(esc).join(' · ')}. 파일이 없다는 사실과 파손 여부의 판단을 구분합니다.</p>`:''}
  <details class="source-notes"><summary>공개 서식 출처와 합성 범위</summary>${config.sources.map(s=>`<p><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)} ↗</a><br>${esc(s.location)}<br>반영: ${esc(s.applied)}<br>제외: ${esc(s.not_imported)}<br>${esc(s.rights)}</p>`).join('')}<p>공개 원문은 ZIP에 포함하지 않습니다. 접수 메일·제품 라벨·반품 규정은 독자 작성 합성 자료입니다. ZIP에는 예상 정답이나 검토 결과가 없으며, 실행 시 문서를 추출하고 대조합니다.</p></details>`;
$$('[data-bundle-doc]').forEach(button=>button.onclick=()=>{showText=false;toggleText();viewDoc(button.dataset.bundleDoc);$('#imageviewer').scrollIntoView({block:'center'});});
$$('[data-bundle-csv]').forEach(button=>button.onclick=()=>csvView(button.dataset.bundleCsv));
}
async function viewDoc(id,value=null){currentDoc=id;documentData=record?.documents[id]||null;const mode=id.startsWith('SYN-R')?'clean':$('#mode').value;$('#doctitle').textContent=`${id} · ${docName(id)}`;$('#pdf').href=`/api/document?id=${encodeURIComponent(id)}&mode=${mode}`;$('#pageimg').src=`/api/page?id=${encodeURIComponent(id)}&mode=${mode}&page=1`;$('#highlights').innerHTML='';$$('[data-doc]').forEach(b=>b.classList.toggle('active',b.dataset.doc===id));$('#sourceinfo').textContent=`${mode==='scan'?'스캔 이미지':'PDF 원본'} · 1페이지`;if(!documentData&&id.startsWith('SYN-R')){try{const result=await api('/api/text?id='+id);if(currentDoc!==id)return;documentData=result;}catch(e){notice(e.message,true);}}$('#ocrtext').textContent=documentData?.text||'아직 추출하지 않았습니다. 문서 추출 · 대조를 실행하세요.';if(value!==null&&documentData)highlight(value);}
function highlight(value){const words=documentData.pages[0].words,needle=String(value).replace(/\s/g,'');if(!needle)return;let boxes=[];for(let i=0;i<words.length;i++){let joined='';for(let j=i;j<Math.min(words.length,i+12);j++){joined+=words[j].text.replace(/\s/g,'');if(joined===needle||words[i].text===String(value)){boxes=words.slice(i,j+1).map(w=>w.box);break;}if(joined.length>needle.length+5)break;}if(boxes.length)break;}$('#highlights').innerHTML=boxes.map(b=>`<div class="highlight" style="left:${b[0]*100}%;top:${b[1]*100}%;width:${b[2]*100}%;height:${b[3]*100}%"></div>`).join('');$('#sourceinfo').textContent=boxes.length?'추출 근거 위치 강조 · 1페이지':'일치 위치를 찾지 못함 · 원문 직접 확인';if(boxes.length){const img=$('#pageimg');const scroll=()=>{$('#imageviewer').scrollTop=Math.max(0,boxes[0][1]*img.clientHeight-120);};if(img.complete)scroll();else img.onload=scroll;}}
async function csvView(name){try{const rows=await api('/api/csv?name='+encodeURIComponent(name));const keys=Object.keys(rows[0]||{});$('#csvcontent').innerHTML=`<p>입력 원장: ${esc(name)} · OCR 결과가 아닌 구조화 데이터</p><table><tr>${keys.map(k=>`<th>${esc(k)}</th>`).join('')}</tr>${rows.map(r=>'<tr>'+keys.map(k=>`<td>${esc(r[k])}</td>`).join('')+'</tr>').join('')}</table>`;$('#csvdialog').showModal();}catch(e){notice(e.message,true);}}
function render(){
const r=record.result;
$('#step2').classList.add('active');
$('#checks').innerHTML=`
  <div class="result-banner">
    <div><span class="eyebrow">대조 결과</span><h2>${esc(r.state)}</h2><small>담당자 최종 결정 필요 · 자동 승인 없음</small></div>
    <span class="extraction-method">${esc(record.mode==='scan'?'스캔 OCR':'PDF 텍스트 추출')}</span>
  </div>
  <table class="quantities" aria-label="수량 비교">
    <thead><tr><th scope="col">요청 수량</th><th scope="col">반품 가능 잔량</th><th scope="col">초과 수량</th></tr></thead>
    <tbody><tr><td>${esc(record.fields.quantity??'—')}</td><td>${esc(r.remaining??'—')}</td><td>${esc(r.excess??'—')}</td></tr></tbody>
  </table>
  <table class="check-table" aria-label="항목별 검토 결과">
    <thead><tr><th scope="col">검토 항목</th><th scope="col">결과</th><th scope="col">검토 내용 · 근거</th></tr></thead>
    <tbody>${r.checks.map((c,i)=>`<tr><th scope="row">${esc(c.name)}</th><td><span class="status ${statusClass(c.state)}">${esc(c.state)}</span></td><td><p>${esc(c.detail)}</p><div class="refs">${c.refs.map((ref,j)=>`<button data-ref="${i},${j}">${esc(ref.csv||ref.doc)} ↗</button>`).join('')}</div></td></tr>`).join('')}</tbody>
  </table>
  <p class="method-note">처리 ${record.seconds}초 · 문서 ${Object.keys(record.documents).length}개 · 수동 보정 ${record.revision}회<br>추출: ${record.mode==='scan'?'Tesseract kor+eng → 서식 기반 파싱':'PDF 텍스트 → 서식 기반 파싱'} / 대조: 명시적 규칙<br>OCR 판독 불가 항목은 원본 값으로 대체하지 않습니다.</p>`;
$$('[data-ref]').forEach(b=>b.onclick=()=>{const [i,j]=b.dataset.ref.split(',');const ref=r.checks[i].refs[j];if(ref.csv)csvView(ref.csv);else{showText=false;toggleText();viewDoc(ref.doc,ref.value);}});
$('#fields').innerHTML=`<p class="method-note">보정은 담당자의 수동 입력으로 기록됩니다. 판독 불가를 추정값으로 채우지 마세요. 보정하면 기존 초안과 저장 상태를 해제합니다.</p><div class="fields-grid">${fieldsSchema().map(([key,label,type])=>`<div class="field ${['shipment_ids','reason'].includes(key)?'wide':''}"><label for="f-${key}">${esc(label)}</label><input id="f-${key}" data-field="${key}" type="${type}" value="${esc(Array.isArray(record.fields[key])?record.fields[key].join(', '):record.fields[key]??'')}"><button class="field-ref" data-field-ref="${key}">원문 확인 ↗</button></div>`).join('')}</div><div class="actions"><button class="primary" id="correct">보정값으로 재검증</button><span>모든 변경 이력 기록</span></div>`;
$$('[data-field-ref]').forEach(b=>b.onclick=()=>{const key=b.dataset.fieldRef,id=fieldDoc(key);if(!record.documents[id])return notice('해당 증빙 문서가 제출되지 않았습니다.',true);showText=false;toggleText();viewDoc(id,record.fields[key]);});$('#correct').onclick=correct;
$('#draft').innerHTML=`<div class="result-banner"><div><span class="eyebrow">회신 작성</span><h2>담당자 회신 초안</h2><small>${esc(config.model)} · 승인·귀책 확정 금지</small></div></div><button class="primary" id="generate">${record.draft?'초안 다시 생성':'로컬 LLM 초안 생성'}</button><p class="method-note">${record.draft?`모델 실행 ${record.draft.seconds}초 · 담당자 검토 필요`:'검토 결과를 바탕으로 로컬 모델을 호출합니다.'}</p><div class="draft-label">고객 회신 · 담당자가 수정 후 사용</div><textarea id="drafttext" class="draft-box" placeholder="생성된 회신 초안이 표시됩니다.">${esc(record.edited_draft??record.draft?.text??'')}</textarea><div class="draft-label">담당자 검토 의견</div><textarea id="reviewnote" class="draft-box note-box" placeholder="검토 내용과 추가 확인 사항을 입력하세요.">${esc(record.review_note||'')}</textarea><div class="actions"><button id="save">검토 기록 저장</button><span>최종 승인·반려 기능 아님</span></div>${record.saved_at?`<p class="saved">저장 완료 · ${esc(record.saved_at)}</p>`:''}`;
$('#generate').onclick=generate;$('#save').onclick=save;if(record.draft)$('#step3').classList.add('active');else $('#step3').classList.remove('active');}
function toggleText(){$('#imageviewer').hidden=showText;$('#ocrtext').hidden=!showText;$('#texttoggle').textContent=showText?'문서 이미지':'추출 텍스트';}
async function work(message,fn){if(busy)return;busy=true;notice(message);$$('button,select,input,textarea').forEach(b=>b.disabled=true);try{await fn();}catch(e){notice(e.message,true);}finally{busy=false;$$('button,select,input,textarea').forEach(b=>b.disabled=false);}}
async function run(){await work($('#mode').value==='scan'?'스캔 이미지를 실제 OCR 처리 중입니다. 원본 텍스트로 대체하지 않습니다.':'PDF 문서 추출 및 거래·규정 대조 중입니다.',async()=>{record=await api('/api/review',{case_id:cid,mode:$('#mode').value});render();tab('checks');await viewDoc(currentDoc);notice(`검토 완료 · ${record.result.state} · 이번 실행 ${record.seconds}초`);});}
async function correct(){const fields={};for(const [key,,type]of fieldsSchema()){const val=$('#f-'+key).value.trim();fields[key]=key==='shipment_ids'?val.split(',').map(s=>s.trim()).filter(Boolean):type==='number'?(val===''?null:Number(val)):(val||null);}await work('수동 보정값으로 다시 검증 중입니다.',async()=>{record=await api('/api/correct',{id:record.id,fields});render();tab('checks');notice('재검증 완료 · 이전 초안은 해제했습니다.');});}
async function generate(){await work(`${config.model} 로컬 추론 중입니다. 첫 실행은 모델 로딩 시간이 포함됩니다.`,async()=>{record=await api('/api/draft',{id:record.id});render();tab('draft');notice(`로컬 초안 생성 완료 · ${record.draft.seconds}초 · 담당자 확인 후 사용하세요.`);});}
async function save(){const note=$('#reviewnote').value,draft=$('#drafttext').value;await work('검토 기록을 저장 중입니다.',async()=>{record=await api('/api/save',{id:record.id,note,draft});render();tab('draft');notice(config.public?'이 방문자 세션에 저장했습니다. 1시간 미사용 또는 서버 재시작 시 초기화됩니다. 승인 처리는 수행하지 않았습니다.':'검토 의견과 초안을 로컬에 저장했습니다. 승인 처리는 수행하지 않았습니다.');});}
$('#run').onclick=run;$('#mode').onchange=()=>{selectCase(cid);viewDoc(cid+'-REQ');};$('#texttoggle').onclick=()=>{showText=!showText;toggleText();};$('#closecsv').onclick=()=>$('#csvdialog').close();$$('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
(async()=>{
try{
  config=await api('/api/config');
  if(!config.cases.some(c=>c.id===cid))throw new Error('접수 건을 찾을 수 없습니다. 접수 목록에서 다시 선택하세요.');
  $('#system').textContent=`${config.network_blocked?'외부 통신 차단 확인':'외부 통신 차단 미확인'} · ${config.model_available?'로컬 모델 준비':'로컬 모델 미준비'}`;
  const previous=await api('/api/record?case_id='+encodeURIComponent(cid));
  if(previous)$('#mode').value=previous.mode;
  selectCase(cid);
  if(previous){record=previous;render();notice('이번 방문의 이전 검토 기록을 불러왔습니다.');}
  await viewDoc(cid+'-REQ');
  $('#run').disabled=false;
}catch(e){notice(e.message,true);$('#run').disabled=true;$('#mode').disabled=true;}
})();
