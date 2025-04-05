from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import yfinance as yf
import os
from dotenv import load_dotenv
from supabase import create_client
import time

load_dotenv()

app = Flask(__name__)
CORS(app)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
INDEX_SYMBOLS = {"NSEI", "NSEBANK", "BSESN", "DJI", "IXIC", "GSPC"}

@app.route('/update-prices', methods=['GET'])
def update_prices():
    try:
        tickers_data = supabase.table("live_prices").select("stock").execute().data
        all_updated = []

        # Batch of 20 tickers at a time
        for i in range(0, len(tickers_data), 20):
            batch = tickers_data[i:i + 20]
            print(f"⏳ Processing batch {i // 20 + 1}...")

            for item in batch:
                raw_symbol = item['stock'].strip().upper()
                symbol = raw_symbol if raw_symbol in INDEX_SYMBOLS else raw_symbol + ".NS"

                try:
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

                    all_updated.append({
                        "stock": raw_symbol,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change
                    })

                except Exception as e:
                    print(f"❌ {raw_symbol} error: {e}")

            # Wait between batches to avoid overload
            time.sleep(15)

        return jsonify({"updated": all_updated}), 200

    except Exception as e:
        print("🔥 Error:", e)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run()
