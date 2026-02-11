import requests
import json
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

def get_kst_time():
    return datetime.now(KST)

class NewsMonitor:
    def __init__(self, telegram_bot_token, telegram_chat_id, github_token, gist_id):
        self.bot_token = telegram_bot_token
        self.chat_id = telegram_chat_id
        self.github_token = github_token
        self.gist_id = gist_id
        self.previous_titles = set()
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
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                gist_data = response.json()
                if 'news_data.json' in gist_data['files']:
                    content = gist_data['files']['news_data.json']['content']
                    data = json.loads(content)
                    
                    if 'articles' in data:
                        self.previous_titles = {item['title'] for item in data['articles']}
                    elif 'titles' in data:
                        self.previous_titles = set(data['titles'])
                    
                    print(f"✅ 이전 데이터 로드: {len(self.previous_titles)}개 기사")
            else:
                print(f"⚠️ Gist 로드 실패 (상태 코드: {response.status_code}). 새로 시작합니다.")
        except Exception as e:
            print(f"❌ 데이터 로드 중 오류 발생: {e}")

    def save_data(self, current_articles):
        """GitHub Gist에 현재 데이터를 업데이트합니다"""
        try:
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
            
            response = requests.patch(url, headers=headers, json=payload, timeout=10)
            if response.status_code == 200:
                print("💾 Gist 데이터 저장 완료")
            else:
                print(f"❌ Gist 저장 실패: {response.status_code}")
        except Exception as e:
            print(f"❌ 데이터 저장 중 오류: {e}")

    def get_news_articles(self):
        """연합뉴스 스포츠 섹션 크롤링"""
        url = "https://www.yna.co.kr/sports/all"
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            # 기사 목록을 담고 있는 리스트 선택 (연합뉴스의 최신 구조 반영)
            # .list-type212 혹은 .box-latest01 내의 li 태그들
            items = soup.select('div.list-type212 li') or soup.select('.section01 .list-type212 li')
            
            articles = {}
            for li in items:
                title_tag = li.select_one('.tit') or li.select_one('strong.tit-news')
                link_tag = li.select_one('a')
                
                if title_tag and link_tag:
                    title = title_tag.get_text(strip=True)
                    link = link_tag.get('href')
                    if link.startswith('//'):
                        link = 'https:' + link
                    elif link.startswith('/'):
                        link = 'https://www.yna.co.kr' + link
                    
                    if title and len(title) > 5:
                        articles[title] = link
            
            return articles
        except Exception as e:
            print(f"❌ 크롤링 중 오류: {e}")
            return {}

    def send_telegram_message(self, message):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }
            requests.post(url, data=data, timeout=10).raise_for_status()
            print("📤 텔레그램 알림 전송 완료")
        except Exception as e:
            print(f"❌ 텔레그램 전송 실패: {e}")

    def check_news(self):
        current_time = get_kst_time()
        print(f"🔍 모니터링 시작: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        current_articles = self.get_news_articles()
        if not current_articles:
            return

        current_titles = set(current_articles.keys())
        new_titles = current_titles - self.previous_titles
        
        if new_titles:
            # 뉴스 순서 유지를 위해 리스트로 변환 (역순으로 보내려면 reversed 사용)
            new_list = [(t, current_articles[t]) for t in current_articles if t in new_titles]
            
            message = f"🆕 <b>새로운 스포츠 뉴스</b>\n\n"
            for title, link in new_list:
                message += f"• <a href='{link}'>{title}</a>\n"
            
            self.send_telegram_message(message)
            self.save_data(current_articles)
        else:
            print("😴 새로운 기사가 없습니다.")

def main():
    # GitHub Secrets에 등록해야 할 변수들
    config = {
        'bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
        'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
        'github_token': os.getenv('GIST_ACCESS_TOKEN'),
        'gist_id': os.getenv('GIST_ID')
    }
    
    if not all(config.values()):
        print("❌ 설정 오류: 모든 환경 변수가 설정되었는지 확인하세요.")
        return

    monitor = NewsMonitor(**config)
    monitor.check_news()

if __name__ == "__main__":
    main()
