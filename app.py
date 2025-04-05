from flask import Flask, jsonify
from supabase import create_client
from datetime import datetime
import yfinance as yf
import os

app = Flask(__name__)

# Load credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route("/")
def home():
    return "Index Price Updater Running"

@app.route("/update-prices", methods=["GET"])
def update_prices():
    try:
        # ✅ Get list of tickers from Supabase
        response = supabase.table("live_prices").select("ticker, stock").execute()
        tickers = response.data

        updated = []

        for item in tickers:
            ticker_code = item["ticker"]
            name = item["stock"]

            try:
                ticker = yf.Ticker(ticker_code)
                data = ticker.history(period="1d")

                if not data.empty:
                    latest = data.iloc[-1]
                    price = float(latest['Close'])
                    prev_close = float(latest['Open'])
                    change = price - prev_close

                    # ✅ Update Supabase
                    supabase.table("live_prices").upsert({
                        "ticker": ticker_code,
                        "stock": name,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change,
                        "created_at": datetime.utcnow().isoformat()
                    }, on_conflict=["ticker"]).execute()

                    updated.append({
                        "ticker": ticker_code,
                        "stock": name,
                        "price": price,
                        "prevClose": prev_close,
                        "change": change
                    })

            except Exception as e:
                print(f"Error for {ticker_code}: {e}")

        return jsonify({"message": "Prices updated", "data": updated})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
