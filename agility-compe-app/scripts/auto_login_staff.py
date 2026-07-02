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
WAKE_TIMEOUT = 10_000
CONNECT_WAIT_MS = 30_000


def main() -> None:
    """アプリにアクセスしてスリープを防ぐ。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print(f"アクセス中: {APP_STAFF_URL}")
            page.goto(APP_STAFF_URL, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            print("ページ読み込み完了")

            # スリープ中なら起動ボタンをクリック
            try:
                page.get_by_text("Yes, get this app back up").click(timeout=WAKE_TIMEOUT)
                print("スリープからの復帰ボタンをクリックしました")
            except PlaywrightTimeoutError:
                print("復帰ボタンなし（起動中）")

            # WebSocket接続確立のために待機
            page.wait_for_timeout(CONNECT_WAIT_MS)
            print("アクセス完了")

        except PlaywrightTimeoutError as e:
            print(f"タイムアウトエラー: {e}", file=sys.stderr)
            sys.exit(1)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
