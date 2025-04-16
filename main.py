import os
import time
import logging
from flask import Flask
from threading import Thread
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest

# --- Flask Setup ---
web = Flask(__name__)

@web.route('/')
def home():
    return "✅ Amazon-Dealbot läuft!"

def run_web():
    web.run(host='0.0.0.0', port=8080)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Environment Variables ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
KEYWORD = os.getenv("KEYWORD", "Nike")
SEARCH_INDEX = os.getenv("SEARCH_INDEX", "Fashion")

# Debug-Check
print("DEBUG CHECK:")
print("KEYWORD:", KEYWORD)
print("SEARCH_INDEX:", SEARCH_INDEX)

# --- Validierung ---
if not all([TELEGRAM_BOT_TOKEN, CHANNEL_NAME, AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG]):
    raise ValueError("❌ Eine oder mehrere Umgebungsvariablen fehlen.")

# --- Telegram-Bot Setup ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# --- Amazon API Setup ---
amazon = AmazonApi(
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_ASSOCIATE_TAG,
    country="DE"
)

POST_INTERVAL_SECONDS = 600
MIN_RABATT_PROZENT = 10

def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

def lade_deals():
    deals = []
    logging.info(f"🔍 Suche nach: {KEYWORD} (SearchIndex: {SEARCH_INDEX})")
    logging.info(f"📦 DEBUG PARAMS: keyword={KEYWORD}, index={SEARCH_INDEX}, tag={AMAZON_ASSOCIATE_TAG}")

    try:
request = SearchItemsRequest(
    partner_tag=AMAZON_ASSOCIATE_TAG,
    partner_type="Associates",
    brand="Nike",  # 🔥 Nur die Marke!
    search_index="Fashion",  # Gültiger Index – wichtig!
    item_count=5,
    resources=[
        "ItemInfo.Title",
        "Offers.Listings.Price",
        "Offers.Listings.SavingBasis",
        "Images.Primary.Large"
    ]
)

        result = amazon.search_items(request=request)
        time.sleep(1)

        for item in result.items:
            try:
                title = item.item_info.title.display_value
                price = float(item.offers.listings[0].price.amount)
                savings = float(item.offers.listings[0].price.savings.amount) if item.offers.listings[0].price.savings else 0.0
                old_price = price + savings
                rabatt = berechne_rabatt(price, old_price)

                if rabatt < MIN_RABATT_PROZENT:
                    continue

                deals.append({
                    "title": title,
                    "price": price,
                    "old_price": old_price,
                    "discount": f"{rabatt} %",
                    "link": item.detail_page_url
                })

            except Exception as e:
                logging.warning(f"⚠️ Fehler beim Verarbeiten eines Artikels: {e}")

    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info("🕒 Warte 600 Sekunden...")
        time.sleep(600)

    return deals

def format_deal(deal):
    return f"""🤖 *{deal['title']}*

💸 *{deal['price']}€* statt *{deal['old_price']}€* – {deal['discount']} Rabatt!

👉 [Zum Deal auf Amazon]({deal['link']})

_Affiliate-Link – Danke für deine Unterstützung!_
"""

def post_deals():
    deals = lade_deals()
    if not deals:
        logging.info("❌ Keine passenden Deals gefunden.")
        return

    logging.info(f"✅ {len(deals)} Deals gefunden.")
    for deal in deals:
        try:
            msg = format_deal(deal)
            bot.send_message(chat_id=CHANNEL_NAME, text=msg, parse_mode="Markdown")
            logging.info("📬 Deal gesendet.")
        except Exception as e:
            logging.error(f"❌ Fehler beim Senden an Telegram: {e}")

# --- Start ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")

    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)

