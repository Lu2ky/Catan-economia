from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg

from .models import (
    MoneyTransfer,
    PlayerAccount,
    PlayerResourceHolding,
    Resource,
    ResourceTrade,
)

MONEY_STEP = Decimal("0.01")
MIN_PRICE = Decimal("0.01")

DEFAULT_RESOURCE_MARKET = {
    "Madera": Decimal("5.00"),
    "Ladrillo": Decimal("5.00"),
    "Trigo": Decimal("5.00"),
    "Lana": Decimal("5.00"),
    "Mineral": Decimal("5.00"),
}


def _quantize_money(amount: Decimal) -> Decimal:
    return amount.quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


def ensure_default_resources():
    for name, base_price in DEFAULT_RESOURCE_MARKET.items():
        Resource.objects.get_or_create(
            name=name,
            defaults={
                "base_price": base_price,
                "current_price": base_price,
            },
        )


@transaction.atomic
def reset_game_state():
    """Reset the economy state to a clean game start."""
    ResourceTrade.objects.all().delete()
    MoneyTransfer.objects.all().delete()
    PlayerResourceHolding.objects.all().delete()
    PlayerAccount.objects.all().delete()

    default_resource_names = list(DEFAULT_RESOURCE_MARKET.keys())
    Resource.objects.exclude(name__in=default_resource_names).delete()
    ensure_default_resources()

    resources_by_name = {
        resource.name: resource
        for resource in Resource.objects.filter(name__in=default_resource_names)
    }

    for name, base_price in DEFAULT_RESOURCE_MARKET.items():
        resource = resources_by_name[name]
        resource.base_price = base_price
        resource.current_price = base_price
        resource.demand_status = Resource.DEMAND_STABLE
        resource.trend = Resource.TREND_STABLE
        resource.regression_a = 0
        resource.regression_b = 0
        resource.save(
            update_fields=[
                "base_price",
                "current_price",
                "demand_status",
                "trend",
                "regression_a",
                "regression_b",
                "updated_at",
            ]
        )


def simple_linear_regression(samples):
    if not samples:
        return 0.0, 0.0

    if len(samples) == 1:
        return float(samples[0][1]), 0.0

    x_mean = sum(price for price, _qty in samples) / len(samples)
    y_mean = sum(qty for _price, qty in samples) / len(samples)

    denominator = sum((price - x_mean) ** 2 for price, _qty in samples)
    if denominator == 0:
        return y_mean, 0.0

    numerator = sum((price - x_mean) * (qty - y_mean) for price, qty in samples)
    b_value = numerator / denominator
    a_value = y_mean - b_value * x_mean
    return a_value, b_value


def _classify_demand(delta_q: float) -> str:
    tolerance = 0.25
    if delta_q > tolerance:
        return Resource.DEMAND_HIGH
    if delta_q < -tolerance:
        return Resource.DEMAND_LOW
    return Resource.DEMAND_STABLE


def _classify_trend(old_price: Decimal, new_price: Decimal) -> str:
    if new_price > old_price:
        return Resource.TREND_UP
    if new_price < old_price:
        return Resource.TREND_DOWN
    return Resource.TREND_STABLE


def _expected_demand(resource: Resource, unit_price: Decimal, effective_quantity: float) -> float:
    has_regression_model = resource.regression_a != 0 or resource.regression_b != 0
    if has_regression_model:
        return resource.regression_a + resource.regression_b * float(unit_price)

    avg_effective_quantity = resource.trades.aggregate(avg_q=Avg("effective_quantity"))["avg_q"]
    if avg_effective_quantity is not None:
        return float(avg_effective_quantity)

    return float(effective_quantity)


def _recalculate_model_if_needed(resource: Resource, turn_number: int) -> bool:
    if turn_number % 5 != 0:
        return False

    samples = list(
        resource.trades.order_by("turn_number").values_list(
            "unit_price",
            "effective_quantity",
        )
    )
    if len(samples) < 2:
        return False

    normalized_samples = [(float(price), float(qty)) for price, qty in samples]
    a_value, b_value = simple_linear_regression(normalized_samples)

    resource.regression_a = a_value
    resource.regression_b = b_value
    resource.save(update_fields=["regression_a", "regression_b", "updated_at"])
    return True


@transaction.atomic
def register_transfer(
    from_account: PlayerAccount,
    to_account: PlayerAccount,
    amount,
    description: str = "",
):
    if from_account.id == to_account.id:
        raise ValidationError("No puedes transferir dinero al mismo jugador.")

    parsed_amount = _quantize_money(Decimal(str(amount)))
    if parsed_amount <= 0:
        raise ValidationError("El monto transferido debe ser mayor que cero.")

    account_ids = [from_account.id, to_account.id]
    accounts = {
        account.id: account
        for account in PlayerAccount.objects.select_for_update().filter(id__in=account_ids)
    }

    sender = accounts[from_account.id]
    receiver = accounts[to_account.id]

    if sender.balance < parsed_amount:
        raise ValidationError(
            f"Saldo insuficiente. {sender.name} solo tiene ${sender.balance}."
        )

    sender.balance = _quantize_money(sender.balance - parsed_amount)
    receiver.balance = _quantize_money(receiver.balance + parsed_amount)
    sender.save(update_fields=["balance", "updated_at"])
    receiver.save(update_fields=["balance", "updated_at"])

    transfer = MoneyTransfer.objects.create(
        from_account=sender,
        to_account=receiver,
        amount=parsed_amount,
        description=description.strip(),
    )
    return transfer


@transaction.atomic
def register_resource_trade(
    player: PlayerAccount,
    resource: Resource,
    trade_type: str,
    quantity: float,
    adjustment_factor: float,
):
    parsed_quantity = float(quantity)
    if parsed_quantity <= 0:
        raise ValidationError("La cantidad debe ser mayor que cero.")

    player_locked = PlayerAccount.objects.select_for_update().get(id=player.id)
    resource_locked = Resource.objects.select_for_update().get(id=resource.id)
    holding, _created = PlayerResourceHolding.objects.select_for_update().get_or_create(
        player=player_locked,
        resource=resource_locked,
        defaults={"quantity": 0},
    )

    unit_price = _quantize_money(resource_locked.current_price)
    total_value = _quantize_money(unit_price * Decimal(str(parsed_quantity)))

    if trade_type == ResourceTrade.TRADE_BUY:
        if player_locked.balance < total_value:
            raise ValidationError(
                f"Saldo insuficiente. {player_locked.name} tiene ${player_locked.balance}."
            )
        player_locked.balance = _quantize_money(player_locked.balance - total_value)
        holding.quantity += parsed_quantity
        effective_quantity = parsed_quantity
    elif trade_type == ResourceTrade.TRADE_SELL:
        if holding.quantity < parsed_quantity:
            raise ValidationError(
                (
                    f"Inventario insuficiente de {resource_locked.name}. "
                    f"Solo tienes {holding.quantity:.3f}."
                )
            )
        player_locked.balance = _quantize_money(player_locked.balance + total_value)
        holding.quantity -= parsed_quantity
        effective_quantity = -parsed_quantity
    else:
        raise ValidationError("Tipo de operacion no valido.")

    expected_demand = _expected_demand(resource_locked, unit_price, effective_quantity)
    delta_q = float(effective_quantity) - expected_demand

    current_price = _quantize_money(resource_locked.current_price)
    price_adjustment = Decimal(str(adjustment_factor)) * Decimal(str(delta_q))
    applied_price = _quantize_money(max(current_price + price_adjustment, MIN_PRICE))

    trend = _classify_trend(current_price, applied_price)
    demand_status = _classify_demand(delta_q)

    last_trade = resource_locked.trades.order_by("-turn_number").first()
    turn_number = 1 if last_trade is None else last_trade.turn_number + 1

    trade_record = ResourceTrade.objects.create(
        player=player_locked,
        resource=resource_locked,
        trade_type=trade_type,
        quantity=parsed_quantity,
        effective_quantity=effective_quantity,
        turn_number=turn_number,
        unit_price=unit_price,
        total_value=total_value,
        expected_demand=expected_demand,
        delta_q=delta_q,
        adjustment_factor=adjustment_factor,
        applied_price=applied_price,
        regression_a_used=resource_locked.regression_a,
        regression_b_used=resource_locked.regression_b,
    )

    player_locked.save(update_fields=["balance", "updated_at"])
    holding.save(update_fields=["quantity", "updated_at"])

    resource_locked.current_price = applied_price
    resource_locked.trend = trend
    resource_locked.demand_status = demand_status
    resource_locked.save(update_fields=["current_price", "trend", "demand_status", "updated_at"])

    model_recalculated = _recalculate_model_if_needed(resource_locked, turn_number)
    if model_recalculated:
        trade_record.model_recalculated = True
        trade_record.save(update_fields=["model_recalculated"])

    return trade_record, model_recalculated
