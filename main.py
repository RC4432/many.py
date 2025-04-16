import logging
import time
import os
from flask import Flask
from threading import Thread
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest

# --- Secrets aus Umgebungsvariablen ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.environ.get("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG")

# --- Validierung ---
if not all([TELEGRAM_BOT_TOKEN, CHANNEL_NAME, AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG]):
    raise ValueError("❌ Fehlende Umgebungsvariablen!")

# --- Konfiguration ---
POST_INTERVAL_SECONDS = 900  # 15 Minuten
MIN_RABATT_PROZENT = 20
backoff_interval = 600

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Telegram Bot & Amazon API Setup ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
amazon = AmazonApi(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, country="DE")

# --- Deal-Suche ---
def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

def lade_deals():
    global backoff_interval
    deals = []

    keyword = "Samsung"
    search_index = "Electronics"
    resources = ["ItemInfo.Title", "Offers.Listings.Price", "Offers.Listings.SavingBasis"]

    logging.info(f"🔍 Suche nach: {keyword} (Index: {search_index})")
    try:
        request = SearchItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            keywords=keyword,
            search_index=search_index,
            item_count=3,
            resources=resources
        )

        result = amazon.search_items(request=request)
        time.sleep(2)
        backoff_interval = 600

        if not result.items:
            logging.warning("⚠️ Keine Ergebnisse.")
            return []

        for item in result.items:
            try:
                if not item.offers or not item.offers.listings:
                    continue

                title = item.item_info.title.display_value
                price = float(item.offers.listings[0].price.amount)
                savings = float(item.offers.listings[0].price.savings.amount) if item.offers.listings[0].price.savings else 0
                old_price = price + savings
                rabatt = berechne_rabatt(price, old_price)

                if rabatt < MIN_RABATT_PROZENT:
                    continue

                deals.append({
                    "title": title,
                    "price": price,
                    "old_price": old_price,
                    "discount": f"{rabatt} %",
                    "shop": "Amazon",
                    "shipping_info": "Versand durch Amazon",
                    "reviews": "–",
                    "rating": "–",
                    "link": item.detail_page_url
                })

            except Exception as e:
                logging.warning(f"🟠 Fehler bei Artikel: {e}")

    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info(f"🕒 Warte {backoff_interval} Sekunden...")
        time.sleep(backoff_interval)
        backoff_interval = min(backoff_interval * 2, 3600)

    return deals

def format_deal(deal):
    return f"""🤴 {deal['title']}

{deal['price']}€ statt {deal['old_price']}€  - {deal['discount']} 🔥

🚚 {deal['shipping_info']}
🛒 {deal['link']}

_Anzeige | Affiliate-Link – Du unterstützt mich ohne Mehrkosten._
"""

def post_deals():
    try:
        deals = lade_deals()
        if not deals:
            logging.info("🚫 Keine Deals gefunden.")
            return

        logging.info(f"📦 {len(deals)} Deals gefunden.")
        for deal in deals:
            bot.send_message(chat_id=CHANNEL_NAME, text=format_deal(deal))
            logging.info("✅ Deal gepostet.")
    except Exception as e:
        logging.error(f"❌ Fehler beim Posten: {e}")

# --- Flask Server für UptimeRobot ---
web = Flask(__name__)

@web.route('/')
def home():
    return '✅ Bot läuft'

def run_web():
    web.run(host='0.0.0.0', port=8080)

# --- Start ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")
    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)
