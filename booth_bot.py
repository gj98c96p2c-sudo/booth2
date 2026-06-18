import os
import requests
from bs4 import BeautifulSoup

# --- 設定項目 ---
# 通知対象：VRChat/3Dモデル関連と、顔・目・体のテクスチャに限定
TARGET_KEYWORDS = [
    "VRChat", "VRC", "3Dモデル", "オリジナル", "アバター", "avatar", 
    "衣装", "素体", "モデル", "キャラクター", "キャラ", "base", "body",
    "アイテクスチャ", "目テクスチャ", "フェイステクスチャ", "顔テクスチャ", 
    "ボディテクスチャ", "肌テクスチャ", "face texture", "eye texture", "body texture"
]

# 除外対象：テクスチャ単体キーワードおよび、不要なカテゴリーを除外
IGNORE_KEYWORDS = [
    "ワールド", "world", "家具", "インテリア", "ステージ", "部屋", "ルーム", 
    "ハウス", "背景", "スカイボックス", "bgm", "BGM", "音源", "ボイス", 
    "楽曲", "テーマ", "パーティクル", "テクスチャ", "texture", "スキン", "skin"
]

# DiscordのWebhook URL（GitHubのSecretsから読み込み）
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def get_booth_items():
    url = "https://booth.pm/ja/browse/3D%E3%83%A2%E3%83%87%E3%83%AB?sort=new"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # BOOTHの商品カードを取得
    items = soup.select(".l-cards-5col_item")
    found_items = []
    
    for item in items:
        title = item.select_one(".item-card_title").text.strip()
        link = "https://booth.pm" + item.select_one("a")["href"]
        
        # 除外キーワードが含まれていたらスキップ
        if any(ignore in title for ignore in IGNORE_KEYWORDS):
            continue
            
        # 通知キーワードが含まれていたらリストに追加
        if any(target in title for target in TARGET_KEYWORDS):
            found_items.append({"title": title, "link": link})
            
    return found_items

def notify_discord(item):
    data = {"content": f"新着アバター・モデルアイテム発見！\n{item['title']}\n{item['link']}"}
    requests.post(DISCORD_WEBHOOK_URL, json=data)

def main():
    seen_file = "seen_items.txt"
    seen_items = set()
    
    if os.path.exists(seen_file):
        with open(seen_file, "r") as f:
            seen_items = set(f.read().splitlines())
            
    items = get_booth_items()
    new_items = []
    
    for item in items:
        if item['link'] not in seen_items:
            notify_discord(item)
            seen_items.add(item['link'])
            new_items.append(item['link'])
            
    with open(seen_file, "w") as f:
        f.write("\n".join(seen_items))

if __name__ == "__main__":
    main()
