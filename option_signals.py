import requests
import pandas as pd
import numpy as np
from datetime import datetime, time
import time as time_module
import json
import os

class FocusedOptionSignalGenerator:
    def __init__(self):
        self.symbols = [
            "NIFTY", "BANKNIFTY",
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", 
            "KOTAKBANK", "HDFC", "BHARTIARTL", "ITC", "SBIN",
            "ASIANPAINT", "MARUTI", "TATAMOTORS", "TATASTEEL",
            "BAJFINANCE", "WIPRO", "HCLTECH", "LT", "AXISBANK"
        ]
        
    def is_market_hours(self):
        """Check if current time is within market hours (9:15 AM to 3:30 PM IST)"""
        current_time = datetime.now().time()
        market_start = time(9, 15)  # 9:15 AM IST
        market_end = time(15, 30)   # 3:30 PM IST
        return market_start <= current_time <= market_end
    
    def fetch_option_chain(self, symbol):
        """Fetch complete option chain data from NSE"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br'
            }
            
            if symbol in ['NIFTY', 'BANKNIFTY']:
                url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            else:
                url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
            
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=10)
            response = session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching {symbol}: Status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return None
    
    def analyze_option_chain(self, data, symbol):
        """Comprehensive option chain analysis focused on ATM ±5 strikes"""
        if not data or 'records' not in data:
            return None
            
        records = data['records']
        current_price = records['underlyingValue']
        expiry_dates = records['expiryDates']
        
        # Use nearest expiry
        current_expiry = expiry_dates[0]
        
        # Filter data for current expiry
        option_data = [item for item in data['records']['data'] 
                      if item.get('expiryDate') == current_expiry]
        
        if not option_data:
            return None
        
        # Find ATM strike
        strikes = [item['strikePrice'] for item in option_data]
        atm_strike = min(strikes, key=lambda x: abs(x - current_price))
        
        # Get ONLY ±5 strikes from ATM (total 11 strikes)
        all_strikes = sorted(strikes)
        atm_index = all_strikes.index(atm_strike)
        start_idx = max(0, atm_index - 5)
        end_idx = min(len(all_strikes), atm_index + 6)  # +6 to include 5 on each side
        
        relevant_strikes = all_strikes[start_idx:end_idx]
        relevant_data = [item for item in option_data 
                        if item['strikePrice'] in relevant_strikes]
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'atm_strike': atm_strike,
            'expiry': current_expiry,
            'relevant_strikes': relevant_strikes,
            'data': relevant_data,
            'all_data': option_data
        }
    
    def calculate_pcr(self, data):
        """Calculate Put-Call Ratio with OI and Volume"""
        if not data:
            return 0, 0
            
        total_ce_oi = 0
        total_pe_oi = 0
        total_ce_volume = 0
        total_pe_volume = 0
        total_ce_coi = 0
        total_pe_coi = 0
        
        for record in data:
            if 'CE' in record:
                ce = record['CE']
                total_ce_oi += ce.get('openInterest', 0)
                total_ce_volume += ce.get('totalTradedVolume', 0)
                total_ce_coi += ce.get('changeinOpenInterest', 0)
            if 'PE' in record:
                pe = record['PE']
                total_pe_oi += pe.get('openInterest', 0)
                total_pe_volume += pe.get('totalTradedVolume', 0)
                total_pe_coi += pe.get('changeinOpenInterest', 0)
        
        pcr_oi = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
        pcr_volume = total_pe_volume / total_ce_volume if total_ce_volume > 0 else 0
        
        return round(pcr_oi, 2), round(pcr_volume, 2)
    
    def select_focused_strike(self, analysis_data, option_type):
        """
        Select strike ONLY from ATM ±5 strikes
        Priority: ATM > Near-ATM > First OTM
        """
        if not analysis_data:
            return None
            
        current_price = analysis_data['current_price']
        atm_strike = analysis_data['atm_strike']
        relevant_data = analysis_data['data']
        
        candidate_strikes = []
        
        for item in relevant_data:
            strike = item['strikePrice']
            
            # Calculate distance from ATM (in strike steps)
            strike_index = analysis_data['relevant_strikes'].index(strike)
            atm_index = analysis_data['relevant_strikes'].index(atm_strike)
            distance_from_atm = abs(strike_index - atm_index)
            
            if option_type == 'CE':
                if 'CE' in item:
                    ce_data = item['CE']
                    # Only consider CE strikes that are ATM or OTM (strike >= current_price)
                    if strike >= current_price:
                        candidate_strikes.append({
                            'strike': strike,
                            'distance_from_atm': distance_from_atm,
                            'is_atm': strike == atm_strike,
                            'is_near_atm': distance_from_atm <= 1,
                            'is_otm': strike > current_price,
                            'oi': ce_data.get('openInterest', 0),
                            'coi': ce_data.get('changeinOpenInterest', 0),
                            'volume': ce_data.get('totalTradedVolume', 0),
                            'iv': ce_data.get('impliedVolatility', 0),
                            'delta': ce_data.get('delta', 0),
                            'gamma': ce_data.get('gamma', 0),
                            'ltp': ce_data.get('lastPrice', 0),
                            'change': ce_data.get('change', 0)
                        })
            else:  # PE
                if 'PE' in item:
                    pe_data = item['PE']
                    # Only consider PE strikes that are ATM or OTM (strike <= current_price)
                    if strike <= current_price:
                        candidate_strikes.append({
                            'strike': strike,
                            'distance_from_atm': distance_from_atm,
                            'is_atm': strike == atm_strike,
                            'is_near_atm': distance_from_atm <= 1,
                            'is_otm': strike < current_price,
                            'oi': pe_data.get('openInterest', 0),
                            'coi': pe_data.get('changeinOpenInterest', 0),
                            'volume': pe_data.get('totalTradedVolume', 0),
                            'iv': pe_data.get('impliedVolatility', 0),
                            'delta': pe_data.get('delta', 0),
                            'gamma': pe_data.get('gamma', 0),
                            'ltp': pe_data.get('lastPrice', 0),
                            'change': pe_data.get('change', 0)
                        })
        
        if not candidate_strikes:
            return None
        
        # Enhanced scoring focused on ATM and near-ATM
        for candidate in candidate_strikes:
            score = 0
            
            # Priority 1: ATM strikes get highest score
            if candidate['is_atm']:
                score += 100
            # Priority 2: Near-ATM strikes (1 strike away)
            elif candidate['is_near_atm']:
                score += 80
            # Priority 3: Other strikes in ±5 range
            else:
                score += 60 - (candidate['distance_from_atm'] * 5)
            
            # Data quality factors (secondary to proximity)
            score += min(candidate['oi'] / 10000, 5)  # Normalize OI
            score += candidate['coi'] / 500  # COI impact
            score += min(candidate['volume'] / 1000, 3)  # Volume impact
            
            # IV consideration (lower IV better for buying)
            score -= candidate['iv'] / 5
            
            candidate['score'] = round(score, 2)
            candidate['selection_reason'] = self.get_selection_reason(candidate)
        
        # Select strike with highest score
        best_strike = max(candidate_strikes, key=lambda x: x['score'])
        return best_strike
    
    def get_selection_reason(self, candidate):
        """Generate reason for strike selection"""
        if candidate['is_atm']:
            return "ATM Strike - Maximum Gamma"
        elif candidate['is_near_atm']:
            return "Near-ATM Strike - Balanced Risk-Reward"
        elif candidate['is_otm']:
            return f"OTM Strike ({candidate['distance_from_atm']} steps from ATM) - Better Risk-Reward"
        else:
            return f"ITM Strike ({candidate['distance_from_atm']} steps from ATM) - Higher Delta"
    
    def generate_signal(self, analysis_data, pcr_oi, pcr_volume):
        """Generate trading signal with focused strike selection"""
        if not analysis_data:
            return None
            
        symbol = analysis_data['symbol']
        current_price = analysis_data['current_price']
        atm_strike = analysis_data['atm_strike']
        
        signal = "HOLD"
        option_type = None
        strike_data = None
        reason = ""
        
        # Enhanced signal logic with strike focus
        if pcr_oi > 1.5 and pcr_volume > 1.2:
            signal = "STRONG BUY"
            option_type = "CE"
            strike_data = self.select_focused_strike(analysis_data, 'CE')
            reason = f"Very High PCR (OI:{pcr_oi}, Vol:{pcr_volume}) - Strong Bullish | Focus: ATM±5"
        elif pcr_oi > 1.2:
            signal = "BUY"
            option_type = "CE"
            strike_data = self.select_focused_strike(analysis_data, 'CE')
            reason = f"High PCR (OI:{pcr_oi}) - Bullish | Focus: ATM±5"
        elif pcr_oi < 0.6 and pcr_volume < 0.8:
            signal = "STRONG BUY"
            option_type = "PE"
            strike_data = self.select_focused_strike(analysis_data, 'PE')
            reason = f"Very Low PCR (OI:{pcr_oi}, Vol:{pcr_volume}) - Strong Bearish | Focus: ATM±5"
        elif pcr_oi < 0.8:
            signal = "BUY"
            option_type = "PE"
            strike_data = self.select_focused_strike(analysis_data, 'PE')
            reason = f"Low PCR (OI:{pcr_oi}) - Bearish | Focus: ATM±5"
        else:
            reason = f"Neutral PCR (OI:{pcr_oi}, Vol:{pcr_volume}) | Monitoring ATM±5"
        
        if signal != "HOLD" and strike_data:
            return {
                'symbol': symbol,
                'signal': signal,
                'option_type': option_type,
                'strike_price': strike_data['strike'],
                'current_price': current_price,
                'atm_strike': atm_strike,
                'distance_from_atm': strike_data['distance_from_atm'],
                'option_ltp': strike_data['ltp'],
                'option_change': strike_data['change'],
                'oi': strike_data['oi'],
                'coi': strike_data['coi'],
                'volume': strike_data['volume'],
                'iv': strike_data['iv'],
                'delta': strike_data['delta'],
                'gamma': strike_data['gamma'],
                'strike_score': strike_data['score'],
                'selection_reason': strike_data['selection_reason'],
                'pcr_oi': pcr_oi,
                'pcr_volume': pcr_volume,
                'reason': reason,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return None
    
    def run_analysis(self):
        """Main analysis function with focused strike selection"""
        print("🎯 Starting FOCUSED Option Signals Analysis (ATM ±5 strikes only)")
        print(f"📅 Market Hours: {self.is_market_hours()}")
        print("=" * 80)
        
        all_signals = []
        detailed_data = []
        
        for symbol in self.symbols:
            print(f"📊 Analyzing {symbol} (ATM ±5 strikes)...")
            
            # Fetch option chain data
            data = self.fetch_option_chain(symbol)
            
            if data:
                # Analyze option chain with focused strikes
                analysis_data = self.analyze_option_chain(data, symbol)
                
                if analysis_data:
                    # Display strike range being analyzed
                    strikes = analysis_data['relevant_strikes']
                    atm_idx = strikes.index(analysis_data['atm_strike'])
                    print(f"   🎯 ATM: {analysis_data['atm_strike']}, Range: {strikes[0]} to {strikes[-1]}")
                    
                    # Calculate PCR
                    pcr_oi, pcr_volume = self.calculate_pcr(analysis_data['all_data'])
                    
                    # Generate signal
                    signal = self.generate_signal(analysis_data, pcr_oi, pcr_volume)
                    
                    if signal:
                        all_signals.append(signal)
                        print(f"   ✅ {signal['signal']} {signal['option_type']} at {signal['strike_price']}")
                        print(f"   📍 {signal['selection_reason']}")
                        print(f"   📈 LTP: {signal['option_ltp']}, OI: {signal['oi']:,}, COI: {signal['coi']:+,}")
                    else:
                        print(f"   ⏸️  No signal (PCR OI: {pcr_oi}, Vol: {pcr_volume})")
                    
                    # Store detailed data
                    detailed_data.append({
                        'symbol': symbol,
                        'current_price': analysis_data['current_price'],
                        'atm_strike': analysis_data['atm_strike'],
                        'strike_range_start': strikes[0],
                        'strike_range_end': strikes[-1],
                        'total_strikes_analyzed': len(strikes),
                        'pcr_oi': pcr_oi,
                        'pcr_volume': pcr_volume,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    print(f"   ❌ No analysis data for {symbol}")
            else:
                print(f"   ❌ Failed to fetch data for {symbol}")
            
            print("-" * 50)
            time_module.sleep(2)
        
        return all_signals, detailed_data

def main():
    generator = FocusedOptionSignalGenerator()
    
    # Run analysis
    signals, detailed_data = generator.run_analysis()
    
    # Save signals to CSV
    if signals:
        df_signals = pd.DataFrame(signals)
        df_signals.to_csv("option_signals.csv", index=False)
        print(f"✅ {len(signals)} signals saved to option_signals.csv")
    
    # Save detailed data
    if detailed_data:
        df_detailed = pd.DataFrame(detailed_data)
        df_detailed.to_csv("detailed_option_data.csv", index=False)
        print(f"✅ Detailed data saved to detailed_option_data.csv")
    
    # Generate HTML report
    generate_html_report(signals, detailed_data)
    
    return signals, detailed_data

def generate_html_report(signals, detailed_data):
    """Generate HTML report with focused strike information"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Focused NSE Option Signals - ATM ±5 Strikes</title>
        <meta http-equiv="refresh" content="300">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
            .signal-card {{ background: white; padding: 15px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .strong-buy {{ border-left: 5px solid #28a745; }}
            .buy {{ border-left: 5px solid #17a2b8; }}
            table {{ width: 100%; border-collapse: collapse; background: white; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; font-weight: bold; }}
            .strike-info {{ background: #e7f3ff; padding: 10px; border-radius: 5px; margin: 5px 0; }}
            .last-update {{ background: white; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎯 Focused NSE Option Signals</h1>
                <p>ATM ±5 Strikes Only • Live PCR Analysis • Auto-updates every 5 minutes</p>
            </div>
            
            <div class="last-update">
                <strong>Last Updated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                <br><strong>Strike Focus:</strong> ATM and ±5 strikes only
                <br><strong>Next Update:</strong> Every 5 minutes during market hours (9:15 AM - 3:30 PM IST)
            </div>
    """
    
    # Active Signals
    if signals:
        html += """
            <h2>🚀 Active Trading Signals</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Signal</th>
                        <th>Option</th>
                        <th>Strike</th>
                        <th>ATM</th>
                        <th>Distance</th>
                        <th>LTP</th>
                        <th>OI</th>
                        <th>COI</th>
                        <th>IV</th>
                        <th>Selection Reason</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for signal in signals:
            signal_class = "strong-buy" if "STRONG" in signal['signal'] else "buy"
            distance = signal['distance_from_atm']
            distance_text = "ATM" if distance == 0 else f"{distance} step{'s' if distance > 1 else ''}"
            
            html += f"""
                    <tr class="{signal_class}">
                        <td><strong>{signal['symbol']}</strong></td>
                        <td><strong>{signal['signal']}</strong></td>
                        <td>{signal['option_type']}</td>
                        <td>{signal['strike_price']}</td>
                        <td>{signal['atm_strike']}</td>
                        <td>{distance_text}</td>
                        <td>{signal['option_ltp']}</td>
                        <td>{signal['oi']:,}</td>
                        <td>{signal['coi']:+,}</td>
                        <td>{signal['iv']}</td>
                        <td><small>{signal['selection_reason']}</small></td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
    else:
        html += """
            <div class="signal-card">
                <h3>â¸ï¸ No Active Signals in ATM Â±5 Range</h3>
                <p>Monitoring ATM and nearby strikes for opportunities...</p>
            </div>
        """
    
    # Strike Analysis Information
    html += """
            <h2>ðŸŽ¯ Strike Selection Strategy</h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                <div style="background: #e8f5e8; padding: 15px; border-radius: 8px;">
                    <h3>ðŸ“ ATM Strike</h3>
                    <p><strong>Priority: Highest</strong></p>
                    <p>â€¢ Maximum Gamma sensitivity<br>â€¢ Balanced Delta<br>â€¢ Highest liquidity</p>
                </div>
                <div style="background: #e3f2fd; padding: 15px; border-radius: 8px;">
                    <h3>ðŸ“ Near-ATM (Â±1)</h3>
                    <p><strong>Priority: High</strong></p>
                    <p>â€¢ High Gamma<br>â€¢ Good liquidity<br>â€¢ Slightly better risk-reward</p>
                </div>
                <div style="background: #fff3e0; padding: 15px; border-radius: 8px;">
                    <h3>ðŸ“ OTM (Â±2-5)</h3>
                    <p><strong>Priority: Medium</strong></p>
                    <p>â€¢ Lower premium<br>â€¢ Higher potential returns<br>â€¢ Lower probability</p>
                </div>
            </div>
    """
    
    # Market Overview
    if detailed_data:
        html += """
            <h2>ðŸ“Š Market Overview (ATM Â±5 Analysis)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Current Price</th>
                        <th>ATM Strike</th>
                        <th>Strikes Analyzed</th>
                        <th>PCR OI</th>
                        <th>PCR Volume</th>
                        <th>Signal Strength</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for data in detailed_data:
            pcr_oi = data['pcr_oi']
            if pcr_oi > 1.5:
                strength = "ðŸŸ¢ Very Bullish"
            elif pcr_oi > 1.2:
                strength = "ðŸŸ¡ Bullish"
            elif pcr_oi < 0.6:
                strength = "ðŸ”´ Very Bearish"
            elif pcr_oi < 0.8:
                strength = "ðŸŸ  Bearish"
            else:
                strength = "âšª Neutral"
                
            html += f"""
                    <tr>
                        <td>{data['symbol']}</td>
                        <td>{data['current_price']}</td>
                        <td>{data['atm_strike']}</td>
                        <td>{data['total_strikes_analyzed']} strikes</td>
                        <td>{data['pcr_oi']}</td>
                        <td>{data['pcr_volume']}</td>
                        <td>{strength}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
    
    html += """
            <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 8px;">
                <h3>ðŸŽ¯ Focused Trading Approach</h3>
                <p><strong>Strategy:</strong> We analyze ONLY ATM and Â±5 strikes for maximum focus and efficiency.</p>
                <p><strong>Priority:</strong> ATM â†’ Near-ATM â†’ Slight OTM in the Â±5 range</p>
                <p><strong>Benefit:</strong> Reduced analysis paralysis, better strike concentration, improved decision making</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w") as f:
        f.write(html)
    print("âœ… Focused HTML report generated: index.html")

if __name__ == "__main__":
    main()
  
