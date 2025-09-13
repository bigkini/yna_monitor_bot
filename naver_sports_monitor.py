import requests
import json
import os
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import time

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
        
        self.load_previous_data()
    
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
                content = gist_data['files']['sports_exclusive_data.json']['content']
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
                self.previous_data = {section: set() for section in self.sports_sections.keys()}
                print("이전 데이터가 없습니다. 새로 시작합니다.")
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
            
            url = f"https://api.github.com/gists/{self.gist_id}"
            headers = {
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json"
            }
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
                print(f"데이터 저장 실패: {response.status_code}")
        except Exception as e:
            print(f"데이터 저장 실패: {e}")
    
    def get_exclusive_articles_from_section(self, section_id, section_name):
        """특정 스포츠 섹션에서 '단독' 기사를 가져옵니다"""
        try:
            current_time = get_kst_time()
            date_str = current_time.strftime('%Y%m%d')
            url = f"https://m.sports.naver.com/{section_id}/news?sectionId={section_id}&sort=latest&date={date_str}&isPhoto=N"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
            }
            
            print(f"📱 {section_name} 페이지 접속 중...")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # .NewsItem_title__BXkJ6 클래스를 가진 요소들 찾기
            title_elements = soup.select('.NewsItem_title__BXkJ6')
            
            if not title_elements:
                print(f"⚠️ {section_name}: 뉴스 아이템을 찾을 수 없습니다")
                return {}
            
            exclusive_articles = {}
            
            for title_element in title_elements:
                # 제목 텍스트 추출
                title_text = title_element.get_text(strip=True)
                
                # '단독'이 포함된 기사만 선택
                if '단독' in title_text:
                    # 링크 찾기 - 부모나 형제 요소에서 링크 찾기
                    link_element = title_element.find('a')
                    if not link_element:
                        # 부모 요소에서 링크 찾기
                        parent = title_element.parent
                        while parent and not link_element:
                            link_element = parent.find('a')
                            parent = parent.parent
                    
                    if link_element:
                        link = link_element.get('href')
                        if link:
                            # 상대 링크를 절대 링크로 변환
                            if link.startswith('/'):
                                link = 'https://m.sports.naver.com' + link
                            elif not link.startswith('http'):
                                link = 'https://m.sports.naver.com/' + link
                            
                            if title_text and len(title_text) > 5:  # 너무 짧은 제목은 제외
                                exclusive_articles[title_text] = link
                                print(f"🔥 {section_name} 단독 기사: {title_text}")
            
            if exclusive_articles:
                print(f"📰 {section_name}: {len(exclusive_articles)}개의 단독 기사 발견")
            else:
                print(f"📰 {section_name}: 단독 기사 없음")
            
            return exclusive_articles
        
        except Exception as e:
            print(f"❌ {section_name} 페이지 접근 실패: {e}")
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
            
            # 요청 간 간격 (너무 빠른 연속 요청 방지)
            time.sleep(1)
        
        # 새로운 기사가 있으면 텔레그램 알림 발송
        if all_new_articles:
            total_new_articles = sum(len(data['articles']) for data in all_new_articles.values())
            
            # 텔레그램 메시지 생성
            message = f"""🚨 새로운 스포츠 단독 뉴스!

📱 네이버 스포츠 통합 모니터링
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

📱 네이버 스포츠 통합 모니터링
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
    monitor = NaverSportsMonitor(bot_token, chat_id, github_token, gist_id)
    monitor.check_all_exclusive_news()

if __name__ == "__main__":
    main()
