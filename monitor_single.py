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
        # {제목: {'link': ..., 'date': ...}} 구조로 관리하여 중복 체크와 날짜 필터링 동시 수행
        self.previous_articles = {} 
        self.load_previous_data()
    
    def load_previous_data(self):
        """GitHub Gist에서 이전 데이터를 로드하고 24시간 지난 데이터는 제외합니다"""
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
                    
                    limit_date = get_kst_time() - timedelta(hours=24)
                    
                    # articles 배열에서 24시간 이내의 데이터만 추출
                    if 'articles' in data:
                        for item in data['articles']:
                            item_date_str = item.get('date', get_kst_time().isoformat())
                            try:
                                item_date = datetime.fromisoformat(item_date_str)
                            except ValueError:
                                item_date = get_kst_time()
                            
                            if item_date > limit_date:
                                self.previous_articles[item['title']] = {
                                    'link': item['link'],
                                    'date': item_date_str
                                }
                    
                    print(f"✅ 이전 데이터 로드: {len(self.previous_articles)}개 (최근 24시간 기준)")
            else:
                print("이전 데이터가 없거나 로드에 실패했습니다. 새로 시작합니다.")
        except Exception as e:
            print(f"데이터 로드 실패: {e}")

    def save_data(self, current_articles_dict):
        """현재 데이터를 병합하고 24시간이 지난 데이터는 삭제한 뒤 Gist에 저장합니다"""
        try:
            limit_date = get_kst_time() - timedelta(hours=24)
            current_time_str = get_kst_time().isoformat()
            
            # 1. 새로 수집된 기사를 previous_articles에 병합 (수집 시간 기록)
            for title, link in current_articles_dict.items():
                if title not in self.previous_articles:
                    self.previous_articles[title] = {
                        'link': link,
                        'date': current_time_str
                    }
            
            # 2. 24시간 필터링을 거친 최종 리스트 생성
            final_list = []
            for title, info in self.previous_articles.items():
                try:
                    article_date = datetime.fromisoformat(info['date'])
                except ValueError:
                    article_date = get_kst_time()
                
                if article_date > limit_date:
                    final_list.append({
                        'title': title,
                        'link': info['link'],
                        'date': info['date']
                    })
            
            # 3. Gist 업데이트 수행
            data = {
                'articles': final_list,
                'last_updated': current_time_str
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
                print(f"💾 데이터 저장 완료 (총 {len(final_list)}개 유지)")
            else:
                print(f"데이터 저장 실패: {response.status_code}")
        except Exception as e:
            print(f"데이터 저장 중 오류 발생: {e}")

    def get_news_articles(self, url):
        """연합뉴스에서 스포츠 기사 제목과 링크를 가져옵니다"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            sports_section = soup.select_one('section.box-latest01 div.list-type212 ul.list01')
            
            if not sports_section:
                print("스포츠 기사 섹션을 찾을 수 없습니다")
                return {}
            
            articles = {}
            for li in sports_section.find_all('li', recursive=False):
                if not li.get('data-cid'): continue
                
                title_element = li.select_one('span.title01')
                link_element = li.select_one('a.tit-news')
                
                if title_element and link_element:
                    title = title_element.get_text(strip=True)
                    link = link_element.get('href')
                    if link.startswith('/'):
                        link = 'https://www.yna.co.kr' + link
                    
                    if title and len(title) > 10:
                        articles[title] = link
            
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
                "disable_web_page_preview": False
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
        
        current_articles = self.get_news_articles(url)
        if not current_articles:
            print("❌ 기사를 가져올 수 없습니다")
            return
        
        # 중복 체크: 제목 기준으로 비교
        new_titles = set(current_articles.keys()) - set(self.previous_articles.keys())
        print(f"새로운 기사: {len(new_titles)}개")
        
        if new_titles:
            new_articles_to_send = [(title, current_articles[title]) for title in current_articles.keys() if title in new_titles]
            
            message = f"🆕 <b>새로운 스포츠 뉴스!</b>\n\n"
            message += f"📍 연합뉴스 스포츠\n"
            message += f"⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}\n\n"
            message += f"📰 새로 올라온 기사:\n"
            
            for title, link in new_articles_to_send:
                message += f"• <a href='{link}'>{title}</a>\n"
            
            # 메시지 전송 (길이 제한 처리 포함)
            if len(message) > 4000:
                self.send_telegram_message("🆕 뉴스가 너무 많아 상위 기사만 먼저 보냅니다.")
                # ... (필요 시 분할 전송 로직 유지)
            else:
                self.send_telegram_message(message)
            
            # 필터링 및 저장 로직 호출
            self.save_data(current_articles)
        else:
            print("새로운 기사가 없습니다")
            # 기사가 없어도 24시간 경과 데이터를 청소하기 위해 저장 로직 호출
            self.save_data(current_articles)
        
        print(f"✅ 모니터링 완료")

def main():
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    github_token = os.getenv('GIST_ACCESS_TOKEN')
    gist_id = os.getenv('GIST_ID')
    
    if not all([bot_token, chat_id, github_token, gist_id]):
        print("❌ 환경변수 설정 확인 필요!")
        return
    
    monitor = NewsMonitor(bot_token, chat_id, github_token, gist_id)
    monitor.check_news()

if __name__ == "__main__":
    main()
