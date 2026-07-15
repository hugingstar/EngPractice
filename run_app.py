import os
import sys
import subprocess
import webbrowser
import time

def kill_port(port):
    print(f"🔄 {port}번 포트를 점유 중인 기존 서버를 강제 종료합니다...")
    try:
        subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        time.sleep(1) # 포트가 닫힐 시간을 잠시 대기
    except Exception:
        pass

def main():
    print("🚀 Language Learner Pro 원클릭 자동 실행기")
    print("================================================")
    
    # 1. 포트 충돌 방지: 8000 포트 정리
    kill_port(8000)
    
    # 2. LanguageLearner 디렉토리로 안전하게 이동
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(base_dir, "LanguageLearner")
    
    if not os.path.exists(target_dir):
        print(f"❌ 오류: '{target_dir}' 폴더를 찾을 수 없습니다.")
        sys.exit(1)
        
    os.chdir(target_dir)
    print("✅ 올바른 작업 폴더로 이동 완료.")
    
    # 3. 백엔드 전용 서버(server.py) 실행
    print("✅ 자막 전용 웹 서버(server.py)를 구동합니다...")
    server_process = subprocess.Popen([sys.executable, "server.py"])
    
    # 서버가 완전히 뜰 때까지 2초 대기
    time.sleep(2)
    
    # 4. 사용자의 웹 브라우저 띄우기
    print("🌐 웹 브라우저를 엽니다...")
    webbrowser.open("http://localhost:8000")
    
    print("================================================")
    print("🎉 실행 완료! 브라우저 창에서 바로 학습을 시작하세요.")
    print("서버를 종료하시려면 이 터미널 창에서 [Ctrl + C]를 누르세요.")
    print("================================================")
    
    try:
        # 파이썬 스크립트가 죽지 않고 자식 프로세스(server.py)를 유지하도록 대기
        server_process.wait()
    except KeyboardInterrupt:
        print("\n\n종료 신호 감지! 서버를 안전하게 끕니다.")
        server_process.terminate()
        server_process.wait()
        sys.exit(0)

if __name__ == "__main__":
    main()
