import os
import time
import yfinance as yf
from flask import Flask, jsonify
from flask_cors import CORS
from supabase import create_client, Client

# ✅ Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
print("✅ Connected to Supabase!")

app = Flask(__name__)
CORS(app)

# ✅ Fetch Stock Prices in Batches
def get_stock_prices(stocks):
    try:
        # ✅ Ensure correct ".NS" formatting
        tickers = [s.upper().replace(".NS.NS", ".NS") for s in stocks]
        
        data = yf.download(tickers, period="2d", group_by="ticker", threads=True)
        stock_prices = []

        for stock in tickers:
            if stock in data:
                try:
                    prices = data[stock]["Close"]
                    if len(prices) >= 2:
                        live_price = round(prices.iloc[-1], 2)
                        prev_close = round(prices.iloc[-2], 2)
                        change = round(((live_price - prev_close) / prev_close) * 100, 2)
                        stock_prices.append({"stock": stock, "price": live_price, "change": change, "prevClose": prev_close})
                except KeyError:
                    print(f"❌ Missing price data for {stock}")
        
        return stock_prices
    except Exception as e:
        print("❌ Error fetching stock prices:", str(e))
        return []

# ✅ Update Supabase in Batches
def update_stock_prices():
    try:
        response = supabase.table("live_prices").select("stock").execute()
        stocks = [row["stock"] for row in response.data] if response.data else []

        if not stocks:
            print("❌ No stocks found in Supabase!")
            return {"message": "No stocks found in Supabase!"}

        # ✅ Process stocks in batches of 100
        all_stock_updates = []
        batch_size = 100
        for i in range(0, len(stocks), batch_size):
            batch_stocks = stocks[i:i + batch_size]
            stock_updates = get_stock_prices(batch_stocks)
            all_stock_updates.extend(stock_updates)
            time.sleep(2)

        # ✅ Update Supabase
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

# ✅ Manual Update API
@app.route("/update_prices", methods=["POST"])
def manual_update():
    result = update_stock_prices()
    return jsonify(result)

# ✅ Get All Prices from Supabase
@app.route("/get_price/<stock>")
def get_price(stock):
    stock = stock.upper()  # Ensure consistency
    # Correct the RPC call to pass the stock_symbol as an argument
    data = supabase.rpc("get_prices", {"stock_symbol": stock}).execute()

    if not data or len(data.data) == 0:
        return jsonify({"error": "Stock not found"}), 404
    
    return jsonify(data.data[0])




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
