"""
Crawler Configuration Manager
쿠팡 크롤러의 전체 설정(Anti-Bot 우회, 크롤링 동작, 페이지네이션 등)을 로드하고 관리하는 모듈
"""

import os
import json
import random
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from stealth_browser.managers.config_cache import get_config_cache, get_crawler_config

logger = logging.getLogger(__name__)

class CrawlerManager:
    """크롤러 전체 설정을 관리하는 클래스 (Anti-Detection, 크롤링 동작, 페이지네이션 등)"""
    
    def __init__(self):
        self.config_dir = Path(__file__).parent.parent / "config"  # ../config로 변경
        self.config_cache = get_config_cache()
        self.js_template = ""
        self._load_js_template()
    
    @property 
    def config_data(self) -> Dict[str, Any]:
        """Get config data from cache"""
        return self.config_cache.get_config('crawler_config')
    
    def _load_js_template(self):
        """JavaScript 템플릿 파일을 로드합니다"""
        js_file = self.config_dir / "fingerprint_injection.js"
        
        try:
            with open(js_file, 'r', encoding='utf-8') as f:
                self.js_template = f.read()
            logger.info("✅ JavaScript template loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load JavaScript template: {e}")
            self.js_template = ""
    
    def get_chrome_options(self) -> List[str]:
        """Chrome 옵션 목록을 반환합니다"""
        return self.config_data.get('chrome_options', {}).get('basic', [])
    
    def get_http_headers(self) -> Dict[str, str]:
        """HTTP 헤더를 반환합니다"""
        headers = {}
        basic_headers = self.config_data.get('http_headers', {}).get('basic', {})
        security_headers = self.config_data.get('http_headers', {}).get('security', {})
        
        headers.update(basic_headers)
        headers.update(security_headers)
        
        return headers
    
    def get_http_headers_as_chrome_args(self) -> List[str]:
        """Chrome 인수 형태로 HTTP 헤더를 반환합니다"""
        headers = self.get_http_headers()
        return [f"--headers={key}: {value}" for key, value in headers.items()]
    
    def get_essential_cookies(self) -> Dict[str, Any]:
        """Essential cookies 설정을 반환합니다"""
        return self.config_data.get('essential_cookies', {})
    
    def get_static_cookies(self) -> Dict[str, str]:
        """정적 쿠키 목록을 반환합니다"""
        return self.config_data.get('essential_cookies', {}).get('static', {})
    
    def get_dynamic_cookie_names(self) -> List[str]:
        """동적 쿠키 이름 목록을 반환합니다"""
        return self.config_data.get('essential_cookies', {}).get('dynamic', [])
    
    def get_human_simulation_config(self) -> Dict[str, Any]:
        """Human behavior simulation 설정을 반환합니다"""
        return self.config_data.get('human_simulation', {})
    
    def get_scrolling_config(self) -> Dict[str, Any]:
        """스크롤링 관련 설정을 반환합니다"""
        return self.config_data.get('human_simulation', {}).get('scrolling', {})
    
    def get_delay_config(self) -> Dict[str, Any]:
        """딜레이 관련 설정을 반환합니다"""
        return self.config_data.get('human_simulation', {}).get('delays', {})
    
    def get_fallback_settings(self) -> Dict[str, Any]:
        """Fallback 설정을 반환합니다"""
        return self.config_data.get('fallback_settings', {})
    
    def get_referrer_settings(self) -> Dict[str, Any]:
        """Referrer 설정을 반환합니다"""
        return self.config_data.get('referrer_settings', {})
    
    def get_referrer_url(self, url: str) -> str:
        """URL에 따른 적절한 referrer를 반환합니다"""
        referrer_settings = self.get_referrer_settings()
        rules = referrer_settings.get('rules', {})
        
        if 'categories' in url:
            referrer_key = rules.get('categories_page', 'coupang_main')
        else:
            referrer_key = rules.get('default', 'google_search')
        
        # referrer_settings는 Dict[str, str]이므로 안전하게 접근
        if isinstance(referrer_key, str) and referrer_key in referrer_settings:
            return referrer_settings[referrer_key]
        else:
            return 'https://www.google.com/'
    
    def generate_javascript_code(self, profile_data: Dict[str, Any]) -> str:
        """프로필 데이터를 사용하여 JavaScript 코드를 생성합니다"""
        if not self.js_template:
            logger.error("❌ JavaScript template not loaded")
            return ""
        
        # 프로필에서 fingerprint 설정 추출
        fingerprint = profile_data.get('fingerprint', {})
        hardware_cores = profile_data.get('hardware_cores', 8)
        
        # 플레이스홀더 교체를 위한 값들
        replacements = {
            'PLUGIN_COUNT': str(fingerprint.get('plugin_count', 23)),
            'HARDWARE_CORES': str(hardware_cores),
            'PRIMARY_LANGUAGE': fingerprint.get('primary_language', 'ko-KR'),
            'LANGUAGES': json.dumps(fingerprint.get('languages', ['ko-KR', 'ko', 'en-US', 'en'])),
            'TIMEZONE_OFFSET': str(fingerprint.get('timezone_offset', -540)),
            'COLOR_DEPTH': str(fingerprint.get('color_depth', 24)),
            'CANVAS_NOISE_LEVEL': str(fingerprint.get('canvas_noise_level', 2)),
            'WEBGL_RENDERER': fingerprint.get('webgl_renderer', 'WebKit WebGL'),
            'WEBGL_VENDOR': fingerprint.get('webgl_vendor', 'WebKit'),
            'WEBGL_VERSION': fingerprint.get('webgl_version', 'WebGL 1.0 (OpenGL ES 2.0 Chromium)'),
            'WEBGL_SHADER_VERSION': fingerprint.get('webgl_shader_version', 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)'),
            'WEBGL2_VERSION': fingerprint.get('webgl_version', 'WebGL 2.0 (OpenGL ES 3.0 Chromium)'),
            'WEBGL2_SHADER_VERSION': fingerprint.get('webgl_shader_version', 'WebGL GLSL ES 3.00 (OpenGL ES GLSL ES 3.0 Chromium)')
        }
        
        # 플레이스홀더를 실제 값으로 교체
        js_code = self.js_template
        for placeholder, value in replacements.items():
            js_code = js_code.replace(f'{{{placeholder}}}', value)
        
        logger.info(f"📄 Generated JavaScript code for profile: {profile_data.get('name', 'unknown')}")
        return js_code
    
    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정값을 반환합니다"""
        return {
            'chrome_options': {
                'basic': [
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--ignore-certificate-errors',
                    '--lang=ko-KR'
                ]
            },
            'http_headers': {
                'basic': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br'
                }
            },
            'essential_cookies': {
                'static': {
                    'x-coupang-origin-region': 'KR',
                    'x-coupang-target-market': 'KR'
                },
                'dynamic': ['PCID', '_coupang_session']
            },
            'human_simulation': {
                'scrolling': {
                    'count_range': [3, 5],
                    'reading_time_range': [0.8, 2.0]
                }
            },
            'fallback_settings': {
                'hardware_cores': 8,
                'webgl_renderer': 'WebKit WebGL',
                'webgl_vendor': 'WebKit'
            }
        }

    # === Anti-Bot Tracking 관련 메서드들 ===
    
    def get_mercury_config(self) -> Dict[str, Any]:
        """Get Mercury tracking configuration"""
        config = self.config_data.get('anti_bot_tracking', {}).get('mercury', {})
        return config
    
    def get_ljc_config(self) -> Dict[str, Any]:
        """Get LJC API configuration"""
        config = self.config_data.get('anti_bot_tracking', {}).get('ljc', {})
        return config
    
    def get_facebook_pixel_config(self) -> Dict[str, Any]:
        """Get Facebook Pixel configuration"""
        config = self.config_data.get('anti_bot_tracking', {}).get('facebook_pixel', {})
        return config
    
    def get_criteo_config(self) -> Dict[str, Any]:
        """Get Criteo tracking configuration"""
        config = self.config_data.get('anti_bot_tracking', {}).get('criteo', {})
        return config
    
    def get_ip_detection_config(self) -> Dict[str, Any]:
        """Get IP detection configuration"""
        config = self.config_data.get('anti_bot_tracking', {}).get('ip_detection', {})
        return config
    
    def get_resource_preloading_config(self) -> Dict[str, Any]:
        """Get resource preloading configuration"""
        config = self.config_data.get('anti_bot_tracking', {}).get('resource_preloading', {})
        return config
    
    # === Dynamic Config Update 관련 메서드들 ===
    # NOTE: 이 메서드들은 DynamicConfigUpdater에서 직접 설정을 읽도록 변경
    # crawler_manager는 순수하게 설정 읽기만 담당
    
    def get_mercury_pattern(self) -> Dict[str, Any]:
        """Get Mercury tracking pattern based on probability"""
        mercury_config = self.get_mercury_config()
        patterns = mercury_config.get('patterns', {})
        
        standard = patterns.get('standard', {})
        extended = patterns.get('extended', {})
        
        # Choose pattern based on probability
        standard_prob = standard.get('probability', 0.7)
        if random.random() < standard_prob:
            return {
                'type': 'standard',
                'events': standard.get('events', []),
                'timing': mercury_config.get('timing', {})
            }
        else:
            return {
                'type': 'extended', 
                'events': extended.get('events', []),
                'timing': mercury_config.get('timing', {})
            }
    
    def get_ljc_pattern(self) -> Dict[str, Any]:
        """Get LJC API pattern based on probability"""
        ljc_config = self.get_ljc_config()
        patterns = ljc_config.get('patterns', {})
        
        standard = patterns.get('standard', {})
        extended = patterns.get('extended', {})
        
        # Choose pattern based on probability
        standard_prob = standard.get('probability', 0.7)
        if random.random() < standard_prob:
            return {
                'type': 'standard',
                'call_count': standard.get('call_count', 5),
                'timing': ljc_config.get('timing', {})
            }
        else:
            return {
                'type': 'extended',
                'call_count': extended.get('call_count', 7),
                'timing': ljc_config.get('timing', {})
            }

    # === Crawler Settings 관련 메서드들 (통합된 crawler.yaml 설정) ===
    
    def get_crawler_timeouts(self) -> Dict[str, Any]:
        """Get crawler timeout configurations"""
        return self.config_data.get('crawler_settings', {}).get('timeouts', {})
    
    def get_crawler_delays(self) -> Dict[str, Any]:
        """Get crawler delay configurations"""
        return self.config_data.get('crawler_settings', {}).get('delays', {})
    
    def get_crawler_selectors(self) -> Dict[str, Any]:
        """Get crawler CSS selectors"""
        return self.config_data.get('crawler_settings', {}).get('selectors', {})
    
    def get_api_endpoints(self) -> Dict[str, Any]:
        """Get API endpoints"""
        return self.config_data.get('crawler_settings', {}).get('api_endpoints', {})
    
    def get_api_headers(self) -> Dict[str, Any]:
        """Get API headers"""
        return self.config_data.get('crawler_settings', {}).get('api_headers', {})
    
    # === 새로운 크롤링 동작 설정 메서드들 ===
    
    def get_crawling_behavior_config(self) -> Dict[str, Any]:
        """Get crawling behavior configuration"""
        return self.config_data.get('crawling_behavior', {})
    
    def get_auto_rocket_delivery_config(self) -> Dict[str, Any]:
        """Get auto rocket delivery selection configuration"""
        return self.get_crawling_behavior_config().get('auto_rocket_delivery', {})
    
    def get_auto_sort_config(self) -> Dict[str, Any]:
        """Get auto sort configuration"""
        return self.get_crawling_behavior_config().get('auto_sort_by_sales', {})
    
    def get_auto_pagination_config(self) -> Dict[str, Any]:
        """Get auto pagination configuration"""
        return self.get_crawling_behavior_config().get('auto_pagination', {})
    
    def get_general_control_config(self) -> Dict[str, Any]:
        """Get general control configuration"""
        return self.get_crawling_behavior_config().get('general_control', {})

# 전역 인스턴스
crawler_manager = CrawlerManager()

# Backward compatibility exports for crawler settings
TIMEOUTS = crawler_manager.get_crawler_timeouts()
DELAYS = crawler_manager.get_crawler_delays()
SELECTORS = crawler_manager.get_crawler_selectors()
API_ENDPOINTS = crawler_manager.get_api_endpoints()
API_HEADERS = crawler_manager.get_api_headers()

 