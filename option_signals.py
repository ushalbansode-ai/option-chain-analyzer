#!/usr/bin/env python3
"""
option_signals.py  —  Optimized final version (Option B)

Outputs:
 - docs/dashboard.json
 - signals/latest.json
 - option_signals.csv
 - detailed_option_data.csv

Notes:
 - Timestamps are forced to IST (UTC +5:30) without external dependencies.
 - Request retries and safe parsing added.
 - Produces "top_buy" and "top_sell" arrays in dashboard JSON.
"""

import requests
import json
import csv
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# -------------------------
# CONFIG
# -------------------------
SYMBOLS = [
    # core indices + original 10
    "NIFTY", "BANKNIFTY",
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "KOTAKBANK", "HDFC", "BHARTIARTL", "ITC", "SBIN",
    # +10 new (now 20 total)
    "LT", "AXISBANK", "MARUTI", "HINDUNILVR", "BAJFINANCE",
    "ADANIENT", "ULTRACEMCO", "SUNPHARMA", "WIPRO", "LTI"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
REQUEST_TIMEOUT = 12
RETRY_ATTEMPTS = 3
SLEEP_BETWEEN_SYMBOLS = 0.6
MIN_VOLUME_FOR_LIQUID = 200  # example threshold (unused in core logic but available)

# -------------------------
# UTILITIES
# -------------------------
def now_ist_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Return current time as IST string (UTC +5:30)."""
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime(fmt)

def safe_int(x) -> int:
    try:
        return int(x or 0)
    except Exception:
        return 0

def safe_float(x) -> float:
    try:
        return float(x or 0.0)
    except Exception:
        return 0.0

def ensure_dir_for_file(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

# -------------------------
# ENGINE
# -------------------------
class OptimizedOptionSignals:
    def __init__(self, symbols: List[str] = SYMBOLS):
        self.symbols = symbols
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "*/*"
        })

    # ---------- network ----------
    def _get_json_with_retries(self, url: str) -> Optional[Dict[str, Any]]:
        """GET JSON with simple retry/backoff; returns parsed JSON or None."""
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                # warm homepage first (some NSE endpoints require it)
                if "nseindia.com" in url and attempt == 1:
                    try:
                        self.session.get("https://www.nseindia.com", timeout=5)
                    except Exception:
                        # ignore warming failure
                        pass
                resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as e:
                        print(f"[WARN] JSON decode error for {url}: {e}")
                        return None
                else:
                    print(f"[WARN] Status {resp.status_code} for {url}")
            except Exception as e:
                print(f"[WARN] Request error (attempt {attempt}) for {url}: {e}")
            # backoff
            time.sleep(1.0 * attempt)
        return None

    def fetch_option_chain(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch option chain from NSE for index/equity symbol."""
        if symbol in ("NIFTY", "BANKNIFTY"):
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        else:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"
        return self._get_json_with_retries(url)

    # ---------- parsing & analysis ----------
    def analyze_atm_window(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Given raw option-chain JSON, return structured ATM-window analysis:
        {
          "underlying": float,
          "atm_strike": int,
          "expiry": "YYYY-MM-DD",
          "strikes_analyzed": [..],
          "strike_rows": [..],  # filtered rows for expiry & strikes
          "all_rows": [..]      # all rows for chosen expiry
        }
        """
        if not raw or "records" not in raw:
            return None
        records = raw["records"]
        underlying = records.get("underlyingValue")
        expiry_dates = records.get("expiryDates") or []
        all_rows = records.get("data") or []
        if underlying is None or not expiry_dates or not all_rows:
            return None
        # choose nearest expiry (first)
        expiry = expiry_dates[0]
        rows_for_expiry = [r for r in all_rows if r.get("expiryDate") == expiry]
        if not rows_for_expiry:
            return None
        # build list of unique strikes (int)
        strikes = sorted({safe_int(r.get("strikePrice")) for r in rows_for_expiry})
        if not strikes:
            return None
        atm = min(strikes, key=lambda s: abs(s - float(underlying)))
        atm_index = strikes.index(atm)
        start = max(0, atm_index - 5)
        end = min(len(strikes), atm_index + 6)
        selected = strikes[start:end]
        filtered_rows = [r for r in rows_for_expiry if safe_int(r.get("strikePrice")) in selected]
        return {
            "underlying": float(underlying),
            "atm_strike": atm,
            "expiry": expiry,
            "strikes_analyzed": selected,
            "strike_rows": filtered_rows,
            "all_rows": rows_for_expiry
        }

    def _strike_summary(self, strike_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert raw strike rows into numeric summaries for CE & PE."""
        out = []
        for r in strike_rows:
            strike = safe_int(r.get("strikePrice"))
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
                "ce_oi": ce_oi, "pe_oi": pe_oi,
                "ce_chg": ce_chg, "pe_chg": pe_chg,
                "ce_vol": ce_vol, "pe_vol": pe_vol,
                "ce_iv": ce_iv, "pe_iv": pe_iv,
                "ce_ltp": ce_ltp, "pe_ltp": pe_ltp,
                "ce_strength": ce_oi + ce_chg + ce_vol,
                "pe_strength": pe_oi + pe_chg + pe_vol
            })
        return out

    def select_optimal_strike(self, analysis: Dict[str, Any], side: str) -> Optional[Dict[str, Any]]:
        """
        Choose an optimal strike for CE or PE from the analysis window.
        Returns dict with strike info and computed score.
        """
        strike_rows = analysis.get("strike_rows", [])
        if not strike_rows:
            return None
        strike_info = self._strike_summary(strike_rows)
        strikes_list = analysis.get("strikes_analyzed", [])
        atm = analysis.get("atm_strike")
        try:
            atm_index = strikes_list.index(atm)
        except Exception:
            atm_index = 0

        candidates = []
        for info in strike_info:
            strike = info["strike"]
            try:
                idx = strikes_list.index(strike)
            except Exception:
                idx = 0
            dist = abs(idx - atm_index)
            if side == "CE":
                # require strike >= underlying for call OTM/ATM
                if strike < analysis["underlying"]:
                    continue
                score = 60 if dist == 0 else 50 if dist == 1 else max(0, 40 - dist * 5)
                score += info["ce_oi"] / 10000
                score += info["ce_chg"] / 500
                score += info["ce_vol"] / 1000
                score += max(0, 5 - info["ce_iv"] / 5)
                score += 1 if info["ce_ltp"] > 0 else 0
                candidates.append({
                    "strike": strike, "side": "CE", "score": round(score, 2),
                    "oi": info["ce_oi"], "coi": info["ce_chg"], "volume": info["ce_vol"],
                    "iv": info["ce_iv"], "ltp": info["ce_ltp"], "distance_from_atm": dist
                })
            else:
                # PE side: require strike <= underlying
                if strike > analysis["underlying"]:
                    continue
                score = 60 if dist == 0 else 50 if dist == 1 else max(0, 40 - dist * 5)
                score += info["pe_oi"] / 10000
                score += info["pe_chg"] / 500
                score += info["pe_vol"] / 1000
                score += max(0, 5 - info["pe_iv"] / 5)
                score += 1 if info["pe_ltp"] > 0 else 0
                candidates.append({
                    "strike": strike, "side": "PE", "score": round(score, 2),
                    "oi": info["pe_oi"], "coi": info["pe_chg"], "volume": info["pe_vol"],
                    "iv": info["pe_iv"], "ltp": info["pe_ltp"], "distance_from_atm": dist
                })

        if not candidates:
            return None
        # rank by score then volume
        candidates.sort(key=lambda x: (x["score"], x["volume"]), reverse=True)
        return candidates[0]

    def calculate_pcr(self, rows: List[Dict[str, Any]]):
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

    def generate_signal_for_analysis(self, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Combines PCR, OI ratios, scoring to signal BUY/SELL/STRONG variants."""
        if not analysis:
            return None
        pcr_oi, pcr_vol = self.calculate_pcr(analysis.get("all_rows", []))
        # sum OI in window
        total_ce = total_pe = 0
        for r in analysis.get("strike_rows", []):
            total_ce += safe_int((r.get("CE") or {}).get("openInterest"))
            total_pe += safe_int((r.get("PE") or {}).get("openInterest"))
        oi_ratio = (total_pe / total_ce) if total_ce else 0

        bullish = bearish = 0
        if pcr_oi >= 1.5: bullish += 2
        elif pcr_oi >= 1.2: bullish += 1
        if pcr_oi <= 0.6: bearish += 2
        elif pcr_oi <= 0.8: bearish += 1

        if oi_ratio >= 1.3: bullish += 1
        elif oi_ratio <= 0.7: bearish += 1

        # finalize label
        label = None; side = None
        if bullish >= 3:
            label = "STRONG BUY"; side = "CE"
        elif bullish >= 2:
            label = "BUY"; side = "CE"
        elif bearish >= 3:
            label = "STRONG SELL"; side = "PE"
        elif bearish >= 2:
            label = "SELL"; side = "PE"
        else:
            return None  # neutral

        best = self.select_optimal_strike(analysis, side)
        if not best:
            # fallback try other side
            alt = "PE" if side == "CE" else "CE"
            best = self.select_optimal_strike(analysis, alt)
            if best:
                side = alt
            else:
                return None

        return {
            "symbol": None,  # set by caller
            "signal": label,
            "option_type": side,
            "strike": best["strike"],
            "atm": analysis.get("atm_strike"),
            "distance_from_atm": best.get("distance_from_atm"),
            "ltp": best.get("ltp"),
            "oi": best.get("oi"),
            "coi": best.get("coi"),
            "volume": best.get("volume"),
            "iv": best.get("iv"),
            "score": best.get("score"),
            "pcr_oi": pcr_oi,
            "pcr_volume": pcr_vol,
            "oi_ratio": round(oi_ratio, 2),
            "timestamp": now_ist_str()
        }

    # ---------- run ----------
    def run_all(self) -> Dict[str, Any]:
        all_signals = []
        dashboard_rows = []
        detailed_rows = []

        for sym in self.symbols:
            print(f"[{now_ist_str('%H:%M:%S')}] Processing {sym} ...")
            raw = self.fetch_option_chain(sym)
            if not raw:
                print(f"  ❌ Failed to fetch {sym}")
                continue

            analysis = self.analyze_atm_window(raw)
            if not analysis:
                print(f"  ❌ No analysis window for {sym}")
                continue

            # attach symbol so internal functions can fill properly
            analysis["symbol"] = sym

            sig = self.generate_signal_for_analysis(analysis)
            if sig:
                sig["symbol"] = sym
                all_signals.append(sig)
                print(f"  ✅ {sig['signal']} {sig['option_type']} @ {sig['strike']}  score={sig['score']}")
            else:
                print(f"  ⏸ No strong signal for {sym}")

            # dashboard row
            dashboard_rows.append({
                "symbol": sym,
                "price": analysis.get("underlying"),
                "atm": analysis.get("atm_strike"),
                "strikes": len(analysis.get("strikes_analyzed", [])),
                "updated": now_ist_str("%Y-%m-%d %H:%M:%S")
            })

            # detailed strike rows
            for s in self._strike_summary(analysis.get("strike_rows", [])):
                detailed_rows.append({"symbol": sym, **s})

            # polite wait
            time.sleep(SLEEP_BETWEEN_SYMBOLS)

        # persist CSVs
        self._save_csv("option_signals.csv", all_signals)
        self._save_csv("detailed_option_data.csv", detailed_rows)

        # build final JSON (structure matches your index.html usage)
        final = {
            "last_updated": now_ist_str("%Y-%m-%d %H:%M:%S"),
            "signals": all_signals,
            "market": dashboard_rows
        }

        # top 3 buys and sells by score
        buys = [s for s in all_signals if "BUY" in s["signal"]]
        sells = [s for s in all_signals if "SELL" in s["signal"]]
        buys.sort(key=lambda x: x.get("score", 0), reverse=True)
        sells.sort(key=lambda x: x.get("score", 0), reverse=True)
        final["top_buy"] = buys[:3]
        final["top_sell"] = sells[:3]

        # save JSON outputs
        self._save_json("docs/dashboard.json", final)
        ensure_dir_for_file("signals/latest.json")
        self._save_json("signals/latest.json", all_signals)

        print(f"\n[{now_ist_str('%H:%M:%S')}] Completed. Signals generated: {len(all_signals)}")
        return final

    # ---------- persistence ----------
    def _save_csv(self, filename: str, rows: List[Dict[str, Any]]):
        try:
            ensure_dir_for_file(filename)
            if not rows:
                # create empty header if no rows
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    f.write("")  # blank file
                print(f"[INFO] CSV saved (empty): {filename}")
                return
            # unify keys
            keys = set()
            for r in rows:
                keys.update(r.keys())
            keys = list(keys)
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            print(f"[INFO] CSV saved: {filename} ({len(rows)} rows)")
        except Exception as e:
            print(f"[ERROR] CSV save failed {filename}: {e}")

    def _save_json(self, filename: str, data: Any):
        try:
            ensure_dir_for_file(filename)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            print(f"[INFO] JSON saved: {filename}")
        except Exception as e:
            print(f"[ERROR] JSON save failed {filename}: {e}")

# -------------------------
# CLI runner
# -------------------------
def main():
    print(f"[{now_ist_str('%Y-%m-%d %H:%M:%S')}] Starting optimized option signals run...")
    engine = OptimizedOptionSignals()
    final = engine.run_all()
    print(f"[{now_ist_str('%Y-%m-%d %H:%M:%S')}] Exiting.")

if __name__ == "__main__":
    main()
            
