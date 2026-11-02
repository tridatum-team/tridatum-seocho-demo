# Seocho 업무 검토 AI 데모 v0.8

공개 업무정보를 참고해 만든 **합성 반품·클레임 문서**로 OCR, 거래·규정 대조, 근거 확인, 로컬 LLM 회신 초안을 시연합니다. 실제 HL홀딩스 내부자료·거래·서식·규정·승인 결과가 아닙니다.

## 구성

- `server.py`: 로컬 HTTP API, 공개 모드 프록시 인증 및 세션별 검토 기록
- `engine.py`: 텍스트 PDF·Tesseract OCR, 서식 기반 필드 추출, 명시적 규칙 검증
- `web/`: 접수 목록과 건별 상세 검토 화면
- `data/`: 실행용 합성 문서 27개, 거래 CSV, 문서·출처 목록
- `bundles/C01.zip`~`C06.zip`: 접수별 문서·규정·거래 자료 묶음
- `authoring/`: 합성 문서 생성·패키징 코드와 합성 원천 데이터
- `reference/`: 공개 참고 출처와 이용 범위. 기관 원문은 미포함
- `deploy/worker.mjs`: 운영 데모에서 사용하는 Cloudflare 중계 코드
- `test_engine.py`: 거래·규정 검증 회귀 테스트 7개

## macOS 로컬 실행

Python 3.12 이상, Ollama, Tesseract 및 한국어·영어 OCR 데이터가 필요합니다.

```sh
brew install ollama tesseract tesseract-lang
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

인터넷 연결이 가능한 준비 단계에서 모델을 내려받습니다. Ollama가 실행 중이 아니라면 별도 터미널에서 `ollama serve`를 실행한 뒤 아래 명령을 실행합니다.

```sh
ollama pull qwen2.5:7b
tesseract --list-langs
IR_MODEL=qwen2.5:7b python launch.py
```

브라우저에서 http://127.0.0.1:8789/ 에 접속합니다. 로컬 접속 코드는 없습니다. 종료는 실행 터미널에서 Control+C입니다.

- 런처: 웹 8789 / 자체 Ollama 서버 11441. 해당 포트는 비어 있어야 합니다.
- 기본 모델은 `gemma3:12b`입니다. 위 명령은 공개 데모와 같은 `qwen2.5:7b`를 명시적으로 선택합니다.
- 런처는 macOS `sandbox-exec`로 검토·추론 프로세스의 외부 통신을 차단하고 루프백 통신을 허용합니다. 모델 다운로드는 실행 전에 완료해야 합니다.
- `python server.py`만 실행하면 이 차단 정책은 적용되지 않습니다. 외부에 직접 노출하지 마세요.

## 시연

1. 접수 목록에서 C02를 선택하고 문서 묶음·원문을 확인합니다.
2. 스캔 OCR 모드에서 대조를 실행하면 요청 품번과 수령 라벨의 **근거 충돌**을 확인할 수 있습니다.
3. 로컬 LLM으로 회신 초안을 생성하고 담당자가 검토합니다.
4. C03 스캔은 일부 항목이 누락되어 자료 부족이 됩니다. 원문을 보고 출고번호 2건·요청 수량 8·단위 EA·사유를 보정하면 잔량 6·초과 2를 확인할 수 있습니다.
5. 목록 복귀 후 같은 건을 열면 같은 실행 세션의 최근 검토 결과가 복원됩니다.

원본 PDF 모드: C01 통과 / C02 근거 충돌 / C03 불일치 / C04 자료 부족 / C05 근거 충돌 / C06 자료 부족.

## 검증

```sh
python -m unittest -v test_engine
```

## 문서 재생성

이미 생성된 `data/`와 ZIP으로 실행할 수 있으므로 재생성은 선택 사항입니다. 재생성에는 `authoring/requirements.txt` 패키지와 생성기가 지정한 `/Library/Fonts/Arial Unicode.ttf`가 필요합니다. 서체는 사용자가 이용 권한을 갖춘 파일을 준비해야 하며 저장소에는 포함하지 않습니다.

서버를 종료한 뒤 실행합니다.

```sh
python -m pip install -r authoring/requirements.txt
cd authoring
python generate.py
python package.py
```

생성용 데이터와 평가 정답은 공개 웹 정적 경로로 배포하지 마세요. 실행 엔진은 생성기의 평가 정답을 읽지 않습니다.

## 공개 배포 코드

이 저장소는 운영 데모의 소스 공유본입니다. 기존 서비스나 계정을 자동으로 배포·변경하는 설정은 포함하지 않습니다.

`deploy/worker.mjs`는 운영 도메인에 결합된 원본 코드입니다. 다른 도메인에 배포하려면 Worker의 `HOST`·별칭 처리와 `server.py`의 `PUBLIC_ORIGIN`을 해당 도메인에 맞춰야 합니다. 자체 Wrangler 설정, 백엔드 HTTPS 연결, 정적 자산 바인딩 `ASSETS`, `ORIGIN_URL`, 필요 시 `DEMO_RATE_LIMIT`을 구성해야 합니다. `web/`가 웹 정적 자산의 원본입니다.

접속 코드는 Worker secret `DEMO_ACCESS_CODE`, 프록시 인증키는 `PROXY_SECRET`에 별도 설정합니다. 백엔드는 `IR_PUBLIC=1`, `IR_PROXY_SECRET_FILE`로 같은 프록시 키를 읽습니다. 실제 비밀값·터널 인증·서버 plist·계정별 Wrangler 설정은 포함하지 않습니다. 공유 영상 경로는 원본 Worker에 남아 있지만 영상 자산은 이 소스 저장소에 포함하지 않았습니다.

## 한계 및 공유 범위

- 정해진 합성 서식을 처리하는 시제품이며 범용 문서 업로드 서비스가 아닙니다.
- OCR·서식 파서·규칙 엔진이 추출과 대조를 수행합니다. LLM은 결과를 문장으로 정리하며 최종 승인·반려·자동 발송을 하지 않습니다.
- OCR 누락은 정답으로 자동 치환하지 않습니다. 담당자 확인·보정이 필요할 수 있습니다.
- 공개 HTTPS 시연은 물리적 폐쇄망과 다릅니다. 기업용 인증·권한·영구 감사 기록·내부망 설치는 별도 구축 범위입니다.
- 기관 공개 원문·개인정보·운영 로그·접속 코드·배포 비밀값·IR·영상은 제외했습니다.
- 별도의 오픈소스 라이선스는 지정하지 않았습니다. 공개 저장소 여부와 별개로 재사용 조건은 권리자와 확인해 주세요.
