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
    
    # 【デバッグ用】1件目のデータの全キーをログに出して構造を暴く
    if items:
        print(f"🛠 [デバッグ] データ1件目の全情報: {items[0]}")

    items.reverse()
    
    for item in items:
        # ネスト（入れ子）構造対策：もし中に 'product' や 'item' という部屋があればそこを基準にする
        inner_item = item.get("product") or item.get("item") or item

        # あらゆるIDのキー名候補を片っ端から探す
        raw_id = (
            inner_item.get("id") or 
            inner_item.get("boothId") or 
            inner_item.get("booth_id") or 
            inner_item.get("idInBooth") or
            inner_item.get("_id")
        )
        item_id = str(raw_id).strip() if raw_id is not None else ""

        # IDがどうしても取れない場合はスキップ
        if not item_id or item_id == "None":
            continue

        # 既読チェック
        if item_id in seen_ids or item_id in new_seen_ids:
            continue

        # あらゆるタイトルのキー名候補を探す
        title = (
            inner_item.get("name") or 
            inner_item.get("title") or 
            inner_item.get("itemName") or 
            "無題のアセット"
        )
        
        # あらゆるURLのキー名候補を探す
        booth_url = inner_item.get("boothUrl") or inner_item.get("url") or inner_item.get("link")
        if not booth_url:
            # URLがデータ内に無ければ、IDを使ってページURLを生成
            booth_url = f"https://vrcfinder.net/ja/products/{item_id}"

        new_seen_ids.add(item_id)
        print(f"➔ 新着検知: {title} (ID: {item_id})")
        
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
