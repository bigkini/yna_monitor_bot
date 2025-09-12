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
                print(f"이전 데이터 로드 완료: {len(self.previous_data.get('titles', []))}개 제목")
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
        """연합뉴스에서 제목을 가져옵니다 (여러 셀렉터 시도)"""
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
                'span.title01',
                '.list-type212 span.title01',
                '.news-con .tit-news span'
            ]
            
            titles = []
            for selector in selectors:
                title_elements = soup.select(selector)
                if title_elements:
                    print(f"✅ 셀렉터 '{selector}'로 {len(title_elements)}개 요소 발견")
                    for element in title_elements:
                        text = element.get_text(strip=True)
                        if text and len(text) > 10:  # 너무 짧은 텍스트 제외
                            titles.append(text)
                    break
                else:
                    print(f"❌ 셀렉터 '{selector}' 실패")
            
            if not titles:
                print("⚠️ 모든 셀렉터 실패. 페이지 구조 확인 필요")
                # 디버깅용: 페이지의 일부 구조 출력
                main_content = soup.select_one('.container, .content, .main')
                if main_content:
                    print("페이지 주요 구조:")
                    print(str(main_content)[:500] + "...")
                return []
            
            # 중복 제거
            titles = list(dict.fromkeys(titles))
            
            print(f"📰 총 {len(titles)}개의 제목을 찾았습니다")
            
            # 처음 몇 개 제목 출력해서 확인
            for i, title in enumerate(titles[:3]):
                print(f"  {i+1}. {title[:50]}...")
                
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
        
        # 이전 제목들 가져오기
        previous_titles = self.previous_data.get('titles', [])
        previous_set = set(previous_titles)
        
        print(f"📊 이전 저장된 제목: {len(previous_titles)}개")
        print(f"📊 현재 가져온 제목: {len(current_set)}개")
        
        # 새로운 제목들 찾기
        new_titles = current_set - previous_set
        
        print(f"📊 새로운 제목: {len(new_titles)}개")
        
        if new_titles:
            print(f"🆕 새로운 제목들:")
            for i, title in enumerate(new_titles, 1):
                print(f"  {i}. {title}")
            
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
            
            # 로그 파일 저장
            try:
                log_filename = f"new_titles_{current_time.strftime('%Y%m%d_%H%M%S')}.txt"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    f.write(f"새로운 제목 발견: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}\n\n")
                    for title in new_titles_ordered:
                        f.write(f"- {title}\n")
                print(f"📄 로그 파일 저장: {log_filename}")
            except Exception as e:
                print(f"로그 파일 저장 실패: {e}")
        
        else:
            print("📰 새로운 제목이 없습니다")
        
        # 현재 데이터 저장
        self.previous_data = {
            'titles': current_titles,
            'last_checked': current_time.isoformat(),
            'total_count': len(current_titles)
        }
        self.save_data()
        
        print(f"✅ 모니터링 완료 (총 {len(current_titles)}개 제목, 새로운 제목 {len(new_titles) if new_titles else 0}개)")

def main():
    # 환경변수에서 설정 가져오기
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ 환경변수가 설정되지 않았습니다!")
        print("TELEGRAM_BOT_TOKEN과 TELEGRAM_CHAT_ID를 설정해주세요.")
        return
    
    current_time = get_kst_time()
    print("🚀 연합뉴스 스포츠 모니터링 시작")
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"봇 토큰: {bot_token[:10]}...")
    print(f"채팅 ID: {chat_id}")
    
    # 모니터 실행
    monitor = NewsMonitor(bot_token, chat_id)
    monitor.check_news()

if __name__ == "__main__":
    main()
