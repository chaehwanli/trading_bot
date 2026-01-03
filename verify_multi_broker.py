import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trading.brokers.factory import get_broker
from trading.brokers.kis import KisBroker
from trading.brokers.kiwoom import KiwoomBroker
from config import settings

def test_broker_loading():
    print("Testing Broker Loading...")
    
    # Test Default (KIS) or whatever is in .env
    print(f"Current BROKER_TYPE in settings: {settings.BROKER_TYPE}")
    broker = get_broker()
    print(f"Loaded Broker Type: {type(broker)}")
    
    # Test Force Kiwoom
    print("\n[Mocking BROKER_TYPE = KIWOOM]")
    settings.BROKER_TYPE = "KIWOOM"
    broker_kiwoom = get_broker()
    print(f"Loaded Broker Type: {type(broker_kiwoom)}")
    assert isinstance(broker_kiwoom, KiwoomBroker)
    print("Kiwoom Broker loaded successfully.")
    
    # Test Force KIS
    print("\n[Mocking BROKER_TYPE = KIS]")
    settings.BROKER_TYPE = "KIS"
    broker_kis = get_broker()
    print(f"Loaded Broker Type: {type(broker_kis)}")
    assert isinstance(broker_kis, KisBroker)
    print("KIS Broker loaded successfully.")

if __name__ == "__main__":
    test_broker_loading()
