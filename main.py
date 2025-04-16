import os
import time
import logging
from flask import Flask
from threading import Thread
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest

# --- Logging konfigurieren ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Flask Setup für Render/UptimeRobot ---
web = Flask(__name__)

@web.route('/')
def home():
    return '✅ Bot läuft!'

def run_web():
    web.run(host="0.0.0.0", port=8080)

# --- Umgebungsvariablen ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")

# Optional: Feste Werte
BRAND = os.getenv("BRAND", "Nike")
SEARCH_INDEX = os.getenv("SEARCH_INDEX", "Fashion")
POST_INTERVAL_SECONDS = int(os.getenv("POST_INTERVAL", 600))

# Debug-Ausgabe
logging.info(f"🔍 Suche nach Brand: {BRAND} (Index: {SEARCH_INDEX}) mit Tag {AMAZON_ASSOCIATE_TAG}")

# --- Telegram Bot Setup ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# --- Amazon API Setup ---
amazon = AmazonApi(
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_ASSOCIATE_TAG,
    country="DE"
)

# --- Rabattberechnung ---
def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

# --- Deal-Suche ---
def lade_deals():
    deals = []
    try:
        request = SearchItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            brand=BRAND,
            search_index=SEARCH_INDEX,
            item_count=5,
            resources=[
                "ItemInfo.Title",
                "Offers.Listings.Price",
                "Offers.Listings.SavingBasis",
                "Images.Primary.Large"
            ]
        )

        result = amazon.search_items(request=request)
        time.sleep(1.5)

        for item in result.items:
            if not item.offers or not item.offers.listings:
                continue

            title = item.item_info.title.display_value
            price = float(item.offers.listings[0].price.amount)
            savings = float(item.offers.listings[0].price.savings.amount) if item.offers.listings[0].price.savings else 0.0
            old_price = price + savings
            discount = berechne_rabatt(price, old_price)

            if discount < 10:
                continue

            deal = {
                "title": title,
                "price": price,
                "old_price": old_price,
                "discount": f"{discount} %",
                "shop": "Amazon",
                "shipping_info": "Versand durch Amazon",
                "reviews": "–",
                "rating": "–",
                "link": item.detail_page_url
            }

            deals.append(deal)

    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info("🕒 Warte 600 Sekunden...")
        time.sleep(600)

    return deals

# --- Nachricht Formatieren ---
def format_deal(deal):
    return f"""🤴  {deal['title']}

{deal['price']}€ statt {deal['old_price']}€ – {deal['discount']} 🔥

🚚 {deal['shop']} | {deal['shipping_info']}
{deal['reviews']}: {deal['rating']}

🛒 [Deal auf Amazon]({deal['link']})

_Anzeige | Affiliate-Link – Du unterstützt mich ohne Mehrkosten._
"""

# --- Senden ---
def post_deals():
    deals = lade_deals()
    if not deals:
        logging.info("😴 Keine Deals gefunden.")
        return

    for deal in deals:
        msg = format_deal(deal)
        try:
            bot.send_message(chat_id=CHANNEL_NAME, text=msg, parse_mode="Markdown")
            logging.info("✅ Deal gepostet.")
        except Exception as e:
            logging.error(f"❌ Fehler beim Posten: {e}")

# --- Main ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")
    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)

