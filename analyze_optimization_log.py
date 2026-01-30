import re
import sys

def parse_log(file_path):
    print(f"Analyzing {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    combinations = []
    current_combo = None
    
    # Regex Patterns
    combo_start_pattern = re.compile(r"Testing combination (\d+)/(\d+)")
    params_pattern = re.compile(r"1X Stop Loss: (.*), 2X Stop Loss: (.*), Take Profit: (.*)")
    
    # 📈 [2024-01-09 19:30] TSLA -> TSLL 롱 진입 @ $13.14 x 161.00 (수수료: $5.29)
    entry_pattern = re.compile(r"📈 \[(.*)\] .* -> (.*) (롱|숏) 진입 @ \$([\d.]+) x ([\d.]+) \(수수료: \$([\d.]+)\)")
    
    # 🔒 [2024-01-11 15:30] TSLL LONG 청산 @ $13.14 $12.41 (손익: -5.56%, 수수료: $5.00) - STOP_LOSS
    exit_pattern = re.compile(r"🔒 \[(.*)\] (.*) (LONG|SHORT) 청산 @ \$([\d.]+) \$([\d.]+) \(손익: .*, 수수료: \$([\d.]+)\)")

    initial_capital = 2300.0
    
    for line in lines:
        # Check for new combination
        if "Testing combination" in line:
            if current_combo:
                combinations.append(current_combo)
            
            current_combo = {
                "id": 0,
                "params": "",
                "capital": initial_capital,
                "min_capital": initial_capital,
                "trades": 0,
                "current_position": None # Store entry info to calculate PnL on exit
            }
            match = combo_start_pattern.search(line)
            if match:
                current_combo["id"] = int(match.group(1))
            continue
            
        if "1X Stop Loss:" in line and "2X Stop Loss:" in line and current_combo:
            match = params_pattern.search(line)
            if match:
                current_combo["params"] = f"1xSL:{match.group(1)}, 2xSL:{match.group(2)}, TP:{match.group(3)}"
            continue

        if not current_combo:
            continue

        # Check for Entry
        entry_match = entry_pattern.search(line)
        if entry_match:
            # ENTRY implies we paid commission
            commission = float(entry_match.group(6))
            current_combo["capital"] -= commission
            
            # Update min capital immediately after paying commission
            if current_combo["capital"] < current_combo["min_capital"]:
                current_combo["min_capital"] = current_combo["capital"]
                
            qty = float(entry_match.group(5))
            entry_price = float(entry_match.group(4))
            direction = entry_match.group(3) # 롱 or 숏
             
            current_combo["current_position"] = {
                "qty": qty,
                "price": entry_price,
                "direction": direction
            }
            continue

        # Check for Exit
        exit_match = exit_pattern.search(line)
        if exit_match:
            if not current_combo["current_position"]:
                # Should not happen if log is consistent
                continue
                
            entry_info = current_combo["current_position"]
            qty = entry_info["qty"]
            entry_price = entry_info["price"] # Using original entry price for calculation reference
            # Note: The log shows exit price in group 5. group 4 is entry price (usually).
            
            exit_price = float(exit_match.group(5)) 
            commission = float(exit_match.group(6))
            
            # Calculate Profit
            # If Long: (Exit - Entry) * Qty
            # If Short: (Entry - Exit) * Qty
            
            is_long = "LONG" in exit_match.group(3) or "롱" in str(entry_info["direction"])
            
            if is_long:
                profit = (exit_price - entry_price) * qty
            else:
                profit = (entry_price - exit_price) * qty
                
            # Net PnL = Profit - Exit Commission
            # (Entry commission was already deducted)
            
            current_combo["capital"] += profit
            current_combo["capital"] -= commission
            
            if current_combo["capital"] < current_combo["min_capital"]:
                current_combo["min_capital"] = current_combo["capital"]
                
            current_combo["trades"] += 1
            current_combo["current_position"] = None
            continue

    if current_combo:
        combinations.append(current_combo)

    # Print Results
    print(f"{'Combo':<5} | {'Parameters':<60} | {'Final Cap':<10} | {'Min Cap (Drawdown)':<20} | {'Trades':<6}")
    print("-" * 115)
    
    for c in combinations:
        print(f"{c['id']:<5} | {c['params']:<60} | ${c['capital']:<9.2f} | ${c['min_capital']:<18.2f} | {c['trades']:<6}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parse_log(sys.argv[1])
    else:
        parse_log("optimization_log_tsla_only_long.txt")
