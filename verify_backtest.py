#!/usr/bin/env python
import os
import sys
import re
import math

def main():
    log_dir = "obsidian_vault/Backtest_Logs"
    if not os.path.exists(log_dir):
        print(f"Error: Log directory '{log_dir}' does not exist.")
        sys.exit(1)

    # Naming pattern: {Strategy}_v{Version}_{YYYY-MM-DD}_{HH-MM}.md
    filename_pattern = re.compile(r"^([A-Za-z0-9_\-]+)_v([0-9\.]+)_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})\.md$")
    
    # Scan log_dir for all files
    all_files = []
    try:
        all_files = os.listdir(log_dir)
    except Exception as e:
        print(f"Error listing log directory: {e}")
        sys.exit(1)
        
    matching_files = []
    for f in all_files:
        match = filename_pattern.match(f)
        if match:
            full_path = os.path.join(log_dir, f)
            try:
                mtime = os.path.getmtime(full_path)
                matching_files.append((mtime, f, full_path, match.groups()))
            except Exception as e:
                print(f"Warning: Could not get mtime for {f}: {e}")
                
    if not matching_files:
        print("Error: No markdown report files matching the pattern {Strategy}_v{Version}_{YYYY-MM-DD}_{HH-MM}.md were found.")
        sys.exit(1)
        
    # Sort by modification time descending to get the latest
    matching_files.sort(reverse=True, key=lambda x: x[0])
    latest_mtime, latest_filename, latest_path, groups = matching_files[0]
    
    strategy_name, version_str, date_str, time_str = groups
    print(f"Verifying latest report: {latest_filename}")
    print(f"Extracted info - Strategy: {strategy_name}, Version: {version_str}, Date: {date_str}, Time: {time_str}")
    
    # Verify the filename pattern explicitly as requested
    if not filename_pattern.match(latest_filename):
        print(f"Error: Filename '{latest_filename}' does not match pattern.")
        sys.exit(1)
        
    # Read the markdown report and extract YAML frontmatter
    try:
        with open(latest_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except Exception as e:
        print(f"Error reading report file: {e}")
        sys.exit(1)
        
    # Parse YAML frontmatter
    lines = content.strip().split('\n')
    if not lines or lines[0].strip() != '---':
        print("Error: Markdown report does not start with '---' YAML frontmatter wrapper.")
        sys.exit(1)
        
    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == '---':
            end_idx = idx
            break
            
    if end_idx == -1:
        print("Error: Could not find ending '---' YAML frontmatter wrapper.")
        sys.exit(1)
        
    frontmatter = {}
    for idx in range(1, end_idx):
        line = lines[idx].strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            frontmatter[key.strip()] = val.strip()
            
    body = '\n'.join(lines[end_idx+1:])
    
    # Assert keys: strategy, version, sharpe, sortino, calmar, total_trades
    required_keys = ['strategy', 'version', 'sharpe', 'sortino', 'calmar', 'total_trades']
    for key in required_keys:
        if key not in frontmatter:
            print(f"Error: Required YAML frontmatter key '{key}' is missing.")
            sys.exit(1)
            
    # Validate types and values
    strategy = frontmatter['strategy']
    version_val = frontmatter['version']
    sharpe_val = frontmatter['sharpe']
    sortino_val = frontmatter['sortino']
    calmar_val = frontmatter['calmar']
    total_trades_val = frontmatter['total_trades']
    
    # Print the values we got
    print(f"YAML frontmatter values:")
    print(f"  strategy: {strategy}")
    print(f"  version: {version_val}")
    print(f"  sharpe: {sharpe_val}")
    print(f"  sortino: {sortino_val}")
    print(f"  calmar: {calmar_val}")
    print(f"  total_trades: {total_trades_val}")
    
    try:
        total_trades = int(total_trades_val)
    except ValueError:
        print(f"Error: total_trades must be an integer, got '{total_trades_val}'")
        sys.exit(1)
        
    if total_trades < 0:
        print(f"Error: total_trades must be >= 0, got {total_trades}")
        sys.exit(1)
        
    try:
        sharpe = float(sharpe_val)
        sortino = float(sortino_val)
        calmar = float(calmar_val)
    except ValueError:
        print(f"Error: Sharpe, Sortino, and Calmar must be valid floats. Got Sharpe='{sharpe_val}', Sortino='{sortino_val}', Calmar='{calmar_val}'")
        sys.exit(1)
        
    # Check for NaN / Inf
    for val, name in [(sharpe, 'sharpe'), (sortino, 'sortino'), (calmar, 'calmar')]:
        if math.isnan(val) or math.isinf(val):
            print(f"Error: YAML frontmatter metric '{name}' is not a valid float (is NaN or Inf): {val}")
            sys.exit(1)
            
    # If total_trades is 0, ensure Sharpe, Sortino, Calmar are 0.0 (or appropriate defaults) and Max Drawdown is 0.0.
    if total_trades == 0:
        # Check that metrics are 0.0
        if sharpe != 0.0 or sortino != 0.0 or calmar != 0.0:
            print(f"Error: total_trades is 0, but Sharpe ({sharpe}), Sortino ({sortino}), Calmar ({calmar}) are not all 0.0")
            sys.exit(1)
            
    # Parse 'Max Drawdown' from markdown body
    dd_pattern = re.compile(r"-\s+\*\*.*Drawdown.*\*\*:\s*(-?[\d\.]+)%", re.IGNORECASE)
    drawdowns_found = []
    for line in body.split('\n'):
        if 'drawdown' in line.lower():
            match = dd_pattern.search(line)
            if match:
                val = float(match.group(1))
                drawdowns_found.append((line.strip(), val))
                
    if not drawdowns_found:
        print("Error: No 'Max Drawdown' values found in markdown body.")
        sys.exit(1)
        
    print(f"Parsed drawdown values from body:")
    for line_text, val in drawdowns_found:
        print(f"  - '{line_text}' -> {val}%")
        if not (0.0 <= val <= 100.0):
            print(f"Error: Drawdown value {val}% is not mathematically bounded between 0% and 100% (inclusive).")
            sys.exit(1)
        if total_trades == 0 and val != 0.0:
            print(f"Error: total_trades is 0, but drawdown is non-zero: {val}%")
            sys.exit(1)
            
    # Verify executions chart
    # Filename matching {Strategy}_executions.png exists in the logs folder.
    png_filename = f"{strategy}_executions.png"
    png_path = os.path.join(log_dir, png_filename)
    if not os.path.exists(png_path):
        print(f"Error: Executions chart file '{png_path}' does not exist.")
        sys.exit(1)
        
    # Verify that the PNG is a valid, non-empty PNG by reading its first 8 bytes and matching PNG magic bytes
    try:
        png_size = os.path.getsize(png_path)
        if png_size == 0:
            print(f"Error: PNG file '{png_path}' is empty.")
            sys.exit(1)
            
        with open(png_path, 'rb') as f_png:
            png_data = f_png.read()
            if len(png_data) < 8 or png_data[:8] != b'\x89PNG\r\n\x1a\n':
                print(f"Error: Executions chart '{png_path}' is not a valid PNG (incorrect magic bytes).")
                sys.exit(1)
            if b'IEND' not in png_data[-12:]:
                print(f"Error: Executions chart '{png_path}' is not a valid PNG (missing IEND chunk at the end).")
                sys.exit(1)
    except Exception as e:
        print(f"Error checking executions chart file: {e}")
        sys.exit(1)
        
    print(f"Successfully verified PNG chart: {png_path} ({png_size} bytes)")
    print("Verification SUCCESS: All checks passed.")
    sys.exit(0)

if __name__ == "__main__":
    main()
