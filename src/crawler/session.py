import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .config import (
    BLOCKED_SIGNALS,
    COOKIE_ALLOWLIST,
    PRODUCT_CARD_SELECTORS,
    CrawlConfig,
)
from .io import save_cookie_header, save_text


def build_cookie_header(cookies: List[dict]) -> str:
    parts = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


def build_proxy_url(config: CrawlConfig) -> Optional[str]:
    proxy_ip = config.proxy_ip.strip()
    proxy_port = config.proxy_port
    if not proxy_ip or proxy_port is None:
        return None

    proxy_scheme = (config.proxy_scheme or "socks5").strip()
    return f"{proxy_scheme}://{proxy_ip}:{proxy_port}"


def page_is_blocked(html: str) -> bool:
    if not html:
        return True
    lowered = html.lower()
    return any(signal in lowered for signal in BLOCKED_SIGNALS)


def has_product_cards(driver) -> bool:
    for selector in PRODUCT_CARD_SELECTORS:
        try:
            if driver.find_elements("css selector", selector):
                return True
        except Exception:
            continue
    return False


def snapshot_page(driver, out_dir: Path, tag: str) -> dict:
    snapshot = {
        "tag": tag,
        "url": driver.current_url,
        "title": driver.title,
        "cookies": [],
    }

    try:
        cookies = driver.get_cookies()
        snapshot["cookies"] = [c for c in cookies if c.get("name") in COOKIE_ALLOWLIST]
    except Exception:
        pass

    try:
        save_text(out_dir / f"{tag}.html", driver.page_source)
    except Exception:
        pass
    return snapshot


def prepare_browser_session(
    driver,
    config: CrawlConfig,
    debug_dir: Path,
    report: dict,
) -> Tuple[bool, str]:
    try:
        warmup_steps = [
            ("01_google", "https://www.google.com/", 1.0),
            ("02_coupang_main", f"{config.base_url}/", 1.0),
            ("03_coupang_category", config.category_url, 2.0),
        ]

        for tag, url, wait_sec in warmup_steps:
            print(f"start {tag} -> {url}")
            driver.get(url)
            time.sleep(wait_sec)
            report["steps"].append(snapshot_page(driver, debug_dir, tag))

        try:
            html = driver.page_source or ""
        except Exception:
            html = ""

        if page_is_blocked(html) or not has_product_cards(driver):
            return False, ""

        cookies = driver.get_cookies()
        cookie_header = build_cookie_header(cookies)
        if not cookie_header:
            return False, ""

        save_cookie_header(cookie_header, config.cookie_path)
        print(f"[COOKIE] Updated: {config.cookie_path}")
        return True, cookie_header
    finally:
        time.sleep(1.0)
        try:
            driver.quit()
        except Exception:
            pass


def default_user_data_dir() -> Path:
    if Path("/.dockerenv").exists():
        return Path("/tmp") / "deal-sniffer-dogbot" / "chrome-profile"

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (
                Path(local_app_data)
                / "Google"
                / "Chrome"
                / "User Data"
                / "Coupang_UC_Profile"
                / "TestProfile"
            )
        return Path.home() / "AppData" / "Local" / "deal-sniffer-dogbot" / "chrome-profile"

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Google"
            / "Chrome"
            / "Coupang_UC_Profile"
            / "TestProfile"
        )

    return Path.home() / ".config" / "deal-sniffer-dogbot" / "chrome-profile"
