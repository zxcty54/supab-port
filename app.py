import os
import threading
import time
import yfinance as yf
from flask import Flask, jsonify
from flask_cors import CORS
from supabase import create_client, Client

# ✅ Set Supabase Credentials Correctly
SUPABASE_URL = "https://xejiiuswustskqkvnwsl.supabase.co"  # Your Supabase URL
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Fetch from Environment Variable

# ✅ Validate Supabase Keys
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise ValueError("🚨 SUPABASE_DOMAIN or SUPABASE_SERVICE_KEY is missing!")

# ✅ Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected to Supabase!")

# ✅ Initialize Flask App
app = Flask(__name__)
CORS(app)

# ✅ Function to Fetch Stock Price
def get_stock_price(stock):
    try:
        stock = stock.lower()
        if not stock.endswith(".ns"):
            stock += ".ns"

        ticker = yf.Ticker(stock)
        history_data = ticker.history(period="2d")

        if history_data.empty:
            return {"price": 0, "change": 0, "prevClose": 0}

        live_price = round(history_data["Close"].iloc[-1], 2)
        prev_close = round(history_data["Close"].iloc[-2], 2) if len(history_data) > 1 else live_price
        change = round(((live_price - prev_close) / prev_close) * 100, 2) if prev_close else 0

        return {"price": live_price, "change": change, "prevClose": prev_close}
    
    except Exception as e:
        return {"error": str(e)}

# ✅ Function to Update Stock Prices in Supabase
def update_stock_prices():
    while True:
        try:
            # ✅ Fetch Stocks from Supabase
            response = supabase.table("live_prices").select("stock").execute()
            if response.data is None:
                print("❌ No stocks found in Supabase!")
                time.sleep(180)
                continue  # Skip iteration if no stocks are found

            stocks = [row["stock"] for row in response.data]

            # ✅ Fetch Live Stock Prices
            stock_data = {stock: get_stock_price(stock) for stock in stocks}

            # ✅ Update Stocks in Supabase
            for stock, data in stock_data.items():
                supabase.table("live_prices").upsert({
                    "stock": stock, 
                    "price": data["price"], 
                    "change": data["change"], 
                    "prevClose": data["prevClose"]
                }).execute()

            print("✅ Stock prices updated:", stock_data)

        except Exception as e:
            print("❌ Error updating stock prices:", str(e))

        time.sleep(180)  # ✅ Wait for 3 minutes before next update

# ✅ Start Background Thread for Updating Stock Prices
threading.Thread(target=update_stock_prices, daemon=True).start()

# ✅ Flask Routes
@app.route("/")
def home():
    return "✅ Stock Price API (Supabase) is Running!"

@app.route("/get_price/<stock>", methods=["GET"])
def get_price(stock):
    try:
        stock = stock.lower()
        response = supabase.table("live_prices").select("*").eq("stock", stock).execute()

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
