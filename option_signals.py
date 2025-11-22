import requests
import pandas as pd
import numpy as np
from datetime import datetime, time
import time as time_module
import json
import os

print("ðŸš€ ADVANCED NSE OPTION SIGNALS - COMPLETE ANALYSIS")

class AdvancedOptionSignalGenerator:
    def __init__(self):
        self.symbols = [
            "NIFTY", "BANKNIFTY",
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", 
            "KOTAKBANK", "HDFC", "BHARTIARTL", "ITC", "SBIN"
        ]
        
    def fetch_option_chain(self, symbol):
        """Fetch complete option chain data from NSE"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
                print(f"âŒ Failed to fetch {symbol}: Status {response.status_code}")
                return None
                
        except Exception as e:
            print(f"âŒ Error fetching {symbol}: {e}")
            return None
    
    def analyze_atm_strikes(self, data, symbol):
        """Analyze only ATM Â±5 strikes with complete data"""
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
        
        # Get ONLY Â±5 strikes from ATM
        all_strikes = sorted(strikes)
        atm_index = all_strikes.index(atm_strike)
        start_idx = max(0, atm_index - 5)
        end_idx = min(len(all_strikes), atm_index + 6)
        
        relevant_strikes = all_strikes[start_idx:end_idx]
        relevant_data = [item for item in option_data 
                        if item['strikePrice'] in relevant_strikes]
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'atm_strike': atm_strike,
            'expiry': current_expiry,
            'strikes_analyzed': relevant_strikes,
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
    
    def select_optimal_strike(self, analysis_data, option_type):
        """Select optimal strike from ATM Â±5 with multi-parameter scoring"""
        if not analysis_data:
            return None
            
        current_price = analysis_data['current_price']
        atm_strike = analysis_data['atm_strike']
        relevant_data = analysis_data['data']
        
        candidate_strikes = []
        
        for item in relevant_data:
            strike = item['strikePrice']
            
            # Calculate distance from ATM
            strike_index = analysis_data['strikes_analyzed'].index(strike)
            atm_index = analysis_data['strikes_analyzed'].index(atm_strike)
            distance_from_atm = abs(strike_index - atm_index)
            
            if option_type == 'CE':
                if 'CE' in item and strike >= current_price:  # OTM or ATM CE
                    ce_data = item['CE']
                            candidate_strikes = ({

        for item in relevant_data:
            strike = item['strikePrice']
            
            # Calculate distance from ATM
            strike_index = analysis_data['strikes_analyzed'].index(strike)
            atm_index = analysis_data['strikes_analyzed'].index(atm_strike)
            distance_from_atm = abs(strike_index - atm_index)
            
            if option_type == 'CE':
                if 'CE' in item and strike >= current_price:  # OTM or ATM CE
                    ce_data = item['CE']
                    candidate_strikes.append({
                        'strike': strike,
                        'distance_from_atm': distance_from_atm,
                        'is_atm': strike == atm_strike,
                        'is_near_atm': distance_from_atm <= 1,
                        'oi': ce_data.get('openInterest', 0),
                        'coi': ce_data.get('changeinOpenInterest', 0),  # Fixed typo
                        'volume': ce_data.get('totalTradedVolume', 0),   # Fixed typo
                        'iv': ce_data.get('impliedVolatility', 0),
                        'delta': ce_data.get('delta', 0),
                        'gamma': ce_data.get('gamma', 0),
                        'ltp': ce_data.get('lastPrice', 0),
                        'change': ce_data.get('change', 0),
                        'change_percentage': ce_data.get('pChange', 0)
                    })  # Removed semicolon
            else:  # PE
                if 'PE' in item and strike <= current_price:  # OTM or ATM PE
                    pe_data = item['PE']
                    candidate_strikes.append({
                        'strike': strike,
                        'distance_from_atm': distance_from_atm,
                        'is_atm': strike == atm_strike,
                        'is_near_atm': distance_from_atm <= 1,
                        'oi': pe_data.get('openInterest', 0),
                        'coi': pe_data.get('changeinOpenInterest', 0),  # Fixed typo
                        'volume': pe_data.get('totalTradedVolume', 0),   # Fixed typo
                        'iv': pe_data.get('impliedVolatility', 0),
                        'delta': pe_data.get('delta', 0),
                        'gamma': pe_data.get('gamma', 0),
                        'ltp': pe_data.get('lastPrice', 0),
                        'change': pe_data.get('change', 0),
                        'change_percentage': pe_data.get('pChange', 0)
                    })  # Removed semicolon

        if not candidate_strikes:
            return None

        # Multi-parameter scoring
        for candidate in candidate_strikes:
            score = 0

            # Priority 1: Proximity to ATM (60% weight)
            if candidate['is_atm']:  # Fixed: removed semicolon, added colon
                score += 60
            elif candidate['is_near_atm']:  # Fixed: removed semicolon, added colon
                score += 50
            else:
                score += 40 - (candidate['distance_from_atm'] * 5)

            # Priority 2: OI and COI analysis (20% weight)
            oi_score = min(candidate['oi'] / 10000, 5)
            coi_score = candidate['coi'] / 500
            score += oi_score + coi_score
            
            # Priority 3: Volume confirmation (10% weight)
            volume_score = min(candidate['volume'] / 1000, 3)
            score += volume_score
            
            # Priority 4: IV consideration (5% weight) - lower IV better for buying
            iv_score = max(0, 5 - (candidate['iv'] or 0) / 5)
            score += iv_score
            
            # Priority 5: Price momentum (5% weight)
            if candidate['change_percentage'] > 0:
                score += 2
            
            candidate['score'] = round(score, 2)
            candidate['selection_reason'] = self.get_selection_reason(candidate)

        # Select strike with highest score
        best_strike = max(candidate_strikes, key=lambda x: x['score'])
        return best_strike
        
        # Multi-parameter scoring
        for candidate in candidate_strikes:
            score = 0
            
            # Priority 1: Proximity to ATM (60% weight)
            if candidate['is_atm']:
                score += 60
            elif candidate['is_near_atm']:
                score += 50
            else:
                score += 40 - (candidate['distance_from_atm'] * 5)
            
            # Priority 2: OI and COI analysis (20% weight)
            oi_score = min(candidate['oi'] / 10000, 5)
            coi_score = candidate['coi'] / 500
            score += oi_score + coi_score
            
            # Priority 3: Volume confirmation (10% weight)
            volume_score = min(candidate['volume'] / 1000, 3)
            score += volume_score
            
            # Priority 4: IV consideration (5% weight) - lower IV better for buying
            iv_score = max(0, 5 - (candidate['iv'] or 0) / 5)
            score += iv_score
            
            # Priority 5: Price momentum (5% weight)
            if candidate['change_percentage'] > 0:
                score += 2
            
            candidate['score'] = round(score, 2)
            candidate['selection_reason'] = self.get_selection_reason(candidate)
        
        # Select strike with highest score
        best_strike = max(candidate_strikes, key=lambda x: x['score'])
        return best_strike
    
    def get_selection_reason(self, candidate):
        """Generate detailed selection reason"""
        reasons = []
        
        if candidate['is_atm']:
            reasons.append("ATM Strike")
        elif candidate['is_near_atm']:
            reasons.append("Near-ATM")
        else:
            reasons.append(f"{candidate['distance_from_atm']} steps from ATM")
        
        if candidate['coi'] > 0:
            reasons.append("Fresh Long Buildup")
        elif candidate['coi'] < 0:
            reasons.append("Long Unwinding")
        
        if candidate['volume'] > 1000:
            reasons.append("High Volume")
        
        if candidate['iv'] and candidate['iv'] < 20:
            reasons.append("Low IV")
        
        return " | ".join(reasons)
        def generate_advanced_signal(self, analysis_data):
        """Generate signals using multiple parameters"""
        if not analysis_data:
            return None
            
        symbol = analysis_data['symbol']
        current_price = analysis_data['current_price']
        atm_strike = analysis_data['atm_strike']
        
        # Calculate PCR
        pcr_oi, pcr_volume = self.calculate_pcr(analysis_data['all_data'])
        
        # Analyze OI buildup
        total_ce_oi = sum(item['CE']['openInterest'] for item in analysis_data['data'] if 'CE' in item)
        total_pe_oi = sum(item['PE']['openInterest'] for item in analysis_data['data'] if 'PE' in item)
        oi_ratio = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
        
        signal = "HOLD"
        option_type = None
        strike_data = None
        reason = ""
        
        # Multi-parameter signal logic
        bullish_conditions = 0
        bearish_conditions = 0
        
        # PCR conditions
        if pcr_oi > 1.5:
            bullish_conditions += 2
        elif pcr_oi > 1.2:
            bullish_conditions += 1
            
        if pcr_oi < 0.6:
            bearish_conditions += 2
        elif pcr_oi < 0.8:
            bearish_conditions += 1
        
        # OI ratio conditions
        if oi_ratio > 1.3:
            bullish_conditions += 1
        elif oi_ratio < 0.7:
            bearish_conditions += 1
        # Generate final signal
        if bullish_conditions >= 3:
            signal = "STRONG BUY"
            option_type = "CE"
            strike_data = self.select_optimal_strike(analysis_data, 'CE')
            reason = f"Strong Bullish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
        elif bullish_conditions >= 2:
            signal = "BUY"
            option_type = "CE"
            strike_data = self.select_optimal_strike(analysis_data, 'CE')
            reason = f"Bullish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
        elif bearish_conditions >= 3:
            signal = "STRONG BUY"
            option_type = "PE"
            strike_data = self.select_optimal_strike(analysis_data, 'PE')
            reason = f"Strong Bearish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
        elif bearish_conditions >= 2:
            signal = "BUY"
            option_type = "PE"
            strike_data = self.select_optimal_strike(analysis_data, 'PE')
            reason = f"Bearish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
        else:
            return None  # No clear signal
        
        if strike_data:
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
                'option_change_percentage': strike_data['change_percentage'],
                'oi': strike_data['oi'],
                'coi': strike_data['coi'],
                'volume': strike_data['volume'],
                'iv': strike_data['iv'],
                'delta': strike_data['delta'],
                'gamma': strike_data['gamma'],
                'pcr_oi': pcr_oi,
                'pcr_volume': pcr_volume,
                'oi_ratio': round(oi_ratio, 2),
                'strike_score': strike_data['score'],
                'selection_reason': strike_data['selection_reason'],
                'signal_reason': reason,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        return None
        def run_complete_analysis(self):
        """Run complete analysis with all parameters"""
        print("ðŸŽ¯ RUNNING COMPLETE OPTION CHAIN ANALYSIS...")
        print("ðŸ“Š Parameters: OI, COI, Price, Change, IV, Delta, Gamma, ATMÂ±5")
        print("=" * 80)
        
        all_signals = []
        market_data = []
        
        for symbol in self.symbols:
            print(f"ðŸ” Analyzing {symbol} (ATM Â±5 strikes)...")
            
            data = self.fetch_option_chain(symbol)
            
            if data:
                analysis_data = self.analyze_atm_strikes(data, symbol)
                
                if analysis_data:
                    # Display strike range
                    strikes = analysis_data['strikes_analyzed']
                    print(f"   ðŸŽ¯ ATM: {analysis_data['atm_strike']}, Range: {strikes[0]} to {strikes[-1]}")
                    
                    # Generate advanced signal
                    signal = self.generate_advanced_signal(analysis_data)
                    
                    if signal:
                        all_signals.append(signal)
                        print(f"   âœ… {signal['signal']} {signal['option_type']} at {signal['strike_price']}")
                        print(f"   ðŸ“ {signal['selection_reason']}")
                        print(f"   ðŸ“ˆ LTP: {signal['option_ltp']}, OI: {signal['oi']:,}, COI: {signal['coi']:+,}")
                    
                    # Store market data for all symbols
                    market_data.append({
                        'symbol': symbol,
                        'current_price': analysis_data['current_price'],
                        'atm_strike': analysis_data['atm_strike'],
                        'strikes_analyzed': len(strikes),
                        'pcr_oi': signal['pcr_oi'] if signal else 0,
                        'pcr_volume': signal['pcr_volume'] if signal else 0,
                        'oi_ratio': signal['oi_ratio'] if signal else 0,
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    print(f"   âŒ No analysis data for {symbol}")
            else:
                print(f"   âŒ Failed to fetch data for {symbol}")
            
            print("-" * 50)
            time_module.sleep(2)
        
        print(f"ðŸ“ˆ Analysis Complete: {len(all_signals)} signals generated")
        return all_signals, market_data
        def main():
    print("=" * 70)
    print("ðŸš€ ADVANCED NSE OPTION SIGNALS - COMPLETE ANALYSIS")
    print("ðŸ“Š Using: OI, COI, Price, Change, IV, Delta, Gamma, ATMÂ±5 Strikes")
    print("=" * 70)
    
    generator = AdvancedOptionSignalGenerator()
    
    # Run complete analysis
    signals, market_data = generator.run_complete_analysis()
    
    # Save detailed signals
    if signals:
        df_signals = pd.DataFrame(signals)
        df_signals.to_csv("option_signals.csv", index=False)
        print(f"âœ… Detailed signals saved: {len(signals)} signals")
        
        # Display sample signal
        if len(signals) > 0:
            sample = signals[0]
            print(f"\nðŸ“‹ SAMPLE SIGNAL:")
            print(f"   Symbol: {sample['symbol']}")
            print(f"   Signal: {sample['signal']} {sample['option_type']}")
            print(f"   Strike: {sample['strike_price']} (ATM: {sample['atm_strike']})")
            print(f"   LTP: {sample['option_ltp']}, Change: {sample['option_change']}")
            print(f"   OI: {sample['oi']:,}, COI: {sample['coi']:+,}")
            print(f"   IV: {sample['iv']}, Delta: {sample['delta']}, Gamma: {sample['gamma']}")
            print(f"   PCR: {sample['pcr_oi']}, Score: {sample['strike_score']}")
    else:
        # Create empty file with all columns
        empty_df = pd.DataFrame(columns=[
            'symbol', 'signal', 'option_type', 'strike_price', 'current_price',
            'atm_strike', 'distance_from_atm', 'option_ltp', 'option_change',
            'option_change_percentage', 'oi', 'coi', 'volume', 'iv', 'delta',
            'gamma', 'pcr_oi', 'pcr_volume', 'oi_ratio', 'strike_score',
            'selection_reason', 'signal_reason', 'timestamp'
        ])
        empty_df.to_csv("option_signals.csv", index=False)
        print("â„¹ï¸ No strong signals - market may be neutral")
    
    # Save market data
    if market_data:
        df_market = pd.DataFrame(market_data)
        df_market.to_csv("detailed_option_data.csv", index=False)
        print(f"âœ… Market data saved: {len(market_data)} symbols")
    
    # Generate comprehensive HTML dashboard
    generate_advanced_dashboard(signals, market_data)
    
    return signals, market_data
    def generate_advanced_dashboard(signals, market_data):
    """Generate comprehensive trading dashboard"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Advanced NSE Option Signals - Complete Analysis</title>
        <meta http-equiv="refresh" content="300">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; }}
            .signal-card {{ background: white; padding: 15px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .strong-buy {{ border-left: 5px solid #28a745; }}
            .buy {{ border-left: 5px solid #17a2b8; }}
            table {{ width: 100%; border-collapse: collapse; background: white; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f8f9fa; }}
            .last-update {{ background: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .param-badge {{ background: #e9ecef; padding: 2px 8px; border-radius: 10px; font-size: 12px; margin: 2px; }}
            .positive {{ color: #28a745; }}
            .negative {{ color: #dc3545; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>ðŸŽ¯ Advanced NSE Option Signals</h1>
                <p>Complete Analysis: OI, COI, Price, IV, Delta, Gamma, ATMÂ±5 Strikes</p>
            </div>
            
            <div class="last-update">
                <strong>Last Updated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                <br><strong>Analysis Focus:</strong> ATM Â±5 strikes only
                <br><strong>Parameters:</strong> 
                <span class="param-badge">OI</span>
                <span class="param-badge">COI</span>
                <span class="param-badge">Price & Change</span>
                <span class="param-badge">IV</span>
                <span class="param-badge">Delta</span>
                <span class="param-badge">Gamma</span>
                <span class="param-badge">PCR</span>
            </div>
    """
    
    if signals:
        html += """
            <h2>ðŸš€ Active Trading Signals</h2>
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Signal</th>
                        <th>Option</th>
                        <th>Strike</th>
                        <th>ATM</th>
                        <th>LTP</th>
                        <th>Change</th>
                        <th>OI</th>
                        <th>COI</th>
                        <th>IV</th>
                        <th>Delta</th>
                        <th>PCR</th>
                        <th>Score</th>
                        <th>Selection Reason</th>
                    </tr>
                </thead>
                <tbody>
        """
        for signal in signals:
            signal_class = "strong-buy" if "STRONG" in signal['signal'] else "buy"
            change_class = "positive" if signal['option_change'] > 0 else "negative"
            coi_class = "positive" if signal['coi'] > 0 else "negative"
            
            html += f"""
                    <tr class="{signal_class}">
                        <td><strong>{signal['symbol']}</strong></td>
                        <td><strong>{signal['signal']}</strong></td>
                        <td>{signal['option_type']}</td>
                        <td>{signal['strike_price']}</td>
                        <td>{signal['atm_strike']}</td>
                        <td>{signal['option_ltp']}</td>
                        <td class="{change_class}">{signal['option_change']:+.2f}</td>
                        <td>{signal['oi']:,}</td>
                        <td class="{coi_class}">{signal['coi']:+,}</td>
                        <td>{signal['iv']}</td>
                        <td>{signal['delta']}</td>
                        <td>{signal['pcr_oi']}</td>
                        <td>{signal['strike_score']}</td>
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
                <h3>â¸ï¸ No Strong Signals Detected</h3>
                <p>Market is in neutral zone. Monitoring ATM Â±5 strikes for opportunities...</p>
            </div>
        """
    
    if market_data:
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
                        <th>OI Ratio</th>
                        <th>Signal Strength</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for data in market_data:
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
                        <td>{data['strikes_analyzed']} strikes</td>
                        <td>{data['pcr_oi']}</td>
                        <td>{data.get('oi_ratio', 0)}</td>
                        <td>{strength}</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        """
        # Strategy explanation
    html += """
            <div style="margin-top: 20px; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px;">
                <div style="background: #e8f5e8; padding: 15px; border-radius: 8px;">
                    <h3>ðŸŽ¯ Strike Selection</h3>
                    <p><strong>Focus:</strong> ATM Â±5 strikes only</p>
                    <p><strong>Priority:</strong> ATM â†’ Near-ATM â†’ Slight OTM</p>
                    <p><strong>Scoring:</strong> OI, COI, Volume, IV, Delta, Gamma</p>
                </div>
                <div style="background: #e3f2fd; padding: 15px; border-radius: 8px;">
                    <h3>ðŸ“ˆ Signal Parameters</h3>
                    <p><strong>OI/COI:</strong> Fresh long buildup</p>
                    <p><strong>PCR:</strong> Market sentiment</p>
                    <p><strong>IV:</strong> Lower better for buying</p>
                    <p><strong>Greeks:</strong> Delta & Gamma analysis</p>
                </div>
                <div style="background: #fff3e0; padding: 15px; border-radius: 8px;">
                    <h3>âš¡ Quick Guide</h3>
                    <p><strong>COI +ve:</strong> Fresh positions</p>
                    <p><strong>COI -ve:</strong> Position unwinding</p>
                    <p><strong>High Volume:</strong> Confirmation</p>
                    <p><strong>Low IV:</strong> Cheaper premiums</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w") as f:
        f.write(html)
    print("âœ… Advanced dashboard generated")

if __name__ == "__main__":
    main()
