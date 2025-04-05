from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
from supabase import create_client
from dotenv import load_dotenv
import threading
import yfinance as yf
import os
import time

load_dotenv()
app = Flask(__name__)
CORS(app)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
INDEX_SYMBOLS = {"NSEI", "NSEBANK", "BSESN", "DJI", "IXIC", "GSPC"}

BATCH_SIZE = 40
DELAY_BETWEEN_BATCH = 15  # seconds

last_updated_time = datetime.min  # 🕒 Global time tracker


def update_in_batches():
    global last_updated_time

    now = datetime.utcnow()
    if now - last_updated_time < timedelta(hours=1):
        print("⏳ Skipping: Last update was less than 1 hour ago.")
        return

    print("📦 Batch update started...")
    try:
        response = supabase.table("live_prices").select("stock").execute()
        all_stocks = response.data
        total = len(all_stocks)
        print(f"🔢 Total stocks: {total}")

        for start in range(0, total, BATCH_SIZE):
            batch = all_stocks[start:start + BATCH_SIZE]
            print(f"🚀 Updating batch: {start} to {start + BATCH_SIZE}")

            for item in batch:
                try:
                    raw_symbol = item["stock"].strip().upper()
                    symbol = raw_symbol if raw_symbol in INDEX_SYMBOLS else raw_symbol + ".NS"

                    ticker = yf.Ticker(symbol)
                    fast = ticker.fast_info

                    price = fast.get("lastPrice")
                    prev_close = fast.get("previousClose")

                    if not price or not prev_close:
                        continue

                    change = round(((price - prev_close) / prev_close) * 100, 2)

                    supabase.table("live_prices").upsert({
                        "stock": raw_symbol,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change,
                        "created_at": datetime.utcnow().isoformat()
                    }, on_conflict=["stock"]).execute()

                    print(f"✅ Updated: {raw_symbol} - ₹{price} ({change}%)")

                except Exception as e:
                    print(f"❌ Error {raw_symbol}: {e}")

            print("⏳ Sleeping for", DELAY_BETWEEN_BATCH, "seconds...")
            time.sleep(DELAY_BETWEEN_BATCH)

        last_updated_time = datetime.utcnow()  # ✅ Update the timestamp
        print("🎉 All batches updated.")

    except Exception as e:
        print("🔥 Error in batch updater:", e)


@app.route("/update-prices", methods=["GET"])
def update_prices():
    threading.Thread(target=update_in_batches).start()
    return jsonify({"message": "Batch update started"}), 200


if __name__ == "__main__":
    app.run()
