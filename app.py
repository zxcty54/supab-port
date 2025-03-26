import os
import threading
import time
import yfinance as yf
from flask import Flask, jsonify, request
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

# ✅ Fetch Multiple Stock Prices in One API Call
def get_stock_prices(stocks):
    try:
        tickers = [s.upper() if s.endswith(".NS") else s.upper() + ".NS" for s in stocks]
        data = yf.download(tickers, period="2d", group_by="ticker", threads=True)

        stock_prices = []
        for stock in tickers:
            if stock in data:
                prices = data[stock]["Close"]
                if len(prices) >= 2:
                    live_price = round(prices.iloc[-1], 2)
                    prev_close = round(prices.iloc[-2], 2)
                    change = round(((live_price - prev_close) / prev_close) * 100, 2)
                    stock_prices.append({"stock": stock, "price": live_price, "change": change, "prevClose": prev_close})

        return stock_prices
    except Exception as e:
        print("❌ Error fetching stock prices:", str(e))
        return []

# ✅ Update Supabase in Batches
def update_stock_prices():
    try:
        # ✅ Fetch Stocks from Supabase
        response = supabase.table("live_prices").select("stock").execute()
        stocks = [row["stock"] for row in response.data] if response.data else []

        if not stocks:
            print("❌ No stocks found in Supabase!")
            return {"message": "No stocks found in Supabase!"}

        # ✅ Fetch stock prices in batches of 100 (to avoid rate limits)
        all_stock_updates = []
        batch_size = 100
        for i in range(0, len(stocks), batch_size):
            batch_stocks = stocks[i:i + batch_size]
            stock_updates = get_stock_prices(batch_stocks)
            all_stock_updates.extend(stock_updates)
            time.sleep(2)  # ✅ Avoid rate limits

        # ✅ Batch Update in Supabase
        if all_stock_updates:
            supabase.table("live_prices").upsert(all_stock_updates).execute()
            print(f"✅ Updated {len(all_stock_updates)} stocks in Supabase!")
            return {"message": "Stock prices updated!", "updated_stocks": all_stock_updates}
        else:
            print("✅ No price change detected.")
            return {"message": "No price change detected."}

    except Exception as e:
        print("❌ Error updating stock prices:", str(e))
        return {"error": str(e)}

# ✅ Manual Update API Route (For Browser)
@app.route("/update_prices", methods=["POST"])
def manual_update():
    result = update_stock_prices()
    return jsonify(result)

# ✅ Background Auto Update (Every 15 Minutes)
def run_auto_update():
    while True:
        update_stock_prices()
        time.sleep(900)  # ✅ Sleep for 15 minutes

threading.Thread(target=run_auto_update, daemon=True).start()

@app.route("/")
def home():
    return "✅ Stock Price API is Running!"

# ✅ Get Single Stock Price from Supabase
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

# ✅ Get All Stock Prices from Supabase
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
