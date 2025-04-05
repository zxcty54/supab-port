from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import yfinance as yf
from supabase import create_client
import os
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

INDEX_SYMBOLS = {"NSEI", "NSEBANK", "BSESN", "DJI", "IXIC", "GSPC"}

def batch_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

@app.route("/update-prices", methods=["GET"])
def update_prices():
    try:
        response = supabase.table("live_prices").select("stock").execute()
        tickers = [item["stock"].strip().upper() for item in response.data]

        updated = []

        for batch in batch_list(tickers, 20):  # ✅ 20 stocks per batch
            for raw_symbol in batch:
                if raw_symbol in INDEX_SYMBOLS:
                    ticker_code = raw_symbol
                else:
                    ticker_code = raw_symbol + ".NS"

                try:
                    ticker = yf.Ticker(ticker_code)

                    if raw_symbol in INDEX_SYMBOLS:
                        fast = ticker.fast_info
                        price = fast.get("lastPrice")
                        prev_close = fast.get("previousClose")
                        if price is None or prev_close is None:
                            raise Exception("Index data not available")
                    else:
                        fast = ticker.fast_info
                        price = fast.get("lastPrice")
                        prev_close = fast.get("previousClose")
                        if price is None or prev_close is None:
                            raise Exception("Stock data not available")

                    change = round(((price - prev_close) / prev_close) * 100, 2)

                    supabase.table("live_prices").upsert({
                        "stock": raw_symbol,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change,
                        "created_at": datetime.utcnow().isoformat()
                    }, on_conflict=["stock"]).execute()

                    updated.append({
                        "stock": raw_symbol,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change
                    })

                    print(f"✅ {raw_symbol} updated: ₹{price}, Change: {change}%")

                except Exception as e:
                    print(f"❌ Error fetching {raw_symbol}: {e}")

            print("⏳ Waiting 15 seconds before next batch...")
            time.sleep(15)  # ✅ 15-second delay between batches

        return jsonify({"updated": updated}), 200

    except Exception as e:
        print(f"🔥 Main error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
