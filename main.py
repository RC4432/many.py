import logging
import time
import os
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest
from flask import Flask
from threading import Thread

# --- Secrets aus Umgebungsvariablen ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.environ.get("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Einstellungen ---
POST_INTERVAL_SECONDS = 300  # alle 5 Minuten
MIN_RABATT_PROZENT = 10
KEYWORD = "Nike"
SEARCH_INDEX = "Fashion"
RESOURCES = ["ItemInfo.Title", "Offers.Listings.Price", "Offers.Listings.SavingBasis"]

# --- Bots & APIs ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
amazon = AmazonApi(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, country="DE")

def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

def lade_deals():
    gefiltert = []
    logging.info(f"🔍 Suche nach: {KEYWORD} (SearchIndex: {SEARCH_INDEX})")
    try:
        request = SearchItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            keywords=KEYWORD,
            search_index=SEARCH_INDEX,
            item_count=5,
            resources=RESOURCES
        )
        result = amazon.search_items(request=request)
        time.sleep(2)

        for item in result.items:
            try:
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
                    "shop": "Amazon",
                    "shipping_info": "Versand durch Amazon",
                    "reviews": "–",
                    "rating": "–",
                    "link": item.detail_page_url
                }
                gefiltert.append(deal)
            except Exception as e:
                logging.warning(f"⚠️ Fehler bei Artikel: {e}")
    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info("🕒 Warte 60 Sekunden...")
        time.sleep(60)

    return gefiltert

def format_deal(deal):
    return f"""🤴 {deal['title']}

{deal['price']} € statt {deal['old_price']} € – {deal['discount']} 🔥

🚚 {deal['shop']} / {deal['shipping_info']}
🛒 {deal['link']}

_Anzeige | Affiliate-Link – Du unterstützt mich ohne Mehrkosten._
"""

def post_deals():
    deals = lade_deals()
    if not deals:
        logging.info("🚫 Keine passenden Deals gefunden.")
        return

    logging.info(f"✅ {len(deals)} Deals gefunden.")
    for deal in deals:
        msg = format_deal(deal)
        bot.send_message(chat_id=CHANNEL_NAME, text=msg)
        logging.info("✅ Deal gepostet.")

# --- Webserver für Render/UptimeRobot ---
web = Flask(__name__)

@web.route('/')
def home():
    return '✅ Bot läuft!'

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

	
