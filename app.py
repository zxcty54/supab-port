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

# Supabase setup
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")  # Use service role key
supabase = create_client(supabase_url, supabase_key)

# List of index symbols (these won't get .NS)
INDEX_LIST = ["NSEI", "BSESN", "NSEBANK", "DJI", "IXIC", "GSPC", "^NSEI", "^BSESN"]

@app.route("/update-prices", methods=["GET"])
def update_prices():
    try:
        # 🔄 Get all stock/index symbols from Supabase
        response = supabase.table("live_prices").select("stock").execute()
        tickers = response.data

        updated = []

        for item in tickers:
            raw_symbol = item["stock"].strip().upper()  # Clean symbol

            # 🧠 Add .NS only for Indian stocks (not indices)
            if raw_symbol in INDEX_LIST or raw_symbol.startswith("^"):
                ticker_code = raw_symbol
            else:
                ticker_code = raw_symbol + ".NS"

            try:
                ticker = yf.Ticker(ticker_code)
                data = ticker.history(period="1d")

                if not data.empty:
                    latest = data.iloc[-1]
                    price = float(latest["Close"])
                    prev_close = float(latest["Open"])
                    change = price - prev_close

                    # 🔄 Update price in Supabase using stock symbol
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
                print(f"Error fetching {ticker_code}: {e}")

        return jsonify({"updated": updated}), 200

    except Exception as e:
        print(f"Error updating prices: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
