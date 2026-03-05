#!/usr/bin/env python
"""
Anti-Bot Tracking System
Implements Mercury tracking and LJC API calls based on real network analysis
"""

import time
import random
import json
import base64
import hashlib
import logging
import socket
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger(__name__)

class AntiBotTracker:
    """
    Implements essential tracking systems to bypass Coupang's anti-bot detection
    Based on real network analysis from Playwright MCP
    """
    
    def __init__(self, driver):
        self.driver = driver
        
        # Import config manager
        from stealth_browser.managers.crawler_manager import crawler_manager
        self.config = crawler_manager
        
        # Generate dynamic session ID with timestamp and random part
        timestamp = int(datetime.now().timestamp())
        random_part = random.randint(100000, 999999)
        self.session_id = f"sess_{timestamp}_{random_part}"
        
        # Get real IP address
        self.real_ip = self._get_real_ip()
        
        # Get current browser profile info for fallback only
        # NOTE: We use actual browser values in tracking to avoid detection
        self.browser_profile = self._get_browser_profile_info()
        
    def _get_real_ip(self):
        """Get the real IP address of the machine"""
        ip_config = self.config.get_ip_detection_config()
        external_servers = ip_config.get('external_servers', ['8.8.8.8'])
        external_port = ip_config.get('external_port', 80)
        fallback_ip = ip_config.get('fallback_ip', '192.168.1.100')
        
        try:
            # Method 1: Connect to external server to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((external_servers[0], external_port))
            ip = s.getsockname()[0]
            s.close()
            logger.info(f"🌐 Using real IP: {ip}")
            return ip
        except Exception:
            try:
                # Method 2: Use hostname resolution
                ip = socket.gethostbyname(socket.gethostname())
                logger.info(f"🌐 Using real IP (hostname): {ip}")
                return ip
            except Exception:
                # Last fallback from config
                logger.warning(f"⚠️ Using fallback IP: {fallback_ip}")
                return fallback_ip
    
    def _get_browser_profile_info(self):
        """Get browser profile info from config cache (integrated session management)"""
        try:
            # Use config cache instead of removed browser profile manager
            from stealth_browser.managers.config_cache import get_browser_profiles
            import random
            
            browser_profiles_data = get_browser_profiles()
            if browser_profiles_data and 'profiles' in browser_profiles_data:
                profiles = browser_profiles_data['profiles']
                if profiles:
                    # Use random profile since we don't have session context here
                    current_profile = random.choice(profiles)
                    logger.info(f"🎭 Anti-bot tracker using profile: {current_profile['name']}")
                    return current_profile
        except Exception as e:
            logger.warning(f"⚠️ Could not get browser profile: {e}")
        
        # Fallback to JavaScript detection (current behavior)
        return None
        
    def generate_mercury_token(self):
        """Generate Mercury tracking token (based on real pattern analysis)"""
        mercury_config = self.config.get_mercury_config()
        token_settings = mercury_config.get('token_settings', {})
        
        timestamp = str(int(datetime.now().timestamp() * 1000))
        random_range = token_settings.get('random_id_range', [100000, 999999])
        random_id = f"{random.randint(random_range[0], random_range[1])}"
        ip_hash = hashlib.md5(f"{self.real_ip}{timestamp}".encode()).hexdigest()[:16]
        
        # Token data from config
        token_data = {
            'session': f"{token_settings.get('session_prefix', 'ChB')}{random_id}{token_settings.get('session_suffix', 'EgwxMC4yMTkuMzguNjk')}",
            'timestamp': timestamp,
            'ip_hash': ip_hash,
            'market': token_settings.get('market', 'KR'),
            'type': token_settings.get('type', 'FLAT')
        }
        
        # Base64 encoding for token generation
        token_string = json.dumps(token_data)
        return base64.b64encode(token_string.encode()).decode()
    
    def simulate_mercury_calls(self):
        """
        Mercury tracking with REAL observed random patterns from config
        """
        # Get pattern from config (already handles probability)
        pattern = self.config.get_mercury_pattern()
        events = pattern.get('events', [])
        timing = pattern.get('timing', {})
        pattern_type = pattern.get('type', 'unknown')
        
        logger.info(f"🎯 Mercury Pattern: {pattern_type} ({len(events)} calls)")
        
        mercury_config = self.config.get_mercury_config()
        base_url = mercury_config.get('base_url', 'https://mercury.coupang.com/e.gif')
        
        min_delay = timing.get('min_delay', 0.05)
        max_delay = timing.get('max_delay', 0.15)
        
        for i, event in enumerate(events):
            try:
                token = self.generate_mercury_token()
                mercury_url = f"{base_url}?r={quote(token)}&t={event['type']}"
                
                self.driver.execute_script(f"""
                    fetch('{mercury_url}', {{
                        method: 'GET',
                        credentials: 'include',
                        mode: 'no-cors'
                    }}).catch(() => {{}});
                """)
                
                logger.info(f"📡 Mercury {i+1}/{len(events)}: {event['event']} (type={event['type']})")
                time.sleep(random.uniform(min_delay, max_delay))
                
            except Exception as e:
                logger.warning(f"❌ Mercury call {i+1} failed: {e}")
                
    def generate_session_id(self):
        """Generate realistic session ID for LJC API"""
        timestamp = int(datetime.now().timestamp() * 1000)
        random_part = ''.join(random.choices('0123456789abcdef', k=8))
        return f"session_{timestamp}_{random_part}"
    
    def generate_ljc_payload(self):
        """Generate LJC API payload using YAML profile values (consistent approach)"""
        ljc_config = self.config.get_ljc_config()
        defaults = ljc_config.get('payload_defaults', {})
        
        # Priority 1: Use YAML profile values (consistent with browser settings)
        if self.browser_profile:
            screen_resolution = f"{self.browser_profile['screen_width']}x{self.browser_profile['screen_height']}"
            user_agent = self.browser_profile['user_agent']
            logger.info(f"✅ LJC using YAML profile: {screen_resolution}, {user_agent[:50]}...")
        else:
            # Priority 2: JavaScript real-time detection (fallback)
            try:
                screen_info = self.driver.execute_script("""
                    return {
                        width: screen.width,
                        height: screen.height,
                        userAgent: navigator.userAgent
                    };
                """)
                screen_resolution = f"{screen_info['width']}x{screen_info['height']}"
                user_agent = screen_info['userAgent']
                logger.warning(f"⚠️ LJC using JavaScript fallback: {screen_resolution}")
            except:
                # Priority 3: Hard fallback from config
                fb_config = self.config.get_facebook_pixel_config()
                default_screen = fb_config.get('default_screen', {'width': 1728, 'height': 1117})
                screen_resolution = f"{default_screen['width']}x{default_screen['height']}"
                user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                logger.warning(f"⚠️ LJC using hard fallback: {screen_resolution}")
        
        return {
            'appCode': ljc_config.get('app_code', 'coupang'),
            'market': ljc_config.get('market', 'KR'),
            'pageType': defaults.get('page_type', 'category'),
            'timestamp': int(datetime.now().timestamp() * 1000),
            'sessionId': self.session_id,
            'userAgent': user_agent,
            'screenResolution': screen_resolution,
            'colorDepth': defaults.get('color_depth', 24),
            'timezone': defaults.get('timezone', 'Asia/Seoul'),
            'language': defaults.get('language', 'ko-KR')
        }
    
    def simulate_ljc_calls(self):
        """
        LJC API calls with REAL observed random patterns from config
        """
        # Get pattern from config (already handles probability)
        pattern = self.config.get_ljc_pattern()
        call_count = pattern.get('call_count', 5)
        timing = pattern.get('timing', {})
        pattern_type = pattern.get('type', 'unknown')
            
        logger.info(f"🎯 LJC Pattern: {pattern_type} ({call_count} calls)")
        
        ljc_config = self.config.get_ljc_config()
        base_url = ljc_config.get('base_url', 'https://ljc.coupang.com/api/v2/submit')
        app_code = ljc_config.get('app_code', 'coupang')
        market = ljc_config.get('market', 'KR')
        
        min_delay = timing.get('min_delay', 0.08)
        max_delay = timing.get('max_delay', 0.20)
        
        for i in range(call_count):
            try:
                ljc_payload = {
                    "appCode": app_code,
                    "market": market,
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "sessionId": self.generate_session_id(),
                    "callIndex": i + 1
                }
                
                self.driver.execute_script(f"""
                    fetch('{base_url}?appCode={app_code}&market={market}', {{
                        method: 'POST',
                        credentials: 'include',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({ljc_payload})
                    }}).catch(() => {{}});
                """)
                
                logger.info(f"📊 LJC {i+1}/{call_count}: API call sent")
                time.sleep(random.uniform(min_delay, max_delay))
                
            except Exception as e:
                logger.warning(f"❌ LJC call {i+1} failed: {e}")
    
    def simulate_facebook_pixel(self, current_url):
        """Facebook Pixel event simulation using YAML profile values (consistent approach)"""
        fb_config = self.config.get_facebook_pixel_config()
        fb_pixel_id = fb_config.get('pixel_id', '652323801535981')
        base_url = fb_config.get('base_url', 'https://www.facebook.com/tr/')
        version = fb_config.get('version', '2.9.211')
        event_type = fb_config.get('event_type', 'PageView')
        default_screen = fb_config.get('default_screen', {'width': 1728, 'height': 1117})
        
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Priority 1: Use YAML profile values (consistent with browser settings)
        if self.browser_profile:
            screen_width = self.browser_profile['screen_width']
            screen_height = self.browser_profile['screen_height']
            logger.info(f"✅ Facebook Pixel using YAML profile: {screen_width}x{screen_height}")
        else:
            # Priority 2: JavaScript real-time detection (fallback)
            try:
                screen_info = self.driver.execute_script("return {width: screen.width, height: screen.height};")
                screen_width = screen_info['width']
                screen_height = screen_info['height']
                logger.warning(f"⚠️ Facebook Pixel using JavaScript fallback: {screen_width}x{screen_height}")
            except:
                # Priority 3: Hard fallback from config
                screen_width = default_screen['width']
                screen_height = default_screen['height']
                logger.warning(f"⚠️ Facebook Pixel using config fallback: {screen_width}x{screen_height}")
        
        try:
            # PageView event with dynamic screen size
            fb_url = f"{base_url}?id={fb_pixel_id}&ev={event_type}&dl={quote(current_url)}&rl=&if=false&ts={timestamp}&sw={screen_width}&sh={screen_height}&v={version}&r=c2&ec=0&o=4126&fbp=fb.1.{timestamp}.{random.randint(100000000000000000, 999999999999999999)}&ler=empty&cdl=API_unavailable&it={timestamp}&coo=false&rqm=GET"
            
            self.driver.execute_script(f"""
                fetch('{fb_url}', {{
                    method: 'GET',
                    credentials: 'include',
                    mode: 'no-cors'
                }}).catch(() => {{}});
            """)
            
            logger.info("👥 Facebook Pixel: PageView event sent")
            
        except Exception as e:
            logger.error(f"❌ Facebook Pixel failed: {e}")
    
    def simulate_criteo_tracking(self):
        """Criteo tracking simulation using config"""
        criteo_config = self.config.get_criteo_config()
        base_url = criteo_config.get('base_url', 'https://gum.criteo.com/syncframe')
        params = criteo_config.get('params', {})
        
        # Build URL with params
        param_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        criteo_url = f"{base_url}?{param_string}"
        
        try:
            self.driver.execute_script(f"""
                fetch('{criteo_url}', {{
                    method: 'GET',
                    credentials: 'include',
                    mode: 'no-cors'
                }}).catch(() => {{}});
            """)
            
            logger.info("🎯 Criteo: Tracking sync completed")
            
        except Exception as e:
            logger.error(f"❌ Criteo tracking failed: {e}")
    
    def preload_essential_resources(self):
        """
        Preload essential CSS/JS resources from config
        """
        resource_config = self.config.get_resource_preloading_config()
        
        if not resource_config.get('enabled', True):
            logger.info("📦 Resource preloading disabled in config")
            return
        
        css_files = resource_config.get('css_files', [])
        js_files = resource_config.get('js_files', [])
        timing = resource_config.get('timing', {})
        
        css_delay_range = timing.get('css_delay_range', [0.1, 0.3])
        js_delay_range = timing.get('js_delay_range', [0.2, 0.5])
        
        essential_resources = css_files + js_files
        
        logger.info(f"📦 Starting essential resource preloading ({len(essential_resources)} files)...")
        
        for i, resource_url in enumerate(essential_resources):
            try:
                self.driver.execute_script(f"""
                    fetch('{resource_url}', {{
                        method: 'GET',
                        credentials: 'include'
                    }}).catch(() => {{}});
                """)
                
                # CSS loads faster, JS takes more time (from config)
                if 'css' in resource_url:
                    time.sleep(random.uniform(css_delay_range[0], css_delay_range[1]))
                else:
                    time.sleep(random.uniform(js_delay_range[0], js_delay_range[1]))
                
                logger.info(f"✅ Resource {i+1}/{len(essential_resources)}: {resource_url.split('/')[-1]}")
                
            except Exception as e:
                logger.error(f"❌ Resource {i+1} failed: {e}")
        
        logger.info("📦 Essential resource preloading completed")
    
    def execute_full_anti_bot_sequence(self, current_url):
        """
        Execute complete anti-bot bypass sequence
        THIS IS THE CORE FUNCTION - ALL TRACKING MUST BE CALLED
        """
        logger.info("🚀 Starting FULL Anti-Bot bypass sequence...")
        
        try:
            # 1. Preload essential resources
            self.preload_essential_resources()
            
            # 2. Mercury tracking (ABSOLUTELY REQUIRED)
            self.simulate_mercury_calls()
            
            # 3. LJC API calls (ABSOLUTELY REQUIRED)
            self.simulate_ljc_calls()
            
            # 4. Facebook Pixel (REQUIRED)
            self.simulate_facebook_pixel(current_url)
            
            # 5. Criteo tracking (OPTIONAL but recommended)
            self.simulate_criteo_tracking()
            
            logger.info("🎉 Anti-Bot bypass sequence completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"💥 Anti-Bot sequence failed: {e}")
            return False 