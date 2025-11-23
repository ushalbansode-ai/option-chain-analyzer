#!/usr/bin/env python3
# option_signals.py - Fixed version with proper indices handling

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time as time_module
import json
import os
import math

PRINT_PREFIX = "🛰️"

class AdvancedOptionSignalGenerator:
    def __init__(self):
        self.symbols = [
            "NIFTY", "BANKNIFTY",
            "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
            "KOTAKBANK", "HDFC", "BHARTIARTL", "ITC", "SBIN"
        ]
    def _session(self):
        """Return a requests session primed for NSE."""
        s = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'application/json, text/plain, */*'
        }
        s.headers.update(headers)
        try:
            s.get("https://www.nseindia.com", timeout=5)
            time_module.sleep(1)
        except Exception:
            pass
        return s

    def fetch_option_chain(self, symbol):
        """Fetch option chain JSON from NSE for symbol."""
        try:
            session = self._session()
            if symbol in ['NIFTY', 'BANKNIFTY']:
                url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            else:
                url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"

            print(f"{PRINT_PREFIX} 📡 Fetching data for {symbol}...")
            r = session.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data and 'records' in data:
                    print(f"{PRINT_PREFIX} ✅ Successfully fetched {symbol}")
                    return data
                else:
                    print(f"{PRINT_PREFIX} ❌ Invalid data format for {symbol}")
                    return None
            else:
                print(f"{PRINT_PREFIX} ❌ Failed to fetch {symbol}: HTTP {r.status_code}")
                return None
        except Exception as e:
            print(f"{PRINT_PREFIX} ❌ Error fetching {symbol}: {str(e)}")
            return None
    def analyze_atm_strikes(self, data, symbol):
        """Return dict with ATM +/-5 strike data and metadata."""
        if not data or 'records' not in data:
            return None

        try:
            records = data.get('records', {})
            current_price = records.get('underlyingValue', None)
            expiry_dates = records.get('expiryDates', []) or []

            if current_price is None or not expiry_dates:
                return None

            # Use nearest expiry
            current_expiry = expiry_dates[0]

            option_rows = [item for item in records.get('data', []) if item.get('expiryDate') == current_expiry]
            if not option_rows:
                return None

            # Build strike list and find nearest (ATM)
            strikes = sorted({item.get('strikePrice', 0) for item in option_rows})
            if not strikes:
                return None

            # nearest strike
            atm_strike = min(strikes, key=lambda x: abs(x - current_price))
            # pick ±5 strikes around ATM
            try:
                atm_index = strikes.index(atm_strike)
            except ValueError:
                atm_index = 0
            start_idx = max(0, atm_index - 5)
            end_idx = min(len(strikes), atm_index + 6)
            relevant_strikes = strikes[start_idx:end_idx]

            # filter rows for relevant strikes
            relevant_rows = [r for r in option_rows if r.get('strikePrice', 0) in relevant_strikes]

            return {
                'symbol': symbol,
                'current_price': float(current_price),
                'atm_strike': atm_strike,
                'expiry': current_expiry,
                'strikes_analyzed': relevant_strikes,
                'data': relevant_rows,
                'all_data': option_rows
            }
        except Exception as e:
            print(f"{PRINT_PREFIX} ❌ Error analyzing {symbol}: {str(e)}")
            return None                                                                                                           
    def calculate_pcr(self, data_rows):
        """Compute PCR based on aggregated OI and volume - FIXED for indices."""
        total_ce_oi = total_pe_oi = 0
        total_ce_vol = total_pe_vol = 0

        for r in data_rows:
            ce = r.get('CE', {})
            pe = r.get('PE', {})
            
            # Handle indices data structure
            if ce:
                ce_oi = ce.get('openInterest', 0)
                ce_vol = ce.get('totalTradedVolume', 0) or 0
                total_ce_oi += float(ce_oi) if ce_oi else 0
                total_ce_vol += float(ce_vol) if ce_vol else 0
                
            if pe:
                pe_oi = pe.get('openInterest', 0)
                pe_vol = pe.get('totalTradedVolume', 0) or 0
                total_pe_oi += float(pe_oi) if pe_oi else 0
                total_pe_vol += float(pe_vol) if pe_vol else 0

        pcr_oi = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else 1.0
        pcr_vol = (total_pe_vol / total_ce_vol) if total_ce_vol > 0 else 1.0
        
        return round(pcr_oi, 2), round(pcr_vol, 2)
    def select_optimal_strike(self, analysis_data, option_type):
        """Select strike from ATM window using multi-parameter scoring."""
        if not analysis_data:
            return None

        try:
            current_price = analysis_data['current_price']
            atm = analysis_data['atm_strike']
            rows = analysis_data['data']
            strikes_list = analysis_data['strikes_analyzed']

            candidates = []
            for r in rows:
                strike = r.get('strikePrice', 0)
                try:
                    strike_idx = strikes_list.index(strike)
                    atm_idx = strikes_list.index(atm)
                except ValueError:
                    continue
                dist = abs(strike_idx - atm_idx)

                if option_type == 'CE':
                    side = r.get('CE')
                    if not side:
                        continue
                    # Consider OTM/ATM CE
                    if strike < current_price * 0.995:
                        continue
                else:
                    side = r.get('PE')
                    if not side:
                        continue
                    # Consider OTM/ATM PE
                    if strike > current_price * 1.005:
                        continue

                # Extract all metrics with safe defaults
                oi = float(side.get('openInterest', 0) or 0)
                coi = float(side.get('changeinOpenInterest', 0) or 0)
                vol = float(side.get('totalTradedVolume', 0) or 0)
                iv = float(side.get('impliedVolatility', 0) or 0)
                ltp = float(side.get('lastPrice', 0) or 0)
                change = float(side.get('change', 0) or 0)
                pchg = float(side.get('pChange', 0) or 0)
                
                # Handle Greek values safely
                delta = side.get('delta', 0)
                gamma = side.get('gamma', 0)
                if isinstance(delta, str):
                    try:
                        delta = float(delta)
                    except:
                        delta = 0
                if isinstance(gamma, str):
                    try:
                        gamma = float(gamma)
                    except:
                        gamma = 0

                candidates.append({
                    'strike': strike,
                    'distance_from_atm': dist,
                    'is_atm': strike == atm,
                    'is_near_atm': dist <= 1,
                    'oi': oi,
                    'coi': coi,
                    'volume': vol,
                    'iv': iv,
                    'ltp': ltp,
                    'change': change,
                    'change_percentage': pchg,
                    'delta': delta,
                    'gamma': gamma
                })

            if not candidates:
                return None

            # Enhanced scoring algorithm
            for c in candidates:
                score = 0.0
                
                # 1. Proximity to ATM (40% weight)
                if c['is_atm']:
                    score += 40.0
                elif c['is_near_atm']:
                    score += 35.0
                else:
                    score += max(20.0, 30.0 - (c['distance_from_atm'] * 2.0))
                
                # 2. OI/COI strength (30% weight)
                oi_score = min(c['oi'] / 10000.0, 10.0)
                score += oi_score
                
                # COI positive is good (fresh positions)
                if c['coi'] > 0:
                    score += min(c['coi'] / 1000.0, 5.0)
                
                # 3. Volume confirmation (15% weight)
                volume_score = min(c['volume'] / 500.0, 7.5)
                score += volume_score
                
                # 4. IV consideration (10% weight) - lower IV preferred for buying
                if c['iv'] > 0:
                    iv_score = max(0.0, 5.0 - (c['iv'] / 10.0))
                    score += iv_score
                
                # 5. Price momentum (5% weight)
                if c['change_percentage'] > 0:
                    score += 2.5
                
                c['score'] = round(score, 2)
                c['selection_reason'] = self.get_selection_reason(c)

            # Select candidate with highest score
            best_candidate = max(candidates, key=lambda x: x['score'])
            return best_candidate
            
        except Exception as e:
            print(f"{PRINT_PREFIX} ❌ Error selecting strike: {str(e)}")
            return None
    def get_selection_reason(self, candidate):
        """Translate candidate metrics into human-readable reasons."""
        reasons = []
        if candidate.get('is_atm'):
            reasons.append("ATM Strike")
        elif candidate.get('is_near_atm'):
            reasons.append("Near-ATM")
        else:
            reasons.append(f"{candidate.get('distance_from_atm')} steps from ATM")
        
        coi = candidate.get('coi', 0)
        if coi > 0:
            reasons.append("Fresh Long Buildup")
        elif coi < 0:
            reasons.append("Long Unwinding")
        
        if candidate.get('volume', 0) > 1000:
            reasons.append("High Volume")
        
        iv = candidate.get('iv') or 0
        if iv and iv < 25:
            reasons.append("Low IV")
        elif iv > 40:
            reasons.append("High IV")
            
        if candidate.get('change_percentage', 0) > 5:
            reasons.append("Strong Momentum")
            
        return " | ".join(reasons) if reasons else "Balanced Parameters"

    def generate_advanced_signal(self, analysis_data):
        """Combine the metrics into final trading signal and pick strike."""
        if not analysis_data:
            return None

        try:
            sym = analysis_data['symbol']
            current_price = analysis_data['current_price']

            pcr_oi, pcr_vol = self.calculate_pcr(analysis_data['all_data'])

            # Calculate OI ratio for relevant strikes only
            total_ce_oi = sum(float(r.get('CE', {}).get('openInterest', 0) or 0) for r in analysis_data['data'] if 'CE' in r)
            total_pe_oi = sum(float(r.get('PE', {}).get('openInterest', 0) or 0) for r in analysis_data['data'] if 'PE' in r)
            oi_ratio = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else 1.0

            # Enhanced signal logic with multiple conditions
            bullish_score = 0
            bearish_score = 0

            # PCR-based signals
            if pcr_oi > 1.8:
                bullish_score += 3
            elif pcr_oi > 1.5:
                bullish_score += 2
            elif pcr_oi > 1.2:
                bullish_score += 1
                
            if pcr_oi < 0.4:
                bearish_score += 3
            elif pcr_oi < 0.6:
                bearish_score += 2
            elif pcr_oi < 0.8:
                bearish_score += 1

            # OI ratio signals
            if oi_ratio > 1.5:
                bullish_score += 2
            elif oi_ratio > 1.2:
                bullish_score += 1
                
            if oi_ratio < 0.6:
                bearish_score += 2
            elif oi_ratio < 0.8:
                bearish_score += 1

            # Determine signal
            signal = None
            option_type = None
            strike_choice = None
            reason = ""

            if bullish_score >= 4:
                signal = "STRONG BUY"
                option_type = "CE"
                strike_choice = self.select_optimal_strike(analysis_data, "CE")
                reason = f"Very Bullish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
            elif bullish_score >= 2:
                signal = "BUY"
                option_type = "CE"
                strike_choice = self.select_optimal_strike(analysis_data, "CE")
                reason = f"Bullish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
            elif bearish_score >= 4:
                signal = "STRONG BUY"
                option_type = "PE"
                strike_choice = self.select_optimal_strike(analysis_data, "PE")
                reason = f"Very Bearish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"
            elif bearish_score >= 2:
                signal = "BUY"
                option_type = "PE"
                strike_choice = self.select_optimal_strike(analysis_data, "PE")
                reason = f"Bearish: PCR({pcr_oi}), OI_Ratio({oi_ratio:.2f})"

            if not signal or not strike_choice:
                return None

            return {
                'symbol': sym,
                'signal': signal,
                'option_type': option_type,
                'strike_price': strike_choice['strike'],
                'current_price': current_price,
                'atm_strike': analysis_data['atm_strike'],
                'distance_from_atm': strike_choice['distance_from_atm'],
                'option_ltp': strike_choice['ltp'],
                'option_change': strike_choice['change'],
                'option_change_percentage': strike_choice['change_percentage'],
                'oi': strike_choice['oi'],
                'coi': strike_choice['coi'],
                'volume': strike_choice['volume'],
                'iv': strike_choice['iv'],
                'delta': strike_choice.get('delta', 0),
                'gamma': strike_choice.get('gamma', 0),
                'pcr_oi': pcr_oi,
                'pcr_volume': pcr_vol,
                'oi_ratio': round(oi_ratio, 2),
                'strike_score': strike_choice['score'],
                'selection_reason': strike_choice['selection_reason'],
                'signal_reason': reason,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            print(f"{PRINT_PREFIX} ❌ Error generating signal for {analysis_data.get('symbol', 'unknown')}: {str(e)}")
            return None
    def run_complete_analysis(self):
        """Main loop: fetch, analyze and return signals + market overview."""
        print(f"{PRINT_PREFIX} 🎯 STARTING COMPLETE OPTION CHAIN ANALYSIS...")
        print(f"{PRINT_PREFIX} 📊 Analyzing {len(self.symbols)} symbols...")
        
        all_signals = []
        market_data = []

        for sym in self.symbols:
            print(f"{PRINT_PREFIX} 🔍 Analyzing {sym}...")
            
            data = self.fetch_option_chain(sym)
            if not data:
                print(f"{PRINT_PREFIX} ❌ No data for {sym}")
                market_data.append({
                    'symbol': sym,
                    'current_price': 0,
                    'atm_strike': 0,
                    'strikes_analyzed': 0,
                    'pcr_oi': 0,
                    'pcr_volume': 0,
                    'oi_ratio': 0,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                time_module.sleep(2)
                continue

            analysis = self.analyze_atm_strikes(data, sym)
            if not analysis:
                print(f"{PRINT_PREFIX} ❌ No ATM analysis for {sym}")
                market_data.append({
                    'symbol': sym,
                    'current_price': 0,
                    'atm_strike': 0,
                    'strikes_analyzed': 0,
                    'pcr_oi': 0,
                    'pcr_volume': 0,
                    'oi_ratio': 0,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                time_module.sleep(2)
                continue

            print(f"{PRINT_PREFIX}   🎯 {sym}: Price {analysis['current_price']}, ATM {analysis['atm_strike']}")
            print(f"{PRINT_PREFIX}   📈 Range: {analysis['strikes_analyzed'][0]} - {analysis['strikes_analyzed'][-1]}")
            
            signal = self.generate_advanced_signal(analysis)
            if signal:
                all_signals.append(signal)
                print(f"{PRINT_PREFIX}   ✅ {signal['signal']} {signal['option_type']} at {signal['strike_price']}")
                print(f"{PRINT_PREFIX}   📍 Reason: {signal['selection_reason']}")
                print(f"{PRINT_PREFIX}   💰 LTP: {signal['option_ltp']}, Score: {signal['strike_score']}")
            else:
                print(f"{PRINT_PREFIX}   ⏸ No clear signal for {sym}")

            # Calculate PCR for market data
            pcr_oi, pcr_vol = self.calculate_pcr(analysis['all_data'])
            total_ce_oi = sum(float(r.get('CE', {}).get('openInterest', 0) or 0) for r in analysis['data'] if 'CE' in r)
            total_pe_oi = sum(float(r.get('PE', {}).get('openInterest', 0) or 0) for r in analysis['data'] if 'PE' in r)
            oi_ratio = (total_pe_oi / total_ce_oi) if total_ce_oi > 0 else 0.0

            # market overview entry
            market_data.append({
                'symbol': sym,
                'current_price': analysis['current_price'],
                'atm_strike': analysis['atm_strike'],
                'strikes_analyzed': len(analysis['strikes_analyzed']),
                'pcr_oi': pcr_oi,
                'pcr_volume': pcr_vol,
                'oi_ratio': round(oi_ratio, 2),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            time_module.sleep(2)  # Be respectful to the API

        print(f"{PRINT_PREFIX} 📊 ANALYSIS COMPLETE: {len(all_signals)} signals generated")
        return all_signals, market_data
def generate_advanced_dashboard(signals, market_data, out_path="docs/index.html"):
    """Generate a comprehensive HTML dashboard."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    # Calculate some stats
    total_signals = len(signals)
    strong_signals = len([s for s in signals if 'STRONG' in s['signal']])
    ce_signals = len([s for s in signals if s['option_type'] == 'CE'])
    pe_signals = len([s for s in signals if s['option_type'] == 'PE'])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live NSE Option Signals</title>
    <meta http-equiv="refresh" content="300">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: white; padding: 15px; border-radius: 8px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        .signal-card {{ background: white; padding: 15px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-left: 5px solid #3498db; }}
        .strong-buy {{ border-left-color: #27ae60; }}
        .buy {{ border-left-color: #3498db; }}
        table {{ width: 100%; border-collapse: collapse; background: white; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Live NSE Option Signals</h1>
            <p>Real-time Option Chain Analysis | Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div style="font-size: 2em; font-weight: bold;">{total_signals}</div>
                <div>Total Signals</div>
            </div>
            <div class="stat-card">
                <div style="font-size: 2em; font-weight: bold;">{strong_signals}</div>
                <div>Strong Signals</div>
            </div>
            <div class="stat-card">
                <div style="font-size: 2em; font-weight: bold;">{ce_signals}</div>
                <div>Call Signals</div>
            </div>
            <div class="stat-card">
                <div style="font-size: 2em; font-weight: bold;">{pe_signals}</div>
                <div>Put Signals</div>
            </div>
        </div>
"""
    
    if signals:
        html += """
        <h2>📊 Active Trading Signals</h2>
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
                    <th>PCR</th>
                    <th>Score</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for signal in signals:
            change_class = "positive" if signal['option_change'] > 0 else "negative"
            coi_class = "positive" if signal['coi'] > 0 else "negative"
            
            html += f"""
                <tr>
                    <td><strong>{signal['symbol']}</strong></td>
                    <td><strong>{signal['signal']}</strong></td>
                    <td>{signal['option_type']}</td>
                    <td>{signal['strike_price']}</td>
                    <td>{signal['atm_strike']}</td>
                    <td>{signal['option_ltp']:.2f}</td>
                    <td class="{change_class}">{signal['option_change']:+.2f}</td>
                    <td>{signal['oi']:,.0f}</td>
                    <td class="{coi_class}">{signal['coi']:+,.0f}</td>
                    <td>{signal['iv']:.1f}</td>
                    <td>{signal['pcr_oi']}</td>
                    <td>{signal['strike_score']}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
    else:
        html += """
        <div class="signal-card">
            <h3>⏸ No Strong Signals Detected</h3>
            <p>Market is in neutral zone. Monitoring ATM ±5 strikes for opportunities...</p>
        </div>
        """
    
    if market_data:
        html += """
        <h2>📈 Market Overview</h2>
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
                strength = "🟢 Very Bullish"
            elif pcr_oi > 1.2:
                strength = "🟡 Bullish"
            elif pcr_oi < 0.6:
                strength = "🔴 Very Bearish"
            elif pcr_oi < 0.8:
                strength = "🟠 Bearish"
            else:
                strength = "⚪ Neutral"
                
            html += f"""
                <tr>
                    <td>{data['symbol']}</td>
                    <td>{data['current_price']:.2f}</td>
                    <td>{data['atm_strike']}</td>
                    <td>{data['strikes_analyzed']} strikes</td>
                    <td>{data['pcr_oi']}</td>
                    <td>{data.get('oi_ratio', 0):.2f}</td>
                    <td>{strength}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        """
    
    html += """
        <div style="text-align: center; margin-top: 20px; padding: 15px; background: white; border-radius: 5px;">
            <strong>Last Updated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | 
            <strong>Auto-refresh:</strong> Every 5 minutes
        </div>
    </div>
</body>
</html>
    """
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{PRINT_PREFIX} ✅ Dashboard generated: {out_path}")
    def main():
        print(f"{PRINT_PREFIX} 🚀 Starting Advanced Option Signal Analysis")
        print(f"{PRINT_PREFIX} ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    gen = AdvancedOptionSignalGenerator()
    signals, market_data = gen.run_complete_analysis()

    # Create output directories
    os.makedirs("output", exist_ok=True)
    os.makedirs("docs", exist_ok=True)

    # Save signals to CSV
    if signals:
        df_signals = pd.DataFrame(signals)
        df_signals.to_csv("output/option_signals.csv", index=False)
        print(f"{PRINT_PREFIX} ✅ Signals saved: output/option_signals.csv ({len(signals)} signals)")
        
        # Display summary
        print(f"{PRINT_PREFIX} 📋 SIGNAL SUMMARY:")
        for signal in signals:
            print(f"   {signal['symbol']}: {signal['signal']} {signal['option_type']} at {signal['strike_price']} (LTP: ₹{signal['option_ltp']:.2f})")
    else:
        # Create empty CSV with proper columns
        empty_df = pd.DataFrame(columns=[
            'symbol','signal','option_type','strike_price','current_price','atm_strike',
            'distance_from_atm','option_ltp','option_change','option_change_percentage',
            'oi','coi','volume','iv','delta','gamma','pcr_oi','pcr_volume',
            'oi_ratio','strike_score','selection_reason','signal_reason','timestamp'
        ])
        empty_df.to_csv("output/option_signals.csv", index=False)
        print(f"{PRINT_PREFIX} ℹ️ No signals - empty CSV created")

    # Save market data
    if market_data:
        df_market = pd.DataFrame(market_data)
        df_market.to_csv("output/detailed_option_data.csv", index=False)
        print(f"{PRINT_PREFIX} ✅ Market data saved: output/detailed_option_data.csv")

    # Generate comprehensive dashboard
    generate_advanced_dashboard(signals, market_data, out_path="docs/index.html")
    
    print(f"{PRINT_PREFIX} 🎉 Analysis completed successfully!")
    print(f"{PRINT_PREFIX} ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
     main()
