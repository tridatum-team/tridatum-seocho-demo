from pathlib import Path
import subprocess,os,sys,time,shutil,socket,urllib.request,signal
ROOT=Path(__file__).resolve().parent
ports=[8789,11441]
for port in ports:
    with socket.socket() as s:
        if s.connect_ex(('127.0.0.1',port))==0:sys.exit(f'{port} 사용 중. 기존 IR 데모를 종료하거나 현재 실행 화면을 이용하세요.')
ollama=shutil.which('ollama')
if not ollama or not shutil.which('tesseract'):sys.exit('Ollama와 Tesseract 설치가 필요합니다.')
if not Path('/usr/bin/sandbox-exec').exists():sys.exit('이 런처는 macOS sandbox-exec가 필요합니다. 폐쇄망 제한 없이 자동 실행하지 않습니다.')
(ROOT/'runtime').mkdir(exist_ok=True)
processes=[]
signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
try:
    env=dict(os.environ,OLLAMA_HOST='127.0.0.1:11441',OLLAMA_NO_CLOUD='1')
    with (ROOT/'runtime/ollama.log').open('a') as log:
        processes.append(subprocess.Popen(['/usr/bin/sandbox-exec','-f',str(ROOT/'offline.sb'),ollama,'serve'],env=env,stdout=log,stderr=log))
        for _ in range(60):
            if processes[0].poll() is not None:raise RuntimeError('모델 서버 종료. runtime/ollama.log 확인')
            try:
                urllib.request.urlopen('http://127.0.0.1:11441/api/tags',timeout=1);break
            except OSError:time.sleep(.5)
        else:raise RuntimeError('로컬 모델 서버 시작 실패')
        processes.append(subprocess.Popen(['/usr/bin/sandbox-exec','-f',str(ROOT/'offline.sb'),sys.executable,str(ROOT/'server.py')],cwd=ROOT))
        print('IR DEMO v0.8: http://127.0.0.1:8789/ | 종료 Control+C',flush=True)
        while all(p.poll() is None for p in processes):time.sleep(1)
except KeyboardInterrupt:pass
finally:
    for p in reversed(processes):
        if p.poll() is None:p.terminate()
    for p in processes:
        try:p.wait(timeout=8)
        except subprocess.TimeoutExpired:p.kill()
