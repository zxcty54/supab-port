from flask import Flask, jsonify
from flask_cors import CORS
from datetime import datetime
import yfinance as yf
from supabase import create_client
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
INDEX_SYMBOLS = {"NSEI", "NSEBANK", "BSESN", "DJI", "IXIC", "GSPC"}

def batch_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

async def process_batch(batch):
    updated = []

    for item in batch:
        raw_symbol = item.strip().upper()
        ticker_code = raw_symbol if raw_symbol in INDEX_SYMBOLS else raw_symbol + ".NS"

        try:
            ticker = yf.Ticker(ticker_code)
            if raw_symbol in INDEX_SYMBOLS:
                fast = ticker.fast_info
                price = fast.get("lastPrice")
                prev_close = fast.get("previousClose")
            else:
                hist = ticker.history(period="1d")
                if hist.empty: continue
                latest = hist.iloc[-1]
                price = float(latest["Close"])
                prev_close = float(latest["Open"])

            if price is None or prev_close is None: continue
            change = round(((price - prev_close) / prev_close) * 100, 2)

            supabase.table("live_prices").upsert({
                "stock": raw_symbol,
                "price": price,
                "prevClose": prev_close,
                "change": change,
                "created_at": datetime.utcnow().isoformat()
            }, on_conflict=["stock"]).execute()

            updated.append({"stock": raw_symbol, "price": price, "prevClose": prev_close, "change": change})

        except Exception as e:
            print(f"❌ Error in {raw_symbol}: {e}")

    return updated

@app.route("/update-prices", methods=["GET"])
def update_prices():
    response = supabase.table("live_prices").select("stock").execute()
    tickers = list(set([item["stock"] for item in response.data]))

    all_updates = []

    async def run_batches():
        for batch in batch_list(tickers, 20):
            print(f"🔄 Processing batch: {batch}")
            updated = await process_batch(batch)
            all_updates.extend(updated)
            await asyncio.sleep(15)  # 15-second delay

    asyncio.run(run_batches())
    return jsonify({"updated": all_updates}), 200

if __name__ == "__main__":
    app.run(debug=True)
