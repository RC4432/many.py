import os
import logging
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest
from flask import Flask
from threading import Thread
import time

# --- Umgebungsvariablen ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")

# 🔎 Feste Werte zum Testen
BRAND = "Nike"
SEARCH_INDEX = "Fashion"

# --- Debugging ---
print("🔧 BRAND:", BRAND)
print("🔧 SEARCH_INDEX:", SEARCH_INDEX)
print("🔧 ASSOCIATE_TAG:", AMAZON_ASSOCIATE_TAG)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
amazon = AmazonApi(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, country="DE")

# --- Flask für Render am Leben halten ---
web = Flask(__name__)

@web.route('/')
def home():
    return "✅ Bot läuft"

def run_web():
    web.run(host='0.0.0.0', port=8080)

# --- Deal-Funktion ---
def lade_deal():
    try:
        request = SearchItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            brand=BRAND,
            search_index=SEARCH_INDEX,
            item_count=1,
            resources=["ItemInfo.Title", "Offers.Listings.Price", "Offers.Listings.SavingBasis"]
        )

        result = amazon.search_items(request=request)
        if not result.items:
            logging.warning("❌ Keine Artikel gefunden.")
            return

        item = result.items[0]
        title = item.item_info.title.display_value
        price = item.offers.listings[0].price.amount
        link = item.detail_page_url

        msg = f"""🛍️ *{title}*\n\n💶 {price} €\n[🔗 Zum Deal]({link})\n\n_Anzeige – Amazon Affiliate_"""
        bot.send_message(chat_id=CHANNEL_NAME, text=msg, parse_mode="Markdown")

        logging.info("✅ Deal gepostet.")

    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")

# --- Start ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Test läuft – wir checken deinen API-Zugang!")
    Thread(target=run_web).start()
    lade_deal()

