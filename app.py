import os
import threading
import time
import yfinance as yf
from flask import Flask, jsonify
from flask_cors import CORS
from supabase import create_client, Client

# ✅ Set Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")  
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("🚨 SUPABASE_URL or SUPABASE_SERVICE_KEY is missing!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected to Supabase!")

app = Flask(__name__)
CORS(app)

# ✅ Function to Fetch Stock Price
def get_stock_price(stock):
    try:
        stock = stock.upper()
        if not stock.endswith(".NS"):
            stock += ".NS"

        ticker = yf.Ticker(stock)
        history_data = ticker.history(period="2d")

        if history_data.empty:
            return None

        live_price = round(history_data["Close"].iloc[-1], 2)
        prev_close = round(history_data["Close"].iloc[-2], 2) if len(history_data) > 1 else live_price
        change = round(((live_price - prev_close) / prev_close) * 100, 2) if prev_close else 0

        return {"stock": stock, "price": live_price, "change": change, "prevClose": prev_close}
    
    except Exception as e:
        return None

# ✅ Function to Update Stock Prices in Supabase
def update_stock_prices():
    while True:
        try:
            response = supabase.table("live_prices").select("stock", "price").execute()
            existing_data = {row["stock"]: row["price"] for row in response.data} if response.data else {}

            # ✅ Fetch Stocks from Supabase
            stocks = list(existing_data.keys())

            if not stocks:
                print("❌ No stocks found in Supabase!")
                time.sleep(600)  # ✅ Sleep for 10 minutes before retrying
                continue

            # ✅ Fetch Live Stock Prices
            stock_updates = []
            for stock in stocks:
                data = get_stock_price(stock)
                if data and data["price"] != existing_data.get(stock):  # ✅ Only update if price changes
                    stock_updates.append(data)

            # ✅ Batch Update Stocks in Supabase
            if stock_updates:
                supabase.table("live_prices").upsert(stock_updates).execute()
                print("✅ Stock prices updated:", stock_updates)
            else:
                print("✅ No price change, skipping update.")

        except Exception as e:
            print("❌ Error updating stock prices:", str(e))

        time.sleep(600)  # ✅ Sleep for 10 minutes

# ✅ Start Background Thread for Updating Stock Prices
threading.Thread(target=update_stock_prices, daemon=True).start()

@app.route("/")
def home():
    return "✅ Stock Price API (Supabase) is Running!"

@app.route("/get_price/<stock>", methods=["GET"])
def get_price(stock):
    try:
        response = supabase.table("live_prices").select("*").eq("stock", stock.upper()).execute()

        if response.data:
            return jsonify(response.data[0])
        else:
            return jsonify({"error": "Stock not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_prices", methods=["GET"])
def get_prices():
    try:
        response = supabase.table("live_prices").select("*").execute()
        return jsonify(response.data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
