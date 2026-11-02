const HOST='seocho.tridatum.co';
const GETS=new Set(['/api/config','/api/records','/api/record','/api/bundle','/api/document','/api/page','/api/text','/api/csv','/healthz']);
const POSTS=new Set(['/api/review','/api/correct','/api/draft','/api/save']);
const json=(obj,status=200)=>Response.json(obj,{status,headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}});
const enc=new TextEncoder();
async function signature(value,secret){const key=await crypto.subtle.importKey('raw',enc.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,enc.encode('secho-access:'+value)))).map(x=>x.toString(16).padStart(2,'0')).join('');}
async function valid(request,env){const raw=(request.headers.get('Cookie')||'').match(/(?:^|;\s*)secho_access=([^;]+)/)?.[1]||'';const [exp,sig]=raw.split('.');return Number(exp)>Date.now()&&sig===await signature(exp,env.PROXY_SECRET);}
const login=message=>new Response(`<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>트라이데이텀 IR 시연 v0.8</title><style>body{font:14px/1.7 -apple-system,sans-serif;background:white;color:#252525;margin:0}main{max-width:440px;margin:14vh auto;padding:30px 24px;border-top:2px solid #333}h1{font-size:23px;font-weight:600}p{color:#686868}label{display:block;margin:24px 0 8px}input{box-sizing:border-box;width:100%;padding:12px;border:1px solid #aaa;border-radius:2px}button{margin-top:16px;padding:12px;width:100%;background:#303030;color:white;border:0;border-radius:2px;cursor:pointer}small{display:block;margin-top:12px;font-weight:600}</style><main><b>TRIDATUM</b><h1>반품 · 교환 문서 검토</h1><p>IR 시연 v0.8 · 공개 업무정보 기반 합성 자료<br>실제 기업의 거래·내부 서식·규정이 아닙니다.<br>기존 시연 접속 코드를 입력해 주세요.</p><form method="post" action="/access"><label for="code">접속 코드</label><input id="code" name="code" type="password" required autocomplete="off"><button>접수 목록 열기</button><small>${message}</small></form></main></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}});
export default {async fetch(request,env){
 const u=new URL(request.url);
 if(u.hostname==='secho.tridatum.co'){u.hostname=HOST;u.protocol='https:';return Response.redirect(u.toString(),308);}
 if(u.hostname!==HOST)return json({error:'없는 사이트입니다.'},404);
 if(u.protocol!=='https:'){u.protocol='https:';return Response.redirect(u.toString(),308);}
 if(u.pathname==='/robots.txt')return new Response('User-agent: *\nDisallow: /');
 // Preserve the existing proposal/QR video URL; this is an intentionally shareable synthetic demo.
 if(u.pathname==='/watch/3915d2bb4ddfb7a7a90a1860')return env.ASSETS.fetch(new Request(new URL('/video',u),request));
 if(u.pathname==='/media/3915d2bb4ddfb7a7a90a1860.mp4')return env.ASSETS.fetch(request);
 if(u.pathname==='/access'&&request.method==='POST'){
  if(request.headers.get('Origin')!=='https://'+HOST)return json({error:'허용하지 않는 요청입니다.'},403);
  if(env.DEMO_RATE_LIMIT){const r=await env.DEMO_RATE_LIMIT.limit({key:'login:'+request.headers.get('CF-Connecting-IP')});if(!r.success)return login('잠시 뒤 다시 시도해 주세요.');}
  if(Number(request.headers.get('Content-Length'))>1024)return json({error:'입력 크기 제한'},413);
  const text=await request.text();if(enc.encode(text).length>1024)return json({error:'입력 크기 제한'},413);
  const form=new URLSearchParams(text);if(form.get('code')!==env.DEMO_ACCESS_CODE)return login('접속 코드를 확인해 주세요.');
  const exp=String(Date.now()+7*24*3600*1000);return new Response(null,{status:303,headers:{Location:'/', 'Set-Cookie':'secho_access='+exp+'.'+await signature(exp,env.PROXY_SECRET)+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=604800','Cache-Control':'no-store'}});
 }
 if(!await valid(request,env))return u.pathname.startsWith('/api/')||u.pathname==='/healthz'?json({error:'접속 코드 인증이 필요합니다.'},401):login('');
 if(!u.pathname.startsWith('/api/')&&u.pathname!=='/healthz'){
  const r=await env.ASSETS.fetch(request);const out=new Response(r.body,r);out.headers.set('X-Robots-Tag','noindex, nofollow');out.headers.set('Cache-Control','no-store');return out;
 }
 if(!(request.method==='GET'&&GETS.has(u.pathname))&&!(request.method==='POST'&&POSTS.has(u.pathname)))return json({error:'없는 기능입니다.'},404);
 if(request.method==='POST'&&request.headers.get('Origin')!=='https://'+HOST)return json({error:'허용하지 않는 요청입니다.'},403);
 if(env.DEMO_RATE_LIMIT){const r=await env.DEMO_RATE_LIMIT.limit({key:request.headers.get('CF-Connecting-IP')||'unknown'});if(!r.success)return json({error:'요청이 많습니다. 1분 뒤 다시 실행해 주세요.'},429);}
 try{
  if(!env.ORIGIN_URL||!env.PROXY_SECRET)throw Error('not ready');
  const headers=new Headers();for(const k of ['Content-Type','Cookie','Origin'])if(request.headers.has(k))headers.set(k,request.headers.get(k));headers.set('X-Secho-Proxy',env.PROXY_SECRET);
  if(Number(request.headers.get('Content-Length'))>32000)return json({error:'입력 크기 제한'},413);
  const body=request.method==='POST'?await request.arrayBuffer():undefined;
  if(body&&body.byteLength>32000)return json({error:'입력 크기 제한'},413);
  if(body)headers.set('Content-Length',String(body.byteLength));
  const r=await fetch(new URL(u.pathname+u.search,env.ORIGIN_URL),{method:request.method,headers,body,redirect:'manual',signal:AbortSignal.timeout(160000)});
  if(r.status>=500||r.status>=300&&r.status<400)throw Error('offline');
  const out=new Response(r.body,r);out.headers.set('Cache-Control','no-store');out.headers.set('X-Content-Type-Options','nosniff');return out;
 }catch(e){return json({error:'맥미니 처리 서버 연결 또는 실행에 실패했습니다. 잠시 뒤 다시 실행하세요. 운영자는 서버 상태를 확인해 주세요.'},503);}
}};
