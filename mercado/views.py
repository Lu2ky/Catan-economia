from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render

from .forms import (
    HistoryFilterForm,
    MoneyTransferForm,
    PlayerAccountForm,
    ResourceTradeForm,
    build_resource_setup_formset,
)
from .models import MoneyTransfer, PlayerAccount, PlayerResourceHolding, Resource, ResourceTrade
from .services import (
    DEFAULT_RESOURCE_MARKET,
    ensure_default_resources,
    register_resource_trade,
    register_transfer,
)


def _has_players():
    return PlayerAccount.objects.exists()


def setup_game(request):
    ensure_default_resources()
    resources = {resource.name: resource for resource in Resource.objects.all()}

    player_form = PlayerAccountForm(prefix="player")
    initial_resource_rows = []
    for resource_name, default_price in DEFAULT_RESOURCE_MARKET.items():
        configured_resource = resources.get(resource_name)
        initial_resource_rows.append(
            {
                "resource_name": resource_name,
                "base_price": configured_resource.base_price if configured_resource else default_price,
            }
        )
    resource_formset = build_resource_setup_formset(
        initial=initial_resource_rows,
        prefix="resources",
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_player":
            player_form = PlayerAccountForm(request.POST, prefix="player")
            if player_form.is_valid():
                player = player_form.save()
                messages.success(
                    request,
                    f"Se creo la cuenta de {player.name} con saldo ${player.balance}.",
                )
                return redirect("mercado:setup")

        if action == "save_resources":
            resource_formset = build_resource_setup_formset(data=request.POST, prefix="resources")
            if resource_formset.is_valid():
                with transaction.atomic():
                    for form in resource_formset:
                        resource_name = form.cleaned_data["resource_name"]
                        base_price = form.cleaned_data["base_price"]
                        resource = resources[resource_name]
                        resource.base_price = base_price
                        if not resource.trades.exists():
                            resource.current_price = base_price
                            resource.demand_status = Resource.DEMAND_STABLE
                            resource.trend = Resource.TREND_STABLE
                            resource.regression_a = 0
                            resource.regression_b = 0
                        resource.save()

                messages.success(
                    request,
                    "Precios base de recursos actualizados correctamente.",
                )
                return redirect("mercado:setup")

    players = PlayerAccount.objects.order_by("name")
    return render(
        request,
        "mercado/setup.html",
        {
            "player_form": player_form,
            "resource_formset": resource_formset,
            "players": players,
            "resource_rows": list(zip(DEFAULT_RESOURCE_MARKET.keys(), resource_formset.forms)),
        },
    )


def dashboard(request):
    ensure_default_resources()

    if not _has_players():
        return redirect("mercado:setup")

    players = PlayerAccount.objects.order_by("name")
    resources = Resource.objects.order_by("name")
    holdings = PlayerResourceHolding.objects.select_related("player", "resource").filter(
        quantity__gt=0
    )
    recent_trades = ResourceTrade.objects.select_related("player", "resource")[:15]
    recent_transfers = MoneyTransfer.objects.select_related("from_account", "to_account")[:15]
    total_money = PlayerAccount.objects.aggregate(total=Sum("balance"))["total"] or 0

    return render(
        request,
        "mercado/dashboard.html",
        {
            "players": players,
            "resources": resources,
            "holdings": holdings,
            "recent_trades": recent_trades,
            "recent_transfers": recent_transfers,
            "total_players": players.count(),
            "total_transfers": MoneyTransfer.objects.count(),
            "total_market_ops": ResourceTrade.objects.count(),
            "total_money": total_money,
        },
    )


def market_trade_view(request):
    ensure_default_resources()

    if not _has_players():
        messages.error(request, "Primero crea al menos dos jugadores con saldo.")
        return redirect("mercado:setup")

    if request.method == "POST":
        form = ResourceTradeForm(request.POST)
        if form.is_valid():
            try:
                trade_record, model_recalculated = register_resource_trade(**form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                if model_recalculated:
                    messages.success(
                        request,
                        (
                            f"Operacion registrada en {trade_record.resource.name} "
                            f"(turno {trade_record.turn_number}). "
                            "Se recalculo la regresion del recurso."
                        ),
                    )
                else:
                    messages.success(
                        request,
                        (
                            f"Operacion registrada en {trade_record.resource.name} "
                            f"(turno {trade_record.turn_number})."
                        ),
                    )
                return redirect("mercado:dashboard")
    else:
        form = ResourceTradeForm()

    recent_trades = ResourceTrade.objects.select_related("player", "resource")[:10]
    return render(
        request,
        "mercado/turn_form.html",
        {
            "form": form,
            "recent_trades": recent_trades,
        },
    )


register_turn_view = market_trade_view


def transfer_money_view(request):
    if not _has_players():
        messages.error(request, "Primero crea al menos dos jugadores con saldo.")
        return redirect("mercado:setup")

    if request.method == "POST":
        form = MoneyTransferForm(request.POST)
        if form.is_valid():
            try:
                transfer = register_transfer(**form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(
                    request,
                    (
                        f"Transferencia registrada: {transfer.from_account.name} "
                        f"-> {transfer.to_account.name} por ${transfer.amount}."
                    ),
                )
                return redirect("mercado:dashboard")
    else:
        form = MoneyTransferForm()

    recent_transfers = MoneyTransfer.objects.select_related("from_account", "to_account")[:10]
    return render(
        request,
        "mercado/transfer_form.html",
        {
            "form": form,
            "recent_transfers": recent_transfers,
        },
    )


def history_view(request):
    ensure_default_resources()

    if not _has_players():
        return redirect("mercado:setup")

    trades = ResourceTrade.objects.select_related("player", "resource")
    filter_form = HistoryFilterForm(request.GET or None)

    if filter_form.is_valid():
        player = filter_form.cleaned_data.get("player")
        resource = filter_form.cleaned_data.get("resource")
        trade_type = filter_form.cleaned_data.get("trade_type")
        min_turn = filter_form.cleaned_data.get("min_turn")
        max_turn = filter_form.cleaned_data.get("max_turn")

        if player:
            trades = trades.filter(player=player)
        if resource:
            trades = trades.filter(resource=resource)
        if trade_type:
            trades = trades.filter(trade_type=trade_type)
        if min_turn:
            trades = trades.filter(turn_number__gte=min_turn)
        if max_turn:
            trades = trades.filter(turn_number__lte=max_turn)

    paginator = Paginator(trades, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "mercado/history.html",
        {
            "filter_form": filter_form,
            "page_obj": page_obj,
            "recent_transfers": MoneyTransfer.objects.select_related("from_account", "to_account")[:10],
        },
    )


def formulas_view(request):
    return render(request, "mercado/formulas.html")
