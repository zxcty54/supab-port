import os
import time
import yfinance as yf
from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client
import asyncio
import aiohttp
import pandas as pd

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected to Supabase!")

app = Flask(__name__)
CORS(app)

async def fetch_stock_data(session, stock, max_retries=3, retry_delay=5):
    print(f"Fetching data for {stock}")
    retries = 0
    while retries < max_retries:
        try:
            data = await asyncio.to_thread(yf.download, stock, period="2d")
            print(f"Yfinance data for {stock}: {data}")
            if data is not None and isinstance(data, pd.DataFrame) and not data.empty and len(data) >= 2:
                prices = data["Close"]
                live_price = round(prices.iloc[-1], 2)
                prev_close = round(prices.iloc[-2], 2)
                change = round(((live_price - prev_close) / prev_close) * 100, 2)
                return {"stock": stock, "price": live_price, "change": change, "prevClose": prev_close}
            else:
                print(f"❌ Insufficient or empty data for {stock}, retry {retries + 1}")
                retries += 1
                await asyncio.sleep(retry_delay)
        except Exception as e:
            print(f"❌ Error fetching {stock}: {e}, retry {retries + 1}")
            retries += 1
            await asyncio.sleep(retry_delay)
    print(f"❌ Failed to fetch data for {stock} after {max_retries} retries")
    return None


async def get_stock_prices_async(stocks):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_stock_data(session, stock) for stock in stocks]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result]


async def update_stock_prices_async():
    print("update_stock_prices_async started")
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
            for stock_update in all_stock_updates:
                try:
                    result = supabase.table("live_prices").upsert(stock_update).execute()
                    print(f"Supabase upsert result for {stock_update['stock']}: {result}")
                except Exception as e:
                    print(f"❌ Error upserting {stock_update['stock']}: {e}")
            print(f"✅ Attempted to update {len(all_stock_updates)} stocks in Supabase!")
            print("update_stock_prices_async finished successfully")
            return {"message": "Stock prices updated!", "updated_stocks": all_stock_updates}
        else:
            print("✅ No price change detected.")
            print("update_stock_prices_async finished, no stock updates")
            return {"message": "No price change detected."}

    except Exception as e:
        print(f"❌ Error updating stock prices: {e}")
        return {"error": str(e)}

    print("update_stock_prices_async finished")


@app.route("/update_prices", methods=["GET", "POST"])
async def handle_update_prices():
    if request.method == "POST":
        result = await update_stock_prices_async()
        return jsonify(result)
    elif request.method == "GET":
        return jsonify({"message": "Use POST to update prices."}), 400


@app.route("/get_price/<stock>")
def get_price(stock):
    stock = stock.upper()
    data = supabase.rpc("get_prices", {"stock_symbol": stock}).execute()

    if not data or len(data.data) == 0:
        return jsonify({"error": "Stock not found"}), 404

    return jsonify(data.data[0])


@app.route("/")
def root():
    return jsonify({"message": "API is running"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
