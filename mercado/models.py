from django.db import models
from django.core.validators import MinValueValidator


class PlayerAccount(models.Model):
    name = models.CharField(max_length=80, unique=True)
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Resource(models.Model):
    DEMAND_HIGH = "ALTA"
    DEMAND_STABLE = "ESTABLE"
    DEMAND_LOW = "BAJA"

    TREND_UP = "SUBE"
    TREND_STABLE = "ESTABLE"
    TREND_DOWN = "BAJA"

    DEMAND_CHOICES = [
        (DEMAND_HIGH, "Alta"),
        (DEMAND_STABLE, "Estable"),
        (DEMAND_LOW, "Baja"),
    ]

    TREND_CHOICES = [
        (TREND_UP, "Sube"),
        (TREND_STABLE, "Estable"),
        (TREND_DOWN, "Baja"),
    ]

    name = models.CharField(max_length=60, unique=True)
    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    current_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    demand_status = models.CharField(
        max_length=10,
        choices=DEMAND_CHOICES,
        default=DEMAND_STABLE,
    )
    trend = models.CharField(
        max_length=10,
        choices=TREND_CHOICES,
        default=TREND_STABLE,
    )
    regression_a = models.FloatField(default=0)
    regression_b = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if self.current_price is None:
            self.current_price = self.base_price
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class PlayerResourceHolding(models.Model):
    player = models.ForeignKey(
        PlayerAccount,
        on_delete=models.CASCADE,
        related_name="resource_holdings",
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="player_holdings",
    )
    quantity = models.FloatField(validators=[MinValueValidator(0)], default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["player__name", "resource__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "resource"],
                name="unique_player_resource_holding",
            )
        ]

    def __str__(self):
        return f"{self.player.name} - {self.resource.name}: {self.quantity}"


class MoneyTransfer(models.Model):
    from_account = models.ForeignKey(
        PlayerAccount,
        on_delete=models.PROTECT,
        related_name="outgoing_transfers",
    )
    to_account = models.ForeignKey(
        PlayerAccount,
        on_delete=models.PROTECT,
        related_name="incoming_transfers",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(from_account=models.F("to_account")),
                name="avoid_self_transfer",
            ),
        ]

    def __str__(self):
        return f"{self.from_account} -> {self.to_account}: {self.amount}"


class ResourceTrade(models.Model):
    TRADE_BUY = "COMPRA"
    TRADE_SELL = "VENTA"

    TRADE_CHOICES = [
        (TRADE_BUY, "Compra"),
        (TRADE_SELL, "Venta"),
    ]

    player = models.ForeignKey(
        PlayerAccount,
        on_delete=models.PROTECT,
        related_name="resource_trades",
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,
        related_name="trades",
    )
    trade_type = models.CharField(max_length=10, choices=TRADE_CHOICES)
    quantity = models.FloatField(validators=[MinValueValidator(0.001)])
    effective_quantity = models.FloatField(default=0)
    turn_number = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    total_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    expected_demand = models.FloatField(default=0)
    delta_q = models.FloatField(default=0)
    adjustment_factor = models.FloatField(default=0.25)
    applied_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    regression_a_used = models.FloatField(default=0)
    regression_b_used = models.FloatField(default=0)
    model_recalculated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-turn_number", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "turn_number"],
                name="unique_turn_per_resource_new",
            )
        ]

    def __str__(self):
        return (
            f"{self.resource.name} turno {self.turn_number} - "
            f"{self.trade_type} {self.quantity}"
        )
