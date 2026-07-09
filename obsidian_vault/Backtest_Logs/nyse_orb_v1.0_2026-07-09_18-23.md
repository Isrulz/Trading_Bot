---
strategy: nyse_orb
version: 1.0
sharpe: 0.44
sortino: 18.86
calmar: 2.65
total_trades: 5
---

# Monte Carlo Performance Report: NYSE_ORB (1.0)

- **Report Generated**: 2026-07-09 18:23:37 AEST

## Performance Visualization
![Executions Chart](nyse_orb_executions.png)

## Executive Summary
This report summarizes the performance of the `nyse_orb` trading strategy under a 1,000-run Monte Carlo sequence risk simulation. Shuffling the historical trade sequence helps analyze path-dependency and sequence of returns risk.

### Baseline (Historical) Metrics
- **Final Balance**: $10,341.06
- **Net Profit**: 3.41%
- **Max Drawdown**: 1.26%
- **Total Trades**: 5
- **Win Rate**: 60.00%
- **Historical Sharpe**: 0.43
- **Historical Sortino**: 17.05
- **Historical Calmar**: 2.71

### Monte Carlo Simulation Metrics (1,000 Iterations)
- **Median Sharpe**: 0.44
- **Median Sortino**: 18.86
- **Median Calmar**: 2.65
- **Mean Max Drawdown**: 1.73%
- **95th Percentile Max Drawdown (Sequence Risk)**: 2.49%

## Conclusion
The Monte Carlo simulation confirms the strategy's resilience against sequence of return risks. The 95th percentile Maximum Drawdown remains at **2.49%**, which is well within the **15%** absolute maximum risk limit constraint.
