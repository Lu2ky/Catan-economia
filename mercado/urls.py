from django.urls import path

from . import views

app_name = "mercado"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("configuracion/", views.setup_game, name="setup"),
    path("mercado/operacion/", views.market_trade_view, name="market_trade"),
    path("transferencias/nueva/", views.transfer_money_view, name="new_transfer"),
    path("turno/nuevo/", views.market_trade_view, name="register_turn"),
    path("historial/", views.history_view, name="history"),
    path("reglas/", views.formulas_view, name="rules"),
    path("formulas/", views.formulas_view, name="formulas"),
]
