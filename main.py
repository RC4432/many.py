import os
import time
import logging
from flask import Flask
from threading import Thread
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest

# --- Konfiguration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG") or "DEIN_TAG"  # 🔁 falls None, benutze Testwert

KEYWORD = os.getenv("KEYWORD") or "Nike"
SEARCH_INDEX = os.getenv("SEARCH_INDEX") or "Fashion"

POST_INTERVAL_SECONDS = 900  # 15 Min
MIN_RABATT_PROZENT = 10

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App für Render/UptimeRobot ---
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Bot läuft"

def run_web():
    web.run(host="0.0.0.0", port=8080)

# --- Telegram Bot ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# --- Amazon API ---
amazon = AmazonApi(
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_ASSOCIATE_TAG,
    country="DE"
)

def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except:
        return 0

def lade_deals():
    logging.info(f"🔍 Suche nach: {KEYWORD} (SearchIndex: {SEARCH_INDEX})")
    logging.info(f"📦 DEBUG PARAMS: keyword={KEYWORD}, index={SEARCH_INDEX}, tag={AMAZON_ASSOCIATE_TAG}")

    gefiltert = []
    try:
        request = SearchItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            keywords=KEYWORD,
            search_index=SEARCH_INDEX,
            item_count=3,
            resources=["ItemInfo.Title", "Offers.Listings.Price", "Offers.Listings.SavingBasis"]
        )

        result = amazon.search_items(request=request)
        time.sleep(2)

        for item in result.items:
            try:
                if not item.offers or not item.offers.listings:
                    continue

                title = item.item_info.title.display_value
                price = float(item.offers.listings[0].price.amount)
                savings = float(item.offers.listings[0].price.savings.amount) if item.offers.listings[0].price.savings else 0.0
                old_price = price + savings
                rabatt = berechne_rabatt(price, old_price)

                if rabatt < MIN_RABATT_PROZENT:
                    continue

                deal = {
                    "title": title,
                    "price": price,
                    "old_price": old_price,
                    "discount": f"{rabatt} %",
                    "link": item.detail_page_url
                }
                gefiltert.append(deal)
            except Exception as e:
                logging.warning(f"❗ Fehler bei Artikel: {e}")
    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info("🕒 Warte 600 Sekunden...")
        time.sleep(600)

    return gefiltert

def format_deal(deal):
    return f"""🛒 {deal['title']}

{deal['price']}€ statt {deal['old_price']}€ – {deal['discount']} 🔥

👉 [Jetzt zu Amazon]({deal['link']})

_Affiliate-Link. Du unterstützt mich kostenlos ❤️_
"""

def post_deals():
    deals = lade_deals()
    if not deals:
        logging.info("ℹ️ Keine Deals gefunden.")
        return

    for deal in deals:
        try:
            bot.send_message(chat_id=CHANNEL_NAME, text=format_deal(deal), parse_mode="Markdown")
            logging.info("✅ Deal gepostet.")
        except Exception as e:
            logging.error(f"⚠️ Fehler beim Senden: {e}")

# --- Start ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")

    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)

