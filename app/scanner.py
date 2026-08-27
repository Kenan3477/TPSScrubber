from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from app.numbers import mask_number
from app.store import load_job, recount_stats, save_job, utc_now

TPS_URL = "https://www.tpsonline.org.uk/register/am_i_registered"
REGISTERED_TEXT = "Phone number is registered"
NOT_REGISTERED_TEXT = "Phone number is not registered"
LIMIT_TEXT = "exceeded the limit"
SEND_ERROR_TEXT = "problem during sending"

MIN_COOLDOWN = 30
MAX_COOLDOWN = 180
MAX_CONSECUTIVE_LIMITS = 6
RATE_LIMIT_PAUSE_MESSAGE = (
    "TPS blocked further checks from this connection. "
    "The public page will not accept more lookups right now. "
    "Wait a while and click Resume, or run the portal on your own computer."
)

_scan_lock = threading.Lock()


def is_scan_running() -> bool:
    return _scan_lock.locked()


def delay_seconds() -> float:
    try:
        return max(0.4, float(os.getenv("TPS_DELAY_SECONDS", "1.0")))
    except ValueError:
        return 1.0


def _dismiss_overlays(page: Any) -> None:
    selectors = [
        "#ccc-notify-accept",
        "#ccc-recommended-settings",
        "button:has-text('Accept')",
        "button:has-text('Reject')",
        "button:has-text('Save and close')",
        "#ccc-close",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible(timeout=800):
                locator.click(timeout=1500)
                page.wait_for_timeout(400)
        except Exception:
            continue


def _page_text(page: Any) -> str:
    try:
        return page.inner_text("body")
    except Exception:
        return ""


def _classify_result(text: str) -> tuple[str, str]:
    if LIMIT_TEXT in text:
        return "rate_limited", "TPS public checker rate limit reached."
    if SEND_ERROR_TEXT in text:
        return "failed", "TPS page reported a problem sending the check."
    if REGISTERED_TEXT in text and NOT_REGISTERED_TEXT not in text:
        return "on_tps", REGISTERED_TEXT
    if NOT_REGISTERED_TEXT in text:
        return "not_on_tps", NOT_REGISTERED_TEXT
    return "unknown", text[-400:]


def check_one_number(page: Any, number: str) -> tuple[str, str]:
    page.goto(TPS_URL, wait_until="domcontentloaded", timeout=45000)
    _dismiss_overlays(page)
    field = page.locator("#telephone_number")
    field.wait_for(state="visible", timeout=30000)
    field.fill("")
    field.fill(number)
    page.get_by_role("button", name="Check my number").click()

    page.wait_for_function(
        """() => {
            const t = document.body.innerText || '';
            return t.includes('Phone number is registered')
                || t.includes('Phone number is not registered')
                || t.includes('exceeded the limit')
                || t.includes('problem during sending');
        }""",
        timeout=30000,
    )
    return _classify_result(_page_text(page))


def _open_browser():
    headed = os.getenv("TPS_HEADED", "").lower() in {"1", "true", "yes"}
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=not headed,
        args=["--disable-dev-shm-usage"],
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="en-GB",
    )
    page = context.new_page()
    return playwright, browser, context, page


def _cancelled(job_id: str, should_stop: Callable[[], bool] | None) -> bool:
    if should_stop and should_stop():
        return True
    fresh = load_job(job_id)
    return bool(fresh and fresh.get("status") in {"cancelled", "paused"})


def _clear_wait(job: dict[str, Any]) -> None:
    job["wait_until"] = None
    job["wait_reason"] = ""


def wait_or_cancel(
    job_id: str,
    seconds: float,
    reason: str,
    should_stop: Callable[[], bool] | None = None,
) -> bool:
    """Sleep while keeping the job cancellable. Returns False if cancelled."""
    if seconds <= 0:
        return not _cancelled(job_id, should_stop)

    until = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    job = load_job(job_id)
    if not job:
        return False
    if reason:
        job["wait_until"] = until.isoformat()
        job["wait_reason"] = reason
        save_job(job)

    while datetime.now(timezone.utc) < until:
        if _cancelled(job_id, should_stop):
            return False
        time.sleep(0.4)

    job = load_job(job_id)
    if job:
        _clear_wait(job)
        save_job(job)
    return not _cancelled(job_id, should_stop)


def run_job(job_id: str, should_stop: Callable[[], bool] | None = None) -> None:
    if not _scan_lock.acquire(blocking=False):
        job = load_job(job_id)
        if job:
            job["status"] = "failed"
            job["error"] = "Another scan is already running. Wait for it to finish."
            save_job(job)
        return

    playwright = browser = context = page = None
    try:
        job = load_job(job_id)
        if not job:
            return
        job["status"] = "running"
        job["error"] = ""
        job["started_at"] = job.get("started_at") or utc_now()
        _clear_wait(job)
        save_job(job)

        playwright, browser, context, page = _open_browser()
        gap = delay_seconds()
        cooldown = MIN_COOLDOWN
        successes = 0
        consecutive_limits = 0

        for index in range(len(job["items"])):
            while True:
                job = load_job(job_id)
                if not job:
                    return
                if _cancelled(job_id, should_stop):
                    job["status"] = "cancelled"
                    job["current_number"] = None
                    _clear_wait(job)
                    save_job(job)
                    return

                item = job["items"][index]
                if item["status"] != "pending":
                    break

                number = item["normalized"]
                job["current_number"] = mask_number(number)
                job["error"] = ""
                _clear_wait(job)
                save_job(job)

                status = "failed"
                message = ""
                try:
                    status, message = check_one_number(page, number)
                except PlaywrightTimeout:
                    status, message = "failed", "Timed out waiting for the TPS result page."
                except Exception as exc:
                    status, message = "failed", f"Browser check failed: {exc.__class__.__name__}"

                if status == "rate_limited":
                    successes = 0
                    consecutive_limits += 1
                    if consecutive_limits >= MAX_CONSECUTIVE_LIMITS:
                        job["status"] = "paused"
                        job["error"] = RATE_LIMIT_PAUSE_MESSAGE
                        job["current_number"] = None
                        _clear_wait(job)
                        recount_stats(job)
                        save_job(job)
                        return
                    job["error"] = ""
                    job["current_number"] = mask_number(number)
                    save_job(job)
                    if not wait_or_cancel(
                        job_id,
                        cooldown,
                        f"TPS rate limit — waiting {int(cooldown)}s, then continuing",
                        should_stop,
                    ):
                        job = load_job(job_id) or job
                        if job.get("status") != "paused":
                            job["status"] = "cancelled"
                        job["current_number"] = None
                        _clear_wait(job)
                        save_job(job)
                        return
                    cooldown = min(MAX_COOLDOWN, int(cooldown * 1.5) or MIN_COOLDOWN)
                    continue

                if status == "unknown":
                    item["status"] = "failed"
                    item["message"] = "Could not read a clear result from the TPS page."
                else:
                    item["status"] = status
                    item["message"] = message
                item["checked_at"] = utc_now()
                successes += 1
                consecutive_limits = 0
                if successes >= 3:
                    cooldown = max(MIN_COOLDOWN, int(cooldown * 0.8))
                recount_stats(job)
                save_job(job)
                if not wait_or_cancel(job_id, gap, "", should_stop):
                    job = load_job(job_id) or job
                    job["status"] = "cancelled"
                    job["current_number"] = None
                    _clear_wait(job)
                    save_job(job)
                    return
                break

        job = load_job(job_id) or job
        recount_stats(job)
        job["status"] = "complete"
        job["current_number"] = None
        job["error"] = ""
        _clear_wait(job)
        save_job(job)
    except Exception as exc:
        job = load_job(job_id) or {"id": job_id, "items": []}
        job["status"] = "failed"
        job["error"] = f"Scan stopped: {exc}"
        job["current_number"] = None
        _clear_wait(job)
        save_job(job)
    finally:
        for closer in (page, context, browser):
            try:
                if closer:
                    closer.close()
            except Exception:
                pass
        try:
            if playwright:
                playwright.stop()
        except Exception:
            pass
        _scan_lock.release()
