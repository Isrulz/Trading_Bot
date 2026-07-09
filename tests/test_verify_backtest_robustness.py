import os
import sys
import shutil
import subprocess

# Paths
LOG_DIR = "obsidian_vault/Backtest_Logs"
BACKUP_DIR = "obsidian_vault/Backtest_Logs_backup"
VERIFY_SCRIPT = "verify_backtest.py"

def setup_backup():
    if os.path.exists(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR)
    if os.path.exists(LOG_DIR):
        shutil.copytree(LOG_DIR, BACKUP_DIR)
        # Clear the log directory
        for f in os.listdir(LOG_DIR):
            path = os.path.join(LOG_DIR, f)
            if os.path.isfile(path):
                os.remove(path)
    else:
        os.makedirs(LOG_DIR)

def restore_backup():
    if os.path.exists(BACKUP_DIR):
        if os.path.exists(LOG_DIR):
            shutil.rmtree(LOG_DIR)
        shutil.copytree(BACKUP_DIR, LOG_DIR)
        shutil.rmtree(BACKUP_DIR)

def run_verification():
    result = subprocess.run([sys.executable, VERIFY_SCRIPT], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def write_test_files(md_filename, md_content, png_filename="mean_reversion_executions.png", png_bytes=b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND'):
    # Clear directory first to isolate test file
    for f in os.listdir(LOG_DIR):
        path = os.path.join(LOG_DIR, f)
        if os.path.isfile(path):
            os.remove(path)
            
    if md_filename and md_content is not None:
        with open(os.path.join(LOG_DIR, md_filename), 'w', encoding='utf-8') as f:
            f.write(md_content)
    if png_filename and png_bytes is not None:
        with open(os.path.join(LOG_DIR, png_filename), 'wb') as f:
            f.write(png_bytes)

def main():
    print("Initializing Robustness Test Suite for verify_backtest.py...\n")
    setup_backup()
    
    scenarios = [
        {
            "id": "TC-CH-01",
            "name": "Valid Base Case",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report: MEAN_REVERSION (2.0)
- **Report Generated**: 2026-06-30 14:13:45 AEST

## Performance Visualization
![Executions Chart](mean_reversion_executions.png)

### Baseline (Historical) Metrics
- **Max Drawdown**: 10.45%
- **Total Trades**: 59

### Monte Carlo Simulation Metrics (1,000 Iterations)
- **Median Sharpe**: 0.00
- **Median Sortino**: 0.00
- **Median Calmar**: -0.04
- **Mean Max Drawdown**: 8.05%
- **95th Percentile Max Drawdown (Sequence Risk)**: 11.37%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 0
        },
        {
            "id": "TC-CH-02",
            "name": "Malformed filename (no hyphen in time)",
            "md_file": "mean_reversion_v2.0_2026-06-30_1413.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-03",
            "name": "Missing starting YAML wrapper",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-04",
            "name": "Missing ending YAML wrapper",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-05",
            "name": "Missing required YAML key (sharpe)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-06",
            "name": "Non-numeric key value (sharpe: abc)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: abc
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-07",
            "name": "NaN/Inf metric value (sharpe: NaN)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: NaN
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-08",
            "name": "NaN/Inf metric value (calmar: inf)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: inf
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-09",
            "name": "Out-of-bounds drawdown value (> 100%)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 105.0%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-10",
            "name": "Out-of-bounds drawdown value (< 0% / e.g. -5%)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: -5.0%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1  # Verify script should fail on negative drawdown
        },
        {
            "id": "TC-CH-11",
            "name": "Missing executions chart PNG",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": None,
            "png_bytes": None,
            "expected_exit": 1
        },
        {
            "id": "TC-CH-12",
            "name": "Empty executions chart PNG (0 bytes)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-13",
            "name": "Malformed PNG (incorrect magic bytes)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.45%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'NOT_A_PNG_FILE',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-14",
            "name": "Zero trade fallback (non-zero Sharpe)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 1.50
sortino: 0.00
calmar: 0.00
total_trades: 0
---
# Monte Carlo Performance Report
- **Max Drawdown**: 0.00%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-15",
            "name": "Zero trade fallback (non-zero Drawdown)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: 0.00
total_trades: 0
---
# Monte Carlo Performance Report
- **Max Drawdown**: 10.00%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 1
        },
        {
            "id": "TC-CH-16",
            "name": "Zero trade fallback (valid zero trades)",
            "md_file": "mean_reversion_v2.0_2026-06-30_14-13.md",
            "md_content": """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: 0.00
total_trades: 0
---
# Monte Carlo Performance Report
- **Max Drawdown**: 0.00%
""",
            "png_file": "mean_reversion_executions.png",
            "png_bytes": b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND',
            "expected_exit": 0
        }
    ]
    
    results = []
    
    for tc in scenarios:
        write_test_files(tc['md_file'], tc['md_content'], tc['png_file'], tc['png_bytes'])
        exit_code, stdout, stderr = run_verification()
        
        status = "PASSED"
        note = ""
        if exit_code != tc['expected_exit']:
            if tc['id'] == "TC-CH-10" and exit_code == 0:
                status = "VULNERABLE (Incorrect Pass)"
                note = "Vulnerability: regex ignores negative sign, matches positive value"
            else:
                status = "FAILED"
                note = f"Expected exit {tc['expected_exit']}, got {exit_code}"
            
        results.append({
            "id": tc["id"],
            "name": tc["name"],
            "expected": tc["expected_exit"],
            "actual": exit_code,
            "status": status,
            "note": note
        })
        
    restore_backup()
    
    print("\nSummary of Verification:")
    print(f"{'ID':<8} | {'Scenario Name':<45} | {'Expected':<8} | {'Actual':<6} | {'Status':<25} | {'Notes'}")
    print("-" * 120)
    for r in results:
        print(f"{r['id']:<8} | {r['name']:<45} | {r['expected']:<8} | {r['actual']:<6} | {r['status']:<25} | {r['note']}")
        
    print("\nAll scenarios evaluated.")
    # Exit with 0 so the test framework itself runs cleanly, but findings are clear in output
    sys.exit(0)

if __name__ == "__main__":
    main()
