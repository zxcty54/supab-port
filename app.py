import os
import yfinance as yf
import asyncio
from supabase import create_client
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Flask setup
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Function to fetch stocks from Supabase
def get_stock_list():
    response = supabase.table("live_prices").select("stock").execute()
    if response.data:
        return [row["stock"] for row in response.data]
    return []

# Function to update stock prices
def update_stock_prices():
    stocks = get_stock_list()
    if not stocks:
        print("No stocks found in Supabase.")
        return
    
    stock_data = yf.download(stocks, period="1d", interval="1m")["Close"].iloc[-1]
    
    for stock, price in stock_data.items():
        prev_close = supabase.table("live_prices").select("price").eq("stock", stock).execute()
        prev_close_price = prev_close.data[0]["price"] if prev_close.data else None
        change = round(((price - prev_close_price) / prev_close_price) * 100, 2) if prev_close_price else 0

        supabase.table("live_prices").update({
            "price": price,
            "prevClose": prev_close_price,
            "change": change
        }).eq("stock", stock).execute()
    
    print("Stock prices updated successfully!")

# Flask API to trigger update manually
@app.route("/update-prices", methods=["GET"])
def trigger_update():
    update_stock_prices()
    return jsonify({"message": "Stock prices updated"}), 200

# Scheduler to run every 3 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(update_stock_prices, "interval", minutes=3)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
