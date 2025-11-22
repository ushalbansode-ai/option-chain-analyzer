import requests
import pandas as pd
from datetime import datetime

def test_connection():
    print("🔍 Testing NSE connection...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Test with NIFTY first
        url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ NSE Connection Successful!")
            data = response.json()
            print(f"📊 Found {len(data['records']['data'])} option records")
            return True
        else:
            print(f"❌ NSE Connection Failed: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

def test_dependencies():
    print("🔍 Testing dependencies...")
    try:
        import pandas as pd
        import numpy as np
        print("✅ All dependencies working!")
        return True
    except ImportError as e:
        print(f"❌ Dependency error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Running Debug Test...")
    test_dependencies()
    test_connection()
    
    # Test file creation
    try:
        test_df = pd.DataFrame({
            'test': ['success'],
            'timestamp': [datetime.now()]
        })
        test_df.to_csv("test_output.csv", index=False)
        print("✅ File creation test passed!")
    except Exception as e:
        print(f"❌ File creation failed: {e}")
