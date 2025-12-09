"""
Option Chain Analyzer Module
Core analysis logic for option chain data
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import AnalysisConfig


class OptionChainAnalyzer:
    """
    Analyzes option chain data and calculates key metrics
    """
    
    @staticmethod
    def parse_option_data(raw_data: Dict) -> pd.DataFrame:
        """Parse raw NSE option chain data into DataFrame"""
        if not raw_data or 'records' not in raw_data:
            return pd.DataFrame()
        
        records = raw_data['records']['data']
        parsed_data = []
        
        for record in records:
            strike = record.get('strikePrice', 0)
            
            row = {
                'strike': strike,
                'expiryDate': record.get('expiryDate', ''),
            }
            
            # Call data
            if 'CE' in record:
                ce = record['CE']
                row.update({
                    'CE_OI': ce.get('openInterest', 0),
                    'CE_changeInOI': ce.get('changeinOpenInterest', 0),
                    'CE_volume': ce.get('totalTradedVolume', 0),
                    'CE_IV': ce.get('impliedVolatility', 0),
                    'CE_LTP': ce.get('lastPrice', 0),
                    'CE_bid': ce.get('bidprice', 0),
                    'CE_ask': ce.get('askPrice', 0),
                })
            
            # Put data
            if 'PE' in record:
                pe = record['PE']
                row.update({
                    'PE_OI': pe.get('openInterest', 0),
                    'PE_changeInOI': pe.get('changeinOpenInterest', 0),
                    'PE_volume': pe.get('totalTradedVolume', 0),
                    'PE_IV': pe.get('impliedVolatility', 0),
                    'PE_LTP': pe.get('lastPrice', 0),
                    'PE_bid': pe.get('bidprice', 0),
                    'PE_ask': pe.get('askPrice', 0),
                })
            
            parsed_data.append(row)
        
        df = pd.DataFrame(parsed_data)
        df = df.fillna(0)
        return df
    
    @staticmethod
    def calculate_pcr(df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate Put-Call Ratio (PCR)"""
        total_call_oi = df['CE_OI'].sum()
        total_put_oi = df['PE_OI'].sum()
        pcr_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
        
        total_call_vol = df['CE_volume'].sum()
        total_put_vol = df['PE_volume'].sum()
        pcr_vol = total_put_vol / total_call_vol if total_call_vol > 0 else 0
        
        return round(pcr_oi, 3), round(pcr_vol, 3)
    
    @staticmethod
    def calculate_max_pain(df: pd.DataFrame) -> int:
        """Calculate Max Pain strike"""
        strikes = df['strike'].unique()
        min_pain = float('inf')
        max_pain_strike = 0
        
        for strike in strikes:
            total_pain = 0
            
            call_pain = df[df['strike'] < strike].apply(
                lambda x: (strike - x['strike']) * x['CE_OI'], axis=1
            ).sum()
            
            put_pain = df[df['strike'] > strike].apply(
                lambda x: (x['strike'] - strike) * x['PE_OI'], axis=1
            ).sum()
            
            total_pain = call_pain + put_pain
            
            if total_pain < min_pain:
                min_pain = total_pain
                max_pain_strike = strike
        
        return int(max_pain_strike)
    
    @staticmethod
    def analyze_oi_changes(df: pd.DataFrame) -> Dict:
        """Analyze Open Interest changes"""
        call_oi_increase = df[df['CE_changeInOI'] > 0]['CE_changeInOI'].sum()
        call_oi_decrease = abs(df[df['CE_changeInOI'] < 0]['CE_changeInOI'].sum())
        
        put_oi_increase = df[df['PE_changeInOI'] > 0]['PE_changeInOI'].sum()
        put_oi_decrease = abs(df[df['PE_changeInOI'] < 0]['PE_changeInOI'].sum())
        
        return {
            'call_build': call_oi_increase > call_oi_decrease,
            'put_build': put_oi_increase > put_oi_decrease,
            'net_call_change': call_oi_increase - call_oi_decrease,
            'net_put_change': put_oi_increase - put_oi_decrease,
        }


if __name__ == "__main__":
    print("Analyzer module loaded successfully")
