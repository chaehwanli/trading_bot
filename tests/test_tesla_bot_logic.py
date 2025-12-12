import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime, timedelta
import pytz

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tesla_reversal_trading_bot import TeslaReversalTradingBot

class TestTeslaBotLogic(unittest.TestCase):
    @patch('tesla_reversal_trading_bot.KisApi')
    @patch('tesla_reversal_trading_bot.DataFetcher')
    def setUp(self, mock_data_fetcher, mock_kis_api):
        self.bot = TeslaReversalTradingBot()
        # Disable scheduler for unit tests
        self.bot.scheduler = MagicMock()
        self.bot.kis = mock_kis_api.return_value
        self.bot.data_fetcher = mock_data_fetcher.return_value

    def test_is_dst(self):
        eastern = pytz.timezone('US/Eastern')
        
        # Winter date
        with patch('tesla_reversal_trading_bot.datetime') as mock_datetime:
            # We must return a datetime that behaves like now(tz)
            # US/Eastern in Winter (Jan 1)
            winter_dt = eastern.localize(datetime(2024, 1, 1, 12, 0))
            mock_datetime.now.return_value = winter_dt
            self.assertFalse(self.bot._is_dst())
            
        # Summer date
        with patch('tesla_reversal_trading_bot.datetime') as mock_datetime:
            # US/Eastern in Summer (Jul 1)
            summer_dt = eastern.localize(datetime(2024, 7, 1, 12, 0))
            mock_datetime.now.return_value = summer_dt
            self.assertTrue(self.bot._is_dst())

    def test_market_status_winter(self):
        # Mock _is_dst to False (Winter)
        with patch.object(self.bot, '_is_dst', return_value=False):
            with patch('tesla_reversal_trading_bot.datetime') as mock_datetime:
                # 10:00 -> DAYTIME
                mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 30)
                self.assertEqual(self.bot._get_market_status(), "DAYTIME")
                
                # 18:00 -> PREMARKET
                mock_datetime.now.return_value = datetime(2024, 1, 1, 18, 0)
                self.assertEqual(self.bot._get_market_status(), "PREMARKET")
                
                # 00:00 -> REGULAR (Next day technically, but checking hour ranges)
                mock_datetime.now.return_value = datetime(2024, 1, 1, 0, 0)
                self.assertEqual(self.bot._get_market_status(), "REGULAR")

    def test_market_status_summer(self):
        # Mock _is_dst to True (Summer)
        with patch.object(self.bot, '_is_dst', return_value=True):
            with patch('tesla_reversal_trading_bot.datetime') as mock_datetime:
                # 10:00 -> DAYTIME
                mock_datetime.now.return_value = datetime(2024, 7, 1, 10, 30)
                self.assertEqual(self.bot._get_market_status(), "DAYTIME")
                
                # 17:00 -> PREMARKET
                mock_datetime.now.return_value = datetime(2024, 7, 1, 17, 0)
                self.assertEqual(self.bot._get_market_status(), "PREMARKET")
                
                # 22:30 -> PREMARKET (Wait, 17:00 ~ 22:30 is Premarket)
                # 22:30 exact should be REGULAR start? 
                # According to my implementation: 
                # if 1020 <= curr_min < 1350: return "PREMARKET" (17:00=1020, 22:30=1350)
                # So 22:30 is REGULAR.
                mock_datetime.now.return_value = datetime(2024, 7, 1, 22, 30)
                self.assertEqual(self.bot._get_market_status(), "REGULAR")

    def test_position_limit_short(self):
        # Setup SHORT position held for 25 hours
        self.bot.strategy.current_position = "SHORT"
        self.bot.strategy.current_etf_symbol = "TSLZ"
        self.bot.strategy.entry_time = datetime.now() - timedelta(hours=25)
        self.bot.etf_short_multiple = "-2"
        
        # Mock strategy check to NOT trigger stop loss
        self.bot.strategy.check_stop_loss_take_profit2 = MagicMock(return_value=None)
        self.bot.strategy.check_max_drawdown = MagicMock(return_value=False)
        self.bot._get_current_price = MagicMock(return_value=100.0)
        self.bot._close_position = MagicMock()
        
        self.bot.monitor_position()
        
        # Should call close position with FORCE_CLOSE_TIME_LIMIT
        self.bot._close_position.assert_called_with(100.0, "FORCE_CLOSE_TIME_LIMIT")

    def test_position_limit_long(self):
        # Setup LONG position held for 40 hours (Should NOT close)
        self.bot.strategy.current_position = "LONG"
        self.bot.strategy.current_etf_symbol = "TSLL"
        self.bot.strategy.entry_time = datetime.now() - timedelta(hours=40)
        self.bot.etf_long_multiple = "2"
        
        self.bot.strategy.check_stop_loss_take_profit2 = MagicMock(return_value=None)
        self.bot.strategy.check_max_drawdown = MagicMock(return_value=False)
        self.bot._get_current_price = MagicMock(return_value=100.0)
        self.bot._close_position = MagicMock()
        
        self.bot.monitor_position()
        self.bot._close_position.assert_not_called()
        
        # Setup LONG position held for 49 hours (Should close)
        self.bot.strategy.entry_time = datetime.now() - timedelta(hours=49)
        self.bot.monitor_position()
        self.bot._close_position.assert_called_with(100.0, "FORCE_CLOSE_TIME_LIMIT")

    def test_stop_loss_no_reversal(self):
        # Setup Stop Loss condition
        self.bot.strategy.current_position = "LONG"
        self.bot.strategy.current_etf_symbol = "TSLL"
        self.bot.strategy.entry_time = datetime.now()
        self.bot.etf_long_multiple = "2"
        
        self.bot.strategy.check_stop_loss_take_profit2 = MagicMock(return_value="STOP_LOSS")
        self.bot._get_current_price = MagicMock(return_value=100.0)
        self.bot._execute_reversal = MagicMock()
        self.bot._close_position = MagicMock()
        
        self.bot.monitor_position()
        
        # Should Call _close_position, NOT _execute_reversal
        self.bot._close_position.assert_called_with(100.0, "STOP_LOSS")
        self.bot._execute_reversal.assert_not_called()

if __name__ == '__main__':
    unittest.main()
