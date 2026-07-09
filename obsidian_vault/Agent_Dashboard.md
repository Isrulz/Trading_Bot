# 🤖 Trading Agent Dashboard

## Latest Backtest Results
```dataview
TABLE 
  sharpe_ratio AS "Sharpe", 
  net_profit AS "Net Profit %", 
  drawdown AS "Max Drawdown %"
FROM "Backtest_Logs"
SORT file.ctime DESC
LIMIT 10
