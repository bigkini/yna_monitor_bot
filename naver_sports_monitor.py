import requests
import json
import os
from datetime import datetime, timezone, timedelta
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

def get_kst_time():
    """현재 한국 시간을 반환합니다"""
    return datetime.now(KST)

class NaverSportsMonitor:
    def __init__(self, telegram_bot_token, telegram_chat_id, github_token, gist_id):
        self.bot_token = telegram_bot_token
        self.chat_id = telegram_chat_id
        self.github_token = github_token
        self.gist_id = gist_id
        
        # 모니터링할 스포츠 섹션들
        self.sports_sections = {
            'kbaseball': '국내야구',
            'wbaseball': '해외야구', 
            'kfootball': '국내축구',
            'wfootball': '해외축구',
            'basketball': '농구',
            'volleyball': '배구',
            'general': '일반스포츠'
        }
        
        # Selenium WebDriver 설정
        self.driver = None
        self.setup_driver()
        
        self.load_previous_data()
    
    def setup_driver(self):
        """Chrome WebDriver를 설정합니다"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 브라우저 창 없이 실행
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1')
            
            # GitHub Actions 환경에서의 추가 설정
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')
            chrome_options.add_argument('--disable-javascript')  # JS 비활성화로 속도 향상
            chrome_options.add_argument('--remote-debugging-port=9222')
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            print("✅ Chrome WebDriver 설정 완료")
            
        except Exception as e:
            print(f"❌ WebDriver 설정 실패: {e}")
            self.driver = None
    
    def close_driver(self):
        """WebDriver를 종료합니다"""
        if self.driver:
            self.driver.quit()
            print("✅ WebDriver 종료")
    
    def load_previous_data(self):
        """GitHub Gist에서 이전 데이터를 로드합니다"""
        try:
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Naver-Sports-Monitor-Bot"
            }
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                gist_data = response.json()
                
                # 파일이 존재하는지 확인
                if 'naver_sports_exclusive_data.json' in gist_data['files']:
                    content = gist_data['files']['naver_sports_exclusive_data.json']['content']
                    data = json.loads(content)
                    
                    # 섹션별로 이전 데이터 로드
                    self.previous_data = {}
                    for section in self.sports_sections.keys():
                        if section in data:
                            if 'articles' in data[section]:
                                self.previous_data[section] = {item['title'] for item in data[section]['articles']}
                            elif 'titles' in data[section]:
                                self.previous_data[section] = set(data[section]['titles'])
                            else:
                                self.previous_data[section] = set()
                        else:
                            self.previous_data[section] = set()
                    
                    total_articles = sum(len(titles) for titles in self.previous_data.values())
                    print(f"이전 데이터 로드: 총 {total_articles}개 기사")
                else:
                    print("네이버 스포츠 데이터 파일이 없습니다. 새로 시작합니다.")
                    self.previous_data = {section: set() for section in self.sports_sections.keys()}
            else:
                print(f"Gist 접근 실패: {response.status_code}")
                self.previous_data = {section: set() for section in self.sports_sections.keys()}
        except Exception as e:
            print(f"데이터 로드 실패: {e}")
            self.previous_data = {section: set() for section in self.sports_sections.keys()}
    
    def save_data(self, current_data):
        """GitHub Gist에 현재 데이터를 저장합니다"""
        try:
            # 각 섹션별 데이터를 저장 형식으로 변환
            save_data = {}
            for section, articles in current_data.items():
                articles_list = [{'title': title, 'link': link} for title, link in articles.items()]
                save_data[section] = {
                    'articles': articles_list,
                    'section_name': self.sports_sections[section]
                }
            
            save_data['last_updated'] = get_kst_time().isoformat()
            
            # 기존 Gist 업데이트 또는 새 파일 생성
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
            
            # 기존 Gist 파일들을 유지하면서 새 파일 추가
            payload = {
                "files": {
                    "naver_sports_exclusive_data.json": {
                        "content": json.dumps(save_data, ensure_ascii=False, indent=2)
                    }
                }
            }
            
            response = requests.patch(url, headers=headers, json=payload)
            if response.status_code == 200:
                print("데이터 저장 완료")
            else:
                print(f"데이터 저장 실패: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"데이터 저장 실패: {e}")
    
    def get_exclusive_articles_from_section(self, section_id, section_name):
        """Selenium을 사용하여 특정 스포츠 섹션에서 '단독' 기사를 가져옵니다"""
        if not self.driver:
            print(f"❌ {section_name}: WebDriver가 초기화되지 않았습니다")
            return {}
            
        try:
            current_time = get_kst_time()
            date_str = current_time.strftime('%Y%m%d')
            url = f"https://m.sports.naver.com/{section_id}/news?sectionId={section_id}&sort=latest&date={date_str}&isPhoto=N"
            
            print(f"📱 {section_name} 페이지 로딩 중...")
            self.driver.get(url)
            
            # JavaScript 로딩 대기
            wait = WebDriverWait(self.driver, 15)
            
            # 다양한 선택자로 뉴스 아이템 찾기
            possible_selectors = [
                "a[href*='/news/']",  # 뉴스 링크
                "[class*='news']",    # news가 포함된 클래스
                "[class*='item']",    # item이 포함된 클래스
                "[class*='title']",   # title이 포함된 클래스
                "article",            # article 태그
                ".list li",           # 리스트 아이템
                "[data-*]"            # data 속성이 있는 요소
            ]
            
            news_elements = []
            for selector in possible_selectors:
                try:
                    elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                    if elements and len(elements) > 5:  # 충분한 요소가 있으면 사용
                        news_elements = elements
                        print(f"✅ {section_name}: '{selector}' 선택자로 {len(elements)}개 요소 발견")
                        break
                except TimeoutException:
                    continue
            
            if not news_elements:
                # 페이지 소스 확인을 위한 디버깅
                print(f"⚠️ {section_name}: 뉴스 요소를 찾을 수 없습니다")
                page_source_sample = self.driver.page_source[:1000]
                print(f"페이지 소스 샘플: {page_source_sample}")
                return {}
            
            exclusive_articles = {}
            
            for element in news_elements:
                try:
                    # 텍스트 추출
                    text_content = element.text.strip()
                    
                    # href 속성이 있는 경우 링크로 간주
                    link = element.get_attribute('href')
                    
                    # 링크가 없으면 자식 요소에서 찾기
                    if not link:
                        try:
                            link_element = element.find_element(By.TAG_NAME, 'a')
                            link = link_element.get_attribute('href')
                            if not text_content:
                                text_content = link_element.text.strip()
                        except NoSuchElementException:
                            continue
                    
                    # '단독'이 포함된 텍스트만 선택
                    if text_content and '단독' in text_content and link:
                        # 네이버 뉴스 링크인지 확인
                        if 'sports.naver.com' in link or 'news.naver.com' in link:
                            # 상대 링크를 절대 링크로 변환
                            if link.startswith('/'):
                                link = 'https://m.sports.naver.com' + link
                            
                            if len(text_content) > 5:  # 너무 짧은 제목은 제외
                                # 제목 정리 (불필요한 텍스트 제거)
                                clean_title = text_content.split('\n')[0].strip()
                                exclusive_articles[clean_title] = link
                                print(f"🔥 {section_name} 단독 기사: {clean_title}")
                
                except Exception as e:
                    # 개별 요소 처리 실패는 무시하고 계속
                    continue
            
            if exclusive_articles:
                print(f"📰 {section_name}: {len(exclusive_articles)}개의 단독 기사 발견")
            else:
                print(f"📰 {section_name}: 단독 기사 없음")
            
            return exclusive_articles
            
        except Exception as e:
            print(f"❌ {section_name} 페이지 크롤링 실패: {e}")
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
    
    def get_section_emoji(self, section_id):
        """섹션별 이모지 반환"""
        emoji_map = {
            'kbaseball': '⚾',
            'wbaseball': '🌍⚾',
            'kfootball': '⚽',
            'wfootball': '🌍⚽',
            'basketball': '🏀',
            'volleyball': '🏐',
            'general': '🏃‍♂️'
        }
        return emoji_map.get(section_id, '🏆')
    
    def check_all_exclusive_news(self):
        """모든 스포츠 섹션의 단독 뉴스를 확인합니다"""
        current_time = get_kst_time()
        print(f"\n{'='*60}")
        print(f"🔍 네이버 스포츠 통합 단독 뉴스 모니터링 시작")
        print(f"⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
        print(f"{'='*60}")
        
        all_current_data = {}
        all_new_articles = {}
        
        # 각 섹션별로 단독 기사 확인
        for section_id, section_name in self.sports_sections.items():
            print(f"\n🔍 {section_name} 섹션 확인 중...")
            
            current_articles = self.get_exclusive_articles_from_section(section_id, section_name)
            all_current_data[section_id] = current_articles
            
            if current_articles:
                # 현재 기사 제목들 (set)
                current_titles = set(current_articles.keys())
                
                # 새로운 기사들 찾기 (제목 기준으로 비교)
                new_titles = current_titles - self.previous_data[section_id]
                
                if new_titles:
                    # 새로운 기사들을 저장
                    new_articles_in_section = [(title, current_articles[title]) for title in current_articles.keys() if title in new_titles]
                    all_new_articles[section_id] = {
                        'section_name': section_name,
                        'articles': new_articles_in_section
                    }
                    print(f"🆕 {section_name}: {len(new_titles)}개 새 단독 기사")
                else:
                    print(f"📰 {section_name}: 새로운 단독 기사 없음")
            
            # 각 섹션 크롤링 간 대기 시간
            time.sleep(3)
        
        # 새로운 기사가 있으면 텔레그램 알림 발송
        if all_new_articles:
            total_new_articles = sum(len(data['articles']) for data in all_new_articles.values())
            
            # 텔레그램 메시지 생성
            message = f"""🚨 새로운 스포츠 단독 뉴스!

📱 네이버 스포츠 Selenium 모니터링
⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}
🔥 총 {total_new_articles}개의 새 단독 기사

"""
            
            # 섹션별로 새 기사 추가
            for section_id, section_data in all_new_articles.items():
                section_name = section_data['section_name']
                articles = section_data['articles']
                emoji = self.get_section_emoji(section_id)
                
                message += f"\n{emoji} {section_name} ({len(articles)}개)\n"
                for title, link in articles:
                    message += f"• <a href='{link}'>{title}</a>\n"
            
            # 메시지가 너무 길면 나누어 전송
            if len(message) > 4000:
                # 헤더 메시지
                header_msg = f"""🚨 새로운 스포츠 단독 뉴스!

📱 네이버 스포츠 Selenium 모니터링
⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}
🔥 총 {total_new_articles}개의 새 단독 기사

"""
                self.send_telegram_message(header_msg)
                
                # 섹션별로 나누어 전송
                for section_id, section_data in all_new_articles.items():
                    section_name = section_data['section_name']
                    articles = section_data['articles']
                    emoji = self.get_section_emoji(section_id)
                    
                    section_msg = f"{emoji} {section_name} ({len(articles)}개)\n\n"
                    for title, link in articles:
                        line = f"• <a href='{link}'>{title}</a>\n"
                        if len(section_msg + line) > 3500:
                            self.send_telegram_message(section_msg)
                            section_msg = f"{emoji} {section_name} 계속...\n{line}"
                        else:
                            section_msg += line
                    
                    if section_msg:
                        self.send_telegram_message(section_msg)
            else:
                self.send_telegram_message(message)
            
            # 로그 파일 저장
            try:
                log_filename = f"sports_exclusive_{current_time.strftime('%Y%m%d_%H%M%S')}.txt"
                with open(log_filename, 'w', encoding='utf-8') as f:
                    f.write(f"새로운 스포츠 단독 기사 발견: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}\n\n")
                    for section_id, section_data in all_new_articles.items():
                        f.write(f"=== {section_data['section_name']} ===\n")
                        for title, link in section_data['articles']:
                            f.write(f"• {title}\n  링크: {link}\n\n")
                        f.write("\n")
                print(f"📄 로그 파일 저장: {log_filename}")
            except Exception as e:
                print(f"로그 파일 저장 실패: {e}")
        
        else:
            print("\n📰 모든 섹션: 새로운 단독 기사가 없습니다")
        
        # 현재 데이터 저장 및 업데이트
        self.save_data(all_current_data)
        for section_id, articles in all_current_data.items():
            self.previous_data[section_id] = set(articles.keys())
        
        print(f"\n✅ 모든 섹션 모니터링 완료")

def main():
    # 환경변수에서 설정 가져오기
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    github_token = os.getenv('GIST_ACCESS_TOKEN')
    gist_id = os.getenv('GIST_ID')
    
    if not all([bot_token, chat_id, github_token, gist_id]):
        print("❌ 환경변수가 설정되지 않았습니다!")
        print("필요한 환경변수:")
        print("- TELEGRAM_BOT_TOKEN")
        print("- TELEGRAM_CHAT_ID")
        print("- GIST_ACCESS_TOKEN")
        print("- GIST_ID")
        return
    
    current_time = get_kst_time()
    print("🚀 네이버 스포츠 통합 단독 뉴스 모니터링 시작")
    print(f"현재 시간: {current_time.strftime('%Y-%m-%d %H:%M:%S KST')}")
    
    # 모니터 실행
    monitor = None
    try:
        monitor = NaverSportsMonitor(bot_token, chat_id, github_token, gist_id)
        monitor.check_all_exclusive_news()
    except Exception as e:
        print(f"❌ 모니터링 실행 중 오류: {e}")
    finally:
        # WebDriver 정리
        if monitor:
            monitor.close_driver()

if __name__ == "__main__":
    main()
