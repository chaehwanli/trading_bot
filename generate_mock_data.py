import numpy as np
import pandas as pd
from typing import List, Dict, Optional
import os
from datetime import time

class MockDataGenerator:
    def __init__(self, days: int = 252, start_price: float = 100.0, interval: str = "1d"):
        self.days = days
        self.start_price = start_price
        self.interval = interval
        
        # Calculate periods per day and total periods
        if interval == "1d":
            self.periods_per_day = 1
            self.dates = pd.date_range(start="2024-01-01", periods=days, freq="B")
        else:
            # US Market hours: 09:30 - 16:00 (6.5 hours = 390 minutes)
            if interval == "1h":
                self.periods_per_day = 7 # 09:30, 10:30, ... 15:30 (approx)
                freq = "1h"
            elif interval == "30m":
                self.periods_per_day = 13 # 390 / 30 = 13
                freq = "30min"
            elif interval == "2m":
                self.periods_per_day = 195 # 390 / 2 = 195
                freq = "2min"
            else:
                 raise ValueError(f"Unsupported interval: {interval}")
            
            # Generate Intraday Dates
            business_days = pd.date_range(start="2024-01-01", periods=days, freq="B")
            timestamps = []
            for date in business_days:
                # Create range for a single day
                day_start = date.replace(hour=9, minute=30)
                # We want exactly periods_per_day points
                day_range = pd.date_range(start=day_start, periods=self.periods_per_day, freq=freq)
                timestamps.extend(day_range)
            
            self.dates = pd.to_datetime(timestamps)

        self.total_periods = len(self.dates)

    def _generate_noise(self, volatility: float) -> np.ndarray:
        return np.random.normal(0, volatility, self.total_periods)

    def _create_ohlcv(self, close_prices: np.ndarray, volatility: float) -> pd.DataFrame:
        # Generate Open, High, Low based on Close and Volatility
        opens = close_prices * (1 + np.random.normal(0, volatility * 0.5, self.total_periods))
        highs = np.maximum(opens, close_prices) * (1 + np.abs(np.random.normal(0, volatility * 0.5, self.total_periods)))
        lows = np.minimum(opens, close_prices) * (1 - np.abs(np.random.normal(0, volatility * 0.5, self.total_periods)))
        
        # Ensure High is highest and Low is lowest
        highs = np.maximum(highs, np.maximum(opens, close_prices))
        lows = np.minimum(lows, np.minimum(opens, close_prices))
        
        # Generate Volume (random with some correlation to volatility)
        # Scale volume down for intraday
        volume_base = 1000000 / self.periods_per_day
        volumes = np.random.lognormal(mean=np.log(volume_base), sigma=0.5, size=self.total_periods)
        volumes = volumes.astype(int)

        df = pd.DataFrame({
            'date': self.dates,
            'open': np.round(opens, 2),
            'high': np.round(highs, 2),
            'low': np.round(lows, 2),
            'close': np.round(close_prices, 2),
            'volume': volumes
        })
        return df

    def calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        close = data['close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50) # Default to 50 for initial nan

    def calculate_macd(self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        close = data['close']
        exp1 = close.ewm(span=fast, adjust=False).mean()
        exp2 = close.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return {
            'macd': macd,
            'signal_line': signal_line,
            'histogram': histogram
        }

    def generate_scenario(self, scenario_type: str) -> pd.DataFrame:
        np.random.seed(42) # For reproducibility
        
        t = np.linspace(0, 1, self.total_periods)
        close_prices = np.zeros(self.total_periods)
        
        # Scale volatility based on interval square root rule approximation
        # sigma_intraday = sigma_daily / sqrt(periods_per_day)
        vol_scale = 1 / np.sqrt(self.periods_per_day)

        if scenario_type == "steady_uptrend":
            # 1. Steady Uptrend: +20%
            trend = t * 0.2
            volatility = 0.01 * vol_scale
            noise = self._generate_noise(volatility)
            close_prices = self.start_price * (1 + trend + noise)

        elif scenario_type == "steady_downtrend":
            # 2. Steady Downtrend: -20%
            trend = -t * 0.2
            volatility = 0.01 * vol_scale
            noise = self._generate_noise(volatility)
            close_prices = self.start_price * (1 + trend + noise)

        elif scenario_type == "high_volatility_sideways":
            # 3. High Volatility Sideways: +/- 5%, sigma 3-4%
            volatility = 0.035 * vol_scale
            close_prices = self.start_price * (1 + 0.05 * np.sin(t * 10) + self._generate_noise(volatility))

        elif scenario_type == "low_volatility_range_bound":
            # 4. Low Volatility Range-bound: Flat, sigma 0.5%
            volatility = 0.005 * vol_scale
            close_prices = self.start_price * (1 + self._generate_noise(volatility))

        elif scenario_type == "v_shape_recovery":
            # 5. V-shape Recovery: -30% then +30%
            mid_point = self.total_periods // 2
            trend = np.zeros(self.total_periods)
            trend[:mid_point] = np.linspace(0, -0.3, mid_point)
            trend[mid_point:] = np.linspace(-0.3, 0.1, self.total_periods - mid_point) 
            volatility = 0.015 * vol_scale
            close_prices = self.start_price * (1 + trend + self._generate_noise(volatility))

        elif scenario_type == "u_shape_recovery":
            # 6. U-shape Recovery
            trend = 0.4 * (t - 0.5)**2 - 0.1 
            volatility = 0.01 * vol_scale
            close_prices = self.start_price * (1 + trend + self._generate_noise(volatility))

        elif scenario_type == "stair_step_uptrend":
            # 7. Stair-step Uptrend
            steps = 4
            trend = np.floor(t * steps) / steps * 0.3 
            volatility = 0.008 * vol_scale
            close_prices = self.start_price * (1 + trend + self._generate_noise(volatility))

        elif scenario_type == "stair_step_downtrend":
            # 8. Stair-step Downtrend
            steps = 4
            trend = np.floor(t * steps) / steps * -0.3 
            volatility = 0.008 * vol_scale
            close_prices = self.start_price * (1 + trend + self._generate_noise(volatility))

        elif scenario_type == "bubble_crash":
            # 9. Bubble & Crash: +80% then -50%
            peak_idx = int(self.total_periods * 0.7)
            trend = np.zeros(self.total_periods)
            trend[:peak_idx] = np.linspace(0, 0.8, peak_idx) 
            trend[peak_idx:] = np.linspace(0.8, -0.2, self.total_periods - peak_idx) 
            volatility = 0.02 * vol_scale
            close_prices = self.start_price * (1 + trend + self._generate_noise(volatility))

        elif scenario_type == "event_shock":
            # 10. Event Shock
            trend = np.zeros(self.total_periods)
            shocks = [int(self.total_periods * 0.2), int(self.total_periods * 0.5), int(self.total_periods * 0.8)]
            current_shock = 0.0
            
            for i in range(self.total_periods):
                # Spread shock over a few periods for intraday smoothness if needed, but keeping it sharp for now
                if i in shocks:
                   current_shock += np.random.choice([-0.15, 0.15]) 
                trend[i] = current_shock
            
            volatility = 0.015 * vol_scale
            close_prices = self.start_price * (1 + trend + self._generate_noise(volatility))

        else:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

        df = self._create_ohlcv(close_prices, volatility)
        
        # Adding Indicators
        df['rsi'] = self.calculate_rsi(df)
        macd_data = self.calculate_macd(df)
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal_line']
        df['macd_hist'] = macd_data['histogram']
        
        df['scenario'] = scenario_type
        
        return df

def generate_all_scenarios(output_dir: str = "mock_data"):
    scenarios = [
        "steady_uptrend",
        "steady_downtrend",
        "high_volatility_sideways",
        "low_volatility_range_bound",
        "v_shape_recovery",
        "u_shape_recovery",
        "stair_step_uptrend",
        "stair_step_downtrend",
        "bubble_crash",
        "event_shock"
    ]
    
    intervals = ["2m", "30m", "1h"]
    
    for interval in intervals:
        interval_dir = os.path.join(output_dir, interval)
        if not os.path.exists(interval_dir):
            os.makedirs(interval_dir)
            
        print(f"\nGeneraring {interval} data...")
        generator = MockDataGenerator(interval=interval)
        
        for sc in scenarios:
            df = generator.generate_scenario(sc)
            filename = f"{interval_dir}/{sc}.csv"
            df.to_csv(filename, index=False)
            print(f"  Generated {filename} ({len(df)} rows)")

if __name__ == "__main__":
    generate_all_scenarios()
