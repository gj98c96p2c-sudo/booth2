import os
import sys
import time
import requests

# 1. 各チャンネルのWebhook URLをGitHubから読み込みます
# 元の DISCORD_WEBHOOK_URL を「無料オンリー兼デフォルト」として使用します
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# 季節ごとのチャンネルURL
SEASON_WEBHOOKS = {
    "春": os.environ.get("DISCORD_WEBHOOK_SPRING"),
    "夏": os.environ.get("DISCORD_WEBHOOK_SUMMER"),
    "秋": os.environ.get("DISCORD_WEBHOOK_AUTUMN"),
    "冬": os.environ.get("DISCORD_WEBHOOK_WINTER"),
}

SEEN_FILE = "seen_items.txt"
API_URL = "https://vrcfinder.net/api/products?page=0&limit=100&sort=newest"

# 🌸🌻🍁❄️ 各季節の判定キーワード設定
KEYWORDS_SPRING = ["春", "スプリング", "桜", "お花見", "新生活", "イースター"]
KEYWORDS_SUMMER = ["夏", "サマー", "浴衣", "水着", "夏祭り", "海", "サンダル", "花火", "プール"]
KEYWORDS_AUTUMN = ["秋", "オータム", "ハロウィン", "紅葉", "もみじ", "お月見", "月見"]
KEYWORDS_WINTER = ["冬", "ウィンター", "クリスマス", "マフラー", "コート", "正月", "バレンタイン", "雪"]

# 👤 【将来の拡張用】特定のアバター対応
AVATAR_KEYWORDS = []

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
    print("=== VRC Finder 同時仕分け監視 開始 ===", flush=True)
    if not DISCORD_WEBHOOK_URL:
        print("🚨 エラー: DISCORD_WEBHOOK_URL が設定されていません。")
        sys.exit(1)

    seen_ids = load_seen_items()
    new_seen_ids = seen_ids.copy()

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        response = requests.get(API_URL, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"🚨 API取得エラー: {e}")
        return

    items = []
    if isinstance(data, list): items = data
    elif isinstance(data, dict):
        for key in ["products", "data", "items", "results"]:
            if key in data and isinstance(data[key], list):
                items = data[key]; break

    if not items: return

    items.reverse()
    
    for item in items:
        item_id = str(item.get("booth_id") or "").strip()
        if not item_id or item_id == "None" or item_id in seen_ids or item_id in new_seen_ids:
            continue

        title = item.get("ai_title") or item.get("name") or "無題のアセット"
        booth_url = f"https://booth.pm/ja/items/{item_id}"
        category = item.get("ai_category") or "その他"
        
        price = str(item.get("price") or "0").strip()
        is_free = (price == "0")

        raw_keywords = item.get("ai_keywords") or []
        keywords_str = "".join(raw_keywords) if isinstance(raw_keywords, list) else str(raw_keywords)

        # 1. 季節の自動判定
        season_type = None
        if any(word in keywords_str for word in KEYWORDS_SPRING): season_type = "春"
        elif any(word in keywords_str for word in KEYWORDS_SUMMER): season_type = "夏"
        elif any(word in keywords_str for word in KEYWORDS_AUTUMN): season_type = "秋"
        elif any(word in keywords_str for word in KEYWORDS_WINTER): season_type = "冬"

        # 既読リストへの追加フラグ
        should_mark_seen = False

        # 🎯 【ルート①】季節ものの処理（有料・無料に関係なく該当の季節チャンネルへ）
        if season_type:
            season_webhook = SEASON_WEBHOOKS.get(season_type)
            if season_webhook:
                tag_name = f"{category} ｜ 🌟{season_type}服特集" + ("(無料)" if is_free else f"(有料: ￥{price})")
                msg = {"content": f"【🎁VRChat新着｜{tag_name}】{title}\n{booth_url}"}
                try:
                    requests.post(season_webhook, json=msg, timeout=10)
                    time.sleep(0.5)
                    should_mark_seen = True
                except Exception as e:
                    print(f"🚨 {season_type}服チャンネル送信エラー: {e}")
            elif not is_free:
                # 季節チャンネルURLが未登録かつ有料の場合は、安全策として既存の無料チャンネルに通知
                tag_name = f"{category} ｜ 🌟{season_type}服特集(有料: ￥{price})"
                msg = {"content": f"【🎁VRChat新着｜{tag_name}】{title}\n{booth_url}"}
                try:
                    requests.post(DISCORD_WEBHOOK_URL, json=msg, timeout=10)
                    time.sleep(0.5)
                    should_mark_seen = True
                except Exception as e:
                    pass

        # 🎯 【ルート②】無料の処理（季節関係なく、無料なら必ず元々の無料チャンネルへ）
        if is_free:
            if season_type:
                tag_name_free = f"{category} ｜ 🎁無料アセット({season_type}モノ)"
            else:
                tag_name_free = f"{category} ｜ 🎁無料アセット"
                
            msg_free = {"content": f"【🎁VRChat新着｜{tag_name_free}】{title}\n{booth_url}"}
            try:
                requests.post(DISCORD_WEBHOOK_URL, json=msg_free, timeout=10)
                time.sleep(0.5)
                should_mark_seen = True
            except Exception as e:
                print(f"🚨 無料チャンネル送信エラー: {e}")

        # いずれかのチャンネルに送信成功したら既読にする
        if should_mark_seen:
            new_seen_ids.add(item_id)
            print(f"➔ 新着検知・送信完了: {title} (ID: {item_id})")

    save_seen_items(new_seen_ids)
    print("=== 監視終了 ===", flush=True)

if __name__ == "__main__":
    check_vrc_finder()
