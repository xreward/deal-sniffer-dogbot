import json
from datetime import datetime
from pathlib import Path
from typing import List


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def load_target_urls(path: Path) -> List[str]:
    if not path.exists():
        return []

    return [
        line.strip()
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_clp_report(path: Path, results: List[dict]) -> None:
    success_count = 0
    fail_count = 0
    lines: List[str] = []

    for result in results:
        is_success = bool(result["success"])
        if is_success:
            success_count += 1
        else:
            fail_count += 1

        status_text = "SUCCESS" if is_success else "FAIL"
        lines.append(
            f"[{status_text}] url={result['target_url']} status={result['status_code']} products={result['products']}"
        )

    lines.append("")
    lines.append(f"TOTAL: success={success_count}, fail={fail_count}, total={len(results)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_cookie_header(cookie_header: str, cookie_path: Path) -> None:
    payload = {
        "cookie_string": cookie_header,
        "last_updated": datetime.now().isoformat(),
        "status": "valid",
    }

    if cookie_path.exists():
        try:
            existing = json.loads(cookie_path.read_text(encoding="utf-8"))
            existing.update(payload)
            payload = existing
        except Exception:
            pass

    cookie_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
