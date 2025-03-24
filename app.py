import os
import threading
import time
import yfinance as yf
from flask import Flask, jsonify
from flask_cors import CORS
from supabase import create_client, Client

# ✅ Initialize Flask App
app = Flask(__name__)
CORS(app)

# ✅ Load Supabase Environment Variables
SUPABASE_DOMAIN = os.getenv("xejiiuswustskqkvnwsl.supabase.co")  # ✅ Updated Variable (No HTTPS)
SUPABASE_SERVICE_KEY = os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhlamlpdXN3dXN0c2txa3Zud3NsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI4MjY3NzcsImV4cCI6MjA1ODQwMjc3N30.dHkcXRctuff7wIw-thXMS3nP1zJi3dK7u0o_5aTTs70")

# ✅ Construct Full Supabase URL
SUPABASE_URL = f"https://{SUPABASE_DOMAIN}"

# ✅ Connect to Supabase
if not SUPABASE_DOMAIN or not SUPABASE_SERVICE_KEY:
    raise ValueError("🚨 SUPABASE_DOMAIN or SUPABASE_SERVICE_KEY is missing!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected to Supabase!")

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
            response = supabase.table("live_prices").select("stock").execute()
            stocks = [row["stock"] for row in response.data]

            stock_data = {stock: get_stock_price(stock) for stock in stocks}

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

        time.sleep(180)  # ✅ Update every 3 minutes

# ✅ Start Background Thread
threading.Thread(target=update_stock_prices, daemon=True).start()

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
