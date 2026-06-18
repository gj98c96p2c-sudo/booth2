import os
import sys
import time
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_items.txt"

API_URL = "https://vrcfinder.net/api/products?page=0&limit=22&sort=newest&free_only=true"

def load_seen_items():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_seen_items(seen_ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item_id in sorted(seen_ids):
            f.write(f"{item_id}\n")

def check_vrc_finder():
    print("=== VRC Finder API 監視開始 ===", flush=True)
    if not DISCORD_WEBHOOK_URL:
        print("🚨 エラー: DISCORD_WEBHOOK_URLが設定されていません。")
        sys.exit(1)

    seen_ids = load_seen_items()
    new_seen_ids = seen_ids.copy()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        print("📡 VRC Finder APIからデータ通信中...", flush=True)
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"🚨 API取得エラー: {e}")
        return

    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ["products", "data", "items", "results"]:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break

    if not items:
        print("ℹ️ アイテムが取得できませんでした。")
        return

    print(f"📊 取得成功！現在の無料アイテム数: {len(items)}件")

    # ========================================================
    # 🧪 【ここからテスト用コード】 既読を無視して最初の1件を強制送信
    # ========================================================
    print("📢 [テスト] 1件だけ強制通知テストを実行します...")
    test_item = items[0]  # 一番最初に見つかったアイテム
    test_title = test_item.get("name") or test_item.get("title") or "タイトルなし"
    test_id = str(test_item.get("id") or test_item.get("_id") or test_item.get("boothId") or "no_id")
    test_url = test_item.get("boothUrl") or test_item.get("url")
    if not test_url:
        test_url = f"https://vrcfinder.net/ja/products/{test_id}"

    test_message = {"content": f"【🧪テスト通知】{test_title}\n{test_url}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=test_message, timeout=10)
        print("📢 テスト通知をDiscordに送信しました！確認してください。")
    except Exception as e:
        print(f"🚨 テスト通知の送信に失敗: {e}")
    # ========================================================
    # 🧪 【ここまでテスト用コード】
    # ========================================================

    # 本番用のループ処理（古い順に処理）
    items.reverse()
    
    for item in items:
        item_id = str(item.get("id") or item.get("_id") or item.get("boothId") or "")
        if not item_id:
            continue

        if item_id in seen_ids or item_id in new_seen_ids:
            continue

        title = item.get("name") or item.get("title") or "無題のアセット"
        booth_url = item.get("boothUrl") or item.get("url")
        if not booth_url:
            booth_url = f"https://vrcfinder.net/ja/products/{item_id}"

        new_seen_ids.add(item_id)
        print(f"➔ 新着検知: {title}")
        
        message = {"content": f"【🎁VRChat無料新着】{title}\n{booth_url}"}
        
        try:
            requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
            time.sleep(1)
        except Exception as e:
            print(f"🚨 Discord通知エラー: {e}")

    save_seen_items(new_seen_ids)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_vrc_finder()
