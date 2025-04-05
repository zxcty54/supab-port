from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import yfinance as yf
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# ✅ Recognized indices (don’t append .NS)
INDEX_SYMBOLS = {"NSEI", "NSEBANK", "BSESN", "DJI", "IXIC", "GSPC"}

@app.route("/update-prices", methods=["GET"])
def update_prices():
    try:
        response = supabase.table("live_prices").select("stock").execute()
        tickers = response.data
        updated = []

        for item in tickers:
            raw_symbol = item["stock"].strip().upper()

            # Index or stock check
            if raw_symbol in INDEX_SYMBOLS:
                ticker_code = raw_symbol
            else:
                ticker_code = raw_symbol + ".NS"

            try:
                ticker = yf.Ticker(ticker_code)

                # 🟢 Index Logic
                if raw_symbol in INDEX_SYMBOLS:
                    fast = ticker.fast_info
                    price = fast.get("lastPrice")
                    prev_close = fast.get("previousClose")

                    if price is None or prev_close is None:
                        raise Exception("Index data not available")

                    change = price - prev_close

                # 🔵 Stock Logic
                else:
                    hist = ticker.history(period="1d")
                    if hist.empty:
                        raise Exception("Stock data not available")

                    latest = hist.iloc[-1]
                    price = float(latest["Close"])
                    prev_close = float(latest["Open"])
                    change = price - prev_close

                # Update to Supabase
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

            except Exception as e:
                print(f"❌ Error fetching {raw_symbol}: {e}")

        return jsonify({"updated": updated}), 200

    except Exception as e:
        print(f"🔥 Main error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
