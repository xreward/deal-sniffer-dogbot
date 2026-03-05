import json
import random
import sys
import time
from datetime import datetime
from typing import List, Tuple

from dotenv import load_dotenv
import undetected_chromedriver as uc

from stealth_browser.browser.anti_detection_browser import AntiDetectionBrowser

from .args import build_runtime_config, parse_args
from .clp.fetcher import ClpFetcher
from .clp.parser import ClpParser
from .config import CrawlConfig, SRC_ROOT
from .io import ensure_directory, load_target_urls, write_clp_report
from .session import build_proxy_url, default_user_data_dir, prepare_browser_session

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(SRC_ROOT / ".env")


def crawl_targets(
    fetcher: ClpFetcher,
    parser: ClpParser,
    config: CrawlConfig,
    target_urls: List[str],
) -> Tuple[List[dict], bool]:
    results = []
    blocked = False

    for target_url in target_urls:
        if blocked:
            break

        parsed = parser.fetch_and_parse_clp(fetcher, target_url)
        if "error" in parsed:
            status_code = None
            product_count = 0
        else:
            status_code = parsed.get("response_info", {}).get("status_code")
            product_count = len(parsed.get("products", []))

        success = status_code == 200 and product_count > 0

        results.append(
            {
                "target_url": target_url,
                "success": success,
                "status_code": status_code,
                "products": product_count,
            }
        )

        if status_code == 403 or (status_code == 200 and product_count == 0):
            print(
                f"[WARN] Blocked or empty response. status={status_code}, products={product_count}"
            )
            blocked = True
            break

        time.sleep(random.uniform(config.sleep_min_sec, config.sleep_max_sec))

    return results, blocked


def run() -> int:
    args = parse_args()
    config = build_runtime_config(args)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_dir = config.debug_root_dir / f"debug_main_{timestamp}"
    ensure_directory(debug_dir)
    ensure_directory(config.output_dir)

    target_urls = load_target_urls(config.category_list_path)
    if not target_urls:
        print(f"[ERROR] target URLs are missing: {config.category_list_path}")
        return 1

    browser = AntiDetectionBrowser()
    report = {"steps": []}

    profile_dir = default_user_data_dir()
    ensure_directory(profile_dir)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    proxy_url = build_proxy_url(config)
    if proxy_url:
        options.add_argument(f"--proxy-server={proxy_url}")

    driver = browser.launch(custom_options=options)

    try:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": True})
        except Exception:
            pass

        session_ok, cookie_header = prepare_browser_session(
            driver,
            config,
            debug_dir,
            report,
        )
        if not session_ok:
            print("[WARN] Session preparation failed due to blocked/empty page.")
            return 1

        fetcher = ClpFetcher(config=config, cookie_header=cookie_header)
        parser = ClpParser(config=config)

        results, _ = crawl_targets(
            fetcher=fetcher,
            parser=parser,
            config=config,
            target_urls=target_urls,
        )

        report_path = config.output_dir / f"coupang_report_{timestamp}.txt"
        write_clp_report(report_path, results)
        print(f"[REPORT] Saved: {report_path}")

        debug_report_path = debug_dir / "debug_report.json"
        debug_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[DEBUG] Saved: {debug_dir}")
        return 0
    finally:
        try:
            browser.quit()
        except Exception:
            pass