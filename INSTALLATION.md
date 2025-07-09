# Installation Guide

## Prerequisites

- Python 3.9+
- Hummingbot installed from source
- Binance Perpetual Testnet account (or live account)

## Step 1: Deploy Strategy

### Copy Strategy File
```bash
# Copy pmm_advanced_volatility.py to your Hummingbot scripts directory
cp pmm_advanced_volatility.py /path/to/hummingbot/scripts/
```

### Verify File Location
```bash
ls hummingbot/scripts/pmm_advanced_volatility.py
```

## Step 2: Configure Exchange Connection

### Start Hummingbot
```bash
cd hummingbot
python bin/hummingbot.py
```

### Connect to Exchange
```bash
# In Hummingbot console
>>> connect binance_perpetual_testnet
```

**For Testnet:**
1. Visit: https://testnet.binancefuture.com/
2. Create account and generate API keys
3. Enter keys when prompted

**For Live Trading:**
```bash
>>> connect binance_perpetual
```
⚠️ **Warning:** Use real API keys and funds at your own risk

## Step 3: Run Strategy

### Start Strategy
```bash
>>> start --script pmm_advanced_volatility.py
```

### Monitor Performance
```bash
>>> status        # View strategy metrics
>>> orders        # Check active orders
>>> history       # Review execution history
>>> balance       # Check portfolio balance
```

### Stop Strategy
```bash
>>> stop
```

## Configuration Parameters

The strategy includes the following configurable parameters:

```python
# Core Configuration
exchange = "binance_perpetual_testnet"
trading_pair = "BTC-USDT"

# Strategy Parameters
base_spread = Decimal("0.002")        # 0.2% base spread
order_amount = Decimal("0.01")        # Base order size
max_inventory_skew = Decimal("0.3")   # Max 30% skew

# Volatility Parameters
volatility_lookback = 20              # Periods for volatility calc
volatility_multiplier = Decimal("2.0") # Spread multiplier
max_spread = Decimal("0.01")          # Maximum spread (1%)
min_spread = Decimal("0.001")         # Minimum spread (0.1%)

# Risk Management
max_order_age = 60                    # Order refresh time (seconds)
refresh_tolerance = Decimal("0.01")   # Price tolerance for refresh
```

## Troubleshooting

### Common Issues

**Strategy won't start:**
- Check file is in correct `scripts/` directory
- Verify Python syntax with: `python -m py_compile scripts/pmm_advanced_volatility.py`

**Connection errors:**
- Verify API keys are correct
- Check network connection
- Ensure exchange is supported

**No orders placing:**
- Check minimum balance requirements
- Verify trading pair is active
- Review logs for error messages

**Orders not executing:**
- Check spread settings aren't too wide
- Verify order sizes meet exchange minimums
- Monitor market conditions

### Getting Help

1. Check Hummingbot logs: `logs/` directory
2. Review strategy status: `>>> status`
3. Monitor error messages in real-time
4. Consult Hummingbot documentation: https://docs.hummingbot.org/

## Performance Monitoring

### Key Metrics to Track
- **Return %**: Overall profitability
- **Volatility adaptation**: Spread adjustments
- **Inventory skew**: Portfolio balance
- **Fill rate**: Order execution frequency
- **Fee efficiency**: Cost management

### Recommended Monitoring Frequency
- **Real-time**: During first hour of operation
- **Hourly**: For first 24 hours
- **Daily**: For ongoing operation

## Safety Recommendations

1. **Start with testnet** before live trading
2. **Use small position sizes** initially
3. **Monitor closely** during first 24 hours
4. **Set portfolio limits** to control maximum exposure
5. **Have exit plan** for emergency situations

---

**Happy Trading! 🚀**
