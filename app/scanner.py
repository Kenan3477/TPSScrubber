from __future__ import annotations

import os
import threading
import time
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

_scan_lock = threading.Lock()


def delay_seconds() -> float:
    try:
        return max(1.0, float(os.getenv("TPS_DELAY_SECONDS", "3.5")))
    except ValueError:
        return 3.5


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
        return "rate_limited", "TPS public checker rate limit reached. Wait and resume later."
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
        save_job(job)

        playwright, browser, context, page = _open_browser()
        wait = delay_seconds()

        for item in job["items"]:
            fresh = load_job(job_id)
            if fresh and fresh.get("status") == "cancelled":
                job["status"] = "cancelled"
                job["current_number"] = None
                save_job(job)
                return
            if should_stop and should_stop():
                job["status"] = "cancelled"
                job["current_number"] = None
                save_job(job)
                return
            if item["status"] != "pending":
                continue

            number = item["normalized"]
            job["current_number"] = mask_number(number)
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
                item["status"] = "pending"
                item["message"] = message
                job["status"] = "paused"
                job["error"] = message
                job["current_number"] = None
                recount_stats(job)
                save_job(job)
                return

            if status == "unknown":
                item["status"] = "failed"
                item["message"] = "Could not read a clear result from the TPS page."
            else:
                item["status"] = status
                item["message"] = message
            item["checked_at"] = utc_now()
            recount_stats(job)
            save_job(job)
            time.sleep(wait)

        recount_stats(job)
        job["status"] = "complete"
        job["current_number"] = None
        job["error"] = ""
        save_job(job)
    except Exception as exc:
        job = load_job(job_id) or {"id": job_id, "items": []}
        job["status"] = "failed"
        job["error"] = f"Scan stopped: {exc}"
        job["current_number"] = None
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
