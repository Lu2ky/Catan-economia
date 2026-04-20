from django.test import TestCase
from decimal import Decimal
from django.core.exceptions import ValidationError

from .models import MoneyTransfer, PlayerAccount, PlayerResourceHolding, Resource, ResourceTrade
from .services import register_resource_trade, register_transfer


class MoneyTransferServiceTests(TestCase):
    def setUp(self):
        self.player_a = PlayerAccount.objects.create(
            name="Jugador A",
            balance=Decimal("120.00"),
        )
        self.player_b = PlayerAccount.objects.create(
            name="Jugador B",
            balance=Decimal("35.00"),
        )

    def test_register_transfer_updates_both_balances(self):
        transfer = register_transfer(
            from_account=self.player_a,
            to_account=self.player_b,
            amount=Decimal("20.25"),
            description="Pago de recursos",
        )

        self.player_a.refresh_from_db()
        self.player_b.refresh_from_db()

        self.assertEqual(self.player_a.balance, Decimal("99.75"))
        self.assertEqual(self.player_b.balance, Decimal("55.25"))
        self.assertEqual(MoneyTransfer.objects.count(), 1)
        self.assertEqual(transfer.description, "Pago de recursos")

    def test_transfer_fails_with_insufficient_balance(self):
        with self.assertRaises(ValidationError):
            register_transfer(
                from_account=self.player_b,
                to_account=self.player_a,
                amount=Decimal("50.00"),
            )

        self.player_a.refresh_from_db()
        self.player_b.refresh_from_db()
        self.assertEqual(self.player_a.balance, Decimal("120.00"))
        self.assertEqual(self.player_b.balance, Decimal("35.00"))
        self.assertEqual(MoneyTransfer.objects.count(), 0)

    def test_transfer_fails_when_sender_equals_receiver(self):
        with self.assertRaises(ValidationError):
            register_transfer(
                from_account=self.player_a,
                to_account=self.player_a,
                amount=Decimal("10.00"),
            )

    def test_transfer_quantizes_to_two_decimals(self):
        register_transfer(
            from_account=self.player_a,
            to_account=self.player_b,
            amount=Decimal("10.005"),
        )

        self.player_a.refresh_from_db()
        self.player_b.refresh_from_db()
        self.assertEqual(self.player_a.balance, Decimal("109.99"))
        self.assertEqual(self.player_b.balance, Decimal("45.01"))


class MarketTradeServiceTests(TestCase):
    def setUp(self):
        self.player = PlayerAccount.objects.create(
            name="Jugador Mercado",
            balance=Decimal("200.00"),
        )
        self.resource = Resource.objects.create(
            name="Madera",
            base_price=Decimal("5.00"),
            current_price=Decimal("5.00"),
        )

    def test_buy_updates_balance_holding_and_price(self):
        self.resource.regression_a = 1.0
        self.resource.regression_b = 0.0
        self.resource.save()

        trade, _model_recalculated = register_resource_trade(
            player=self.player,
            resource=self.resource,
            trade_type=ResourceTrade.TRADE_BUY,
            quantity=3,
            adjustment_factor=0.5,
        )

        self.player.refresh_from_db()
        self.resource.refresh_from_db()
        holding = PlayerResourceHolding.objects.get(player=self.player, resource=self.resource)

        self.assertEqual(trade.turn_number, 1)
        self.assertEqual(self.player.balance, Decimal("185.00"))
        self.assertAlmostEqual(holding.quantity, 3.0, places=6)
        self.assertAlmostEqual(trade.expected_demand, 1.0, places=6)
        self.assertAlmostEqual(trade.delta_q, 2.0, places=6)
        self.assertEqual(self.resource.current_price, Decimal("6.00"))

    def test_sell_requires_inventory(self):
        with self.assertRaises(ValidationError):
            register_resource_trade(
                player=self.player,
                resource=self.resource,
                trade_type=ResourceTrade.TRADE_SELL,
                quantity=1,
                adjustment_factor=0.25,
            )

    def test_sell_reduces_price_when_effective_demand_drops(self):
        PlayerResourceHolding.objects.create(
            player=self.player,
            resource=self.resource,
            quantity=4,
        )
        self.resource.regression_a = 1.0
        self.resource.regression_b = 0.0
        self.resource.save()

        trade, _model_recalculated = register_resource_trade(
            player=self.player,
            resource=self.resource,
            trade_type=ResourceTrade.TRADE_SELL,
            quantity=2,
            adjustment_factor=0.5,
        )

        self.player.refresh_from_db()
        self.resource.refresh_from_db()
        holding = PlayerResourceHolding.objects.get(player=self.player, resource=self.resource)

        self.assertAlmostEqual(trade.effective_quantity, -2.0, places=6)
        self.assertAlmostEqual(trade.delta_q, -3.0, places=6)
        self.assertEqual(self.player.balance, Decimal("210.00"))
        self.assertAlmostEqual(holding.quantity, 2.0, places=6)
        self.assertEqual(self.resource.current_price, Decimal("3.50"))

    def test_recalculates_regression_every_five_turns(self):
        for quantity in [1, 2, 3, 4]:
            register_resource_trade(
                player=self.player,
                resource=self.resource,
                trade_type=ResourceTrade.TRADE_BUY,
                quantity=quantity,
                adjustment_factor=0.2,
            )

        trade, model_recalculated = register_resource_trade(
            player=self.player,
            resource=self.resource,
            trade_type=ResourceTrade.TRADE_BUY,
            quantity=5,
            adjustment_factor=0.2,
        )

        self.resource.refresh_from_db()
        self.assertEqual(trade.turn_number, 5)
        self.assertTrue(model_recalculated)
        self.assertTrue(trade.model_recalculated)
        self.assertNotEqual(self.resource.regression_b, 0.0)
