from datetime import date

# 2025 ~ 2026 KRX (Korean Stock Market) Holidays
KRX_HOLIDAYS = [
    # 2025
    date(2025, 12, 31), # Year-end holiday
    
    # 2026
    date(2026, 1, 1),   # New Year's Day
    date(2026, 2, 16),  # Lunar New Year
    date(2026, 2, 17),  # Lunar New Year
    date(2026, 2, 18),  # Lunar New Year
    date(2026, 3, 2),   # Independence Movement Day (Substitute)
    date(2026, 5, 1),   # Labor Day (Market Closed)
    date(2026, 5, 5),   # Children's Day
    date(2026, 5, 25),  # Buddha's Birthday (Substitute)
    date(2026, 8, 17),  # Liberation Day (Substitute)
    date(2026, 9, 24),  # Chuseok
    date(2026, 9, 25),  # Chuseok
    date(2026, 9, 26),  # Chuseok (Saturday) -> Substitute logic covered by specific dates if declared
    date(2026, 9, 28),  # Chuseok (Substitute)
    date(2026, 10, 5),  # National Foundation Day (Substitute)
    date(2026, 10, 9),  # Hangeul Day
    date(2026, 12, 25), # Christmas
    date(2026, 12, 31), # Year-end holiday
]
