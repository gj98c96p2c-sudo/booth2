import os
import sys
import time
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
SEEN_FILE = "seen_items.txt"

# 突き止めてもらったVRC Finderの神API URL
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

    # --- JSONのデータ構造を自動判別して中身を取り出す ---
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # APIが辞書型だった場合、よくあるキーから商品リストを探す
        for key in ["products", "data", "items", "results"]:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        # もし上記で見つからず、特定の構造だったらここにデバッグ出力
        if not items:
            print(f"⚠️ データの解析に失敗しました。取得したJSONの形: {list(data.keys())}")
            return

    if not items:
        print("ℹ️ 新着アイテムが0件、または解析できませんでした。")
        return

    # 古い順に処理して最新が最後に通知されるように反転
    items.reverse()
    
    for item in items:
        # 商品の識別IDを取得（一意のキーを探索）
        item_id = str(item.get("id") or item.get("_id") or item.get("boothId") or "")
        if not item_id:
            continue

        # 既読チェック
        if item_id in seen_ids or item_id in new_seen_ids:
            continue

        # タイトルとリンクの取得（一般的なキーから安全に抽出）
        title = item.get("name") or item.get("title") or "無題のアセット"
        
        # BOOTHの直リンク、またはVRC Finderの商品ページURLを生成
        booth_url = item.get("boothUrl") or item.get("url")
        if not booth_url:
            # URLがデータ内に無ければ、IDを使ってVRC Finderの詳細ページへ飛ばすリンクを生成
            booth_url = f"https://vrcfinder.net/ja/products/{item_id}"

        new_seen_ids.add(item_id)
        print(f"➔ 新着検知: {title}")
        
        # Discord用のメッセージ作成
        message = {"content": f"【🎁VRChat無料新着】{title}\n{booth_url}"}
        
        try:
            requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
            time.sleep(1) # 連投対策の1秒ウェイト
        except Exception as e:
            print(f"🚨 Discord通知エラー: {e}")

    save_seen_items(new_seen_ids)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_vrc_finder()
