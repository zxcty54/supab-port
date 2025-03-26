import os
import time
import yfinance as yf
from flask import Flask, jsonify
from flask_cors import CORS
from supabase import create_client, Client
import asyncio
import aiohttp
from apscheduler.schedulers.background import BackgroundScheduler

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected to Supabase!")

app = Flask(__name__)
CORS(app)

async def fetch_stock_data(session, stock):
    try:
        data = await asyncio.to_thread(yf.download, stock, period="2d", group_by="ticker")
        if stock in data and len(data[stock]["Close"]) >= 2:
            prices = data[stock]["Close"]
            live_price = round(prices.iloc[-1], 2)
            prev_close = round(prices.iloc[-2], 2)
            change = round(((live_price - prev_close) / prev_close) * 100, 2)
            return {"stock": stock, "price": live_price, "change": change, "prevClose": prev_close}
        else:
            print(f"❌ Insufficient data for {stock}")
            return None
    except Exception as e:
        print(f"❌ Error fetching {stock}: {e}")
        return None

async def get_stock_prices_async(stocks):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_stock_data(session, stock) for stock in stocks]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result]

async def update_stock_prices_async():
    try:
        response = supabase.table("live_prices").select("stock").execute()
        stocks = [row["stock"] for row in response.data] if response.data else []

        if not stocks:
            print("❌ No stocks found in Supabase!")
            return {"message": "No stocks found in Supabase!"}

        all_stock_updates = []
        batch_size = 100
        for i in range(0, len(stocks), batch_size):
            batch_stocks = stocks[i:i + batch_size]
            stock_updates = await get_stock_prices_async(batch_stocks)
            all_stock_updates.extend(stock_updates)
            time.sleep(2)

        if all_stock_updates:
            result = supabase.table("live_prices").upsert(all_stock_updates).execute()
            print(f"✅ Supabase upsert result: {result}")
            print(f"✅ Updated {len(all_stock_updates)} stocks in Supabase!")
            return {"message": "Stock prices updated!", "updated_stocks": all_stock_updates}
        else:
            print("✅ No price change detected.")
            return {"message": "No price change detected."}

    except Exception as e:
        print(f"❌ Error updating stock prices: {e}")
        return {"error": str(e)}

@app.route("/update_prices", methods=["POST"])
async def manual_update():
    result = await update_stock_prices_async()
    return jsonify(result)

@app.route("/get_price/<stock>")
def get_price(stock):
    stock = stock.upper()
    data = supabase.rpc("get_prices", {"stock_symbol": stock}).execute()

    if not data or len(data.data) == 0:
        return jsonify({"error": "Stock not found"}), 404
    
    return jsonify(data.data[0])

def scheduled_update():
    asyncio.run(update_stock_prices_async())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    scheduler = BackgroundScheduler()
    scheduler.add_job(func=scheduled_update, trigger="interval", minutes=1)
    scheduler.start()

    app.run(host="0.0.0.0", port=port)
