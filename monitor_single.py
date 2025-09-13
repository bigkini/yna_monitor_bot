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
                # 제목과 링크를 함께 저장하도록 수정
                self.previous_articles = {item['title']: item['link'] for item in data.get('articles', [])}
                print(f"이전 데이터 로드: {len(self.previous_articles)}개 기사")
            else:
                self.previous_articles = {}
                print("이전 데이터가 없습니다. 새로 시작합니다.")
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            self.previous_articles = {}
    
    def save_data(self, current_articles):
        """GitHub Gist에 현재 데이터를 저장합니다"""
        try:
            # 제목과 링크를 함께 저장
            articles_list = [{'title': title, 'link': link} for title, link in current_articles.items()]
            data = {
                'articles': articles_list,
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
    
    def get_news_articles(self, url):
        """연합뉴스에서 스포츠 기사 제목과 링크를 가져옵니다"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            print(f"뉴스 페이지 접속 중: {url}")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 첫 번째 스포츠 기사 목록만 선택 (div.list-type212 > ul.list01)
            sports_section = soup.select_one('section.box-latest01 div.list-type212 ul.list01')
            
            if not sports_section:
                print("스포츠 기사 섹션을 찾을 수 없습니다")
                return {}
            
            articles = {}
            # li 요소들에서 제목과 링크 추출
            for li in sports_section.find_all('li', recursive=False):
                # 광고나 다른 요소는 제외 (data-cid가 있는 것만)
                if not li.get('data-cid'):
                    continue
                
                # 제목 추출
                title_element = li.select_one('span.title01')
                if not title_element:
                    continue
                
                title = title_element.get_text(strip=True)
                
                # 링크 추출
                link_element = li.select_one('a.tit-news')
                if not link_element:
                    continue
                
                link = link_element.get('href')
                if link:
                    # 상대 링크를 절대 링크로 변환
                    if link.startswith('/'):
                        link = 'https://www.yna.co.kr' + link
                    
                    if title and len(title) > 10:  # 너무 짧은 제목은 제외
                        articles[title] = link
            
            print(f"📰 총 {len(articles)}개의 스포츠 기사를 찾았습니다")
            return articles
        
        except Exception as e:
            print(f"뉴스 페이지 접근 실패: {e}")
            return {}
    
    def send_telegram_message(self, message):
        """텔레그램 메시지를 전송합니다"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False  # 링크 미리보기 활성화
            }
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            print("✅ 텔레그램 메시지 전송 완료")
            return True
        except Exception as e:
            print(f"❌ 텔레그램 메시지 전송 실패: {e}")
            return False
    
    def check_news(self):
        """뉴스를 확인하고 새로운 기사가 있으면 알림을 보냅니다"""
        url = "https://www.yna.co.kr/sports/all"
        current_time = get_kst_time()
        print(f"\n{'='*60}")
        print(f"🔍 뉴스 모니터링 시작: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
        print(f"{'='*60}")
        
        current_articles = self.get_news_articles(url)
        if not current_articles:
            print("❌ 기사를 가져올 수 없습니다")
            return
        
        # 데이터 타입 확인 및 처리
        print(f"현재 기사 데이터 타입: {type(current_articles)}")
        
        # 딕셔너리로 반환된 경우 리스트로 변환
        if isinstance(current_articles, dict):
            print("딕셔너리 형태의 데이터를 리스트로 변환합니다")
            articles_list = []
            for title, link in current_articles.items():
                articles_list.append({'title': title, 'link': link})
            current_articles = articles_list
        
        if current_articles:
            print(f"첫 번째 기사: {current_articles[0]}")
        
        # 새로운 기사들 찾기 (제목 기준으로 비교)
        current_titles = {article['title'] for article in current_articles}
        new_titles = current_titles - self.previous_titles
        
        print(f"새로운 기사: {len(new_titles)}개")
        
        if new_titles:
            # 새로운 기사들을 페이지 순서대로 정렬 (위에 있는 기사가 먼저)
            new_articles = [article for article in current_articles if article['title'] in new_titles]
            
            # 텔레그램 메시지 생성
            message = f"""🆕 새로운 스포츠 뉴스!

📍 연합뉴스 스포츠
⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}

📰 새로 올라온 기사:
"""
            
            for article in new_articles:
                # HTML 형식으로 링크 포함
                message += f"• <a href='{article['link']}'>{article['title']}</a>\n"
            
            # 메시지가 너무 길면 나누어 전송
            if len(message) > 4000:
                base_msg = f"""🆕 새로운 스포츠 뉴스!

📍 연합뉴스 스포츠
⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}

📰 새로 올라온 기사 ({len(new_articles)}개):
"""
                
                current_msg = base_msg
                for article in new_articles:
                    line = f"• <a href='{article['link']}'>{article['title']}</a>\n"
                    if len(current_msg + line) > 3500:
                        self.send_telegram_message(current_msg)
                        current_msg = f"📰 계속...\n{line}"
                    else:
                        current_msg += line
                
                if current_msg:
                    self.send_telegram_message(current_msg)
            else:
                self.send_telegram_message(message)
            
            # 현재 기사들을 저장 (다음 비교를 위해)
            self.save_data(current_articles)
            self.previous_articles = current_articles
            self.previous_titles = current_titles
            
            # 로그 파일 저장
            try:
                log_filename = f"new_articles_{current_time.strftime('%Y%m%d_%H%M%S')}.txt"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    f.write(f"새로운 기사 발견: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}\n\n")
                    for article in new_articles:
                        f.write(f"• {article['title']}\n  링크: {article['link']}\n\n")
                print(f"📄 로그 파일 저장: {log_filename}")
            except Exception as e:
                print(f"로그 파일 저장 실패: {e}")
        
        else:
            print("새로운 기사가 없습니다")
            # 기사가 새로운 게 없어도 현재 상태 저장
            self.save_data(current_articles)
            self.previous_articles = current_articles
            self.previous_titles = current_titles
        
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
