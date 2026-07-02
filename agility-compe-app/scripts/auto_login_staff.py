"""スタッフアプリのスリープ回避スクリプト。

Playwright でアプリ URL を実際にレンダリングして WebSocket 接続を確立し、
Streamlit のスリープを防ぐ。
環境変数 APP_STAFF_URL が必要。
"""

import os
import sys

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

APP_STAFF_URL: str = os.environ["APP_STAFF_URL"]

PAGE_TIMEOUT = 60_000
WAKE_TIMEOUT = 5_000


def main() -> None:
    """アプリにアクセスしてスリープを防ぐ。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print(f"アクセス中: {APP_STAFF_URL}")
            page.goto(APP_STAFF_URL, timeout=PAGE_TIMEOUT)

            # スリープ中なら起動ボタンをクリック
            try:
                page.get_by_text("Yes, get this app back up").click(timeout=WAKE_TIMEOUT)
                print("スリープからの復帰ボタンをクリックしました")
            except PlaywrightTimeoutError:
                pass

            # アプリの読み込み完了を待つ（WebSocket接続確立）
            page.wait_for_selector("text=スタッフ画面", timeout=PAGE_TIMEOUT)
            print("アクセス成功")

        except PlaywrightTimeoutError as e:
            print(f"タイムアウトエラー: {e}", file=sys.stderr)
            page.screenshot(path="error_screenshot.png")
            print("スクリーンショットを error_screenshot.png に保存しました")
            sys.exit(1)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
