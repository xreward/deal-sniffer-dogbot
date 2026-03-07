from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
from .io import ensure_directory, load_target_urls, write_clp_report, write_fetch_report
from .redis_queue import RedisQueueClient
from .session import build_proxy_url, default_user_data_dir, prepare_browser_session

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(SRC_ROOT / ".env")


def fetch_targets_to_redis(
    fetcher: ClpFetcher,
    queue_client: RedisQueueClient,
    queue_key: str,
    config: CrawlConfig,
    target_urls: List[str],
    workers: int = 1,
) -> Tuple[List[dict], bool]:
    def process_target(target_url: str) -> Tuple[dict, bool]:
        status_code = None
        html_length = 0
        html = ""
        error = ""
        queued = False

        try:
            fetched = fetcher.fetch(target_url)
            if "error" in fetched:
                error = str(fetched["error"])
            else:
                status_code = fetched.get("response_info", {}).get("status_code")
                html = str(fetched.get("html", ""))
                html_length = len(html)
                if status_code == 200:
                    queue_client.push(queue_key, fetched)
                    queued = True
        except Exception as exc:
            error = str(exc)

        result = {
            "target_url": target_url,
            "success": queued,
            "status_code": status_code,
            "html_length": html_length,
        }
        if error:
            result["error"] = error

        is_blocked = status_code == 403 or (
            status_code == 200 and ("chlgeId" in html or html_length < 5000)
        )
        return result, is_blocked

    effective_workers = max(1, int(workers))
    results: List[dict] = []
    blocked = False

    if effective_workers == 1:
        for target_url in target_urls:
            if blocked:
                break

            result, is_blocked = process_target(target_url)
            results.append(result)

            if is_blocked:
                print(
                    f"[WARN] Blocked or empty response. status={result['status_code']}, html_length={result['html_length']}"
                )
                blocked = True
                break

            time.sleep(random.uniform(config.sleep_min_sec, config.sleep_max_sec))

        return results, blocked

    ordered_results: List[dict] = [{} for _ in target_urls]
    next_idx = 0
    future_map = {}

    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        while next_idx < len(target_urls) and len(future_map) < effective_workers:
            future = executor.submit(process_target, target_urls[next_idx])
            future_map[future] = next_idx
            next_idx += 1

        while future_map:
            done, _ = wait(set(future_map.keys()), return_when=FIRST_COMPLETED)

            for future in done:
                idx = future_map.pop(future)
                if future.cancelled():
                    continue
                result, is_blocked = future.result()
                ordered_results[idx] = result

                if is_blocked and not blocked:
                    print(
                        f"[WARN] Blocked or empty response. status={result['status_code']}, html_length={result['html_length']}"
                    )
                    blocked = True

            if blocked:
                for pending in list(future_map.keys()):
                    pending.cancel()
                break

            while next_idx < len(target_urls) and len(future_map) < effective_workers:
                future = executor.submit(process_target, target_urls[next_idx])
                future_map[future] = next_idx
                next_idx += 1

    return [result for result in ordered_results if result], blocked


def build_fetcher_with_browser_session(
    config: CrawlConfig,
    debug_dir,
    report: dict,
) -> Tuple[ClpFetcher, bool]:
    browser = AntiDetectionBrowser()
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
            return ClpFetcher(config=config), False
        return ClpFetcher(config=config, cookie_header=cookie_header), True
    finally:
        try:
            browser.quit()
        except Exception:
            pass


def run_fetcher(
    config: CrawlConfig,
    timestamp: str,
    workers: int,
) -> int:
    started_at = time.perf_counter()
    try:
        debug_dir = config.debug_root_dir / f"debug_main_{timestamp}"
        ensure_directory(debug_dir)
        ensure_directory(config.output_dir)

        target_urls = load_target_urls(config.category_list_path)
        if not target_urls:
            print(f"[ERROR] target URLs are missing: {config.category_list_path}")
            return 1

        report = {"steps": []}
        fetcher, session_ok = build_fetcher_with_browser_session(config, debug_dir, report)
        if not session_ok:
            print("[WARN] Session preparation failed due to blocked/empty page.")
            return 1

        try:
            queue_client = RedisQueueClient(config)
        except Exception as exc:
            print(f"[ERROR] Redis connection failed: {exc}")
            return 1

        results, _ = fetch_targets_to_redis(
            fetcher=fetcher,
            queue_client=queue_client,
            queue_key=config.redis_queue_key,
            config=config,
            target_urls=target_urls,
            workers=workers,
        )

        report_path = config.output_dir / f"fetch_report_{timestamp}.txt"
        write_fetch_report(report_path, results, config.redis_queue_key)
        print(f"[REPORT] Saved: {report_path}")

        debug_report_path = debug_dir / "debug_report.json"
        debug_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[DEBUG] Saved: {debug_dir}")
        return 0
    finally:
        elapsed_sec = time.perf_counter() - started_at
        print(f"[TIME] run_fetcher took {elapsed_sec:.2f}s")


def run_parser(
    config: CrawlConfig,
    timestamp: str,
) -> int:
    started_at = time.perf_counter()
    try:
        ensure_directory(config.output_dir)
        parser = ClpParser(config=config)

        try:
            queue_client = RedisQueueClient(config)
        except Exception as exc:
            print(f"[ERROR] Redis connection failed: {exc}")
            return 1

        results: List[dict] = []
        consumed_payloads: List[dict] = []

        for _ in range(max(0, int(config.parser_consume_count))):
            try:
                payload = queue_client.pop(
                    config.redis_queue_key,
                    timeout_sec=max(1, int(config.parser_block_timeout_sec)),
                )
            except Exception as exc:
                print(f"[ERROR] Redis queue read failed: {exc}")
                return 1

            if payload is None:
                break
            if not isinstance(payload, dict):
                print("[WARN] Invalid queue payload. Skipping.")
                continue

            consumed_payloads.append(payload)

        for payload in consumed_payloads:
            parsed = parser.parse_fetch_result(payload)
            request_info = parsed.get("request_info", {})
            target_url = request_info.get("target_url") or request_info.get("url")
            if "error" in parsed:
                status_code = None
                product_count = 0
            else:
                status_code = parsed.get("response_info", {}).get("status_code")
                product_count = len(parsed.get("products", []))

            results.append(
                {
                    "target_url": str(target_url or "unknown"),
                    "success": status_code == 200 and product_count > 0,
                    "status_code": status_code,
                    "products": product_count,
                }
            )

        if not results:
            print("[INFO] No messages were consumed from Redis queue.")
            return 0

        report_path = config.output_dir / f"coupang_report_{timestamp}.txt"
        write_clp_report(report_path, results)
        print(f"[REPORT] Saved: {report_path}")
        return 0
    finally:
        elapsed_sec = time.perf_counter() - started_at
        print(f"[TIME] run_parser took {elapsed_sec:.2f}s")


def run() -> int:
    args = parse_args()
    config = build_runtime_config(args)
    workers = max(1, int(args.workers))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = str(args.mode).strip().lower()

    if mode == "parser":
        return run_parser(
            config=config,
            timestamp=timestamp,
        )
    return run_fetcher(
        config=config,
        timestamp=timestamp,
        workers=workers,
    )