#!/usr/bin/env python
import time
import random
import logging
import ssl
import os
import re
import subprocess
import undetected_chromedriver as uc
from typing import Optional, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from stealth_browser.managers.crawler_manager import TIMEOUTS, DELAYS, SELECTORS, crawler_manager
from stealth_browser.utils.delay import random_delay
from stealth_browser.browser.anti_bot_tracker import AntiBotTracker
# from stealth_browser.managers.browser_profile_manager import get_profile_manager  # Removed: integrated to session management
from stealth_browser.utils.page_actions import PageActionsUtil

# Fix SSL certificate issues
ssl._create_default_https_context = ssl._create_unverified_context

# Logging configuration (bind Prefect run logger when available)
logger = logging.getLogger(__name__)
try:
    from prefect import get_run_logger as _prefect_get_run_logger  # type: ignore
except Exception:  # pragma: no cover - Prefect 미실행 환경 대비
    _prefect_get_run_logger = None

def _maybe_bind_prefect_logger():
    """If running under Prefect, bind module logger to Prefect run logger."""
    global logger
    if _prefect_get_run_logger is not None:
        try:
            logger = _prefect_get_run_logger()  # type: ignore
        except Exception:
            pass

class AntiDetectionBrowser:
    """
    Enhanced browser with advanced anti-detection settings for web scraping
    Configures undetected-chromedriver with optimized settings to avoid bot detection
    Includes Mercury tracking and LJC API simulation based on real network analysis
    """
    
    def __init__(self):
        """Initialize the anti-detection browser"""
        self.driver = None
        self.anti_bot_tracker = None
        # self.profile_manager = get_profile_manager()  # Removed: integrated to session management
        self.current_profile = None

    @staticmethod
    def _detect_chrome_version_main() -> Optional[int]:
        env_version = os.environ.get("UC_CHROME_VERSION_MAIN") or os.environ.get("CHROME_VERSION_MAIN")
        if env_version and str(env_version).isdigit():
            return int(env_version)

        candidates = []
        env_bin = os.environ.get("CHROME_BIN")
        if env_bin:
            candidates.append(env_bin)
        candidates.extend([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ])

        for path in candidates:
            if not path:
                continue
            if os.path.exists(path):
                try:
                    result = subprocess.run(
                        [path, "--version"],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    output = (result.stdout or result.stderr or "").strip()
                    match = re.search(r"(\\d+)\\.", output)
                    if match:
                        return int(match.group(1))
                except Exception:
                    continue

        for cmd in ("google-chrome", "chrome", "chromium", "chromium-browser"):
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                output = (result.stdout or result.stderr or "").strip()
                match = re.search(r"(\\d+)\\.", output)
                if match:
                    return int(match.group(1))
            except Exception:
                continue

        return None

    @staticmethod
    def _detect_chromedriver_version_main(driver_path: str) -> Optional[int]:
        try:
            result = subprocess.run(
                [driver_path, "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
            output = (result.stdout or result.stderr or "").strip()
            match = re.search(r"(\\d+)\\.", output)
            if match:
                return int(match.group(1))
        except Exception:
            return None
        return None
    
    @staticmethod
    def build_options(user_data_dir: str, browser_profile: Dict[str, Any], ip_address: Optional[str] = None) -> uc.ChromeOptions:
        """Build minimal ChromeOptions for integration with launch(custom_options).

        - Sets user-data-dir and Default sub-profile for consistency
        - Applies user agent and optional window size from browser_profile
        - Normalizes and applies proxy from ip_address when provided
        Note: General chrome flags are applied inside launch(); this builder focuses on per-session inputs.
        """
        options = uc.ChromeOptions()
        # user data dir and sub-profile
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument("--profile-directory=Default")

        # user agent from profile
        try:
            user_agent = browser_profile.get('user_agent')
            if user_agent:
                options.add_argument(f"--user-agent={user_agent}")
        except Exception:
            pass

        # optional window size
        try:
            width = browser_profile.get('screen_width')
            height = browser_profile.get('screen_height')
            if width and height:
                options.add_argument(f"--window-size={int(width)},{int(height)}")
        except Exception:
            pass

        # optional proxy
        if ip_address and isinstance(ip_address, str) and ip_address.strip():
            pv = ip_address.strip()
            pv = f"socks5://{pv}"
            if pv:
                options.add_argument(f"--proxy-server={pv}")

        return options
    
    def get_random_user_agent(self):
        """Get a random user agent as fallback"""
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def set_profile(self, profile):
        """Set the browser profile to use"""
        self.current_profile = profile
        
    def _get_current_profile(self):
        """Get current profile (from set profile only - no fallback to global manager)"""
        # Only use explicitly set profile (integrated session management)
        if self.current_profile:
            return self.current_profile
        
        # No fallback - profile must be explicitly set by IntegratedSessionManager
        return None
    
    def launch(self, custom_options=None):
        """Launch a browser with enhanced anti-detection settings"""
        # Try to bind Prefect run logger so logs appear in Prefect UI
        _maybe_bind_prefect_logger()
        # 항상 uc.ChromeOptions()를 베이스로 시작 (anti-bot 우회 성능 우수)
        options = uc.ChromeOptions()
        logger.info("🔧 Starting with UC ChromeOptions base (anti-bot 우회 최적화)")
        
        # Try to get current profile from global manager
        current_profile = self._get_current_profile()
        
        # Use profile-specific window size or randomized fallback
        if current_profile:
            width = current_profile['screen_width']
            height = current_profile['screen_height']
            logger.info(f"🎭 Using profile screen size: {width}x{height}")
        else:
            width = random.randint(1366, 1920)
            height = random.randint(768, 1080)
            logger.info(f"🎲 Using random screen size: {width}x{height}")
        options.add_argument(f'--window-size={width},{height}')

        # Use Chrome options from config file (Docker-aware safety)
        chrome_options = crawler_manager.get_chrome_options()
        dangerous_flags = {
            "--disable-web-security",
            "--remote-debugging-port=9222",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        }
        for option in chrome_options:
            if not os.path.exists('/.dockerenv') and option in dangerous_flags:
                # Skip highly fingerprintable/unsafe flags outside Docker
                continue
            options.add_argument(option)
        
        # Docker: stability flags & headless
        if os.path.exists('/.dockerenv'):
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-setuid-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            logger.info("🐳 Docker detected: enabling headless & sandbox-safe flags")
        
        # custom_options가 제공되면 UC 베이스에 우선 추가 (통합 세션 설정 우선)
        custom_user_data_dir = None
        custom_user_agent = None
        custom_proxy_server = None
        
        if custom_options:
            logger.info("🎯 Adding custom_options to UC base (통합 세션 설정 우선 적용)")
            
            # custom_options의 _arguments를 UC options에 추가
            if hasattr(custom_options, '_arguments'):
                for arg in custom_options._arguments:
                    # 중복 방지: 이미 있는 설정은 custom_options 것으로 덮어쓰기
                    if arg.startswith('--user-data-dir='):
                        custom_user_data_dir = arg.split('=', 1)[1]
                        options.add_argument(arg)
                        logger.info(f"🎯 통합 세션 user-data-dir: {custom_user_data_dir}")
                    elif arg.startswith('--user-agent='):
                        custom_user_agent = arg.split('=', 1)[1]
                        options.add_argument(arg)
                        logger.info(f"🎯 통합 세션 user-agent: {custom_user_agent[:50]}...")
                    elif arg.startswith('--proxy-server='):
                        custom_proxy_server = arg.split('=', 1)[1]
                        options.add_argument(arg)
                        logger.info(f"🌐 통합 세션 proxy-server: {custom_proxy_server}")
                    else:
                        # 다른 옵션들은 그대로 추가
                        options.add_argument(arg)
                        logger.info(f"➕ Adding custom option: {arg}")
            
            # 사용자 데이터 디렉토리를 사용하는 경우, 항상 Default 서브프로필을 강제해 일관성 유지
            if custom_user_data_dir:
                options.add_argument("--profile-directory=Default")
                logger.info("🗂️ Enforcing sub-profile: Default")
        
        # Profile 설정은 custom_options가 없을 때만 fallback으로 사용
        if not custom_options:
            logger.info("📝 No custom_options - using profile fallback")
            
            # Add user-data-dir from profile if available
            if current_profile and 'user_data_dir' in current_profile:
                user_data_dir = current_profile['user_data_dir']
                options.add_argument(f'--user-data-dir={user_data_dir}')
                logger.info(f"🗂️ Profile user-data-dir: {user_data_dir}")
                # 동일한 하위 프로필 재사용을 위해 Default 강제
                options.add_argument("--profile-directory=Default")
                logger.info("🗂️ Enforcing sub-profile: Default")
                # Fallback path cleanup for potential stale Chrome locks/ports
                try:
                    logger.info(f"🧪 Cleanup check at: {user_data_dir}")
                    for fname in ("SingletonLock", "SingletonCookie", "SingletonSocket", "DevToolsActivePort"):
                        fpath = os.path.join(user_data_dir, fname)
                        try:
                            if os.path.lexists(fpath):
                                os.unlink(fpath)
                                logger.info(f"🧹 Removed stale Chrome file: {fname}")
                            else:
                                logger.info(f"ℹ️ No cleanup target: {fname}")
                        except Exception as fe:
                            logger.info(f"⚠️ Could not remove {fname}: {fe}")
                except Exception as cleanup_err:
                    logger.info(f"⚠️ user-data-dir cleanup skipped: {cleanup_err}")
            else:
                logger.warning("⚠️ No user_data_dir found in profile - will use default Chrome profile")
            
            # Use profile-specific user agent or random fallback
            if current_profile:
                user_agent = current_profile['user_agent']
                logger.info(f"🎭 Profile User-Agent: {user_agent[:50]}...")
            else:
                user_agent = self.get_random_user_agent()
                logger.info(f"🎲 Random User-Agent: {user_agent[:50]}...")
            options.add_argument(f"--user-agent={user_agent}")
        else:
            logger.info("✅ 통합 세션 설정 적용 완료 (profile 설정 생략)")
        
        # Ensure binary location explicitly when available (Chromium inside Docker)
        try:
            chromium_bin = "/usr/bin/chromium"
            if os.path.exists(chromium_bin):
                options.binary_location = chromium_bin  # type: ignore[attr-defined]
                logger.info(f"🧭 Using Chromium binary at: {chromium_bin}")
        except Exception as bin_err:
            logger.debug(f"Chromium binary_location set skip: {bin_err}")
        
        # Pre-clean potential stale Chrome locks/port files when using custom user-data-dir
        try:
            if custom_user_data_dir:
                logger.info(f"🧪 Cleanup check at: {custom_user_data_dir}")
                for fname in ("SingletonLock", "SingletonCookie", "SingletonSocket", "DevToolsActivePort"):
                    fpath = os.path.join(custom_user_data_dir, fname)
                    try:
                        if os.path.lexists(fpath):  # broken symlink도 True
                            os.unlink(fpath)
                            logger.info(f"🧹 Removed stale Chrome file: {fname}")
                        else:
                            logger.info(f"ℹ️ No cleanup target: {fname}")
                    except Exception as fe:
                        logger.info(f"⚠️ Could not remove {fname}: {fe}")
        except Exception as cleanup_err:
            logger.info(f"⚠️ user-data-dir cleanup skipped: {cleanup_err}")

        # Disable SSL verification and pin driver version if configured
        version_main = None
        try:
            cfg = crawler_manager.config_data
            version_main = cfg.get('chromedriver', {}).get('version_main')
        except Exception:
            version_main = None
        if isinstance(version_main, str) and version_main.isdigit():
            version_main = int(version_main)

        # Align driver handling with login_manager: use system chromedriver when available
        driver_path = os.environ.get("CHROME_DRIVER_PATH", "/usr/bin/chromedriver")
        force_system_driver = os.environ.get("UC_USE_SYSTEM_DRIVER") == "1"
        driver_version_main = None
        if os.path.exists(driver_path):
            driver_version_main = self._detect_chromedriver_version_main(driver_path)
            logger.info(
                "Found chromedriver at %s (version_main=%s)",
                driver_path,
                driver_version_main or "unknown",
            )
        else:
            driver_path = None
            logger.info("chromedriver not found; UC may download its own driver")

        if driver_path and isinstance(version_main, int) and isinstance(driver_version_main, int):
            if driver_version_main != version_main and not force_system_driver:
                logger.info(
                    "Chromedriver version mismatch (driver=%s, chrome=%s); letting UC download driver.",
                    driver_version_main,
                    version_main,
                )
                driver_path = None

        if not isinstance(version_main, int):
            detected = self._detect_chrome_version_main()
            if isinstance(detected, int):
                version_main = detected
                logger.info(f"🔎 Detected Chrome major version: {version_main}")

        chrome_kwargs = {
            'options': options,
            'ssl_verify': False,
            'driver_executable_path': driver_path,
            'use_subprocess': True,
        }
        if isinstance(version_main, int):
            chrome_kwargs['version_main'] = version_main
            logger.info(f"📦 Pinning chromedriver version_main={version_main} for crawler")

        self.driver = uc.Chrome(**chrome_kwargs)
        
        # Enhanced JavaScript environment setup using config
        self.setup_enhanced_js_environment()
        
        # Set page load timeout
        self.driver.set_page_load_timeout(TIMEOUTS['page_load'])
        
        # Initialize anti-bot tracker
        self.anti_bot_tracker = AntiBotTracker(self.driver)
        
        logger.info("🚀 Enhanced anti-detection browser launched successfully")
        
        return self.driver
    
    def setup_enhanced_js_environment(self):
        """
        Setup enhanced JavaScript environment to bypass detection
        Uses fingerprint settings from browser profile for consistency
        """
        if not self.driver:
            raise Exception("Browser not launched. Call launch() first.")
        
        # Get current profile
        current_profile = self._get_current_profile()
        
        if current_profile and 'fingerprint' in current_profile:
            # Use profile-specific settings
            logger.info(f"🎭 Using profile fingerprint: {current_profile['name']}")
            js_code = crawler_manager.generate_javascript_code(current_profile)
        else:
            # Use fallback settings from config
            logger.warning("⚠️ Using fallback fingerprint settings")
            fallback_settings = crawler_manager.get_fallback_settings()
            fallback_profile = {
                'name': 'fallback',
                'hardware_cores': fallback_settings.get('hardware_cores', 8),
                'fingerprint': fallback_settings
            }
            js_code = crawler_manager.generate_javascript_code(fallback_profile)
        
        if js_code:
            self.driver.execute_script(js_code)
            logger.info("✅ Enhanced JavaScript environment setup completed")
        else:
            logger.error("❌ Failed to generate JavaScript code")
    
    def setup_essential_cookies(self):
        """Setup essential Coupang cookies with profile-based consistency"""
        if not self.driver:
            raise Exception("Browser not launched. Call launch() first.")
        
        # Get current profile for consistent session data
        current_profile = self._get_current_profile()
        
        if current_profile:
            # Generate profile-consistent PCID (same profile = same format/base)
            profile_name = current_profile['name']
            # Use profile name hash to determine format and base values consistently
            profile_hash = hash(profile_name) % 1000000
            pcid_base = abs(profile_hash) + 100000000
            
            # Different PCID formats based on profile (consistent)
            if 'edge' in profile_name.lower():
                pcid = f'{pcid_base}_pc'
            elif 'windows' in profile_name.lower():
                pcid = f'pc_{pcid_base}'
            elif 'mac' in profile_name.lower():
                pcid = f'pc{pcid_base}'
            else:
                pcid = f'pc_{pcid_base}'
            
            # Generate profile-consistent session identifiers
            session_base = abs(hash(profile_name + "session")) % 100000000
            tracking_base = abs(hash(profile_name + "tracking")) % 10000
            session_id = f"{session_base:08x}" + "0" * 24  # 32 chars
            tracking_id = f"{tracking_base:04X}" + "0" * 12  # 16 chars
            
            logger.info(f"🍪 Using profile-based cookies for: {profile_name}")
        else:
            # Fallback for no profile
            pcid = f'pc_{random.randint(100000000, 999999999)}'
            session_id = ''.join(random.choices('0123456789abcdef', k=32))
            tracking_id = ''.join(random.choices('0123456789ABCDEF', k=16))
            logger.warning("⚠️ Using random cookies (no profile)")
            
        # Get static cookies from config
        static_cookies = crawler_manager.get_static_cookies()
        
        # Combine static and dynamic cookies
        essential_cookies = []
        
        # Add static cookies from config
        for name, value in static_cookies.items():
            essential_cookies.append({'name': name, 'value': value})
        
        # Add dynamic cookies
        dynamic_cookies = {
            'PCID': pcid,
            '_coupang_session': session_id,
            'coupang_tracking': tracking_id,
            'visit_id': str(int(time.time() * 1000))
        }
        
        for name, value in dynamic_cookies.items():
            essential_cookies.append({'name': name, 'value': value})
        
        for cookie in essential_cookies:
            try:
                self.driver.add_cookie(cookie)
                logger.info(f"✅ Cookie set: {cookie['name']}")
            except Exception as e:
                logger.error(f"❌ Failed to set cookie {cookie['name']}: {e}")
        
        logger.info(f"🍪 Profile-consistent PCID: {pcid}")
    
    def set_realistic_referrer(self, url):
        """Set a realistic referrer using config rules"""
        if not self.driver:
            raise Exception("Browser not launched. Call launch() first.")
        
        # Get referrer URL from config based on URL type
        referer = crawler_manager.get_referrer_url(url)
        
        # Set referrer via CDP
        self.driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
            "headers": {
                "Referer": referer
            }
        })
    
    def simulate_human_scrolling(self):
        """
        Enhanced natural scrolling behavior using config settings
        """
        if not self.driver:
            raise Exception("Browser not launched. Call launch() first.")
        
        try:
            # Get scrolling config
            scrolling_config = crawler_manager.get_scrolling_config()
            count_range = scrolling_config.get('count_range', [3, 5])
            reading_time_range = scrolling_config.get('reading_time_range', [0.8, 2.0])
            position_randomness = scrolling_config.get('position_randomness', 100)
            
            # Get the page height
            page_height = self.driver.execute_script("return document.body.scrollHeight")
            current_position = 0
            
            # Enhanced scroll count using config
            scroll_count = random.randint(count_range[0], count_range[1])
            scroll_step = page_height // scroll_count
            
            logger.info(f"👤 Starting human-like scrolling ({scroll_count} scrolls)...")
            
            for i in range(scroll_count):
                # Calculate scroll position with randomness from config
                current_position += scroll_step + random.randint(-position_randomness, position_randomness)
                current_position = min(current_position, page_height)
                
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                
                # Natural reading time from config
                time.sleep(random.uniform(reading_time_range[0], reading_time_range[1]))
                
                logger.info(f"📜 Scroll {i+1}/{scroll_count}: position {current_position}")
            
            logger.info("👤 Human-like scrolling completed")
            
        except Exception as e:
            logger.error(f"❌ Scrolling simulation failed: {e}")
    
    def navigate_with_enhanced_anti_detection(self, url):
        """
        Enhanced navigation with comprehensive anti-detection measures
        Includes Mercury tracking and LJC API simulation
        """
        if not self.driver:
            raise Exception("Browser not launched. Call launch() first.")
            
        try:
            logger.info("🚀 Starting enhanced anti-detection navigation...")
            
            # Step 1: Navigate to main page first
            logger.info("📱 Step 1: Navigating to Coupang main page...")
            self.driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
                "headers": {
                    "Referer": "https://www.google.com/",
                    "Sec-Fetch-Site": "cross-site",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-User": "?1",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                    "Cache-Control": "max-age=0",
                    "Upgrade-Insecure-Requests": "1"
                }
            })
            
            self.driver.get("https://www.coupang.com")
            
            # Wait for loading
            WebDriverWait(self.driver, TIMEOUTS['navigation']).until(
                EC.presence_of_element_located((By.TAG_NAME, SELECTORS['body']))
            )
            
            # Setup essential cookies
            logger.info("🍪 Setting up essential cookies...")
            self.setup_essential_cookies()
            
            # Random wait after main page load
            min_ms = DELAYS['after_page_load']['min']
            max_ms = DELAYS['after_page_load']['max']
            random_delay(min_ms, max_ms)
            
            # Step 2: Navigate to target page
            logger.info(f"🎯 Step 2: Navigating to target page: {url}")
            self.driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {
                "headers": {
                    "Referer": "https://www.coupang.com/",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "navigate", 
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-User": "?1",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                    "Cache-Control": "max-age=0",
                    "Upgrade-Insecure-Requests": "1"
                }
            })
            
            self.driver.get(url)
            
            # Wait for page loading
            WebDriverWait(self.driver, TIMEOUTS['navigation']).until(
                EC.presence_of_element_located((By.TAG_NAME, SELECTORS['body']))
            )
            
            # 🔥 NEW: 페이지 로드 직후 로켓 배송 및 판매량순 정렬 처리 (single page 모드 대응)
            self._handle_page_load_actions()
            
            # Check for connection errors
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                if "사이트에 연결할 수 없음" in page_text:
                    logger.error("🚫 Connection error detected")
                    raise Exception("Connection error: Cannot reach the site")
            except Exception as e:
                if "Connection error" in str(e):
                    raise  # Re-raise connection errors to main handler
                # Ignore other errors (page structure issues)
            
            logger.info("✅ Page navigation completed")
            
            # Step 3: Execute anti-bot tracking sequence (ALWAYS execute - essential for detection)
            logger.info("🎯 Step 3: Executing anti-bot tracking sequence...")
            if self.anti_bot_tracker:
                tracking_success = self.anti_bot_tracker.execute_full_anti_bot_sequence(url)
            else:
                tracking_success = False
            
            if not tracking_success:
                logger.warning("⚠️ Anti-bot tracking sequence had issues, but continuing...")
            
            # Step 4: Simulate human behavior
            logger.info("👤 Step 4: Simulating human behavior...")
            self.simulate_human_scrolling()
            
            # Final wait
            time.sleep(random.uniform(1.0, 3.0))
            
            logger.info("🎉 Enhanced anti-detection navigation completed successfully!")
            return True
            
        except Exception as navigation_error:
            logger.error(f"💥 Enhanced navigation failed: {navigation_error}")
            return False

    def _handle_page_load_actions(self):
        """페이지 로드 직후 로켓 배송 선택 및 판매량순 정렬 처리"""
        try:
            # Use common page actions utility
            page_actions = PageActionsUtil(self.driver)
            results = page_actions.execute_page_load_actions("navigation")
            
            if results['rocket_delivery']:
                logger.info("✅ Navigate: Successfully selected rocket delivery")
            else:
                logger.warning("⚠️ Navigate: Rocket delivery selection failed")
                
            if results['sales_sort']:
                logger.info("✅ Navigate: Successfully clicked sales volume sort")
            else:
                logger.warning("⚠️ Navigate: Sales volume sort not available")
                
        except Exception as e:
            logger.error(f"❌ Error in page load actions: {e}")
    
    def quit(self):
        """Close the browser properly"""
        if self.driver:
            logger.info("Closing browser...")
            self.driver.quit()
            self.driver = None
            logger.info("Browser closed")

    def _get_realistic_hardware_config(self):
        """Generate realistic hardware configuration with natural variations"""
        
        # Common realistic screen resolutions (prioritize observed 1728x1117)
        common_resolutions = [
            (1728, 1117),  # 실제 관찰된 해상도 (60% 확률)
            (1920, 1080),  # 표준 FHD (25% 확률)
            (1440, 900),   # MacBook Air (10% 확률)
            (2560, 1440),  # QHD (5% 확률)
        ]
        
        # Weighted random selection
        weights = [0.6, 0.25, 0.1, 0.05]
        resolution = random.choices(common_resolutions, weights=weights)[0]
        
        # CPU cores (8 is common, but allow some variation)
        cores_options = [4, 6, 8, 12, 16]
        cores_weights = [0.1, 0.15, 0.5, 0.2, 0.05]  # 8 cores most common
        cores = random.choices(cores_options, weights=cores_weights)[0]
        
        # Color depth (24-bit most common)
        color_depth = random.choices([24, 32], weights=[0.8, 0.2])[0]
        
        return {
            'screen_width': resolution[0],
            'screen_height': resolution[1], 
            'cores': cores,
            'color_depth': color_depth
        }
