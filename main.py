import logging
import time
import os
from threading import Thread
from flask import Flask
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest

# --- Flask Webserver für Render/UptimeRobot ---
web = Flask(__name__)

@web.route('/')
def home():
    return '✅ Bot läuft'

def run_web():
    web.run(host='0.0.0.0', port=8080)

# --- Umgebungsvariablen ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
KEYWORD = os.getenv("KEYWORD", "Nike")
SEARCH_INDEX = os.getenv("SEARCH_INDEX", "Fashion")
DEBUG = os.getenv("DEBUG", "False") == "True"

# --- Logging konfigurieren ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Validierung ---
VALID_SEARCH_INDICES = {
    "All","AmazonVideo","Apparel","Appliances","Automotive","Baby","Beauty","Books",
    "Classical","Computers","DigitalMusic","Electronics","EverythingElse","Fashion",
    "ForeignBooks","GardenAndOutdoor","GiftCards","GroceryAndGourmetFood","Handmade",
    "HealthPersonalCare","HomeAndKitchen","Industrial","Jewelry","KindleStore","Lighting",
    "Luggage","LuxuryBeauty","Magazines","MobileApps","MoviesAndTV","Music",
    "MusicalInstruments","OfficeProducts","PetSupplies","Photo","Shoes","Software",
    "SportsAndOutdoors","ToolsAndHomeImprovement","ToysAndGames","VHS","VideoGames","Watches"
}

if SEARCH_INDEX not in VALID_SEARCH_INDICES:
    raise ValueError(f"❌ Ungültiger SearchIndex: {SEARCH_INDEX}")

if not all([TELEGRAM_BOT_TOKEN, CHANNEL_NAME, AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, KEYWORD]):
    raise ValueError("❌ Eine oder mehrere erforderliche Umgebungsvariablen fehlen!")

# --- Telegram-Bot ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# --- Amazon API ---
amazon = AmazonApi(
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_ASSOCIATE_TAG,
    country="DE"
)

# --- Konfiguration ---
POST_INTERVAL_SECONDS = 300
MIN_RABATT_PROZENT = 10
backoff_interval = 600

resources = ["ItemInfo.Title", "Offers.Listings.Price", "Offers.Listings.SavingBasis"]

def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

def lade_deals():
    global backoff_interval
    gefiltert = []

    logging.info(f"🔍 Suche nach: {KEYWORD} (SearchIndex: {SEARCH_INDEX})")
    logging.info(f"📦 DEBUG PARAMS: keyword={KEYWORD}, index={SEARCH_INDEX}, tag={AMAZON_ASSOCIATE_TAG}")

    try:
        request = SearchItemsRequest(
            partner_tag=AMAZON_ASSOCIATE_TAG,
            partner_type="Associates",
            keywords=KEYWORD,
            search_index=SEARCH_INDEX,
            item_count=5,
            resources=resources
        )

        result = amazon.search_items(request=request)
        time.sleep(2)

        backoff_interval = 600

        if not result.items:
            logging.warning("⚠️ Keine Artikel von Amazon erhalten.")
            return []

        for item in result.items:
            try:
                if not item.offers or not item.offers.listings:
                    continue

                title = item.item_info.title.display_value
                price = float(item.offers.listings[0].price.amount)
                savings = float(item.offers.listings[0].price.savings.amount) if item.offers.listings[0].price.savings else 0.0
                old_price = price + savings
                discount = berechne_rabatt(price, old_price)

                if discount < MIN_RABATT_PROZENT:
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
                gefiltert.append(deal)

            except Exception as e:
                logging.warning(f"Fehler bei Artikel: {e}")

    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info(f"🕒 Warte {backoff_interval} Sekunden...")
        time.sleep(backoff_interval)
        backoff_interval = min(backoff_interval * 2, 3600)

    return gefiltert

def format_deal(deal):
    return f"""🤴  {deal['title']}

{deal['price']}€  statt {deal['old_price']}€  - {deal['discount']} 🔥

🚚 Verkauft durch {deal['shop']} und {deal['shipping_info']}
{deal['reviews']}: {deal['rating']}

🛒 zu Amazon  {deal['link']}

_Anzeige | Affiliate-Link – Du unterstützt mich ohne Mehrkosten._"""

def post_deals():
    try:
        deals = lade_deals()
        if not deals:
            logging.info("Keine passenden Deals gefunden.")
            return

        logging.info(f"{len(deals)} Deals gefunden.")
        for deal in deals:
            msg = format_deal(deal)
            bot.send_message(chat_id=CHANNEL_NAME, text=msg)
            logging.info("Deal gepostet.")
    except Exception as e:
        logging.error(f"Fehler beim Posten: {e}")

# --- Start ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")
    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)
