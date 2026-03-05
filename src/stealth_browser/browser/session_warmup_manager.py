#!/usr/bin/env python
"""
Session Warmup Manager
4단계 완전한 세션 워밍업 시스템으로 브라우저 신뢰도를 점진적으로 구축
상위 2-5% 수준의 Anti-Bot 우회를 위한 핵심 컴포넌트
"""

import random
import time
import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from stealth_browser.browser.bezier_mouse import BezierMouseManager
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)


class SessionWarmupManager:
    """완전한 4단계 세션 워밍업 시스템"""
    
    def __init__(self, driver):
        self.driver = driver
        # 베지에 마우스 초기화 (실패해도 계속 진행)
        try:
            self.bezier_mouse = BezierMouseManager(driver)
            self.use_bezier = True
            logger.info("✅ Bezier mouse initialized successfully")
        except Exception as e:
            logger.warning(f"⚠️ Bezier mouse initialization failed, using simple mouse: {e}")
            self.bezier_mouse = None
            self.use_bezier = False
            
        self.wait = WebDriverWait(driver, 10)
        
        # Phase 간 상태 추적 변수 추가
        self.already_on_coupang = False
        
        # YAML 설정 로드 (모든 설정을 여기서 읽어옴)
        self._load_config()

    def _load_config(self):
        """YAML 설정 파일에서 세션 워밍업 설정 로드"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "crawler_config.yaml"
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 세션 워밍업 설정 추출
            warmup_config = config.get('session_warmup', {})
            
            self.enabled = warmup_config.get('enabled', True)
            self.duration_range = warmup_config.get('duration_range', [15, 25])
            self.browser_trust_signals = warmup_config.get('browser_trust_signals', True)
            self.pre_exploration = warmup_config.get('pre_exploration', True)
            
            # 단계별 시간 배분
            phase_durations = warmup_config.get('phase_durations', {})
            self.phase1_duration = phase_durations.get('browser_init', [1, 2])
            self.phase2_duration = phase_durations.get('external_trust', [5, 8])
            self.phase3_duration = phase_durations.get('coupang_exploration', [4, 7])
            self.phase4_duration = phase_durations.get('final_stabilization', [3, 5])
            
            # Phase 2: External Trust Building 설정
            external_trust_config = warmup_config.get('external_trust_building', {})
            
            # Google 검색 키워드 (YAML에서 읽어옴)
            google_config = external_trust_config.get('google_search', {})
            self.coupang_search_keywords = google_config.get('coupang_keywords', [
                "쿠팡 할인", "쿠팡 특가", "쿠팡 로켓배송", "쿠팡 골드박스", "쿠팡 추천"
            ])
            self.click_coupang_link_probability = google_config.get('click_coupang_link_probability', 0.7)
            
            # 한국 포털 설정 (YAML에서 읽어옴)
            korean_portals_config = external_trust_config.get('korean_portals', {})
            self.korean_portals_enabled = korean_portals_config.get('enabled', True)
            self.korean_portals_visit_probability = korean_portals_config.get('visit_probability', 0.4)
            self.korean_portals_coupang_search_probability = korean_portals_config.get('coupang_search_probability', 0.7)
            self.korean_portals = korean_portals_config.get('portals', [
                {"name": "naver", "url": "https://www.naver.com", "weight": 80},
                {"name": "daum", "url": "https://www.daum.net", "weight": 20}
            ])
            self.korean_portals_scroll_range = korean_portals_config.get('scroll_count_range', [1, 2])
            
            # Phase 3: Coupang Exploration 설정
            coupang_exploration_config = warmup_config.get('coupang_exploration', {})
            self.main_page_scroll_count = coupang_exploration_config.get('main_page_scroll_count', [0, 1])
            self.banner_hover_probability = coupang_exploration_config.get('banner_hover_probability', 0.1)
            
            # 카테고리 사전 탐색 설정
            category_config = coupang_exploration_config.get('category_pre_exploration', {})
            self.category_exploration_enabled = category_config.get('enabled', False)
            self.categories_to_explore_range = category_config.get('categories_to_explore_range', [0, 0])
            
            # 특별 페이지 설정
            special_pages_config = coupang_exploration_config.get('special_pages', {})
            self.special_pages_enabled = special_pages_config.get('enabled', True)
            self.special_pages_visit_probability = special_pages_config.get('visit_probability', 0.3)
            self.special_pages_interaction_probability = special_pages_config.get('interaction_probability', 0.3)
            
            # Phase 4: Final Stabilization 설정
            final_stabilization_config = warmup_config.get('final_stabilization', {})
            micro_interactions_config = final_stabilization_config.get('micro_interactions', {})
            self.search_box_click_cancel_probability = micro_interactions_config.get('search_box_click_cancel_probability', 0.1)
            self.category_menu_hover_probability = micro_interactions_config.get('category_menu_hover_probability', 0.1)
            self.micro_scroll_count = micro_interactions_config.get('micro_scroll_count', [0, 1])
            
            final_familiarity_config = final_stabilization_config.get('final_user_familiarity', {})
            self.final_hover_probability = final_familiarity_config.get('final_hover_probability', 0.2)
            self.elements_to_consider = final_familiarity_config.get('elements_to_consider', 3)
            
            logger.info(f"✅ Session warmup config loaded: enabled={self.enabled}, keywords={len(self.coupang_search_keywords)}")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to load session warmup config, using defaults: {e}")
            # 기본값 설정
            self.enabled = True
            self.duration_range = [15, 25]
            self.browser_trust_signals = True
            self.pre_exploration = True
            self.phase1_duration = [1, 2]
            self.phase2_duration = [5, 8]
            self.phase3_duration = [4, 7]
            self.phase4_duration = [3, 5]
            
            # 기본 키워드 및 포털 설정
            self.coupang_search_keywords = [
                "쿠팡 할인", "쿠팡 특가", "쿠팡 로켓배송", "쿠팡 골드박스", "쿠팡 추천"
            ]
            self.click_coupang_link_probability = 0.7
            self.korean_portals_enabled = True
            self.korean_portals_visit_probability = 0.4
            self.korean_portals_coupang_search_probability = 0.7
            self.korean_portals = [
                {"name": "naver", "url": "https://www.naver.com", "weight": 80},
                {"name": "daum", "url": "https://www.daum.net", "weight": 20}
            ]
            self.korean_portals_scroll_range = [1, 2]

    def should_execute_warmup(self) -> bool:
        """세션 워밍업 실행 여부 결정"""
        return self.enabled

    def execute_full_warmup_sequence(self, target_url: Optional[str] = None) -> bool:
        """완전한 4단계 세션 워밍업 시퀀스 실행"""
        if not self.should_execute_warmup():
            logger.info("⏭️ Session warmup disabled, skipping...")
            return True
        
        total_duration = random.uniform(*self.duration_range)
        logger.info(f"🎭 Starting COMPLETE session warmup sequence ({total_duration:.1f}s)")
        logger.info(f"🖱️ Bezier mouse status: {'✅ Enabled' if self.use_bezier else '❌ Disabled'}")
        
        start_time = time.time()
        
        try:
            # Phase 1: 브라우저 초기화 & 기본 신호
            logger.info("🔧 Phase 1: Browser Initialization & Basic Signals")
            phase1_success = self._phase1_browser_initialization()
            
            # Phase 2: 외부 도메인 신뢰도 구축
            logger.info("🌐 Phase 2: External Domain Trust Building")
            phase2_success = self._phase2_external_trust_building()
            
            # Phase 3: 쿠팡 사전 탐색
            logger.info("🛒 Phase 3: Coupang Pre-exploration")
            phase3_success = self._phase3_coupang_exploration()
            
            # Phase 4: 최종 안정화
            logger.info("🎯 Phase 4: Final Stabilization")
            phase4_success = self._phase4_final_stabilization()
            
            elapsed_time = time.time() - start_time
            
            if all([phase1_success, phase2_success, phase3_success, phase4_success]):
                logger.info(f"🎉 Session warmup COMPLETED successfully in {elapsed_time:.1f}s")
                
                # 목표 URL로 최종 이동 (있는 경우)
                if target_url:
                    logger.info(f"🎯 Final navigation to target URL: {target_url}")
                    time.sleep(random.uniform(2, 5))
                    self.driver.get(target_url)
                    time.sleep(random.uniform(3, 7))
                
                return True
            else:
                logger.warning(f"⚠️ Session warmup completed with some failures in {elapsed_time:.1f}s")
                return False
                
        except Exception as e:
            logger.error(f"❌ Session warmup sequence failed: {e}")
            return False

    def _phase1_browser_initialization(self) -> bool:
        """Phase 1: 브라우저 초기화 & 기본 신호"""
        try:
            phase_duration = random.uniform(*self.phase1_duration)
            logger.info(f"🔧 Phase 1 duration: {phase_duration:.1f}s")
            
            start_time = time.time()
            
            # 1.1 윈도우 포커스/블러 이벤트 시뮬레이션 (빠르게)
            if self.browser_trust_signals:
                logger.info("👁️ Simulating window focus/blur events...")
                try:
                    # 윈도우 블러 시뮬레이션 (대기시간 제거)
                    self.driver.execute_script("""
                        window.dispatchEvent(new Event('blur'));
                        setTimeout(() => {
                            window.dispatchEvent(new Event('focus'));
                        }, 100);
                    """)
                    time.sleep(0.1)  # 대기 시간 대폭 단축 (0.3초 → 0.1초)
                except Exception as e:
                    logger.warning(f"⚠️ Window focus/blur simulation failed: {e}")
            
            # 1.2 뷰포트 정보 수집 (빠르게)
            try:
                viewport_info = self.driver.execute_script("""
                    return {
                        width: window.innerWidth,
                        height: window.innerHeight,
                        devicePixelRatio: window.devicePixelRatio || 1
                    };
                """)
                logger.info(f"📊 Viewport info collected: {viewport_info['width']}x{viewport_info['height']}")
            except Exception as e:
                logger.warning(f"⚠️ Viewport info collection failed: {e}")
            
            # 1.3 기본 브라우저 신호 생성 (최소한의 대기)
            logger.info("🖱️ Finalizing browser initialization signals...")
            try:
                # 최소한의 대기만 유지
                time.sleep(random.uniform(0.1, 0.3))  # 대기 시간 대폭 단축 (0.5-1초 → 0.1-0.3초)
                logger.info("✅ Browser initialization signals completed")
                        
            except Exception as e:
                logger.warning(f"⚠️ Browser initialization signals failed: {e}")
            
            # Phase 1 완료까지 대기
            elapsed = time.time() - start_time
            remaining = phase_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)
            
            logger.info("✅ Phase 1 completed: Browser initialization")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 1 failed: {e}")
            return False

    def _phase2_external_trust_building(self) -> bool:
        """Phase 2: 외부 도메인 신뢰도 구축"""
        try:
            phase_duration = random.uniform(*self.phase2_duration)
            logger.info(f"🌐 Phase 2 duration: {phase_duration:.1f}s")
            
            start_time = time.time()
            
            # 안정화 0: Google Service Worker 간섭 회피 및 지역 리디렉션 최소화
            try:
                self.driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})
                logger.debug("🛠️ Bypass ServiceWorker enabled for Phase 2")
            except Exception as e:
                logger.debug(f"SW bypass not applied: {e}")

            # 2.1 Google 검색 시뮬레이션 (쿠팡 관련 키워드)
            search_keyword = random.choice(self.coupang_search_keywords)
            logger.info(f"🔍 Google search simulation: '{search_keyword}'")
            
            try:
                # Google 검색 페이지로 이동 (SW/국가 리디렉션 최소화)
                self.driver.get("https://www.google.com/ncr")
                time.sleep(random.uniform(0.5, 1))  # 대기 시간 대폭 단축 (1-2초 → 0.5-1초)
                
                # 검색창 찾기 및 키워드 입력
                search_selectors = [
                    "input[name='q']",
                    "textarea[name='q']", 
                    "#APjFqb",
                    ".gLFyf"
                ]
                
                search_box = None
                # 짧은 타임아웃으로 빠르게 실패 후 fallback
                local_wait = WebDriverWait(self.driver, 5)
                for selector in search_selectors:
                    try:
                        search_box = local_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        break
                    except Exception:
                        continue
                # Fallback: 한국 도메인
                if not search_box:
                    logger.info("🔄 Fallback to google.co.kr ...")
                    self.driver.get("https://www.google.co.kr/?hl=ko")
                    time.sleep(1)
                    for selector in search_selectors:
                        try:
                            search_box = local_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                            break
                        except Exception:
                            continue
                
                if search_box:
                    # 빠른 클릭
                    ActionChains(self.driver).move_to_element(search_box).click().perform()
                    time.sleep(random.uniform(0.1, 0.3))  # 대기 시간 대폭 단축 (0.2-0.5초 → 0.1-0.3초)
                    
                    # 빠른 키워드 타이핑
                    for char in search_keyword:
                        search_box.send_keys(char)
                        time.sleep(random.uniform(0.02, 0.05))  # 타이핑 속도 대폭 단축 (0.03-0.1초 → 0.02-0.05초)
                    
                    time.sleep(random.uniform(0.1, 0.3))  # 대기 시간 대폭 단축 (0.3-0.8초 → 0.1-0.3초)
                    search_box.send_keys(Keys.RETURN)
                    time.sleep(random.uniform(0.8, 1.5))  # 대기 시간 대폭 단축 (1-3초 → 0.8-1.5초)
                    
                    # 검색 결과에서 쿠팡 링크 찾기 (있으면 클릭)
                    try:
                        coupang_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'coupang.com')]")
                        if coupang_links:
                            # 첫 번째 쿠팡 링크 클릭 (YAML 설정 확률 사용)
                            if random.random() < self.click_coupang_link_probability:
                                coupang_link = coupang_links[0]
                                ActionChains(self.driver).move_to_element(coupang_link).click().perform()
                                time.sleep(random.uniform(1, 2))  # 대기 시간 대폭 단축 (2-4초 → 1-2초)
                                logger.info("🎯 Clicked Coupang link from Google search")
                                self.already_on_coupang = True # 쿠팡 링크를 클릭했으므로 쿠팡에 있음
                    except:
                        pass
                        
                else:
                    logger.warning("⚠️ Could not find Google search box - skipping Google phase")
                    
            except Exception as e:
                logger.warning(f"⚠️ Google search simulation failed: {e}")
            
            # 2.2 네이버/다음 방문 (한국 사용자 패턴, YAML 설정 사용)
            if self.korean_portals_enabled and random.random() < self.korean_portals_visit_probability:
                portal = random.choices(
                    self.korean_portals,
                    weights=[p['weight'] for p in self.korean_portals],
                    k=1
                )[0]
                
                logger.info(f"🇰🇷 Visiting Korean portal: {portal['name']}")
                
                try:
                    self.driver.get(portal['url'])
                    time.sleep(random.uniform(0.5, 1))  # 대기 시간 대폭 단축 (1-2초 → 0.5-1초)
                    
                    # 포털에서 빠른 스크롤 (YAML 설정 사용)
                    for _ in range(random.randint(*self.korean_portals_scroll_range)):
                        scroll_amount = random.randint(200, 400)  # 스크롤 양 단축
                        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                        time.sleep(random.uniform(0.2, 0.5))  # 대기 시간 대폭 단축 (0.5-1초 → 0.2-0.5초)
                    
                    # 한국 포털에서 쿠팡 관련 검색 후 링크 찾기 (YAML 설정 사용)
                    if random.random() < self.korean_portals_coupang_search_probability:
                        try:
                            logger.info(f"🔍 Searching for Coupang on {portal['name']}...")
                            
                            # 포털별 검색창 찾기
                            search_box = None
                            search_selectors = []
                            
                            if portal['name'] == 'naver':
                                search_selectors = [
                                    "input#query",
                                    "input.search_input",
                                    "input[name='query']",
                                    ".search_input_box input"
                                ]
                            elif portal['name'] == 'daum':
                                search_selectors = [
                                    "input#q",
                                    "input.tf_keyword",
                                    "input[name='q']",
                                    ".search_box input"
                                ]
                            
                            # 검색창 찾기
                            for selector in search_selectors:
                                try:
                                    search_box = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                                    break
                                except:
                                    continue
                            
                            if search_box:
                                # 쿠팡 관련 검색어 입력
                                search_keyword = random.choice(self.coupang_search_keywords)
                                logger.info(f"🔍 Searching '{search_keyword}' on {portal['name']}")
                                
                                # 검색창 클릭 및 키워드 입력
                                ActionChains(self.driver).move_to_element(search_box).click().perform()
                                time.sleep(random.uniform(0.3, 0.8))
                                
                                # 기존 텍스트 지우기
                                search_box.clear()
                                time.sleep(random.uniform(0.2, 0.5))
                                
                                # 인간처럼 키워드 타이핑
                                for char in search_keyword:
                                    search_box.send_keys(char)
                                    time.sleep(random.uniform(0.05, 0.15))
                                
                                time.sleep(random.uniform(0.5, 1))
                                search_box.send_keys(Keys.RETURN)
                                time.sleep(random.uniform(2, 4))  # 검색 결과 로딩 대기
                                
                                # 검색 결과에서 쿠팡 관련 링크 찾기
                                coupang_elements = self.driver.find_elements(By.XPATH, 
                                    "//a[contains(@href, 'coupang.com')] | //a[contains(text(), '쿠팡')] | //*[contains(text(), '쿠팡')]/ancestor::a")
                                
                                if coupang_elements:
                                    # 보이는 쿠팡 링크만 필터링
                                    visible_coupang_links = []
                                    for link in coupang_elements[:5]:  # 상위 5개만 확인
                                        try:
                                            if link.is_displayed() and link.is_enabled() and link.size['height'] > 0:
                                                visible_coupang_links.append(link)
                                        except:
                                            continue
                                    
                                    if visible_coupang_links:
                                        coupang_link = random.choice(visible_coupang_links)
                                        logger.info(f"🎯 Found Coupang link in search results on {portal['name']}, clicking...")
                                        
                                        # 링크까지 스크롤
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", coupang_link)
                                        time.sleep(0.5)
                                        
                                        ActionChains(self.driver).move_to_element(coupang_link).click().perform()
                                        time.sleep(random.uniform(3, 5))
                                        self.already_on_coupang = True
                                        logger.info(f"✅ Successfully navigated to Coupang from {portal['name']} search")
                                    else:
                                        logger.info(f"ℹ️ No visible Coupang links found in {portal['name']} search results")
                                else:
                                    logger.info(f"ℹ️ No Coupang links found in {portal['name']} search results")
                            else:
                                logger.warning(f"⚠️ Could not find search box on {portal['name']}")
                                
                        except Exception as e:
                            logger.debug(f"Coupang search failed on {portal['name']}: {e}")
                    
                    # 상단으로 돌아가기
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(random.uniform(0.5, 1))  # 대기 시간 단축 (1-2초 → 0.5-1초)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Korean portal visit failed: {e}")
            
            # Phase 2 완료까지 대기
            elapsed = time.time() - start_time
            remaining = phase_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)
            
            logger.info("✅ Phase 2 completed: External trust building")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 2 failed: {e}")
            return False

    def _phase3_coupang_exploration(self) -> bool:
        """Phase 3: 쿠팡 사전 탐색"""
        try:
            phase_duration = random.uniform(*self.phase3_duration)
            logger.info(f"🛒 Phase 3 duration: {phase_duration:.1f}s")
            
            start_time = time.time()
            
            # 3.1 쿠팡 메인 페이지 자연스러운 행동
            logger.info("🏠 Coupang main page exploration...")
            try:
                # Phase 2에서 이미 쿠팡에 있으면 불필요한 재이동 방지
                if self.already_on_coupang:
                    current_url = self.driver.current_url
                    if "coupang.com" in current_url:
                        logger.info(f"✅ Already on Coupang from Phase 2: {current_url}")
                        # 메인 페이지가 아니면 메인으로 이동 (자연스럽게)
                        if not (current_url.endswith("coupang.com") or current_url.endswith("coupang.com/")):
                            logger.info("🏠 Navigating to main page from current Coupang page...")
                            # 로고 클릭으로 자연스럽게 메인으로 이동
                            try:
                                logo = self.driver.find_element(By.XPATH, 
                                    "//a[@href='https://www.coupang.com'] | //a[contains(@href, 'coupang.com')] | //img[@alt='Coupang']/parent::a")
                                if logo.is_displayed():
                                    ActionChains(self.driver).move_to_element(logo).click().perform()
                                    time.sleep(random.uniform(1, 2))
                                    logger.info("🏠 Moved to main page via logo click")
                                else:
                                    self.driver.get("https://www.coupang.com")
                                    time.sleep(random.uniform(1, 2))
                            except:
                                self.driver.get("https://www.coupang.com")
                                time.sleep(random.uniform(1, 2))
                        else:
                            logger.info("✅ Already on Coupang main page")
                            time.sleep(random.uniform(0.5, 1))  # 짧은 대기
                    else:
                        # 쿠팡이 아닌 페이지에 있으면 직접 이동
                        logger.info("🔄 Not on Coupang, navigating directly...")
                        self.driver.get("https://www.coupang.com")
                        time.sleep(random.uniform(1, 2))
                else:
                    # Phase 2에서 쿠팡에 오지 않았으면 직접 이동
                    logger.info("🔄 Navigating to Coupang main page...")
                    self.driver.get("https://www.coupang.com")
                    time.sleep(random.uniform(1, 2))
                
                # 메인 페이지 스크롤 (YAML 설정 사용)
                for _ in range(random.randint(*self.main_page_scroll_count)):
                    scroll_amount = random.randint(200, 500)  # 스크롤 양 단축
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(0.5, 1))  # 대기 시간 단축 (1.5-3초 → 0.5-1초)
                
                # 메인 배너나 추천 상품에 호버 (YAML 설정 사용)
                if random.random() < self.banner_hover_probability:
                    try:
                        banners = self.driver.find_elements(By.CSS_SELECTOR, ".banner, .main-banner, .carousel-item")
                        if banners:
                            banner = random.choice(banners)
                            ActionChains(self.driver).move_to_element(banner).perform()
                            time.sleep(random.uniform(0.3, 0.8))  # 대기 시간 단축 (1-2초 → 0.3-0.8초)
                    except:
                        pass
                
                # 상단으로 돌아가기
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.warning(f"⚠️ Main page exploration failed: {e}")
            
            # 3.2 카테고리 메뉴를 통한 자연스러운 탐색 (실제 사용자처럼)
            if self.pre_exploration:
                # 실제 카테고리 메뉴 열어서 탐색
                categories_to_explore = random.randint(0, 1)  # 0-1개 카테고리 탐색
                
                for _ in range(categories_to_explore):
                    logger.info("📂 Exploring categories through menu navigation...")
                    
                    try:
                        # 1. 반드시 카테고리 메뉴에 hover
                        category_menu = self.driver.find_element(By.XPATH, "//*[text()='카테고리']")
                        ActionChains(self.driver).move_to_element(category_menu).perform()
                        time.sleep(random.uniform(0.5, 1.0))  # 드롭다운 열릴 때까지 대기

                        # 2. 드롭다운 내 카테고리 링크 찾기
                        category_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/np/categories/')]")
                        # 3. 보이는 카테고리만 필터링
                        visible_categories = []
                        for link in category_links:
                            try:
                                if link.is_displayed() and link.is_enabled() and link.size['height'] > 0:
                                    visible_categories.append(link)
                            except:
                                continue
                        if visible_categories:
                            selected_category = random.choice(visible_categories)
                            category_name = selected_category.text or "Unknown"
                            logger.info(f"🎯 Clicking category: {category_name}")
                            try:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", selected_category)
                                time.sleep(0.3)
                                ActionChains(self.driver).move_to_element(selected_category).click().perform()
                            except Exception as e:
                                logger.warning(f"⚠️ Category click failed: {e}")
                                # 카테고리 페이지에서 자연스러운 행동
                                logger.info(f"🛍️ Exploring category page: {category_name}")
                                self.driver.execute_script("window.scrollBy(0, 300);")
                                time.sleep(random.uniform(0.5, 1))
                                # 상품에 호버 (20% 확률)
                                if random.random() < 0.2:
                                    try:
                                        products = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='products/'], .product-item, .baby-product")
                                        if products:
                                            product = random.choice(products[:5])
                                            ActionChains(self.driver).move_to_element(product).perform()
                                            time.sleep(random.uniform(0.8, 1.5))
                                            logger.info("👆 Hovered on product")
                                    except:
                                        pass
                                # 메인으로 복귀
                                try:
                                    logo = self.driver.find_element(By.XPATH, "//a[@href='https://www.coupang.com'] | //a[contains(@href, 'coupang.com')] | //img[@alt='Coupang']/parent::a | //a[text()='Coupang']")
                                    if logo.is_displayed() and logo.size['height'] > 0:
                                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", logo)
                                        time.sleep(0.3)
                                        ActionChains(self.driver).move_to_element(logo).click().perform()
                                        time.sleep(random.uniform(1, 1.5))
                                        logger.info("🏠 Returned to main page via logo click")
                                    else:
                                        self.driver.get("https://www.coupang.com")
                                        time.sleep(random.uniform(1, 1.5))
                                        logger.info("🏠 Returned to main page via direct navigation")
                                except:
                                    self.driver.get("https://www.coupang.com")
                                    time.sleep(random.uniform(1, 1.5))
                                    logger.info("🏠 Returned to main page via fallback navigation")
                        else:
                            logger.warning("⚠️ No visible categories found after dropdown opened")                  
                    except Exception as e:
                        logger.warning(f"⚠️ Category menu interaction failed: {e}")
                        # 실패시 메인 페이지 확인
                        try:
                            self.driver.get("https://www.coupang.com")
                            time.sleep(random.uniform(2, 3))
                        except:
                            pass
            
            # 3.3 특별 페이지 탐색 (클릭 기반 - YAML 설정 사용)
            if self.special_pages_enabled and random.random() < self.special_pages_visit_probability:
                logger.info("⭐ Looking for special pages to explore...")
                
                try:
                    # 메인 페이지에서 특별 페이지 링크 찾기 (Playwright 분석 결과 반영)
                    
                    special_links = []
                    
                    # CSS 선택자로 찾기
                    css_selectors = [
                        "a[href*='goldbox']",                    # 골드박스
                        "a[href*='campaigns']",                  # 캠페인 페이지들  
                        "a[href*='event']",                      # 이벤트
                        "a[href*='coupangplay']",                # 쿠팡플레이
                        "a[href*='coupangglobal']",              # 로켓직구
                        "a[href*='omp']",                        # 판매자특가
                        "a[href*='coupangbenefit']",             # 이벤트/쿠폰
                        "a[href*='pages.coupang.com']"           # 쿠팡 특별 페이지들
                    ]
                    
                    for selector in css_selectors:
                        try:
                            links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            special_links.extend(links[:3])  # 각 타입별로 최대 3개
                        except:
                            continue
                    
                    # XPath로 텍스트 기반 링크 찾기
                    try:
                        xpath_links = self.driver.find_elements(By.XPATH, 
                            "//a[text()='로켓배송' or text()='로켓프레시' or text()='골드박스' or text()='이달의신상' or text()='판매자특가' or text()='와우회원할인' or text()='이벤트/쿠폰' or text()='반품마켓' or text()='착한상점' or text()='기획전']")
                        special_links.extend(xpath_links[:5])  # 최대 5개
                    except:
                        pass
                    
                    if special_links:
                        # 보이는 특별 페이지만 필터링
                        visible_special_links = []
                        for link in special_links:
                            try:
                                if link.is_displayed() and link.is_enabled() and link.size['height'] > 0:
                                    visible_special_links.append(link)
                            except:
                                continue
                        
                        if visible_special_links:
                            # 보이는 특별 페이지 중에서 랜덤 선택
                            selected_link = random.choice(visible_special_links)
                            link_text = selected_link.text or selected_link.get_attribute("title") or "Special Page"
                            logger.info(f"🎯 Clicking special page: {link_text}")
                            
                            try:
                                # 요소까지 스크롤
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", selected_link)
                                time.sleep(0.5)
                                
                                # 특별 페이지 클릭 (Bezier 마우스 사용)
                                if self.use_bezier and self.bezier_mouse and selected_link.is_displayed():
                                    try:
                                        self.bezier_mouse.click_with_bezier_move(selected_link, 'normal')
                                    except Exception as e:
                                        logger.debug(f"Bezier click failed, using fallback: {e}")
                                        ActionChains(self.driver).move_to_element(selected_link).click().perform()
                                else:
                                    ActionChains(self.driver).move_to_element(selected_link).click().perform()
                                    
                            except Exception as e:
                                logger.warning(f"⚠️ Special page click failed: {e}")
                        else:
                            logger.warning("⚠️ No visible special page links found")
                        
                        time.sleep(random.uniform(1, 2))  # 대기 시간 단축 (3-5초 → 1-2초)
                        
                        logger.info(f"⭐ Exploring special page: {link_text}")
                        
                        # 특별 페이지에서 간단한 탐색 (빠르게)
                        self.driver.execute_script("window.scrollBy(0, 300);")  # 스크롤 양 단축
                        time.sleep(random.uniform(0.5, 1))  # 대기 시간 단축 (2-4초 → 0.5-1초)
                        
                        # 특별 페이지의 상품이나 요소에 호버 (YAML 설정 사용)
                        if random.random() < self.special_pages_interaction_probability:
                            try:
                                interactive_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                                    "a[href*='products/'], .product-item, .deal-item, .promotion-item")
                                if interactive_elements:
                                    element = random.choice(interactive_elements[:5])
                                    ActionChains(self.driver).move_to_element(element).perform()
                                    time.sleep(random.uniform(0.5, 1))  # 대기 시간 단축 (1-2초 → 0.5-1초)
                                    logger.info("👆 Interacted with special page element")
                            except:
                                pass
                        
                        # 메인으로 돌아가기 (Bezier 마우스 사용)
                        try:
                            logo = self.driver.find_element(By.XPATH, 
                                "//a[@href='https://www.coupang.com'] | //a[contains(@href, 'coupang.com')] | //img[@alt='Coupang']/parent::a | //a[text()='Coupang']")
                            
                            # 로고가 보이는지 확인
                            if logo.is_displayed() and logo.size['height'] > 0:
                                # 로고까지 스크롤
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", logo)
                                time.sleep(0.3)
                                
                                if self.use_bezier and self.bezier_mouse and logo.is_displayed():
                                    try:
                                        self.bezier_mouse.click_with_bezier_move(logo, 'normal')
                                    except Exception as e:
                                        logger.debug(f"Bezier click failed, using fallback: {e}")
                                        ActionChains(self.driver).move_to_element(logo).click().perform()
                                else:
                                    ActionChains(self.driver).move_to_element(logo).click().perform()
                                
                                time.sleep(random.uniform(1, 1.5))  # 대기 시간 단축 (2-3초 → 1-1.5초)
                                logger.info("🏠 Returned to main page from special page")
                            else:
                                # 로고가 보이지 않으면 직접 이동
                                self.driver.get("https://www.coupang.com")
                                time.sleep(random.uniform(1, 1.5))  # 대기 시간 단축 (2-3초 → 1-1.5초)
                                logger.info("🏠 Returned to main page via direct navigation")
                        except:
                            self.driver.get("https://www.coupang.com")
                            time.sleep(random.uniform(1, 1.5))  # 대기 시간 단축 (2-3초 → 1-1.5초)
                            logger.info("🏠 Returned to main page via fallback navigation")
                        
                    else:
                        logger.info("ℹ️ No special page links found on main page")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Special page exploration failed: {e}")
                    # 실패시 메인 페이지로 복귀
                    try:
                        self.driver.get("https://www.coupang.com")
                        time.sleep(random.uniform(2, 3))
                    except:
                        pass
            
            # Phase 3 완료까지 대기
            elapsed = time.time() - start_time
            remaining = phase_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)
            
            logger.info("✅ Phase 3 completed: Coupang exploration")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 3 failed: {e}")
            return False

    def _phase4_final_stabilization(self) -> bool:
        """Phase 4: 최종 안정화"""
        try:
            phase_duration = random.uniform(*self.phase4_duration)
            logger.info(f"🎯 Phase 4 duration: {phase_duration:.1f}s")
            
            start_time = time.time()
            
            # 4.1 마이크로 인터랙션들
            logger.info("🔬 Executing micro-interactions...")
            
            # 쿠팡 메인에서 미세한 행동들 (이미 쿠팡에 있으면 재이동하지 않음)
            try:
                current_url = self.driver.current_url
                if "coupang.com" not in current_url:
                    logger.info("🔄 Not on Coupang, navigating for Phase 4...")
                    self.driver.get("https://www.coupang.com")
                    time.sleep(random.uniform(0.5, 1))
                else:
                    logger.info(f"✅ Already on Coupang for Phase 4: {current_url}")
                    # 메인 페이지가 아니면 로고 클릭으로 메인으로
                    if not (current_url.endswith("coupang.com") or current_url.endswith("coupang.com/")):
                        try:
                            logo = self.driver.find_element(By.XPATH, 
                                "//a[@href='https://www.coupang.com'] | //a[contains(@href, 'coupang.com')] | //img[@alt='Coupang']/parent::a")
                            if logo.is_displayed():
                                ActionChains(self.driver).move_to_element(logo).click().perform()
                                time.sleep(random.uniform(0.5, 1))
                                logger.info("🏠 Moved to main page for Phase 4")
                        except:
                            pass
                
                # 검색창 클릭했다가 취소 (YAML 설정 사용) #TODO 수정 필요!
                if random.random() < self.search_box_click_cancel_probability:
                    try:
                        # 2. aria-label='쿠팡 상품 검색' textbox 역할 요소 명확하게 찾기
                        search_box = self.driver.find_element(By.XPATH, "//*[@aria-label='쿠팡 상품 검색' and (@role='textbox' or self::input)]")
                        if search_box.is_displayed() and search_box.is_enabled():
                            ActionChains(self.driver).move_to_element(search_box).click().perform()
                            time.sleep(random.uniform(0.2, 0.5))
                            search_box.send_keys(Keys.ESCAPE)
                            time.sleep(random.uniform(0.2, 0.5))
                            logger.info("🔍 Search box micro-interaction completed")
                        else:
                            logger.warning("🔍 Search box micro-interaction skipped: 검색창이 보이지 않거나 비활성화됨")
                    except Exception as e:
                        logger.warning(f"🔍 Search box micro-interaction skipped: {e}")

                # 카테고리 메뉴 엿보기 (YAML 설정 사용)
                if random.random() < self.category_menu_hover_probability:
                    try:
                        # 실제 DOM: 텍스트가 '카테고리'인 div
                        category_btn = self.driver.find_element(By.XPATH, "//*[text()='카테고리']")
                        ActionChains(self.driver).move_to_element(category_btn).perform()
                        time.sleep(random.uniform(0.3, 0.8))
                        logger.info("📂 Category menu micro-interaction completed")
                    except Exception as e:
                        logger.info("🔍 Category menu micro-interaction skipped")
                        pass
                
                # 미세한 스크롤들 (YAML 설정 사용)
                for _ in range(random.randint(*self.micro_scroll_count)):
                    scroll_amount = random.randint(100, 300)  # 스크롤 양 단축 (100-300 → 50-150)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(0.2, 0.5))  # 대기 시간 단축 (0.8-1.5초 → 0.2-0.5초)
                
            except Exception as e:
                logger.warning(f"⚠️ Micro-interactions failed: {e}")
            
            # 4.2 브라우저 세션 안정화 신호
            if self.browser_trust_signals:
                logger.info("🔒 Generating browser session stabilization signals...")
                
                try:
                    # localStorage/sessionStorage 값 설정
                    self.driver.execute_script("""
                        // Set some realistic browser storage values
                        try {
                            localStorage.setItem('coupang_visit_time', Date.now().toString());
                            localStorage.setItem('user_preference_theme', 'default');
                            sessionStorage.setItem('session_start', Date.now().toString());
                            sessionStorage.setItem('page_views', '3');
                        } catch(e) {
                            console.log('Storage operation failed:', e);
                        }
                        
                        // Simulate some realistic browser events
                        window.dispatchEvent(new Event('beforeunload'));
                        setTimeout(() => {
                            window.dispatchEvent(new Event('load'));
                        }, 100);
                    """)
                    
                    # 쿠키 mature 시간 확보 (빠르게)
                    time.sleep(random.uniform(0.5, 1))  # 대기 시간 단축 (2-4초 → 0.5-1초)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Browser stabilization signals failed: {e}")
            
            # 4.3 최종 "사용자가 익숙해진" 신호
            try:
                # 마지막으로 자연스러운 페이지 상호작용 (빠르게)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(random.uniform(0.3, 0.8))  # 대기 시간 단축 (1-2초 → 0.3-0.8초)
                
                # 페이지에서 마지막 호버 동작 (YAML 설정 사용)
                if random.random() < self.final_hover_probability:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, "a, button")
                        if elements:
                                element = random.choice(elements[:self.elements_to_consider])  # YAML 설정 사용
                                ActionChains(self.driver).move_to_element(element).perform()
                                time.sleep(random.uniform(0.2, 0.5))  # 대기 시간 단축 (0.5-1초 → 0.2-0.5초)
                    except:
                        pass
                    
            except Exception as e:
                logger.warning(f"⚠️ Final user familiarity signals failed: {e}")
            
            # Phase 4 완료까지 대기
            elapsed = time.time() - start_time
            remaining = phase_duration - elapsed
            if remaining > 0:
                time.sleep(remaining)
            
            logger.info("✅ Phase 4 completed: Final stabilization")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 4 failed: {e}")
            return False


def get_session_warmup_manager(driver):
    """SessionWarmupManager 인스턴스 반환"""
    return SessionWarmupManager(driver) 