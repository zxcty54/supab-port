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

@app.route("/update-prices", methods=["GET"])
def update_prices():
    try:
        response = supabase.table("live_prices").select("stock").execute()
        tickers = response.data
        updated = []

        for item in tickers:
            raw_ticker = item["stock"]

            # Add .NS only for Indian stocks
            if not raw_ticker.startswith("^") and not raw_ticker.endswith(".NS"):
                ticker_code = raw_ticker + ".NS"
            else:
                ticker_code = raw_ticker

            try:
                ticker = yf.Ticker(ticker_code)
                info = ticker.info

                price = info.get("regularMarketPrice")
                prev_close = info.get("previousClose")

                if price is not None and prev_close is not None:
                    change = round(price - prev_close, 2)

                    # Upsert price
                    supabase.table("live_prices").upsert({
                        "stock": raw_ticker,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change,
                        "created_at": datetime.utcnow().isoformat()
                    }, on_conflict=["stock"]).execute()

                    updated.append({
                        "stock": raw_ticker,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change
                    })

            except Exception as e:
                print(f"Error fetching {ticker_code}: {e}")

        return jsonify({"updated": updated}), 200

    except Exception as e:
        print(f"Error updating prices: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
