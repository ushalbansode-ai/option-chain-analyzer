import requests
import pandas as pd
from datetime import datetime
import time

class NSEDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.cookies = None
        
    def get_cookies(self):
        try:
            self.session.get("https://www.nseindia.com")
            return True
        except:
            return False
            
    def fetch_option_chain(self, symbol):
        if not self.cookies:
            self.get_cookies()
            
        try:
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None

class DataProcessor:
    @staticmethod
    def process_option_chain(data, symbol):
        if not data or 'records' not in data:
            return None
            
        records = data['records']
        spot_price = records['underlyingValue']
        timestamp = records['timestamp']
        
        # Process strike-wise data
        strike_data = []
        for record in records['data']:
            if 'CE' in record and 'PE' in record:
                strike_data.append({
                    'strike': record['strikePrice'],
                    'ce_oi': record['CE']['openInterest'],
                    'ce_change_oi': record['CE']['changeinOpenInterest'],
                    'ce_volume': record['CE']['totalTradedVolume'],
                    'ce_iv': record['CE']['impliedVolatility'],
                    'ce_last_price': record['CE']['lastPrice'],
                    'pe_oi': record['PE']['openInterest'],
                    'pe_change_oi': record['PE']['changeinOpenInterest'],
                    'pe_volume': record['PE']['totalTradedVolume'],
                    'pe_iv': record['PE']['impliedVolatility'],
                    'pe_last_price': record['PE']['lastPrice']
                })
        
        return {
            'symbol': symbol,
            'spot_price': spot_price,
            'timestamp': timestamp,
            'strike_data': strike_data
        }
