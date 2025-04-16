import logging
import time
import os
from threading import Thread
from flask import Flask
from telegram import Bot
from amazon_paapi import AmazonApi
from amazon_paapi.sdk.models.search_items_request import SearchItemsRequest

# --- Webserver für Render / Replit am Leben halten ---
web = Flask(__name__)

@web.route('/')
def home():
    return '✅ Amazon-Dealbot läuft!'

def run_web():
    web.run(host='0.0.0.0', port=8080)

# --- Umgebungsvariablen auslesen ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.environ.get("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.environ.get("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.environ.get("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.environ.get("AMAZON_ASSOCIATE_TAG")
KEYWORD = os.environ.get("KEYWORD")
SEARCH_INDEX = os.environ.get("SEARCH_INDEX")

# --- Debug-Ausgabe ---
print("🧪 DEBUG: KEYWORD =", KEYWORD)
print("🧪 DEBUG: SEARCH_INDEX =", SEARCH_INDEX)
print("🧪 DEBUG: TELEGRAM_BOT_TOKEN =", TELEGRAM_BOT_TOKEN)
print("🧪 DEBUG: TELEGRAM_CHANNEL =", CHANNEL_NAME)
print("🧪 DEBUG: AMAZON_ASSOCIATE_TAG =", AMAZON_ASSOCIATE_TAG)

# --- Validierung ---
if not all([TELEGRAM_BOT_TOKEN, CHANNEL_NAME, AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, KEYWORD, SEARCH_INDEX]):
    raise ValueError("❌ Eine oder mehrere Umgebungsvariablen fehlen! Bitte KEYWORD, SEARCH_INDEX und Amazon/Telegram-Keys setzen.")

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

# --- Einstellungen ---
POST_INTERVAL_SECONDS = 300  # 5 Minuten
MIN_RABATT_PROZENT = 10
backoff_interval = 600

# --- Logging konfigurieren ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Bots initialisieren ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
amazon = AmazonApi(
    AMAZON_ACCESS_KEY,
    AMAZON_SECRET_KEY,
    AMAZON_ASSOCIATE_TAG,
    country="DE"
)

def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

def lade_deals():
    global backoff_interval
    gefiltert = []
    resources = ["ItemInfo.Title", "Offers.Listings.Price", "Offers.Listings.SavingBasis"]

    logging.info(f"🔍 Suche nach: {KEYWORD} (SearchIndex: {SEARCH_INDEX})")
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
        time.sleep(1.5)
        backoff_interval = 600

        if not result.items:
            logging.warning("Keine Ergebnisse von Amazon erhalten.")
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

if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")
    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)
