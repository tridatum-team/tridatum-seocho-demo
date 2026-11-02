from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, os, socket, threading, uuid, mimetypes, time, urllib.request, secrets, hmac
from http.cookies import SimpleCookie
from urllib.parse import urlparse,parse_qs
import fitz
import engine
ROOT=Path(__file__).resolve().parent
MODEL=os.environ.get('IR_MODEL','gemma3:12b')
OLLAMA=os.environ.get('IR_OLLAMA','http://127.0.0.1:11441')
PORT=int(os.environ.get('IR_PORT','8789'))
PUBLIC=os.environ.get('IR_PUBLIC')=='1'
PUBLIC_ORIGIN='https://seocho.tridatum.co'
SECRET=Path(os.environ['IR_PROXY_SECRET_FILE']).read_text().strip() if PUBLIC else ''
if PUBLIC and not SECRET:raise RuntimeError('공개 중계 인증키가 필요합니다.')
LOCK=threading.Lock();RECORDS={};SESSIONS={};SESSION_LOCK=threading.Lock()
BUNDLES=json.loads((ROOT/'data/bundles.json').read_text())
SOURCES=json.loads((ROOT/'data/sources.json').read_text())
RUNTIME=ROOT/'runtime';RUNTIME.mkdir(exist_ok=True)

def network_blocked():
    try:
        with socket.create_connection(('1.1.1.1',443),timeout=1):return False
    except PermissionError:return True
    except OSError as e:return e.errno in (1,13)
BLOCKED=network_blocked()

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def output(self,data,status=200,content_type='application/json; charset=utf-8'):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if getattr(self,'new_session',None):
            self.send_header('Set-Cookie','ir_demo_session='+self.new_session+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=3600')
        self.end_headers();self.wfile.write(data)
    def host_ok(self):
        if PUBLIC:return hmac.compare_digest(self.headers.get('X-Secho-Proxy',''),SECRET)
        return self.headers.get('Host') in (f'127.0.0.1:{PORT}',f'localhost:{PORT}')
    def records(self):
        if not PUBLIC:return RECORDS
        jar=SimpleCookie()
        try:jar.load(self.headers.get('Cookie',''))
        except Exception:pass
        sid=jar['ir_demo_session'].value if 'ir_demo_session' in jar else ''
        now=time.monotonic()
        with SESSION_LOCK:
            for key in list(SESSIONS):
                if now-SESSIONS[key]['last']>3600:del SESSIONS[key]
            if sid not in SESSIONS:
                if len(SESSIONS)>=64:raise ValueError('동시 방문자 제한입니다. 잠시 후 다시 시도해 주세요.')
                sid=secrets.token_hex(24)
                SESSIONS[sid]={'last':now,'records':{}}
                self.new_session=sid
            SESSIONS[sid]['last']=now
            return SESSIONS[sid]['records']
    def do_GET(self):
        if not self.host_ok():return self.output({'error':'허용하지 않는 호스트'},403)
        try:
            parsed=urlparse(self.path);path=parsed.path;query=parse_qs(parsed.query)
            if path=='/healthz':
                with urllib.request.urlopen(OLLAMA+'/api/tags',timeout=3) as f:
                    available=any(x['name']==MODEL for x in json.load(f).get('models',[]))
                return self.output({'ok':available,'model':MODEL,'network_blocked':BLOCKED,'version':'ir-v0.8'},200 if available else 503)
            records=self.records()
            if path=='/api/config':
                available=False
                try:
                    with urllib.request.urlopen(OLLAMA+'/api/tags',timeout=2) as f:available=any(x['name']==MODEL for x in json.load(f).get('models',[]))
                except OSError:pass
                return self.output({'cases':[{'id':cid,'documents':sum(x['case_id']==cid for x in engine.MANIFEST)} for cid in engine.CASE_IDS],'documents':engine.MANIFEST,'bundles':BUNDLES,'sources':SOURCES,'model':MODEL,'model_available':available,'network_blocked':BLOCKED,'public':PUBLIC,'version':'ir-v0.8','ocr':'Tesseract kor+eng','extraction':'문서 서식 기반 추출','disclaimer':'공개 업무정보 기반 합성 문서 · 실제 HL 거래·서식·규정 아님'})
            if path=='/api/records':return self.output([{'id':r['id'],'case_id':r['case_id'],'state':r['result']['state'],'saved_at':r.get('saved_at'),'revision':r['revision']} for r in list(records.values())])
            if path=='/api/record':
                cid=query.get('case_id',[''])[0]
                if cid not in BUNDLES:raise ValueError('접수 건 확인')
                return self.output(next((r for r in reversed(list(records.values())) if r['case_id']==cid),None))
            if path=='/api/bundle':
                cid=query.get('case_id',[''])[0]
                if cid not in BUNDLES:raise ValueError('접수 묶음 확인')
                return self.output((ROOT/'bundles'/f'{cid}.zip').read_bytes(),content_type='application/zip')
            if path=='/api/document':
                docid=query.get('id',[''])[0];mode=query.get('mode',['clean'])[0]
                if docid not in engine.DOCS or mode not in ('clean','scan'):raise ValueError('문서 또는 모드 확인')
                meta=engine.DOCS[docid]
                return self.output((engine.DATA/meta[mode]).read_bytes(),content_type='application/pdf')
            if path=='/api/page':
                docid=query.get('id',[''])[0];mode=query.get('mode',['clean'])[0];page=int(query.get('page',['1'])[0])-1
                if docid not in engine.DOCS or mode not in ('clean','scan'):raise ValueError('문서 또는 모드 확인')
                with fitz.open(engine.DATA/engine.DOCS[docid][mode]) as pdf:
                    if not 0<=page<len(pdf):raise ValueError('페이지 확인')
                    img=pdf[page].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).tobytes('png')
                return self.output(img,content_type='image/png')
            if path=='/api/text':
                docid=query.get('id',[''])[0]
                if docid not in engine.DOCS:raise ValueError('문서 확인')
                return self.output(engine.extract(docid,'clean'))
            if path=='/api/csv':
                name=query.get('name',[''])[0]
                if name not in ('shipments.csv','completed_returns.csv','parts.csv'):raise ValueError('데이터 확인')
                return self.output(engine.load_csv(name))
            names={'/':'index.html','/review':'review.html','/review.html':'review.html','/inbox.js':'inbox.js','/app.js':'app.js','/style.css':'style.css'}
            if path in names:
                file=ROOT/'web'/names[path]
                return self.output(file.read_bytes(),content_type=(mimetypes.guess_type(file)[0] or 'text/plain')+'; charset=utf-8')
            return self.output({'error':'경로 없음'},404)
        except (ValueError,KeyError) as e:return self.output({'error':str(e)},400)
        except Exception as e:return self.output({'error':str(e)},500)
    def do_POST(self):
        origins=(PUBLIC_ORIGIN,) if PUBLIC else (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}')
        if not self.host_ok() or self.headers.get('Origin') not in origins:
            return self.output({'error':'허용하지 않는 요청 출처'},403)
        if not LOCK.acquire(blocking=False):return self.output({'error':'다른 문서 처리 중입니다. 완료 후 실행하세요.'},409)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=32000:raise ValueError('요청 크기 확인')
            data=json.loads(self.rfile.read(n))
            records=self.records()
            if self.path=='/api/review':
                cid=data.get('case_id');mode=data.get('mode')
                if cid not in engine.CASE_IDS or mode not in ('clean','scan'):raise ValueError('사례와 모드 확인')
                record=engine.review(cid,mode);record['id']=uuid.uuid4().hex
                if len(records)>=24:records.pop(next(iter(records)))
                records[record['id']]=record
                return self.output(record)
            record=records.get(data.get('id'))
            if not record:raise ValueError('먼저 문서 검토를 실행하세요.')
            if self.path=='/api/correct':
                allowed={'customer','shipment_ids','part','quantity','unit','request_date','reason','label_part','received_quantity','vendor_quantity'}
                changes=data.get('fields',{})
                if not isinstance(changes,dict) or set(changes)-allowed:raise ValueError('보정 항목 확인')
                fields=dict(record['fields']);fields.update(changes)
                for key in ['quantity','received_quantity','vendor_quantity']:
                    v=fields.get(key)
                    if v is not None and (type(v) is not int or v<0 or v>100000):raise ValueError('수량은 0 이상 정수 또는 미상값이어야 합니다.')
                for key in ['customer','part','unit','request_date','reason','label_part']:
                    v=fields.get(key)
                    if v is not None and (not isinstance(v,str) or len(v)>1000):raise ValueError('문자열 필드 확인')
                if not isinstance(fields.get('shipment_ids'),list) or any(not isinstance(s,str) or len(s)>100 for s in fields['shipment_ids']):raise ValueError('출고번호 목록 확인')
                result=engine.evaluate(record['case_id'],fields,record['documents'])
                record.setdefault('corrections',[]).append({'before':dict(record['fields']),'after':fields,'at':time.strftime('%Y-%m-%dT%H:%M:%S')})
                record.update(fields=fields,result=result,revision=record['revision']+1,draft=None,approved=False)
                record.pop('saved_at',None);record.pop('review_note',None);record.pop('edited_draft',None)
                return self.output(record)
            if self.path=='/api/draft':
                record['draft']=engine.draft(record,MODEL,OLLAMA)
                record.pop('edited_draft',None);record.pop('saved_at',None)
                return self.output(record)
            if self.path=='/api/save':
                note=str(data.get('note','')).strip()
                if not note or len(note)>4000:raise ValueError('검토 의견을 1~4000자로 입력하세요.')
                record['review_note']=note;record['saved_at']=time.strftime('%Y-%m-%dT%H:%M:%S')
                record['edited_draft']=str(data.get('draft',''))[:6000]
                if not PUBLIC:
                    (RUNTIME/(record['id']+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2))
                return self.output(record)
            return self.output({'error':'경로 없음'},404)
        except (ValueError,KeyError) as e:return self.output({'error':str(e)},400)
        except Exception as e:return self.output({'error':str(e)},500)
        finally:LOCK.release()

if __name__=='__main__':
    print(f'IR demo ready http://127.0.0.1:{PORT} | network_blocked={BLOCKED}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
