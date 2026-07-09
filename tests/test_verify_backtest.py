import os
import shutil
import subprocess
import sys
import pytest

LOG_DIR = "obsidian_vault/Backtest_Logs"
BACKUP_DIR = os.path.join(LOG_DIR, "backup_temp")

@pytest.fixture(autouse=True)
def backup_and_restore_logs():
    # Setup: backup all files in LOG_DIR
    os.makedirs(BACKUP_DIR, exist_ok=True)
    moved_files = []
    for item in os.listdir(LOG_DIR):
        item_path = os.path.join(LOG_DIR, item)
        if os.path.isfile(item_path):
            dest_path = os.path.join(BACKUP_DIR, item)
            shutil.move(item_path, dest_path)
            moved_files.append((item_path, dest_path))
            
    yield
    
    # Teardown: clean up any files created by tests in LOG_DIR
    for item in os.listdir(LOG_DIR):
        item_path = os.path.join(LOG_DIR, item)
        if os.path.isfile(item_path):
            os.remove(item_path)
            
    # Restore original files
    for item in os.listdir(BACKUP_DIR):
        src_path = os.path.join(BACKUP_DIR, item)
        dest_path = os.path.join(LOG_DIR, item)
        shutil.move(src_path, dest_path)
        
    # Remove backup directory
    shutil.rmtree(BACKUP_DIR)

def run_verify_script():
    result = subprocess.run([sys.executable, "verify_backtest.py"], capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def write_test_report(filename, content, mtime=None):
    filepath = os.path.join(LOG_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    if mtime is not None:
        os.utime(filepath, (mtime, mtime))
    return filepath

def write_test_png(filename, content):
    filepath = os.path.join(LOG_DIR, filename)
    with open(filepath, 'wb') as f:
        f.write(content)
    return filepath

def test_malformed_filename():
    # Create a malformed report filename (e.g. missing hyphen in time field or using wrong characters)
    write_test_report("mean_reversion_v2.0_2026-06-30_1408.md", "dummy content")
    
    # Run verification
    code, stdout, stderr = run_verify_script()
    
    # Should fail because no file matching the pattern was found
    assert code != 0
    assert "No markdown report files matching the pattern" in stdout or "No markdown report files matching the pattern" in stderr

def test_missing_yaml_frontmatter_start():
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", "strategy: mean_reversion\n---\n")
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "Markdown report does not start with '---'" in stdout

def test_missing_yaml_frontmatter_end():
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", "---\nstrategy: mean_reversion\n")
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "Could not find ending '---'" in stdout

@pytest.mark.parametrize("missing_key", ["strategy", "version", "sharpe", "sortino", "calmar", "total_trades"])
def test_missing_required_keys(missing_key):
    keys = {
        "strategy": "mean_reversion",
        "version": "2.0",
        "sharpe": "0.00",
        "sortino": "0.00",
        "calmar": "-0.04",
        "total_trades": "59"
    }
    keys.pop(missing_key)
    
    content = "---\n" + "\n".join(f"{k}: {v}" for k, v in keys.items()) + "\n---\n"
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert f"Required YAML frontmatter key '{missing_key}' is missing" in stdout

def test_non_integer_total_trades():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 12.3
---
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "total_trades must be an integer" in stdout

def test_negative_total_trades():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: -5
---
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "total_trades must be >= 0" in stdout

@pytest.mark.parametrize("metric", ["sharpe", "sortino", "calmar"])
def test_non_float_metrics(metric):
    keys = {
        "strategy": "mean_reversion",
        "version": "2.0",
        "sharpe": "0.00",
        "sortino": "0.00",
        "calmar": "-0.04",
        "total_trades": "59"
    }
    keys[metric] = "abc"
    content = "---\n" + "\n".join(f"{k}: {v}" for k, v in keys.items()) + "\n---\n"
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "must be valid floats" in stdout

@pytest.mark.parametrize("metric,val", [
    ("sharpe", "NaN"), ("sharpe", "Inf"), ("sharpe", "-Inf"),
    ("sortino", "NaN"), ("sortino", "Inf"), ("sortino", "-Inf"),
    ("calmar", "NaN"), ("calmar", "Inf"), ("calmar", "-Inf")
])
def test_nan_inf_metrics(metric, val):
    keys = {
        "strategy": "mean_reversion",
        "version": "2.0",
        "sharpe": "0.00",
        "sortino": "0.00",
        "calmar": "-0.04",
        "total_trades": "59"
    }
    keys[metric] = val
    content = "---\n" + "\n".join(f"{k}: {v}" for k, v in keys.items()) + "\n---\n"
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert f"metric '{metric}' is not a valid float (is NaN or Inf)" in stdout

def test_out_of_bounds_drawdown_high():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
- **Max Drawdown**: 105.0%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean_reversion_executions.png", b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB\x60\x82') # Valid PNG magic
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "is not mathematically bounded between 0% and 100%" in stdout

def test_out_of_bounds_drawdown_negative():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
- **Max Drawdown**: -5.0%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean_reversion_executions.png", b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB\x60\x82')
    code, stdout, stderr = run_verify_script()
    
    assert code != 0
    assert "is not mathematically bounded" in stdout

def test_missing_executions_png():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
- **Max Drawdown**: 10.45%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    # Ensure PNG does not exist
    png_path = os.path.join(LOG_DIR, "mean_reversion_executions.png")
    if os.path.exists(png_path):
        os.remove(png_path)
        
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "does not exist" in stdout

def test_empty_executions_png():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
- **Max Drawdown**: 10.45%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean_reversion_executions.png", b'') # 0 bytes
    
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "is empty" in stdout

def test_corrupt_executions_png():
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: -0.04
total_trades: 59
---
- **Max Drawdown**: 10.45%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean_reversion_executions.png", b'BADMAGICBYTES') # Non-empty but invalid magic
    
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "is not a valid PNG (incorrect magic bytes" in stdout

def test_zero_trades_non_zero_metrics():
    # total_trades = 0, but Sharpe is 1.5
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 1.50
sortino: 0.00
calmar: 0.00
total_trades: 0
---
- **Max Drawdown**: 0.0%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean_reversion_executions.png", b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB\x60\x82')
    
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "total_trades is 0, but Sharpe" in stdout

def test_zero_trades_non_zero_drawdown():
    # total_trades = 0, Sharpe/Sortino/Calmar are 0, but Drawdown is 5%
    content = """---
strategy: mean_reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: 0.00
total_trades: 0
---
- **Max Drawdown**: 5.0%
"""
    write_test_report("mean_reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean_reversion_executions.png", b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB\x60\x82')
    
    code, stdout, stderr = run_verify_script()
    assert code != 0
    assert "total_trades is 0, but drawdown is non-zero" in stdout

def test_zero_trades_correct_fallback():
    # total_trades = 0, Sharpe/Sortino/Calmar are 0, Drawdown is 0
    content = """---
strategy: mean-reversion
version: 2.0
sharpe: 0.00
sortino: 0.00
calmar: 0.00
total_trades: 0
---
- **Max Drawdown**: 0.0%
"""
    write_test_report("mean-reversion_v2.0_2099-01-01_12-00.md", content)
    write_test_png("mean-reversion_executions.png", b'\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\xaeB\x60\x82')
    
    code, stdout, stderr = run_verify_script()
    assert code == 0
    assert "Verification SUCCESS" in stdout
