from flask import Flask, jsonify
from flask_cors import CORS
from supabase import create_client
import yfinance as yf
import os
from datetime import datetime

# Supabase configuration
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_API_KEY"

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# Initialize Flask app
app = Flask(__name__)

# Enable CORS
CORS(app)

# Function to fetch stock data from YFinance
def fetch_stock_data(stock):
    try:
        # Fetch stock data from YFinance
        stock_data = yf.Ticker(stock).history(period="1d")
        latest_data = stock_data.iloc[-1]
        
        # Calculate price change
        change = latest_data['Close'] - latest_data['Open']
        
        return {
            'price': latest_data['Close'],
            'prevClose': latest_data['Close'],  # This can be adjusted to your needs
            'change': change
        }
    except Exception as e:
        print(f"Error fetching data for {stock}: {e}")
        return None

# Function to fetch the list of stocks from Supabase
def get_stocks_from_supabase():
    response = supabase.from_("live_prices").select("stock").execute()
    
    if response.get("error"):
        print(f"Error fetching stocks from Supabase: {response['error']}")
        return []
    
    stock_list = [stock['stock'] for stock in response['data']]
    return stock_list

# Function to update live prices in Supabase
def update_live_prices(stock, data):
    try:
        response = supabase.from_("live_prices").upsert({
            "stock": stock,
            "price": data['price'],
            "prevClose": data['prevClose'],
            "change": data['change'],
            "created_at": datetime.now().isoformat()  # Set the timestamp
        }).execute()
        
        if response.get("error"):
            print(f"Error updating {stock}: {response['error']}")
        else:
            print(f"Updated {stock} successfully")
    except Exception as e:
        print(f"Error updating {stock}: {e}")

# Route to fetch and update stock data
@app.route('/update_stock_prices', methods=['GET'])
def update_stock_prices():
    stock_list = get_stocks_from_supabase()
    
    if not stock_list:
        return jsonify({"error": "No stocks found in the database"}), 400
    
    # Fetch and update data for each stock
    for stock in stock_list:
        data = fetch_stock_data(stock)
        
        if data:
            update_live_prices(stock, data)
    
    return jsonify({"message": "Stock prices updated successfully!"})

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
