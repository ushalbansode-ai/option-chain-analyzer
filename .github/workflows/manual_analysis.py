import pandas as pd
from option_signals import AdvancedOptionSignalGenerator
from datetime import datetime

def manual_analysis():
    """Run manual analysis with full data output"""
    print("🔍 MANUAL OPTION CHAIN ANALYSIS")
    print("=" * 80)
    
    generator = AdvancedOptionSignalGenerator()
    
    # Run analysis
    signals, detailed_data = generator.run_analysis()
    
    # Display full option chain data for manual inspection
    print("\n📋 DETAILED OPTION CHAIN DATA:")
    print("=" * 80)
    
    for symbol in generator.symbols[:3]:  # Show first 3 symbols for brevity
        print(f"\n📊 {symbol} - Complete Option Chain Analysis:")
        data = generator.fetch_option_chain(symbol)
        if data:
            analysis = generator.analyze_option_chain(data, symbol)
            if analysis:
                print(f"Current Price: {analysis['current_price']}")
                print(f"ATM Strike: {analysis['atm_strike']}")
                print(f"Expiry: {analysis['expiry']}")
                
                # Display ±5 strikes data
                print("\nStrike | Type | OI | COI | LTP | IV | Delta | Gamma")
                print("-" * 70)
                for item in analysis['data']:
                    strike = item['strikePrice']
                    if 'CE' in item:
                        ce = item['CE']
                        print(f"{strike:6} | CE   | {ce.get('openInterest',0):6} | {ce.get('changeinOpenInterest',0):+4} | {ce.get('lastPrice',0):5} | {ce.get('impliedVolatility',0):4.1f} | {ce.get('delta',0):5.2f} | {ce.get('gamma',0):5.3f}")
                    if 'PE' in item:
                        pe = item['PE']
                        print(f"{strike:6} | PE   | {pe.get('openInterest',0):6} | {pe.get('changeinOpenInterest',0):+4} | {pe.get('lastPrice',0):5} | {pe.get('impliedVolatility',0):4.1f} | {pe.get('delta',0):5.2f} | {pe.get('gamma',0):5.3f}")

if __name__ == "__main__":
    manual_analysis()
