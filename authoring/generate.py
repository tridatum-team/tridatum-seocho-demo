"""Rebuild this synthetic evidence pack. Requires reportlab, Pillow, PyMuPDF."""
from pathlib import Path
import csv, json, html, random, hashlib
from datetime import date, timedelta
from xml.sax.saxutils import escape
import fitz
from PIL import Image, ImageFilter, ImageDraw
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT/'source_data.json').read_text())
NOTICE = DATA['notice']
FONT = '/Library/Fonts/Arial Unicode.ttf'
pdfmetrics.registerFont(TTFont('KR', FONT))
STYLE = ParagraphStyle('body', fontName='KR', fontSize=9, leading=15, wordWrap='CJK')
TITLE = ParagraphStyle('title', parent=STYLE, fontSize=20, leading=28, spaceAfter=16)
SMALL = ParagraphStyle('small', parent=STYLE, fontSize=7, leading=11)
PARTS = {p['id']:p for p in DATA['parts']}
MANIFEST, GOLD, SHIPS, RETURNS, TOTALS = [], [], [], [], []
for folder in ['inputs/clean','inputs/scanned','inputs/master','editable','evaluation']:
    (ROOT/folder).mkdir(parents=True, exist_ok=True)

def para(text, style=STYLE):
    return Paragraph(escape(str(text)).replace('\n','<br/>'),style)

def csvfile(name, rows):
    with (ROOT/'inputs/master'/name).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def document(docid, title, sections, case=None, label=False):
    """Each section is (heading, paragraphs, table rows). Inputs contain no answer annotations."""
    pdfpath=ROOT/'inputs/clean'/f'{docid}.pdf'
    story=[para(DATA['supplier'],SMALL),Spacer(1,12),para(title,TITLE),para(f'문서번호: {docid}',SMALL),Spacer(1,12)]
    chunks=[f'<h1>{html.escape(title)}</h1><p>문서번호: {docid}</p>']
    for heading, texts, rows in sections:
        story += [Spacer(1,10),para(heading),Spacer(1,5)]
        chunks.append('<h2>'+html.escape(heading)+'</h2>')
        for text in texts:
            story += [para(text),Spacer(1,7)]
            chunks.append('<p>'+html.escape(text).replace('\n','<br>')+'</p>')
        if rows:
            widths=[(A4[0]-80)/len(rows[0])]*len(rows[0])
            table=Table([[para(cell,SMALL) for cell in row] for row in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f1f1f1')),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#aaaaaa')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
            story.append(table)
            chunks.append('<table>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</table>')
    if label:
        # The missing character is not embedded behind the visible redaction.
        label_text = case['label'].replace('?', '■')
        story += [Spacer(1,22),para('LABEL / 제품 식별표',TITLE),para('표시 품번: '+label_text,TITLE),para('LOT: SYN-2610 / 합성 식별표 — 실물 제품 사진 아님')]
        if '?' in case['label']:
            story.append(para('검은 영역: 원문 훼손으로 식별 불가. 재촬영 필요.'))
        chunks.append('<h2>LABEL / 제품 식별표</h2><p>표시 품번: '+html.escape(label_text)+'</p>')
    def footer(canvas, doc):
        canvas.setFont('KR',7);canvas.setFillColor(colors.HexColor('#555555'))
        canvas.drawString(40,29,NOTICE);canvas.drawRightString(A4[0]-40,29,str(doc.page))
    SimpleDocTemplate(str(pdfpath),pagesize=A4,rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=52).build(story,onFirstPage=footer,onLaterPages=footer)
    htmlpath=ROOT/'editable'/f'{docid}.html'
    htmlpath.write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>body{font:15px/1.7 sans-serif;max-width:900px;margin:40px auto}td{border:1px solid #bbb;padding:8px}table{border-collapse:collapse;width:100%}footer{margin-top:30px}</style>'+''.join(chunks)+'<footer>'+NOTICE+'</footer></html>')
    source=fitz.open(pdfpath); scanpdf=fitz.open(); images=[]
    rng=random.Random(docid)
    for n,page in enumerate(source):
        pix=page.get_pixmap(matrix=fitz.Matrix(1.65,1.65),alpha=False)
        im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples).convert('L')
        im=im.rotate(rng.uniform(-0.65,0.65),resample=Image.Resampling.BICUBIC,expand=False,fillcolor=255)
        im=im.filter(ImageFilter.GaussianBlur(0.35))
        draw=ImageDraw.Draw(im)
        for _ in range(1800):
            x,y=rng.randrange(im.width),rng.randrange(im.height)
            draw.point((x,y),fill=rng.randrange(170,245))
        imgpath=ROOT/'inputs/scanned'/f'{docid}_p{n+1:02}.png';im.save(imgpath)
        outpage=scanpdf.new_page(width=page.rect.width,height=page.rect.height)
        outpage.insert_image(outpage.rect,filename=str(imgpath))
        images.append(str(imgpath.relative_to(ROOT)))
    scanpath=ROOT/'inputs/scanned'/f'{docid}.pdf';scanpdf.save(scanpath);scanpdf.close()
    record={'id':docid,'case_id':case['id'] if case else None,'title':title,'clean':str(pdfpath.relative_to(ROOT)),'scan':str(scanpath.relative_to(ROOT)),'pages':len(source),'images':images,'editable':str(htmlpath.relative_to(ROOT))}
    source.close();MANIFEST.append(record)
    return docid

# Policy text is deliberately synthetic, not attributed to HL.
for p in DATA['policies']:
    document(p['id'],'데모 반품·클레임 처리 기준',[
        ('문서 관리',[f"규정번호 {p['id']} / 시행 {p['from']} / 적용 출고일 {p['from']} ~ {p['to']}",'본 기준은 시연을 위해 작성한 가상 규정입니다. 실제 기업의 계약·보증 조건이 아닙니다.'],[]),
        ('제1조 적용 및 기한',[f"원거래 출고일에 유효한 규정을 선택한다. 출고 다음 날을 1일로 계산하며 접수일과 출고일의 날짜 차이가 {p['days']}일 이하이면 기한 검사를 통과한다. 경계일을 포함한다. 분할 출고는 출고 건별로 계산한다."],[]),
        ('제2조 수량',['동일 원거래·품번·단위별 출고 수량에서 접수일 이전에 완료된 반품 수량을 차감한다. 처리 중 요청은 완료 반품으로 중복 차감하지 않는다. 회수 수량과 요청 수량은 별개로 대조한다.'],[]),
        ('제3조 증빙',['공통: 거래명세서 또는 원거래 연결자료. 파손 주장: 파손 부위 사진 및 포장 상태 사진. 오출고·식별 확인: 수령 제품 라벨. 제품 이상 주장: 반품 입고 검수 기록 및 매입처 판정 회신. 미사용 재고: 미사용·포장 상태 확인 기록. 제출 언급만으로 파일이 존재한다고 간주하지 않는다.'],[]),
        ('제4조 불확실·충돌',['가려진 품번을 주문·출고 품번으로 추정해 채우지 않는다. 고객 주장, 검수 관찰, 매입처 판정을 구분한다. 서로 다른 인정 수량이나 식별값은 근거 충돌로 표시한다.'],[]),
        ('제5조 결정 권한',['통과·불일치·자료 부족·근거 충돌은 검토 상태다. 상태 우선순위는 근거 충돌, 자료 부족, 불일치, 통과 순이며 개별 검사 결과는 함께 보존한다. 모든 건의 최종 승인·반려·대체·변제는 담당자가 확정한다. 자동 보상 및 원인·책임 단정은 금지한다.'],[])
    ])

for c in DATA['cases']:
    cid=c['id'];part=PARTS[c['part']];shipids=[];invoiceids=[]
    for idx,qty in enumerate(c['shipments'],1):
        sid=f'SYN-OUT-{cid}-{idx:02}';shipids.append(sid)
        day=(date.fromisoformat(c['ship_date'])+timedelta(days=idx-1)).isoformat()
        lineitems=[(part,qty)]+[(p,2+(j%3)) for j,p in enumerate(DATA['parts']) if p['id']!=part['id'] and not (part['id']=='SYN-BP-410A' and p['id']=='SYN-BP-410B')]
        rows=[['품번 / 품명','수량 / 단위','단가(원)','공급가액(원)']]
        subtotal=0
        for pp,q in lineitems:
            amount=pp['price']*q;subtotal+=amount
            rows.append([pp['id']+'\n'+pp['name'],f"{q} {pp['unit']}",f"{pp['price']:,}",f'{amount:,}'])
            SHIPS.append({'shipment_id':sid,'order_id':f'SYN-PO-{cid}','date':day,'customer':c['customer'],'part':pp['id'],'qty':q,'unit':pp['unit'],'unit_price':pp['price'],'amount':amount})
        vat=subtotal//10
        inv=document(f'{cid}-INV-{idx:02}','거래명세서',[
            ('거래 정보',[f"공급자: {DATA['supplier']}\n공급받는 자: {c['customer']}\n주문번호: SYN-PO-{cid}\n출고번호: {sid}\n출고일: {day}"],rows),
            ('금액 및 인수',[f'공급가액 {subtotal:,}원 / 부가세 {vat:,}원 / 합계 {subtotal+vat:,}원','금액은 합성 단가를 적용한 원화 금액입니다. 사업자등록번호·실제 계좌는 기재하지 않습니다.\n창고 확인: 데모 출고담당 / 인수 확인: 데모 고객담당'],[]),
            ('요청 품목 납품 이력',[f"대상 품번: {c['part']} / 주문번호: SYN-PO-{cid}\n전회 납품량은 반품 수량이 아닙니다. 반품 완료 이력은 별도 원장으로 관리합니다."],[['주문 총량','전회 납품량','금회 납품량','미납품량','단위'],[sum(c['shipments']),sum(c['shipments'][:idx-1]),qty,sum(c['shipments'][idx:]),part['unit']]]),
            ('서식 참고',['세종시시설관리공단 계약 업무 처리 지침(2017), 검수 내역서의 분할 납품 항목 구조 참고. 공단의 실제 거래가 아닌 독자 작성 합성 문서입니다.'],[])
        ],c)
        invoiceids.append(inv);TOTALS.append({'document':inv,'subtotal':subtotal,'vat':vat,'total':subtotal+vat})
    if c['returned']:
        RETURNS.append({'return_id':f'SYN-RET-{cid}-PRE','shipment_id':shipids[0],'part':c['part'],'qty':c['returned'],'unit':part['unit'],'completed_date':'2026-10-14','status':'완료'})
        document(f'{cid}-PRE','기처리 반품 완료 내역',[('완료 기록',[f"반품번호 SYN-RET-{cid}-PRE / 원출고 {shipids[0]}\n완료일 2026-10-14\n품번 {c['part']} / 완료 수량 {c['returned']} {part['unit']}\n이번 요청과 별개로 이미 반품 완료되어 출고 잔량에서 차감합니다."],[])],c)
    attachments=list(invoiceids)
    if c['returned']:
        attachments.append(f'{cid}-PRE')
    if c['label']:
        attachments.append(document(f'{cid}-LBL','수령 제품 라벨 기록',[('기록 정보',[f"관련 주문 SYN-PO-{cid}\n기록일 {c['date']}\n제출자: {c['customer']}\n수령 제품의 식별 표시를 옮긴 합성 라벨입니다."],[])],c,label=True))
    if c['received'] is not None:
        condition='포장 미개봉·미사용 상태 확인' if cid in ('C01','C03') else '외관 및 수량만 확인. 기능 불량과 귀책은 본 기록으로 확정하지 않음.'
        attachments.append(document(f'{cid}-INS','반품 입고·검수 기록',[
            ('접수 정보',[f"접수번호 SYN-CLM-{cid} / 주문번호 SYN-PO-{cid}\n회수처: {c['customer']}\n반품 입고일 {c['date']} / 검사일 {c['date']} / 검수일 {c['date']}\n검수 장소: 데모 물류센터 반품검수구역 / 실재 주소 아님"],[]),
            ('계수 및 관찰',[],[['요청 품번','요청량','회수 확인량','단위'],[c['part'],c['qty'],c['received'],part['unit']]]),
            ('상태 및 범위',[],[['확인 항목','관찰 기록','판정 범위'],['포장·사용 상태',condition,'외관 관찰'],['기능 시험','미실시','불량 원인 확정 불가'],['제품 식별','별첨 라벨 기록 대조' if c['label'] else '요청 품번으로 접수, 실물 식별 별도 확인','주문 품번으로 실물 확정 금지']]),
            ('검수 의견',['입고 검수는 회수 상태 기록이며 반품 승인·변제 확정이 아닙니다.'],[]),
            ('확인 담당',[f"검사자: 데모 품질담당 / 검수자: 데모 창고담당 / 접수 담당: 데모 고객지원\n모두 가상 역할이며 서명·직인·승인 기록을 위조하지 않습니다."],[]),
            ('서식 참고',['강원종합기술연구원 공개 물품납품확인서 및 검사·검수조서의 날짜·품목·담당 구분 참고. 기관 원문의 개인정보·사업자번호·규정은 전재하지 않았습니다.'],[])
        ],c))
    if c['vendor_qty'] is not None:
        attachments.append(document(f'{cid}-VND','매입처 검토 회신',[
            ('회신 정보',[f"발신: 데모 부품공급 (가상) <supplier@example.com>\n수신: claims@example.com\n회신일 {c['date']} / 참조 SYN-CLM-{cid}"],[]),
            ('검토 수량',[],[['검토 품번','고객 요청','매입처 인정 의견','단위'],[c['part'],c['qty'],c['vendor_qty'],part['unit']]]),
            ('의견',['미사용 포장 확인 기록 기준으로 요청 수량에 이견 없습니다. 최종 처리는 담당자 확인이 필요합니다.' if cid=='C01' else '회수 4개 중 2개만 대체 검토 대상으로 인정합니다. 나머지 2개는 원인 확인자료가 더 필요합니다. 고객의 전량 요청과 합의되지 않았으며 귀책을 확정하지 않습니다.'],[])
        ],c))
    request=document(f'{cid}-REQ','고객 클레임 접수 메일',[
        ('메일 헤더',[f"보낸 사람: {c['customer']} <service@example.com>\n받는 사람: claims@example.com\n접수일: {c['date']}\n제목: [SYN-PO-{cid}] {part['name']} 확인 요청"],[]),
        ('고객 요청',[c['body']],[]),
        ('대조용 접수 정보',[],[['참조 출고','주문 품번','요청 수량','사유'],[', '.join(shipids),c['part'],f"{c['qty']} {part['unit']}",c['reason']]]),
        ('제출 파일 목록',[', '.join(x+'.pdf' for x in attachments),'사진 미제출. 회수·검수 미진행.' if cid=='C04' else '위 목록은 본 접수에 포함된 파일 목록입니다.'],[])
    ],c)
    policy=next(p for p in DATA['policies'] if p['from']<=c['ship_date']<=p['to'])
    remaining=sum(c['shipments'])-c['returned']
    outcomes={'C01':'통과','C02':'근거 충돌','C03':'불일치','C04':'자료 부족','C05':'근거 충돌','C06':'자료 부족'}
    issue={'C01':'규정 R1: 출고 9/30, 접수 10/20, 20일 <= 30일. 담당자 최종 확인 필요.',
           'C02':'명세서 SYN-BP-410A와 라벨 SYN-BP-410B가 다름. 오출고 원인·귀책 단정 금지.',
           'C03':'출고 6+4, 완료 반품 4, 잔여 6. 요청 8은 2 초과. 회수 6과 요청 8도 불일치.',
           'C04':'파손 부위·포장 사진 미제출. 고객 파손 주장을 사실로 확정하지 말 것.',
           'C05':'고객 요청 4, 회수 4, 매입처 인정 의견 2. 차이 2에 대한 담당자 검토 필요.',
           'C06':'라벨 끝자리 미상. 주문 품번으로 실물 품번을 채우지 말고 재촬영 요청.'}
    fields=[{'field':'customer','expected':c['customer'],'document':request,'page':1},
            {'field':'requested_part','expected':c['part'],'document':request,'page':1},
            {'field':'quantity','expected':c['qty'],'document':request,'page':1},
            {'field':'unit','expected':part['unit'],'document':request,'page':1},
            {'field':'request_date','expected':c['date'],'document':request,'page':1}]
    if c['label']:
        fields.append({'field':'received_label_part','expected':None if cid=='C06' else c['label'],'document':cid+'-LBL','page':1,'must_abstain':cid=='C06'})
    GOLD.append({'id':cid,'scenario':c['kind'],'expected_state':outcomes[cid],'policy':policy['id'],'remaining':remaining,'excess':max(0,c['qty']-remaining),'fields':fields,'field_denominator':len(fields),'checks_explanation':issue[cid],'references':[request]+attachments+[policy['id']],'approval':'담당자 최종 결정 필수','auto_approve':False})

csvfile('parts.csv',DATA['parts']);csvfile('shipments.csv',SHIPS);csvfile('completed_returns.csv',RETURNS)
(ROOT/'evaluation/expected.json').write_text(json.dumps({'version':1,'field_denominator':sum(g['field_denominator'] for g in GOLD),'cases':GOLD,'invoice_totals':TOTALS},ensure_ascii=False,indent=2))
(ROOT/'manifest.json').write_text(json.dumps(MANIFEST,ensure_ascii=False,indent=2))
merged=fitz.open()
for item in MANIFEST:
    with fitz.open(ROOT/item['clean']) as pdf:merged.insert_pdf(pdf)
merged.save(ROOT/'전체문서_검토용.pdf');merged.close()
links=[]
for item in MANIFEST:
    links.append(f"<tr><td>{item['id']}</td><td>{html.escape(item['title'])}</td><td><a href='{item['clean']}'>원본 PDF</a> · <a href='{item['scan']}'>스캔 PDF</a> · <a href='{item['editable']}'>편집 원본</a></td></tr>")
(ROOT/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>v0.8 합성 문서 작성본</title><style>body{font:15px/1.7 sans-serif;max-width:1050px;margin:35px auto}td{padding:9px;border-bottom:1px solid #ccc}a{margin-right:10px}</style><h1>v0.8 합성 문서 작성본</h1><p>'+NOTICE+'</p><p>6개 사건 · 기관 공개 서식의 항목 구조를 참고한 독자 작성 문서. 거래처·품번·금액·반품 규정은 모두 가상입니다.</p><p><a href="전체문서_검토용.pdf">전체 문서 합본</a><a href="../reference/출처와_이용범위.md">출처와 이용범위</a></p><table>'+''.join(links)+'</table></html>')
print(json.dumps({'documents':len(MANIFEST),'pages':sum(x['pages'] for x in MANIFEST),'cases':len(GOLD),'field_denominator':sum(g['field_denominator'] for g in GOLD)},ensure_ascii=False))
