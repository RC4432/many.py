import logging
import time
import os
import random
from threading import Thread
from flask import Flask
from telegram import Bot
from amazon_paapi import AmazonApi

# --- Umgebungsvariablen ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL")
AMAZON_ACCESS_KEY = os.getenv("AMAZON_ACCESS_KEY")
AMAZON_SECRET_KEY = os.getenv("AMAZON_SECRET_KEY")
AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG")
KEYWORD = os.getenv("KEYWORD", "Nike")
SEARCH_INDEX = os.getenv("SEARCH_INDEX", "Fashion")
DEBUG = os.getenv("DEBUG", "False") == "True"

# --- Validierung ---
if not all([TELEGRAM_BOT_TOKEN, CHANNEL_NAME, AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG]):
    raise ValueError("❌ Fehlende Umgebungsvariablen. Bitte alle Secrets setzen.")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Telegram Bot & Amazon API ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
amazon = AmazonApi(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOCIATE_TAG, country="DE")

# --- Flask für Render ---
web = Flask(__name__)

@web.route("/")
def home():
    return '✅ Bot läuft'

def run_web():
    web.run(host='0.0.0.0', port=8080)

# --- Konstante ---
POST_INTERVAL_SECONDS = 300  # 5 Minuten
MIN_RABATT_PROZENT = 10

# --- Rabattberechnung ---
def berechne_rabatt(preis, altpreis):
    try:
        return round((1 - (preis / altpreis)) * 100)
    except ZeroDivisionError:
        return 0

# --- Deals abrufen ---
def lade_deals():
    gefiltert = []
    logging.info(f"🔍 Suche nach: {KEYWORD} (SearchIndex: {SEARCH_INDEX})")
    logging.info(f"📦 DEBUG PARAMS: keyword={KEYWORD}, index={SEARCH_INDEX}, tag={AMAZON_ASSOCIATE_TAG}")

    try:
        result = amazon.search_items_by_keywords(keywords=KEYWORD, search_index=SEARCH_INDEX, item_count=3)
        time.sleep(2)

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
                logging.warning(f"⚠️ Fehler bei Artikel: {e}")

    except Exception as e:
        logging.error(f"❌ Amazon API Fehler: {e}")
        logging.info("🕒 Warte 600 Sekunden...")
        time.sleep(600)

    return gefiltert

# --- Formatierter Deal ---
def format_deal(deal):
    return f"""🤴  {deal['title']}

{deal['price']}€  statt {deal['old_price']}€  - {deal['discount']} 🔥

🚚 Verkauft durch {deal['shop']} und {deal['shipping_info']}
{deal['reviews']}: {deal['rating']}

🛒 zu Amazon  {deal['link']}

_Anzeige | Affiliate-Link – Du unterstützt mich ohne Mehrkosten._"""

# --- Deals posten ---
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
            logging.info("✅ Deal gepostet.")

    except Exception as e:
        logging.error(f"Fehler beim Posten: {e}")

# --- Hauptprogramm ---
if __name__ == "__main__":
    logging.info("🚀 Bot gestartet.")
    bot.send_message(chat_id=CHANNEL_NAME, text="👋 Amazon-Dealbot ist jetzt aktiv!")
    Thread(target=run_web).start()

    while True:
        post_deals()
        time.sleep(POST_INTERVAL_SECONDS)
