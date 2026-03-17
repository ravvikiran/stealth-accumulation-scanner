"""
Data Ingestion Layer for Stealth Accumulation Scanner
Fetches OHLCV and delivery data from NSE/Yahoo Finance
"""

import pandas as pd
import numpy as np
import requests
import yfinance as yf
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import time
import os

logger = logging.getLogger(__name__)


class NSEDataFetcher:
    """
    Fetches data from NSE India and Yahoo Finance
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.session = requests.Session()
        self.yahoo_base = config.get('yahoo', {}).get('base_url', 'https://query1.finance.yahoo.com')
        
    def get_stock_data(
        self, 
        symbol: str, 
        period: str = "1y",
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data for a stock
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE.NS')
            period: Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo)
            
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        try:
            # Add .NS suffix for NSE stocks
            if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                ticker = f"{symbol}.NS"
            else:
                ticker = symbol
                
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            
            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return None
                
            # Rename columns to lowercase
            df.columns = [col.lower() for col in df.columns]
            
            # Add symbol column
            df['symbol'] = symbol
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_delivery_data(
        self, 
        symbol: str, 
        days: int = 20
    ) -> Optional[pd.DataFrame]:
        """
        Fetch delivery percentage data from NSE
        
        Args:
            symbol: Stock symbol
            days: Number of days to fetch
            
        Returns:
            DataFrame with delivery data or None if failed
        """
        try:
            # NSE delivery data endpoint
            url = f"https://www.nseindia.com/api/historyBySymbol?symbol={symbol}&series=EQ"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                # Fallback: try to get delivery from Yahoo
                return self._get_delivery_from_yahoo(symbol, days)
                
            data = response.json()
            
            if 'data' not in data:
                return self._get_delivery_from_yahoo(symbol, days)
                
            records = []
            for item in data.get('data', [])[-days:]:
                records.append({
                    'date': pd.to_datetime(item.get('mTIMESTAMP')),
                    'symbol': symbol,
                    'delivery_pct': float(item.get('DELIVERYPERCENTAGE', 0)),
                    'volume': int(item.get('TOTALTRADEDQUANTITY', 0)),
                    'turnover': float(item.get('TURNOVER', 0))
                })
                
            if records:
                return pd.DataFrame(records)
                
            return self._get_delivery_from_yahoo(symbol, days)
            
        except Exception as e:
            logger.warning(f"NSE delivery fetch failed for {symbol}, using Yahoo: {str(e)}")
            return self._get_delivery_from_yahoo(symbol, days)
    
    def _get_delivery_from_yahoo(
        self, 
        symbol: str, 
        days: int = 20
    ) -> Optional[pd.DataFrame]:
        """
        Fallback: Estimate delivery data from Yahoo Finance
        Yahoo doesn't directly provide delivery %, so we estimate from volume patterns
        """
        try:
            # For Indian stocks, we'll use a simpler approach
            # In production, you might want to use a paid API
            df = self.get_stock_data(symbol, period=f"{days}d", interval="1d")
            
            if df is None or df.empty:
                return None
                
            # Create delivery estimation based on volume stability
            # This is a rough estimate - actual delivery data would require NSE API
            df_delivery = df[['volume']].copy()
            df_delivery['date'] = df.index
            df_delivery['symbol'] = symbol
            
            # Estimate delivery % based on volume stability
            # Higher consistency in volume = higher delivery
            # This is an estimation - actual delivery requires NSE API
            volume_std = df['volume'].std()
            volume_mean = df['volume'].mean()
            cv = volume_std / volume_mean if volume_mean > 0 else 1  # Coefficient of variation
            
            # Lower CV = higher delivery % (more stable trading)
            # Typical delivery in India is 40-70%
            base_delivery = 55
            if cv < 0.3:
                delivery_estimate = base_delivery + 10  # ~65%
            elif cv < 0.5:
                delivery_estimate = base_delivery + 5  # ~60%
            else:
                delivery_estimate = base_delivery - 5  # ~50%
            
            df_delivery['delivery_pct'] = delivery_estimate
            
            return df_delivery[['date', 'symbol', 'delivery_pct', 'volume']]
            
        except Exception as e:
            logger.error(f"Error getting delivery data for {symbol}: {str(e)}")
            return None
    
    def get_index_data(
        self, 
        index_symbol: str = "^NSEI",
        period: str = "3mo",
        interval: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch index data for relative strength calculation
        
        Args:
            index_symbol: Index symbol (^NSEI for Nifty 50)
            period: Data period
            interval: Data interval
            
        Returns:
            DataFrame with index OHLCV data
        """
        # Try different index symbols for Nifty 50
        symbols_to_try = ["^NSEI", "^NIFTY", "NIFTY 50"]
        
        for symbol in symbols_to_try:
            df = self.get_stock_data(symbol, period, interval)
            if df is not None and not df.empty:
                return df
        
        # If all fail, return None - relative strength won't be calculated
        return None
    
    def get_stock_info(self, symbol: str) -> Optional[Dict]:
        """
        Get stock metadata (market cap, volume, etc.)
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with stock info
        """
        try:
            if not symbol.endswith('.NS') and not symbol.endswith('.BO'):
                ticker = f"{symbol}.NS"
            else:
                ticker = symbol
                
            stock = yf.Ticker(ticker)
            info = stock.info
            
            return {
                'symbol': symbol,
                'name': info.get('longName', info.get('shortName', symbol)),
                'market_cap': info.get('marketCap'),
                'avg_volume': info.get('averageVolume'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'pe_ratio': info.get('trailingPE'),
                '52w_high': info.get('fiftyTwoWeekHigh'),
                '52w_low': info.get('fiftyTwoWeekLow'),
            }
            
        except Exception as e:
            logger.error(f"Error getting stock info for {symbol}: {str(e)}")
            return None


class StockUniverse:
    """
    Defines and filters the stock universe
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.universe_config = config.get('scanner', {}).get('universe', {})
        
    def get_nse_stocks(self) -> List[str]:
        """
        Get list of NSE stocks to scan
        
        Returns:
            List of stock symbols
        """
        # List of actively traded NSE stocks with correct Yahoo Finance symbols
        # Large cap and mid-cap stocks that are actively traded
        nse_stocks = [
            # Large Cap - Using correct Yahoo Finance symbols
            'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'HINDUNILVR', 
            'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'AXISBANK', 'HDFC',
            'ASIANPAINT', 'MARUTI', 'TITAN', 'BAJFINANCE', 'SUNPHARMA', 'NESTLEIND',
            'WIPRO', 'ULTRACEMCO', 'ADANIPORTS', 'POWERGRID', 'NTPC',
            'M&M', 'BAJAJFINSV', 'INDUSINDBK', 'CIPLA', 'ADANIENT', 'GRASIM',
            'HCLTECH', 'DIVISLAB', 'TATASTEEL', 'COALINDIA', 'VEDL', 'ONGC',
            'JSWSTEEL', 'BPCL', 'IOC', 'SHREECEM', 'SBILIFE', 'DRREDDY', 'EICHERMOT',
            'APOLLOHOSP', 'TECHM', 'HEROMOTOCO', 'TATACONSUM',
            'UPL', 'SHRIRAMFIN', 'TVSMOTOR', 'PIDILITIND',
            # Mid Cap
            'DABUR', 'GODREJCP', 'MARICO', 'TATAPOWER', 'ADANIGREEN',
            'DMART', 'DELHIVERY', 'HAL', 'BEL',
            'MUTHOOTFIN', 'AUROPHARMA', 'SRF', 'ALKEM', 'MAXHEALTH',
            'LUPIN', 'APOLLOTYRE', 'BANDHANBNK', 'CANBK', 'PNB',
            'UNIONBANK', 'IOB', 'RBLBANK', 'FEDERALBNK',
            # Additional stocks
            'JINDALSTEL', 'SAIL', 'NMDC', 'HINDZINC', 'ACC', 'AMBUJCEM',
            'RAMCOCEM', 'WHIRLPOOL', 'VOLTAS', 'SYMPHONY', 'KRBL',
            'PRAJIND', 'CONCOR', 'ALLCARGO', 'GICRE',
            'CDSL', 'CAMS', 'POLYCAB', 'KEI', 'FINCABLES',
            # New listings and others
            'LIC', 'ZOMATO', 'PAYTM', 'MINDTREE',
        ]
        
        return nse_stocks
    
    def filter_by_criteria(
        self, 
        stocks: List[str],
        fetcher: NSEDataFetcher,
        min_market_cap: float = None,
        min_volume: int = None
    ) -> List[str]:
        """
        Filter stocks by market cap and volume criteria
        
        Args:
            stocks: List of stock symbols
            fetcher: Data fetcher instance
            min_market_cap: Minimum market cap in Cr (default from config)
            min_volume: Minimum average volume (default from config)
            
        Returns:
            Filtered list of stocks
        """
        if min_market_cap is None:
            min_market_cap = self.universe_config.get('min_market_cap_cr', 500)
            
        if min_volume is None:
            min_volume = self.universe_config.get('min_avg_volume', 200000)
            
        filtered = []
        
        for symbol in stocks:
            try:
                info = fetcher.get_stock_info(symbol)
                
                if info is None:
                    continue
                    
                # Check market cap (convert to Cr)
                market_cap = info.get('market_cap', 0)
                if market_cap:
                    market_cap_cr = market_cap / 1e7  # Convert to Cr
                    if market_cap_cr < min_market_cap:
                        continue
                        
                # Check average volume
                avg_volume = info.get('avg_volume', 0)
                if avg_volume and avg_volume < min_volume:
                    continue
                    
                filtered.append(symbol)
                
            except Exception as e:
                logger.warning(f"Error filtering {symbol}: {str(e)}")
                continue
                
        logger.info(f"Filtered {len(filtered)} stocks from {len(stocks)}")
        return filtered


def load_config(config_path: str = "config.yaml") -> Dict:
    """
    Load configuration from YAML file
    
    Args:
        config_path: Path to config file
        
    Returns:
        Configuration dictionary
    """
    import yaml
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return {}
