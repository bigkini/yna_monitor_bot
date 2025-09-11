import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

class NewsMonitor:
    def __init__(self, telegram_bot_token, telegram_chat_id):
        self.bot_token = telegram_bot_token
        self.chat_id = telegram_chat_id
        self.data_file = "news_data.json"
        self.load_previous_data()
    
    def load_previous_data(self):
        """이전에 저장된 뉴스 데이터를 로드합니다"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.previous_data = json.load(f)
            else:
                self.previous_data = {}
                print("이전 데이터 파일이 없습니다. 새로 시작합니다.")
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            self.previous_data = {}
    
    def save_data(self):
        """현재 뉴스 데이터를 저장합니다"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.previous_data, f, ensure_ascii=False, indent=2)
            print("데이터 저장 완료")
        except Exception as e:
            print(f"데이터 저장 실패: {e}")
    
    def get_news_titles(self, url):
        """연합뉴스에서 span.title01 요소의 텍스트를 가져옵니다"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            print(f"뉴스 페이지 접속 중: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            title_elements = soup.select('span.title01')
            
            if not title_elements:
                print("⚠️ span.title01 요소를 찾을 수 없습니다")
                return []
            
            titles = []
            for element in title_elements:
                text = element.get_text(strip=True)
                if text:
                    titles.append(text)
            
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
        print(f"\n{'='*60}")
        print(f"🔍 뉴스 모니터링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        current_titles = self.get_news_titles(url)
        if not current_titles:
            print("❌ 제목을 가져올 수 없습니다")
            return
        
        # 현재 제목들을 세트로 변환
        current_set = set(current_titles)
        
        # 이전 제목들 가져오기
        previous_titles = self.previous_data.get('titles', [])
        previous_set = set(previous_titles)
        
        # 새로운 제목들 찾기
        new_titles = current_set - previous_set
        
        if new_titles:
            print(f"🆕 새로운 제목 {len(new_titles)}개 발견!")
            
            # 새 제목들을 리스트로 변환하고 정렬
            new_titles_list = sorted(list(new_titles))
            
            # 텔레그램 메시지 생성
            message = f"""🆕 <b>새로운 스포츠 뉴스!</b>

📍 연합뉴스 스포츠
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📰 새로 올라온 제목:
"""
            
            for i, title in enumerate(new_titles_list, 1):
                message += f"{i}. {title}\n"
            
            message += f"\n🔗 {url}"
            
            # 메시지가 너무 길면 나누어 전송
            if len(message) > 4000:
                base_msg = f"""🆕 <b>새로운 스포츠 뉴스!</b>

📍 연합뉴스 스포츠
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📰 새로 올라온 제목 ({len(new_titles_list)}개):
"""
                
                current_msg = base_msg
                for i, title in enumerate(new_titles_list, 1):
                    line = f"{i}. {title}\n"
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
            
            # 로그 파일 저장
            try:
                log_filename = f"new_titles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    f.write(f"새로운 제목 발견: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    for title in new_titles_list:
                        f.write(f"- {title}\n")
                print(f"📄 로그 파일 저장: {log_filename}")
            except Exception as e:
                print(f"로그 파일 저장 실패: {e}")
        
        else:
            print("📰 새로운 제목이 없습니다")
        
        # 현재 데이터 저장
        self.previous_data = {
            'titles': current_titles,
            'last_checked': datetime.now().isoformat(),
            'total_count': len(current_titles)
        }
        self.save_data()
        
        print(f"✅ 모니터링 완료 (총 {len(current_titles)}개 제목)")

def main():
    # 환경변수에서 설정 가져오기
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ 환경변수가 설정되지 않았습니다!")
        print("TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 설정해주세요.")
        return
    
    print("🚀 연합뉴스 스포츠 모니터링 시작")
    print(f"봇 토큰: {bot_token[:10]}...")
    print(f"채팅 ID: {chat_id}")
    
    # 모니터 실행
    monitor = NewsMonitor(bot_token, chat_id)
    monitor.check_news()

if __name__ == "__main__":
    main()