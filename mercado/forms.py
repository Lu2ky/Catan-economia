from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory

from .models import MoneyTransfer, PlayerAccount, Resource, ResourceTrade


class PlayerAccountForm(forms.ModelForm):
    class Meta:
        model = PlayerAccount
        fields = ["name", "balance"]
        labels = {
            "name": "Nombre del jugador",
            "balance": "Saldo inicial",
        }


class ResourceSetupForm(forms.Form):
    resource_name = forms.CharField(widget=forms.HiddenInput())
    base_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Precio base",
    )


ResourceSetupFormSet = formset_factory(ResourceSetupForm, extra=0)


def build_resource_setup_formset(data=None, initial=None, prefix=None):
    if data is not None:
        return ResourceSetupFormSet(data=data, prefix=prefix)
    return ResourceSetupFormSet(initial=initial, prefix=prefix)


class MoneyTransferForm(forms.ModelForm):
    class Meta:
        model = MoneyTransfer
        fields = ["from_account", "to_account", "amount", "description"]
        labels = {
            "from_account": "Jugador origen",
            "to_account": "Jugador destino",
            "amount": "Monto",
            "description": "Detalle (opcional)",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        player_queryset = PlayerAccount.objects.order_by("name")
        self.fields["from_account"].queryset = player_queryset
        self.fields["to_account"].queryset = player_queryset

    def clean(self):
        cleaned_data = super().clean()
        from_account = cleaned_data.get("from_account")
        to_account = cleaned_data.get("to_account")
        amount = cleaned_data.get("amount")

        if from_account and to_account and from_account.id == to_account.id:
            raise ValidationError("El origen y destino deben ser jugadores distintos.")

        if from_account and amount and amount > from_account.balance:
            raise ValidationError(
                f"Saldo insuficiente. {from_account.name} tiene ${from_account.balance}."
            )

        return cleaned_data


class ResourceTradeForm(forms.Form):
    player = forms.ModelChoiceField(
        queryset=PlayerAccount.objects.none(),
        label="Jugador",
    )
    resource = forms.ModelChoiceField(
        queryset=Resource.objects.none(),
        label="Recurso",
    )
    trade_type = forms.ChoiceField(
        choices=ResourceTrade.TRADE_CHOICES,
        label="Operacion",
    )
    quantity = forms.FloatField(
        min_value=0.001,
        label="Cantidad",
    )
    adjustment_factor = forms.FloatField(
        min_value=0,
        max_value=10,
        initial=0.25,
        label="Factor de ajuste k",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["player"].queryset = PlayerAccount.objects.order_by("name")
        self.fields["resource"].queryset = Resource.objects.order_by("name")


class HistoryFilterForm(forms.Form):
    player = forms.ModelChoiceField(
        queryset=PlayerAccount.objects.none(),
        required=False,
        empty_label="Todos los jugadores",
        label="Jugador",
    )
    resource = forms.ModelChoiceField(
        queryset=Resource.objects.none(),
        required=False,
        empty_label="Todos los recursos",
        label="Recurso",
    )
    trade_type = forms.ChoiceField(
        required=False,
        choices=[("", "Compra y venta")] + ResourceTrade.TRADE_CHOICES,
        label="Operacion",
    )
    min_turn = forms.IntegerField(
        required=False,
        min_value=1,
        label="Desde turno",
    )
    max_turn = forms.IntegerField(
        required=False,
        min_value=1,
        label="Hasta turno",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["player"].queryset = PlayerAccount.objects.order_by("name")
        self.fields["resource"].queryset = Resource.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        min_turn = cleaned_data.get("min_turn")
        max_turn = cleaned_data.get("max_turn")

        if min_turn and max_turn and min_turn > max_turn:
            raise forms.ValidationError("El turno inicial no puede ser mayor al turno final.")

        return cleaned_data
