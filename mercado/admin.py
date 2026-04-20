from django.contrib import admin
from .models import (
    MoneyTransfer,
    PlayerAccount,
    PlayerResourceHolding,
    Resource,
    ResourceTrade,
)


@admin.register(PlayerAccount)
class PlayerAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "balance", "updated_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(MoneyTransfer)
class MoneyTransferAdmin(admin.ModelAdmin):
    list_display = ("from_account", "to_account", "amount", "created_at")
    search_fields = ("from_account__name", "to_account__name", "description")
    list_filter = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "base_price",
        "current_price",
        "demand_status",
        "trend",
        "regression_a",
        "regression_b",
        "updated_at",
    )
    list_filter = ("demand_status", "trend")
    search_fields = ("name",)


@admin.register(PlayerResourceHolding)
class PlayerResourceHoldingAdmin(admin.ModelAdmin):
    list_display = ("player", "resource", "quantity", "updated_at")
    list_filter = ("resource",)
    search_fields = ("player__name", "resource__name")
    ordering = ("player__name", "resource__name")


@admin.register(ResourceTrade)
class ResourceTradeAdmin(admin.ModelAdmin):
    list_display = (
        "resource",
        "turn_number",
        "player",
        "trade_type",
        "quantity",
        "unit_price",
        "delta_q",
        "applied_price",
        "model_recalculated",
    )
    list_filter = ("resource", "trade_type", "model_recalculated")
    search_fields = ("resource__name", "player__name")
    ordering = ("-turn_number", "-id")
