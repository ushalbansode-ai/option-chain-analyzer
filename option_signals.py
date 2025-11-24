#!/usr/bin/env python3
"""
option_signals.py (updated)
- Adds 10 more stocks (20 total)
- Computes top 3 buys and top 3 sells (by score)
- Exports: docs/dashboard.json, signals/latest.json, option_signals.csv, detailed_option_data.csv
"""

import requests
import json
import csv
import os
from datetime import datetime
import time as time_module

# -----------------------
# Config - now 20 symbols
# -----------------------
SYMBOLS = [
    "NIFTY", "BANKNIFTY",
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "KOTAKBANK", "HDFC", "BHARTIARTL", "ITC", "SBIN",
    # +10 new
    "LT", "AXISBANK", "MARUTI", "HINDUNILVR", "BAJFINANCE",
    "ADANIENT", "ULTRACEMCO", "SUNPHARMA", "WIPRO", "LTI"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

def now_str(fmt="%Y-%m-%d %H:%M:%S"):
    # If you need strict IST, you could use pytz; here we use system timezone (Action runner is UTC)
    # To force IST without external libs, we can add 5.5 hours to UTC:
    from datetime import datetime, timedelta
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime(fmt)

# -----------------------
# Helper functions
# -----------------------
def safe_int(x):
    try:
        return int(x or 0)
    except:
        return 0

def safe_float(x):
    try:
        return float(x or 0)
    except:
        return 0.0

# ==================================================================
# Core engine (compact, based on your working script)
# ==================================================================
class AdvancedOptionSignalGenerator:
    def __init__(self, symbols=SYMBOLS):
        self.symbols = symbols
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "*/*"
        })

    def fetch_option_chain(self, symbol):
        try:
            # warm homepage
            self.session.get("https://www.nseindia.com", timeout=5)
        except:
            pass

        if symbol in ("NIFTY", "BANKNIFTY"):
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        else:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"

        try:
            r = self.session.get(url, timeout=12)
            if r.status_code == 200:
                return r.json()
            print(f"❌ HTTP {r.status_code} for {symbol}")
            return None
        except Exception as e:
            print(f"❌ Fetch error for {symbol}: {e}")
            return None

    def analyze_atm_strikes(self, raw):
        if not raw or "records" not in raw:
            return None
        records = raw["records"]
        underlying = records.get("underlyingValue")
        expiry_list = records.get("expiryDates", [])
        all_rows = records.get("data", []) or []
        if underlying is None or not expiry_list or not all_rows:
            return None
        expiry = expiry_list[0]
        rows_for_expiry = [r for r in all_rows if r.get("expiryDate") == expiry]
        if not rows_for_expiry:
            return None
        strikes = sorted({int(r.get("strikePrice", 0)) for r in rows_for_expiry})
        if not strikes:
            return None
        atm = min(strikes, key=lambda x: abs(x - float(underlying)))
        atm_index = strikes.index(atm)
        start = max(0, atm_index - 5)
        end = min(len(strikes), atm_index + 6)
        selected_strikes = strikes[start:end]
        filtered_rows = [r for r in rows_for_expiry if int(r.get("strikePrice", 0)) in selected_strikes]
        return {
            "symbol": raw.get("records", {}).get("underlyingValue", None),
            "underlying": float(underlying),
            "atm_strike": atm,
            "expiry": expiry,
            "strikes_analyzed": selected_strikes,
            "strike_rows": filtered_rows,
            "all_rows": rows_for_expiry
        }

    def analyze_strike_strength(self, strike_rows):
        out = []
        for r in strike_rows:
            strike = int(r.get("strikePrice", 0))
            ce = r.get("CE") or {}
            pe = r.get("PE") or {}
            ce_oi = safe_int(ce.get("openInterest"))
            pe_oi = safe_int(pe.get("openInterest"))
            ce_chg = safe_int(ce.get("changeinOpenInterest"))
            pe_chg = safe_int(pe.get("changeinOpenInterest"))
            ce_vol = safe_int(ce.get("totalTradedVolume"))
            pe_vol = safe_int(pe.get("totalTradedVolume"))
            ce_iv = safe_float(ce.get("impliedVolatility"))
            pe_iv = safe_float(pe.get("impliedVolatility"))
            ce_ltp = safe_float(ce.get("lastPrice"))
            pe_ltp = safe_float(pe.get("lastPrice"))
            out.append({
                "strike": strike,
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "ce_chg": ce_chg,
                "pe_chg": pe_chg,
                "ce_vol": ce_vol,
                "pe_vol": pe_vol,
                "ce_iv": ce_iv,
                "pe_iv": pe_iv,
                "ce_ltp": ce_ltp,
                "pe_ltp": pe_ltp,
                "ce_strength": ce_oi + ce_chg + ce_vol,
                "pe_strength": pe_oi + pe_chg + pe_vol
            })
        return out

    def select_optimal_strike(self, analysis_data, option_side):
        rows = analysis_data.get("strike_rows", [])
        strike_info = self.analyze_strike_strength(rows)
        strikes_list = analysis_data["strikes_analyzed"]
        atm = analysis_data["atm_strike"]
        try:
            atm_index = strikes_list.index(atm)
        except:
            atm_index = 0
        candidates = []
        for info in strike_info:
            strike = info["strike"]
            try:
                idx = strikes_list.index(strike)
            except:
                idx = 0
            dist = abs(idx - atm_index)
            if option_side == "CE":
                if strike < analysis_data["underlying"]:
                    continue
                score = (60 if dist == 0 else 50 if dist == 1 else max(0, 40 - dist*5))
                score += info["ce_oi"] / 10000
                score += info["ce_chg"] / 500
                score += info["ce_vol"] / 1000
                score += max(0, 5 - info["ce_iv"] / 5)
                score += 1 if info["ce_ltp"] > 0 else 0
                candidates.append({
                    "strike": strike,
                    "side": "CE",
                    "score": round(score, 2),
                    "oi": info["ce_oi"],
                    "coi": info["ce_chg"],
                    "volume": info["ce_vol"],
                    "iv": info["ce_iv"],
                    "ltp": info["ce_ltp"],
                    "distance_from_atm": dist
                })
            else:
                if strike > analysis_data["underlying"]:
                    continue
                score = (60 if dist == 0 else 50 if dist == 1 else max(0, 40 - dist*5))
                score += info["pe_oi"] / 10000
                score += info["pe_chg"] / 500
                score += info["pe_vol"] / 1000
                score += max(0, 5 - info["pe_iv"] / 5)
                score += 1 if info["pe_ltp"] > 0 else 0
                candidates.append({
                    "strike": strike,
                    "side": "PE",
                    "score": round(score, 2),
                    "oi": info["pe_oi"],
                    "coi": info["pe_chg"],
                    "volume": info["pe_vol"],
                    "iv": info["pe_iv"],
                    "ltp": info["pe_ltp"],
                    "distance_from_atm": dist
                })
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x["score"], x["volume"]), reverse=True)
        return candidates[0]

    def calculate_pcr(self, rows):
        ce_oi = pe_oi = ce_vol = pe_vol = 0
        for r in rows:
            ce = r.get("CE") or {}
            pe = r.get("PE") or {}
            ce_oi += safe_int(ce.get("openInterest"))
            pe_oi += safe_int(pe.get("openInterest"))
            ce_vol += safe_int(ce.get("totalTradedVolume"))
            pe_vol += safe_int(pe.get("totalTradedVolume"))
        pcr_oi = (pe_oi / ce_oi) if ce_oi else 0
        pcr_vol = (pe_vol / ce_vol) if ce_vol else 0
        return round(pcr_oi, 2), round(pcr_vol, 2)

    def generate_signal_from_analysis(self, analysis):
        pcr_oi, pcr_vol = self.calculate_pcr(analysis["all_rows"])
        ce_total = pe_total = 0
        for r in analysis["strike_rows"]:
            ce = r.get("CE") or {}
            pe = r.get("PE") or {}
            ce_total += safe_int(ce.get("openInterest"))
            pe_total += safe_int(pe.get("openInterest"))
        oi_ratio = (pe_total / ce_total) if ce_total else 0
        bullish = bearish = 0
        if pcr_oi > 1.4: bullish += 2
        elif pcr_oi > 1.1: bullish += 1
        if pcr_oi < 0.7: bearish += 2
        elif pcr_oi < 0.9: bearish += 1
        if oi_ratio > 1.3: bullish += 1
        elif oi_ratio < 0.7: bearish += 1
        signal = None; side = None
        if bullish >= 3:
            signal = "STRONG BUY"; side = "CE"
        elif bullish == 2:
            signal = "BUY"; side = "CE"
        elif bearish >= 3:
            signal = "STRONG SELL"; side = "PE"
        elif bearish == 2:
            signal = "SELL"; side = "PE"
        else:
            return None
        best = self.select_optimal_strike(analysis, side)
        if not best:
            return None
        return {
            "symbol": analysis.get("symbol"),
            "signal": signal,
            "option_type": side,
            "strike": best["strike"],
            "atm": analysis["atm_strike"],
            "distance_from_atm": best["distance_from_atm"],
            "ltp": best["ltp"],
            "oi": best["oi"],
            "coi": best["coi"],
            "volume": best["volume"],
            "iv": best["iv"],
            "score": best["score"],
            "pcr_oi": pcr_oi,
            "pcr_volume": pcr_vol,
            "oi_ratio": round(oi_ratio, 2),
            "timestamp": now_str()
        }

    def run_all(self):
        all_signals = []
        dashboard_data = []
        detailed_rows = []
        for sym in self.symbols:
            print(f"\n🔍 Processing {sym}")
            raw = self.fetch_option_chain(sym)
            if not raw:
                print(f"❌ No data for {sym}")
                continue
            analysis = self.analyze_atm_strikes(raw)
            if not analysis:
                print(f"❌ ATM analysis error for {sym}")
                continue
            analysis["symbol"] = sym
            sig = self.generate_signal_from_analysis(analysis)
            if sig:
                all_signals.append(sig)
                print(f"   ✅ Signal {sig['signal']} @ {sig['strike']}")
            else:
                print(f"   ⏸ No strong signal for {sym}")
            dashboard_data.append({
                "symbol": sym,
                "current_price": analysis["underlying"],
                "atm_strike": analysis["atm_strike"],
                "strikes_analyzed": analysis["strikes_analyzed"],
                "signal": sig["signal"] if sig else None,
                "timestamp": now_str()
            })
            for s in self.analyze_strike_strength(analysis["strike_rows"]):
                detailed_rows.append({
                    "symbol": sym,
                    **s
                })
            time_module.sleep(0.6)

        # Save CSVs
        self.save_csv("option_signals.csv", all_signals)
        self.save_csv("detailed_option_data.csv", detailed_rows)

        # Build final JSON and pick top 3 buys/sells
        final_json = {
            "last_updated": now_str(),
            "signals": all_signals,
            "market": [
                {
                    "symbol": d["symbol"],
                    "price": d["current_price"],
                    "atm": d["atm_strike"],
                    "strikes": len(d["strikes_analyzed"]),
                    "updated": d["timestamp"]
                }
                for d in dashboard_data
            ]
        }

        # top buys (BUY or STRONG BUY) and top sells (SELL or STRONG SELL) by score
        buy_candidates = [s for s in all_signals if "BUY" in s["signal"]]
        sell_candidates = [s for s in all_signals if "SELL" in s["signal"]]

        buy_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        sell_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

        final_json["top_buy"] = buy_candidates[:3]
        final_json["top_sell"] = sell_candidates[:3]

        # Save JSON for GitHub Pages and latest signals
        self.save_json("docs/dashboard.json", final_json)
        os.makedirs("signals", exist_ok=True)
        self.save_json("signals/latest.json", all_signals)

        print("\n✅ Completed.")
        return all_signals

    def save_csv(self, filename, rows):
        try:
            keys = set()
            for r in rows:
                keys.update(r.keys())
            keys = list(keys)
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            print(f"📄 Saved CSV: {filename}")
        except Exception as e:
            print(f"❌ CSV error {e}")

    def save_json(self, filename, data):
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"🟢 JSON saved: {filename}")
        except Exception as e:
            print(f"❌ JSON error {filename}: {e}")

# ==================================================================
# MAIN
# ==================================================================
def main():
    print("\n🔵 Starting NSE Option Signals…")
    engine = AdvancedOptionSignalGenerator()
    engine.run_all()
    print("🔚 Done.")

if __name__ == "__main__":
    main()
  
