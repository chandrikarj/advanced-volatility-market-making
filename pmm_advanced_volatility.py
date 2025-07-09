import pandas as pd
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType, PositionAction
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.utils.async_utils import safe_ensure_future
import asyncio
from datetime import datetime, timedelta


class AdvancedVolatilityMarketMaking(ScriptStrategyBase):
    """
    Advanced Market Making Strategy with:
    - Volatility-based spread adjustments
    - Trend analysis and momentum
    - Inventory risk management
    - Dynamic order sizing
    """
    
    # Core Configuration
    exchange = "binance_perpetual_testnet"
    trading_pair = "BTC-USDT"
    
    # Required markets attribute for Hummingbot
    markets = {exchange: {trading_pair}}
    
    # Strategy Parameters
    base_spread = Decimal("0.002")  # 0.2% base spread
    order_amount = Decimal("0.01")  # Base order size
    inventory_target_base_pct = Decimal("0.5")  # Target 50% base asset
    max_inventory_skew = Decimal("0.3")  # Max 30% skew from target
    
    # Volatility Parameters
    volatility_lookback = 20  # Candles for volatility calculation
    volatility_multiplier = Decimal("2.0")  # Spread multiplier based on volatility
    max_spread = Decimal("0.01")  # Maximum spread (1%)
    min_spread = Decimal("0.001")  # Minimum spread (0.1%)
    
    # Trend Parameters
    trend_lookback = 14  # Candles for trend analysis
    trend_threshold = Decimal("0.003")  # 0.3% threshold for trend detection
    trend_adjustment = Decimal("0.5")  # How much to adjust for trend
    
    # Risk Management
    max_order_age = 60  # Maximum order age in seconds (increased to stop loop)
    refresh_tolerance = Decimal("0.01")  # Price tolerance for order refresh (increased)
    
    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        self.last_price_data = []
        self.last_volatility = Decimal("0.01")
        self.last_trend = Decimal("0")
        self.inventory_skew = Decimal("0")
        self.last_refresh_time = 0
        self.orders_placed = False  # Flag to prevent constant ordering
        
    def on_tick(self):
        """Main strategy execution loop"""
        try:
            # Get current market data
            connector = self.connectors[self.exchange]
            
            if not connector.ready:
                return
                
            # Update market data and calculate indicators
            self._update_market_data()
            
            # Calculate current inventory
            self._calculate_inventory()
            
            # Check if we need to refresh orders (less frequent)
            if self._should_refresh_orders():
                self._cancel_all_orders()
                self.orders_placed = False
                # Place orders after delay
                safe_ensure_future(self._place_orders_after_delay())
                
        except Exception as e:
            self.logger().error(f"Error in on_tick: {e}")
    
    async def _place_orders_after_delay(self):
        """Place orders after a delay to ensure cancellations are processed"""
        await asyncio.sleep(2.0)  # Wait 2 seconds
        if not self.orders_placed:
            self._place_orders()
    
    def _update_market_data(self):
        """Update price data and calculate volatility/trend indicators"""
        try:
            connector = self.connectors[self.exchange]
            
            # Get current mid price
            current_price = connector.get_mid_price(self.trading_pair)
            if current_price is None:
                return
                
            # Store price data (less frequently)
            current_time = datetime.now()
            
            # Only add data every 10 seconds to prevent overprocessing
            if (not self.last_price_data or 
                (current_time - self.last_price_data[-1]['timestamp']).seconds >= 10):
                
                self.last_price_data.append({
                    'timestamp': current_time,
                    'price': float(current_price)
                })
                
                # Keep only recent data
                cutoff_time = current_time - timedelta(minutes=30)
                self.last_price_data = [
                    data for data in self.last_price_data 
                    if data['timestamp'] > cutoff_time
                ]
                
                # Calculate indicators if we have enough data
                if len(self.last_price_data) >= self.volatility_lookback:
                    self._calculate_volatility()
                    self._calculate_trend()
                
        except Exception as e:
            self.logger().error(f"Error updating market data: {e}")
    
    def _calculate_volatility(self):
        """Calculate price volatility using rolling standard deviation"""
        try:
            if len(self.last_price_data) < self.volatility_lookback:
                return
                
            # Get recent prices
            recent_prices = [data['price'] for data in self.last_price_data[-self.volatility_lookback:]]
            
            # Calculate returns
            returns = []
            for i in range(1, len(recent_prices)):
                ret = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]
                returns.append(ret)
            
            if len(returns) > 1:
                # Calculate standard deviation of returns
                mean_return = np.mean(returns)
                variance = np.mean([(r - mean_return) ** 2 for r in returns])
                volatility = np.sqrt(variance)
                
                # Annualize volatility
                annualized_volatility = volatility * np.sqrt(525600)
                
                self.last_volatility = Decimal(str(min(annualized_volatility, 1.0)))
                
        except Exception as e:
            self.logger().error(f"Error calculating volatility: {e}")
    
    def _calculate_trend(self):
        """Calculate trend using simple moving average crossover"""
        try:
            if len(self.last_price_data) < self.trend_lookback:
                return
                
            # Get recent prices
            recent_prices = [data['price'] for data in self.last_price_data[-self.trend_lookback:]]
            
            # Calculate short and long moving averages
            short_ma = np.mean(recent_prices[-5:])
            long_ma = np.mean(recent_prices[-self.trend_lookback:])
            
            # Calculate trend as percentage difference
            trend = (short_ma - long_ma) / long_ma
            self.last_trend = Decimal(str(trend))
            
        except Exception as e:
            self.logger().error(f"Error calculating trend: {e}")
    
    def _calculate_inventory(self):
        """Calculate current inventory skew"""
        try:
            connector = self.connectors[self.exchange]
            
            # Get balances
            base_balance = connector.get_available_balance(self.trading_pair.split('-')[0])
            quote_balance = connector.get_available_balance(self.trading_pair.split('-')[1])
            
            if base_balance is None or quote_balance is None:
                return
                
            # Get current price
            current_price = connector.get_mid_price(self.trading_pair)
            if current_price is None:
                return
                
            # Calculate total portfolio value in quote currency
            total_value = quote_balance + (base_balance * current_price)
            
            if total_value > 0:
                # Calculate current base percentage
                base_value = base_balance * current_price
                current_base_pct = base_value / total_value
                
                # Calculate skew from target
                self.inventory_skew = current_base_pct - self.inventory_target_base_pct
                
        except Exception as e:
            self.logger().error(f"Error calculating inventory: {e}")
    
    def _calculate_dynamic_spreads(self) -> Tuple[Decimal, Decimal]:
        """Calculate dynamic bid/ask spreads based on volatility, trend, and inventory"""
        try:
            # Base spread adjusted for volatility
            volatility_spread = self.base_spread * (Decimal("1") + self.volatility_multiplier * self.last_volatility)
            
            # Clamp spread to min/max bounds
            spread = max(self.min_spread, min(volatility_spread, self.max_spread))
            
            # Adjust for trend
            trend_adjustment = abs(self.last_trend) * self.trend_adjustment
            
            # Adjust for inventory
            inventory_adjustment = self.inventory_skew * Decimal("0.2")  # Reduced impact
            
            # Calculate final spreads
            bid_spread = spread + trend_adjustment + inventory_adjustment
            ask_spread = spread + trend_adjustment - inventory_adjustment
            
            # Ensure minimum spreads
            bid_spread = max(self.min_spread, bid_spread)
            ask_spread = max(self.min_spread, ask_spread)
            
            return bid_spread, ask_spread
            
        except Exception as e:
            self.logger().error(f"Error calculating spreads: {e}")
            return self.base_spread, self.base_spread
    
    def _calculate_order_size(self, side: str) -> Decimal:
        """Calculate dynamic order size based on inventory and volatility"""
        try:
            # Fixed base size to avoid Decimal/float mixing
            base_size = self.order_amount
            
            # Simple inventory adjustment (no complex multipliers)
            if side == "buy" and self.inventory_skew < 0:
                size_multiplier = Decimal("1.2")  # 20% larger
            elif side == "sell" and self.inventory_skew > 0:
                size_multiplier = Decimal("1.2")  # 20% larger
            else:
                size_multiplier = Decimal("1.0")
            
            final_size = base_size * size_multiplier
            
            # Ensure minimum size for Binance
            return max(Decimal("0.001"), final_size)
            
        except Exception as e:
            self.logger().error(f"Error calculating order size: {e}")
            return self.order_amount
    
    def _should_refresh_orders(self) -> bool:
        """Determine if orders should be refreshed - LESS AGGRESSIVE"""
        try:
            current_time = self.current_timestamp
            
            # Only refresh every 60 seconds minimum
            if current_time - self.last_refresh_time < self.max_order_age:
                return False
            
            # Check if we have too many or too few orders
            connector = self.connectors[self.exchange]
            active_orders = connector.in_flight_orders
            
            # If no orders, place them
            if len(active_orders) == 0 and not self.orders_placed:
                return True
            
            # If too many orders (more than 2), refresh
            if len(active_orders) > 2:
                return True
            
            return False
            
        except Exception as e:
            self.logger().error(f"Error checking refresh condition: {e}")
            return False
    
    def _place_orders(self):
        """Place new buy and sell orders"""
        try:
            connector = self.connectors[self.exchange]
            current_price = connector.get_mid_price(self.trading_pair)
            
            if current_price is None or self.orders_placed:
                return
            
            # Calculate dynamic spreads
            bid_spread, ask_spread = self._calculate_dynamic_spreads()
            
            # Calculate order prices
            bid_price = current_price * (Decimal("1") - bid_spread)
            ask_price = current_price * (Decimal("1") + ask_spread)
            
            # Calculate order sizes
            buy_size = self._calculate_order_size("buy")
            sell_size = self._calculate_order_size("sell")
            
            # Place buy order
            connector.buy(
                trading_pair=self.trading_pair,
                amount=buy_size,
                order_type=OrderType.LIMIT,
                price=bid_price,
                position_action=PositionAction.OPEN
            )
            
            # Place sell order
            connector.sell(
                trading_pair=self.trading_pair,
                amount=sell_size,
                order_type=OrderType.LIMIT,
                price=ask_price,
                position_action=PositionAction.OPEN
            )
            
            self.last_refresh_time = self.current_timestamp
            self.orders_placed = True  # Prevent immediate re-ordering
            
            # Log strategy state
            self.logger().info(
                f"Orders placed - Price: {current_price:.4f}, "
                f"Volatility: {self.last_volatility:.4f}, "
                f"Trend: {self.last_trend:.4f}, "
                f"Inventory Skew: {self.inventory_skew:.4f}, "
                f"Spreads: {bid_spread:.4f}/{ask_spread:.4f}"
            )
            
        except Exception as e:
            self.logger().error(f"Error placing orders: {e}")
    
    def _cancel_all_orders(self):
        """Cancel all active orders"""
        try:
            connector = self.connectors[self.exchange]
            active_orders = connector.in_flight_orders
            
            for order_id, order in active_orders.items():
                connector.cancel(self.trading_pair, order_id)
                
        except Exception as e:
            self.logger().error(f"Error canceling orders: {e}")
    
    def did_fill_order(self, event: OrderFilledEvent):
        """Handle order fill events"""
        try:
            self.logger().info(
                f"Order filled - {event.trade_type} {event.amount} {event.trading_pair} "
                f"at {event.price}"
            )
            
            # Reset flag to allow new orders after fill
            self.orders_placed = False
            
            # Recalculate inventory after fill
            self._calculate_inventory()
            
        except Exception as e:
            self.logger().error(f"Error handling order fill: {e}")
    
    def format_status(self) -> str:
        """Format strategy status for display"""
        try:
            connector = self.connectors[self.exchange]
            current_price = connector.get_mid_price(self.trading_pair)
            
            if current_price is None:
                return "No market data available"
            
            bid_spread, ask_spread = self._calculate_dynamic_spreads()
            
            return (
                f"\n--- Advanced Volatility Market Making ---\n"
                f"Trading Pair: {self.trading_pair}\n"
                f"Current Price: {current_price:.4f}\n"
                f"Volatility: {self.last_volatility:.4f}\n"
                f"Trend: {self.last_trend:.4f}\n"
                f"Inventory Skew: {self.inventory_skew:.4f}\n"
                f"Bid Spread: {bid_spread:.4f}\n"
                f"Ask Spread: {ask_spread:.4f}\n"
                f"Active Orders: {len(connector.in_flight_orders)}\n"
                f"Orders Placed Flag: {self.orders_placed}\n"
            )
            
        except Exception as e:
            return f"Error formatting status: {e}"
