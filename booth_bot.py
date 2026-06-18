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

# ★ どんなキー名でタイトルが入っていても自動で探し出す賢い関数
def judge_and_get_title(item_dict):
    # 1. ありがちなキー名で完全一致検索
    for key in ["name", "title", "itemName", "productName", "nameJa", "titleJa", "heading"]:
        val = item_dict.get(key)
        if val:
            if isinstance(val, str): return val
            if isinstance(val, dict): return next(iter(val.values())) # 辞書型なら中身を取り出す

    # 2. キー名に 'name' や 'title' が含まれる文字列を探す (大文字小文字無視)
    for key, val in item_dict.items():
        if ("name" in key.lower() or "title" in key.lower()) and isinstance(val, str) and val.strip():
            return val.strip()

    # 3. 最終手段：URLや画像、IDっぽくない「2文字以上の普通の文字列」を引っ張り出す
    for key, val in item_dict.items():
        if isinstance(val, str) and len(val) >= 2:
            key_lower = key.lower()
            if not val.startswith("http") and not any(x in key_lower for x in ["id", "url", "image", "thumb", "path", "locale"]):
                return val.strip()
                
    return "無題のアセット"

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
    
    # --------------------------------------------------------
    # 🛠 【デバッグ用】データの構造（キー一覧）をDiscordにこっそり報告
    # --------------------------------------------------------
    if items:
        sample = items[0]
        inner_sample = sample.get("product") or sample.get("item") or sample
        keys_list = list(inner_sample.keys())
        sample_str = str({k: str(v)[:25] for k, v in inner_sample.items()})[:150]
        try:
            debug_msg = f"⚙️ [システムログ] キー一覧: {keys_list}\n中身サンプル: {sample_str}"
            requests.post(DISCORD_WEBHOOK_URL, json={"content": debug_msg}, timeout=10)
        except:
            pass
    # --------------------------------------------------------

    items.reverse()
    
    for item in items:
        inner_item = item.get("product") or item.get("item") or item

        # IDの抽出
        raw_id = (
            inner_item.get("id") or 
            inner_item.get("boothId") or 
            inner_item.get("booth_id") or 
            inner_item.get("idInBooth") or
            inner_item.get("_id")
        )
        item_id = str(raw_id).strip() if raw_id is not None else ""

        if not item_id or item_id == "None":
            continue

        # 既読チェック
        if item_id in seen_ids or item_id in new_seen_ids:
            continue

        # ★ 強化した関数でタイトルを抽出
        title = judge_and_get_title(inner_item)
        
        # URLの抽出
        booth_url = inner_item.get("boothUrl") or inner_item.get("url") or inner_item.get("link")
        if not booth_url:
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
