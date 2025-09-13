import requests
import json
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

def get_kst_time():
    """현재 한국 시간을 반환합니다"""
    return datetime.now(KST)

class NewsMonitor:
    def __init__(self, telegram_bot_token, telegram_chat_id, github_token, gist_id):
        self.bot_token = telegram_bot_token
        self.chat_id = telegram_chat_id
        self.github_token = github_token
        self.gist_id = gist_id
        self.load_previous_data()
    
    def load_previous_data(self):
        """GitHub Gist에서 이전 데이터를 로드합니다"""
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "News-Monitor-Bot"
            }
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                gist_data = response.json()
                content = gist_data['files']['news_data.json']['content']
                data = json.loads(content)
                self.previous_titles = set(data.get('titles', []))
                print(f"이전 데이터 로드: {len(self.previous_titles)}개 제목")
            else:
                self.previous_titles = set()
                print("이전 데이터가 없습니다. 새로 시작합니다.")
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            self.previous_titles = set()
    
    def save_data(self, current_titles):
        """GitHub Gist에 현재 데이터를 저장합니다"""
        try:
            data = {
                'titles': list(current_titles),
                'last_updated': get_kst_time().isoformat()
            }
            
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            payload = {
                "files": {
                    "news_data.json": {
                        "content": json.dumps(data, ensure_ascii=False, indent=2)
                    }
                }
            }
            
            response = requests.patch(url, headers=headers, json=payload)
            if response.status_code == 200:
                print("데이터 저장 완료")
            else:
                print(f"데이터 저장 실패: {response.status_code}")
        except Exception as e:
            print(f"데이터 저장 실패: {e}")
    
    def get_news_titles(self, url):
        """연합뉴스에서 제목을 가져옵니다"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            print(f"뉴스 페이지 접속 중: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 여러 셀렉터 시도
            selectors = [
                'ul.list01 span.title01',
                'div.section01 span.title01', 
                'span.title01'
            ]
            
            titles = []
            for selector in selectors:
                title_elements = soup.select(selector)
                if title_elements:
                    for element in title_elements:
                        text = element.get_text(strip=True)
                        if text and len(text) > 10:
                            titles.append(text)
                    break
            
            if not titles:
                print("제목을 찾을 수 없습니다")
                return []
            
            # 중복 제거
            titles = list(dict.fromkeys(titles))
            print(f"📰 총 {len(titles)}개의 제목을 찾았습니다")
            return titles
        
        except Exception as e:
            print(f"뉴스 페이지 접근 실패: {e}")
            return []
    
    def send_telegram_message(self, message):
        """텔레그램 메시지를 전송합니다"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            print("✅ 텔레그램 메시지 전송 완료")
            return True
        except Exception as e:
            print(f"❌ 텔레그램 메시지 전송 실패: {e}")
            return False
    
    def check_news(self):
        """뉴스를 확인하고 새로운 제목이 있으면 알림을 보냅니다"""
        url = "https://www.yna.co.kr/sports/all"
        current_time = get_kst_time()
        print(f"\n{'='*60}")
        print(f"🔍 뉴스 모니터링 시작: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
        print(f"{'='*60}")
        
        current_titles = self.get_news_titles(url)
        if not current_titles:
            print("❌ 제목을 가져올 수 없습니다")
            return
        
        # 현재 제목들을 세트로 변환
        current_set = set(current_titles)
        
        # 새로운 제목들 찾기
        new_titles = current_set - self.previous_titles
        
        print(f"새로운 제목: {len(new_titles)}개")
        
        if new_titles:
            # 새 제목들을 원래 순서대로 정렬 (current_titles 순서 유지)
            new_titles_ordered = [title for title in current_titles if title in new_titles]
            
            # 텔레그램 메시지 생성
            message = f"""🆕 새로운 스포츠 뉴스!

📍 연합뉴스 스포츠
⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}

📰 새로 올라온 제목:
"""
            
            for title in new_titles_ordered:
                message += f"-{title}\n"
            
            message += f"\n🔗 {url}"
            
            # 메시지 전송
            if len(message) > 4000:
                # 메시지가 너무 길면 나누어 전송
                base_msg = f"""🆕 새로운 스포츠 뉴스!

📍 연합뉴스 스포츠
⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}

📰 새로 올라온 제목 ({len(new_titles_ordered)}개):
"""
                
                current_msg = base_msg
                for title in new_titles_ordered:
                    line = f"-{title}\n"
                    if len(current_msg + line) > 3500:
                        self.send_telegram_message(current_msg)
                        current_msg = f"📰 계속...\n{line}"
                    else:
                        current_msg += line
                
                if current_msg:
                    current_msg += f"\n🔗 {url}"
                    self.send_telegram_message(current_msg)
            else:
                self.send_telegram_message(message)
            
            # 현재 제목들을 저장 (다음 비교를 위해)
            self.save_data(current_set)
            self.previous_titles = current_set
            
            # 로그 파일 저장
            try:
                log_filename = f"new_titles_{current_time.strftime('%Y%m%d_%H%M%S')}.txt"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    f.write(f"새로운 제목 발견: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}\n\n")
                    for title in new_titles_ordered:
                        f.write(f"-{title}\n")
                print(f"📄 로그 파일 저장: {log_filename}")
            except Exception as e:
                print(f"로그 파일 저장 실패: {e}")
        
        else:
            print("새로운 제목이 없습니다")
            # 제목이 새로운 게 없어도 현재 상태 저장
            self.save_data(current_set)
            self.previous_titles = current_set
        
        print(f"✅ 모니터링 완료")

def main():
    # 환경변수에서 설정 가져오기
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    github_token = os.getenv('GIST_ACCESS_TOKEN')
    gist_id = os.getenv('GIST_ID')
    
    if not all([bot_token, chat_id, github_token, gist_id]):
        print("❌ 환경변수가 설정되지 않았습니다!")
        return
    
    current_time = get_kst_time()
    print("🚀 연합뉴스 스포츠 모니터링 시작")
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    
    # 모니터 실행
    monitor = NewsMonitor(bot_token, chat_id, github_token, gist_id)
    monitor.check_news()

if __name__ == "__main__":
    main()

