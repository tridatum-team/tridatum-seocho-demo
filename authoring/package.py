"""Publish generated inputs and self-contained case bundles; never publish answer keys."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / 'data'
BUNDLES = ROOT / 'bundles'
manifest = json.loads((HERE / 'manifest.json').read_text())
sources = json.loads((ROOT / 'reference/sources.json').read_text())
BUNDLES.mkdir(exist_ok=True)
for folder in ('inputs', 'editable'):
    shutil.copytree(HERE / folder, DATA / folder, dirs_exist_ok=True)
shutil.copy2(HERE / 'manifest.json', DATA / 'manifest.json')
shutil.copy2(ROOT / 'reference/sources.json', DATA / 'sources.json')

TITLES = {
    'C01': ('미사용 필터 반품', '출고일에 맞는 규정 버전과 고객 요청·검수·매입처 의견을 대조합니다.'),
    'C02': ('전륜 패드 교환 요청', '요청서와 실제 제출된 라벨의 품번을 비교합니다. 품번 차이만으로 귀책을 확정하지 않습니다.'),
    'C03': ('분할 출고 재고 반품', '두 차례 납품과 이미 완료된 반품을 구분하여 이번 반품 요청량을 검토합니다.'),
    'C04': ('와이퍼 파손 접수', '고객의 파손 주장과 실제 제출된 사진·검수 기록의 존재를 구분합니다.'),
    'C05': ('점화 플러그 대체 요청', '고객 요청량·회수 검수량·매입처 인정 의견을 각각 대조합니다.'),
    'C06': ('패드 라벨 식별 요청', '라벨에서 판독할 수 없는 부분을 주문 품번으로 채우지 않고 원문을 확인합니다.'),
}


def role(docid):
    suffix = docid.split('-', 1)[1]
    if suffix.startswith('INV'):
        return ('거래 근거', '출고번호·품목·금액·분할 납품 이력. 자동 잔량 계산은 별도 거래 CSV를 사용합니다.', ['SJFMC-2017'])
    return {
        'REQ': ('고객 요청', '거래처·접수일·출고번호·품번·수량·단위·사유 추출', []),
        'PRE': ('기처리 이력', '이전 반품 완료 근거. 자동 계산은 completed_returns.csv와 연결', []),
        'LBL': ('제품 식별', '수령 품번 판독 및 요청 품번과 대조. 합성 라벨이며 제품 실사 아님', []),
        'INS': ('회수 검수', '회수 수량 추출. 날짜·장소·검사/검수 담당·관찰 내용은 담당자 열람', ['KIIT-2019']),
        'VND': ('매입처 의견', '인정 의견 수량 추출 및 고객 요청량과 비교. 확정 승인 아님', []),
    }[suffix]


def csv_rows(name):
    with (DATA / 'inputs/master' / name).open(encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


index = {}
for cid, (title, purpose) in TITLES.items():
    folder = BUNDLES / cid
    folder.mkdir(exist_ok=True)
    docs = [d for d in manifest if d['case_id'] == cid]
    policies = [d for d in manifest if d['case_id'] is None]
    items = []
    for d in docs:
        category, use, refs = role(d['id'])
        items.append({'id': d['id'], 'title': d['title'], 'role': category, 'use': use, 'sources': refs})
    for d in docs + policies:
        for relative in (d['clean'], d['scan'], d['editable'], *d['images']):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DATA / relative, target)
    master = folder / 'inputs/master'
    master.mkdir(exist_ok=True)
    fields, rows = csv_rows('shipments.csv')
    shipments = [r for r in rows if r['order_id'] == 'SYN-PO-' + cid]
    shipids = {r['shipment_id'] for r in shipments}
    write_csv(master / 'shipments.csv', fields, shipments)
    fields, rows = csv_rows('completed_returns.csv')
    write_csv(master / 'completed_returns.csv', fields, [r for r in rows if r['shipment_id'] in shipids])
    shutil.copy2(DATA / 'inputs/master/parts.csv', master / 'parts.csv')
    (folder / 'manifest.json').write_text(json.dumps(docs + policies, ensure_ascii=False, indent=2))
    (folder / 'sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=2))
    missing = []
    if cid == 'C04':
        missing = ['파손 부위 사진', '포장 상태 사진', '회수·검수 기록']
    info = {'case_id': cid, 'title': title, 'customer': shipments[0]['customer'], 'purpose': purpose, 'documents': items, 'policies': [d['id'] for d in policies], 'missing_submission': missing}
    index[cid] = info
    rows = [{'문서번호': i['id'], '문서명': i['title'], '업무역할': i['role'], '검토범위': i['use'], '참고출처': ', '.join(i['sources'])} for i in items]
    write_csv(folder / '00_문서목록.csv', list(rows[0]), rows)
    listing = '\n'.join(f"- {i['id']}: {i['title']} — {i['use']}" for i in items)
    links = '\n'.join(f"- {s['title']}: {s['url']}\n  반영: {s['applied']}\n  제외: {s['not_imported']}" for s in sources)
    (folder / '00_묶음안내.md').write_text(f'''# {cid} · {title}

{purpose}

## 입력 구성

{listing}

- inputs/clean/: 합성 원본 PDF
- inputs/scanned/: 같은 문서의 이미지형 PDF 및 실제 OCR 입력 PNG
- inputs/master/: 이 접수 건으로 범위를 제한한 출고/기처리 원장, 합성 품목표
- SYN-R1 / SYN-R2: 두 시점의 가상 반품 규정. 실제 기업/기관 규정 아님
- editable/: 문서 작성 HTML. 편집하면 PDF·스캔을 재생성해야 하며 데모에 자동 업로드되지는 않음
- manifest.json: 묶음 파일 목록. 정답/기대 결과는 포함하지 않음

## 시연 순서

1. 접수 목록에서 {cid} 클릭 → 별도 상세 페이지의 '접수 파일 묶음'에서 문서와 용도 확인.
2. 원본 PDF 또는 스캔 PDF 모드 선택 → '문서 추출 · 대조 실행'.
3. 검토표의 근거 링크로 원문 위치/거래 CSV 확인. 거래명세서는 원문 열람용이며 잔량 계산 근거는 CSV임.
4. OCR 누락은 원문을 보고 '추출값 · 보정'에서 수동 수정. 수정 이력과 초안 무효화 확인.
5. 로컬 모델로 회신 작성 → 담당자 검토 의견 저장. 자동 승인/발송은 수행하지 않음.

## 자료의 성격

모든 접수·거래처·수량·가격·품번·식별표·규정은 합성입니다. 실제 HL 또는 참고기관 업무 데이터가 아닙니다.
공개 서식은 구조 참고에만 사용했습니다. 기관 원문/개인정보/사업자번호/직인/실제 거래는 이 ZIP에 없습니다.
미제출 자료: {', '.join(missing) if missing else '별도 지정 없음. 제출 파일 존재만으로 내용의 진실성이나 완전성을 보장하지 않음.'}
수량/기한/품번 등의 명시된 대조만 수행하며 원문의 모든 항목을 자동 이해·검증하는 범용 시스템은 아닙니다.
전회 납품량은 기처리 반품량과 다른 값입니다. 공공기관의 검사 기한을 가상 반품 기한의 근거로 사용하지 않습니다.

## 공개 참고 출처

{links}

원문 이용 라이선스는 확인되지 않았습니다. 원문은 별도 로컬 조사 폴더에만 보관합니다.
''')
    archive = BUNDLES / f'{cid}.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.rglob('*')):
            if path.is_file():
                z.write(path, str(Path(cid) / path.relative_to(folder)))
    info['zip_bytes'] = archive.stat().st_size
    info['zip_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()

(DATA / 'bundles.json').write_text(json.dumps(index, ensure_ascii=False, indent=2))
print(json.dumps({'bundles': len(index), 'documents': len(manifest), 'zip_bytes': sum(x['zip_bytes'] for x in index.values())}, ensure_ascii=False))
