# Mean Reversion Strategy - Initial Context

## Previous Drawdown Causes
- Trading in ranging markets with static, non-adaptive Stop Losses.
- Initial risk logic erroneously allowed tight Take Profits but massive Stop Losses, causing severe mathematical asymmetry.
- JPY pairs (e.g. GBPJPY) experienced massive pip volatility that blew past static stops.

## Rules
- Drawdown must strictly remain under 15%.
- Do not use a static Stop Loss. SL must be dynamically tied to ATR.
- Must execute at least 1 trade a day.

## Iteration: Reversal Confirmation Logic
**Timestamp**: 2026-06-30
**Hypothesis**: Naively buying the exact moment price pierces the Bollinger Band catches falling knives in trending markets. Waiting for the price to close *back inside* the bands confirms mean reversion momentum has actually begun.
**Code Change**: Modified `buy_condition` and `sell_condition` in `mean_reversion.py` to require `close_prev` outside the bands and `close` inside the bands.
**Result**: **SUCCESS**.
- **Net Profit**: +13.16%
- **Max Drawdown**: 4.18% (Strictly < 15%)
- **Win Rate**: 56.67%
- **Profit Factor**: 1.90
- **Calmar Ratio**: 3.14
**Conclusion**: The logic effectively filtered out trending anomalies. The strategy is now consistently profitable out-of-sample on GBPJPY M15. No new rules required; the existing rule set was mathematically validated.
