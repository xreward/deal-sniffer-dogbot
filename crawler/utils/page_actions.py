#!/usr/bin/env python
"""
Page Actions Utility
Common page action utilities for rocket delivery selection, sales volume sorting, and pagination
"""

import time
import random
import logging
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from crawler.managers.config_cache import get_crawler_config
from crawler.managers.crawler_manager import crawler_manager, SELECTORS, TIMEOUTS

logger = logging.getLogger(__name__)


class PageActionsUtil:
    """Utility class for common page actions like rocket delivery, sales sorting, and pagination"""
    
    def __init__(self, driver):
        """Initialize with selenium driver"""
        self.driver = driver
        self._load_configs()
    
    def _load_configs(self):
        """Load configuration from cache"""
        try:
            crawling_config = get_crawler_config('crawling_behavior', {})
            self.auto_rocket_delivery_config = crawling_config.get('auto_rocket_delivery', {})
            self.auto_sort_config = crawling_config.get('auto_sort_by_sales', {})
            self.auto_pagination_config = crawling_config.get('auto_pagination', {})
            
            logger.debug("✅ Page actions config loaded from cache")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load page actions config: {e}")
            # Fallback defaults
            self.auto_rocket_delivery_config = {
                'enabled': True,
                'retry_attempts': 3,
                'delay_after_selection': {'min': 1500, 'max': 3000}
            }
            self.auto_sort_config = {
                'enabled': True,
                'retry_attempts': 3,
                'delay_after_sort': {'min': 2000, 'max': 4000}
            }
            self.auto_pagination_config = {
                'enabled': True,
                'delay_between_pages': {'min': 3000, 'max': 5000}
            }

    # 🔥 NEW: 페이지네이션 관련 기능들 추가
    
    def has_next_page(self) -> bool:
        """
        다음 페이지 버튼의 HTML 구조를 확인하여 더 이상 넘어갈 페이지가 있는지 확인
        
        Returns:
            bool: True if next page exists, False if last page
        """
        try:
            if not self.driver:
                logger.error("❌ Browser driver is not available")
                return False
            
            # 다음 페이지 버튼 존재 여부 확인 (활성화된 링크)
            active_next_selectors = [
                'a.Pagination_nextBtn__TU6Yt[href]',           # 활성화된 다음 버튼 (링크)
                'a[title="다음"][href*="page="]',               # href가 있는 다음 버튼
                'a[data-page="next"][href]',                   # data-page가 next이고 href가 있는 버튼
            ]
            
            for selector in active_next_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(el.is_displayed() for el in elements):
                        logger.info(f"✅ Active next page button found: {selector}")
                        return True
                except Exception as e:
                    logger.debug(f"Active next selector {selector} failed: {e}")
                    continue
            
            # 비활성화된 다음 페이지 버튼 확인 (마지막 페이지 표시)
            disabled_next_selectors = [
                'span.Pagination_nextBtn__TU6Yt.Pagination_disabled__EbhY6',  # 비활성화된 다음 버튼
                'span[title="다음"].Pagination_disabled__EbhY6',              # disabled 클래스가 있는 span
                'span[title="다음"]:not([href])',                            # href가 없는 다음 버튼
            ]
            
            for selector in disabled_next_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(el.is_displayed() for el in elements):
                        logger.info(f"🏁 Disabled next page button found - reached last page: {selector}")
                        return False
                except Exception as e:
                    logger.debug(f"Disabled next selector {selector} failed: {e}")
                    continue
            
            # 아무것도 찾지 못한 경우 (안전을 위해 중단)
            logger.warning("⚠️ Could not determine next page status - stopping pagination")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking next page availability: {e}")
            return False

    def go_to_next_page(self) -> bool:
        """다음 페이지로 이동"""
        try:
            if not self.driver:
                logger.error("❌ Browser driver is not available")
                return False
                
            # 여러 가지 다음 페이지 셀렉터 시도
            next_page_selectors = [
                'button[aria-label="다음 페이지"]',           # 실제 다음 페이지 버튼
                'a[aria-label="다음 페이지"]',               # 링크 형태
                '.pagination .next',                        # 일반적인 페이지네이션
                'button:contains("다음")',                   # 텍스트 기반
                'a:contains(">")',                          # 화살표 기반
            ]
            
            for selector in next_page_selectors:
                try:
                    if 'contains' in selector:
                        # XPath 방식으로 텍스트 검색
                        if '다음' in selector:
                            xpath_selector = "//*[contains(text(), '다음')]"
                        else:
                            xpath_selector = "//*[contains(text(), '>')]"
                        element = self.driver.find_element(By.XPATH, xpath_selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element.is_displayed() and element.is_enabled():
                        # 다음 페이지 버튼을 찾기 위한 자연스러운 스크롤링
                        logger.info("📜 Performing human-like scrolling to find next page button...")
                        self._scroll_to_find_next_page_button(element)
                        
                        # ActionChains를 사용한 자연스러운 클릭
                        ActionChains(self.driver).move_to_element(element).click().perform()
                        logger.info(f"✅ Clicked next page using selector: {selector}")
                        return True
                        
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            logger.info("🏁 Next page button not found or not clickable")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error going to next page: {e}")
            return False
    
    def _scroll_to_find_next_page_button(self, target_element):
        """다음 페이지 버튼을 찾기 위한 자연스러운 스크롤링"""
        try:
            if not self.driver:
                logger.error("❌ Browser driver is not available")
                return False
                
            # Get scrolling config from crawler_manager
            scrolling_config = crawler_manager.get_scrolling_config()
            reading_time_range = scrolling_config.get('reading_time_range', [0.8, 2.0])
            position_randomness = scrolling_config.get('position_randomness', 100)
            
            # Get page height and target element position
            page_height = self.driver.execute_script("return document.body.scrollHeight")
            target_position = self.driver.execute_script("return arguments[0].offsetTop;", target_element)
            
            # 현재 스크롤 위치
            current_position = self.driver.execute_script("return window.pageYOffset;")
            
            # 자연스러운 스크롤링: 목표 위치까지 여러 단계로 나누어 스크롤
            steps = random.randint(2, 4)  # 2-4단계로 나누어 스크롤
            step_size = (target_position - current_position) // steps if steps > 0 else 0
            
            logger.info(f"📜 Scrolling to next page button in {steps} natural steps...")
            
            for i in range(steps):
                # 무작위성을 추가한 스크롤 위치 계산
                if i == steps - 1:
                    # 마지막 단계에서는 정확히 타겟 위치로 (약간의 여유 추가)
                    next_position = target_position - 100  # 버튼이 화면 중앙 근처에 오도록
                else:
                    # 중간 단계에서는 무작위성 추가
                    next_position = current_position + step_size + random.randint(-position_randomness, position_randomness)
                
                # 스크롤 범위 제한
                next_position = max(0, min(next_position, page_height))
                
                # 자연스러운 스크롤 실행
                self.driver.execute_script(f"window.scrollTo(0, {next_position});")
                current_position = next_position
                
                # 자연스러운 읽기 시간
                reading_time = random.uniform(reading_time_range[0], reading_time_range[1])
                time.sleep(reading_time)
                
                logger.debug(f"📜 Scroll step {i+1}/{steps}: position {next_position}")
            
            # 최종적으로 타겟 요소가 화면 중앙에 오도록 조정
            if self.driver:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", target_element)
            
            # 마지막 자연스러운 대기
            time.sleep(random.uniform(0.5, 1.0))
            
            logger.info("✅ Natural scrolling to next page button completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in natural scrolling to next page button: {e}")
            # 실패 시 기본 스크롤로 fallback
            try:
                if self.driver:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_element)
                    time.sleep(random.uniform(0.5, 1.0))
            except:
                pass
            return False

    def execute_pagination_with_anti_bot(self, current_page_num: int) -> bool:
        """
        페이지 이동 후 anti-bot 우회 시퀀스 실행
        
        Args:
            current_page_num: 현재 페이지 번호 (로깅용)
            
        Returns:
            bool: 성공 여부
        """
        try:
            logger.info(f"🛡️ Executing anti-bot sequence for page {current_page_num}")
            
            # 페이지 로딩 대기
            WebDriverWait(self.driver, TIMEOUTS['navigation']).until(
                EC.presence_of_element_located((By.TAG_NAME, SELECTORS['body']))
            )
            
            # Anti-bot 추적 시퀀스 (browser에서 가져옴)
            # Note: 이 부분은 browser 객체가 필요하므로 crawler에서 호출해야 함
            
            logger.info(f"✅ Page {current_page_num}: Anti-bot sequence setup completed")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Page {current_page_num}: Anti-bot sequence failed: {e}")
            return False

    def wait_between_pages(self):
        """페이지 간 딜레이"""
        delay_min = self.auto_pagination_config.get('delay_between_pages', {}).get('min', 3000)
        delay_max = self.auto_pagination_config.get('delay_between_pages', {}).get('max', 5000)
        delay_seconds = random.uniform(delay_min/1000, delay_max/1000)
        time.sleep(delay_seconds)
    
    def execute_page_load_actions(self, page_context: str = "general") -> Dict[str, bool]:
        """
        Execute standard page load actions (rocket delivery + sales sort)
        
        Args:
            page_context: Context for logging (e.g., "navigation", "page_1", etc.)
            
        Returns:
            Dictionary with success status for each action
        """
        results = {
            'rocket_delivery': False,
            'sales_sort': False
        }
        
        try:
            # Brief wait for page elements to load
            time.sleep(2)
            
            # 🚀 Rocket delivery selection
            if self.auto_rocket_delivery_config.get('enabled', True):
                results['rocket_delivery'] = self._select_rocket_delivery_with_retry(page_context)
                
                if results['rocket_delivery']:
                    # Wait after successful selection
                    self._wait_after_rocket_selection()
            else:
                logger.info(f"📋 {page_context}: Auto rocket delivery disabled in configuration")
            
            # 🔥 Sales volume sorting
            if self.auto_sort_config.get('enabled', True):
                results['sales_sort'] = self._click_sales_volume_sort_with_retry(page_context)
                
                if results['sales_sort']:
                    # Wait after successful sort
                    self._wait_after_sales_sort()
            else:
                logger.info(f"📋 {page_context}: Auto sales sort disabled in configuration")
                
        except Exception as e:
            logger.error(f"❌ Error in page load actions for {page_context}: {e}")
        
        return results
    
    def _select_rocket_delivery_with_retry(self, context: str) -> bool:
        """Select rocket delivery with retry logic"""
        retry_attempts = self.auto_rocket_delivery_config.get('retry_attempts', 3)
        
        for attempt in range(retry_attempts):
            if self._select_rocket_delivery():
                logger.info(f"✅ {context}: Successfully selected rocket delivery (attempt {attempt + 1})")
                return True
            else:
                logger.warning(f"⚠️ {context}: Rocket delivery selection failed (attempt {attempt + 1}/{retry_attempts})")
                if attempt < retry_attempts - 1:
                    time.sleep(1)  # Wait before retry
        
        logger.warning(f"⚠️ {context}: Rocket delivery selection failed after all attempts")
        return False
    
    def _select_rocket_delivery(self) -> bool:
        """Core rocket delivery selection logic"""
        try:
            if not self.driver:
                return False
                
            # 여러 가능한 rocket delivery 셀렉터들 시도
            rocket_selectors = [
                'label[data-component-name="deliveryFilterOption-rocket_luxury,rocket_wow,coupang_global"]',  # 새로운 형식
                'label[data-component-name="deliveryFilterOption-rocket_luxury,rocket,coupang_global"]',      # 기존 형식
                'label[data-component-name*="deliveryFilterOption-rocket"]',                                   # 포함하는 형식
                'li.filter-function-bar-service label[data-component-name*="rocket"]'                         # 더 구체적인 형식
            ]
            
            rocket_label = None
            
            # 각 셀렉터를 순서대로 시도
            for selector in rocket_selectors:
                try:
                    rocket_labels = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if rocket_labels:
                        rocket_label = rocket_labels[0]
                        logger.debug(f"✅ Found rocket delivery with selector: {selector}")
                        break
                except:
                    continue
            
            if not rocket_label:
                logger.debug("❌ No rocket delivery label found with any selector")
                return False
                
            class_attr = rocket_label.get_attribute('class') or ''
            
            # Check status
            if 'disabled' in class_attr:
                logger.debug("⚠️ Rocket delivery is disabled")
                return False
            elif 'selected' in class_attr:
                logger.debug("✅ Rocket delivery already selected")
                return True
            else:
                # Click to select if not selected
                logger.debug("🖱️ Clicking rocket delivery label")
                self.driver.execute_script("arguments[0].click();", rocket_label)
                time.sleep(0.5)
                
                # Verify selection
                updated_class = rocket_label.get_attribute('class') or ''
                success = 'selected' in updated_class
                
                if success:
                    logger.debug("✅ Rocket delivery successfully selected")
                else:
                    logger.debug("❌ Rocket delivery selection verification failed")
                
                return success
                    
        except Exception as e:
            logger.debug(f"Rocket delivery selection failed: {e}")
            return False
    
    def _click_sales_volume_sort_with_retry(self, context: str) -> bool:
        """Click sales volume sort with retry logic"""
        retry_attempts = self.auto_sort_config.get('retry_attempts', 3)
        
        for attempt in range(retry_attempts):
            if self._click_sales_volume_sort():
                logger.info(f"✅ {context}: Successfully clicked sales volume sort (attempt {attempt + 1})")
                return True
            else:
                logger.warning(f"⚠️ {context}: Sales volume sort failed (attempt {attempt + 1}/{retry_attempts})")
                if attempt < retry_attempts - 1:
                    time.sleep(1)  # Wait before retry
        
        logger.warning(f"⚠️ {context}: Sales volume sort failed after all attempts")
        return False
    
    def _click_sales_volume_sort(self) -> bool:
        """Core sales volume sort logic"""
        try:
            if not self.driver:
                return False
                
            # Sales sort button selectors from config
            sales_sort_selectors = [
                'button[data-testid="sorter-salesVolume"]',
                'button:contains("판매량순")',
                'a:contains("판매량순")',
                '.sorter button:contains("판매량")',
            ]
            
            for selector in sales_sort_selectors:
                try:
                    if 'contains' in selector:
                        # XPath approach for text search
                        xpath_selector = "//*[contains(text(), '판매량')]"
                        element = self.driver.find_element(By.XPATH, xpath_selector)
                    else:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    if element.is_displayed() and element.is_enabled():
                        # Natural click using ActionChains
                        ActionChains(self.driver).move_to_element(element).click().perform()
                        return True
                        
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.debug(f"Sales volume sort click failed: {e}")
            return False
    
    def _wait_after_rocket_selection(self):
        """Wait after rocket delivery selection"""
        delay_min = self.auto_rocket_delivery_config.get('delay_after_selection', {}).get('min', 1500)
        delay_max = self.auto_rocket_delivery_config.get('delay_after_selection', {}).get('max', 3000)
        delay_seconds = random.uniform(delay_min/1000, delay_max/1000)
        time.sleep(delay_seconds)
    
    def _wait_after_sales_sort(self):
        """Wait after sales volume sort"""
        delay_min = self.auto_sort_config.get('delay_after_sort', {}).get('min', 2000)
        delay_max = self.auto_sort_config.get('delay_after_sort', {}).get('max', 4000)
        delay_seconds = random.uniform(delay_min/1000, delay_max/1000)
        time.sleep(delay_seconds)
    
    def select_rocket_delivery_only(self, context: str = "manual") -> bool:
        """Select only rocket delivery (for specific use cases)"""
        if not self.auto_rocket_delivery_config.get('enabled', True):
            logger.info(f"📋 {context}: Auto rocket delivery disabled")
            return False
            
        success = self._select_rocket_delivery_with_retry(context)
        if success:
            self._wait_after_rocket_selection()
        return success
    
    def click_sales_sort_only(self, context: str = "manual") -> bool:
        """Click only sales volume sort (for specific use cases)"""
        if not self.auto_sort_config.get('enabled', True):
            logger.info(f"📋 {context}: Auto sales sort disabled")
            return False
            
        success = self._click_sales_volume_sort_with_retry(context)
        if success:
            self._wait_after_sales_sort()
        return success 