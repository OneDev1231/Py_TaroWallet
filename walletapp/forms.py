from zipfile import ZipFile

from ajax_select.fields import AutoCompleteSelectField

# from captcha.fields import CaptchaField
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django_recaptcha.fields import ReCaptchaField

from .const_utils import (
    get_fee_sat_estimate_exchange,
    get_fee_sat_estimate_lnd,
    get_fee_sat_estimate_onchain,
    get_max_withdrawal_lnd,
    get_max_withdrawal_onchain,
    get_min_exchange_sats,
)
from .models import Balances, Collections, Currencies, Listings, Transactions
from .utils import (
    check_alphanumeric,
    check_invoice_lnd,
    decode_btc_address,
    decode_invoice,
    decode_invoice_lnd,
)


class CreateUserForm(UserCreationForm):

    username = forms.CharField()

    password1 = forms.PasswordInput()

    password2 = forms.PasswordInput()

    captcha = ReCaptchaField()


class LoginForm(AuthenticationForm):
    captcha = ReCaptchaField()


class BalanceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(BalanceForm, self).__init__(*args, **kwargs)

        # allow for init
        if self.user:
            self.fields["currency"].queryset = self.user.get_currencies_dont_have()

    class Meta:
        model = Balances

        fields = ["currency"]


class CurrencyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(CurrencyForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Currencies

        fields = ["acronym", "asset_id", "universe_host", "picture_orig"]

        widgets = {
            "asset_id": forms.Textarea(attrs={"cols": 80, "rows": 3}),
        }

    def clean_universe_host(self):
        universe_host = self.cleaned_data["universe_host"]

        check_alphanumeric(universe_host)

        return universe_host

    def clean_asset_id(self):
        asset_id = self.cleaned_data["asset_id"]

        check_alphanumeric(asset_id)

        if Currencies.objects.filter(~Q(status="error"), asset_id=asset_id).exists():
            raise ValidationError(
                "A currency with this asset_id already exists in our records."
            )

        return asset_id

    def clean_name(self):
        name = self.cleaned_data["name"]

        if Currencies.objects.filter(name=name).exists():
            raise ValidationError(f"An asset with the name '{name}' already exists.")

        if name == "Bitcoin":
            raise ValidationError(
                "Please call your currency something else than Bitcoin"
            )
        return name


class TransactionReceiveTaroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)

        super(TransactionReceiveTaroForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Balances.objects.filter(
                ~Q(currency__name="Bitcoin"), user=self.user, currency__status="minted"
            )
        ]

    class Meta:
        model = Transactions

        fields = ["amount", "currency", "description"]

        widgets = {
            "description": forms.Textarea(attrs={"cols": 40, "rows": 3}),
        }

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description

    def clean_currency(self):
        currency = self.cleaned_data["currency"]

        if not currency:
            raise ValidationError("Please provide a value for currency.")

        return currency

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise ValidationError("Please enter amount larger than 0")

        return amount


class TransactionReceiveBtcForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(TransactionReceiveBtcForm, self).__init__(*args, **kwargs)

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description

    class Meta:
        model = Transactions

        fields = ["description"]

        widgets = {
            "description": forms.Textarea(attrs={"cols": 40, "rows": 3}),
        }


class TransactionReceiveBtcLndForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(TransactionReceiveBtcLndForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Transactions

        fields = ["description", "amount"]

        widgets = {
            "description": forms.Textarea(attrs={"cols": 40, "rows": 3}),
        }

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description


class TransactionSendTaroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(TransactionSendTaroForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Transactions

        fields = ["invoice_outbound"]

        widgets = {
            "invoice_outbound": forms.Textarea(attrs={"cols": 40, "rows": 1}),
        }

    def clean_invoice_outbound(self):
        invoice_outbound = self.cleaned_data["invoice_outbound"]

        if invoice_outbound is None:
            raise ValidationError(
                "The value you have provided is too short to be correct"
            )

        if invoice_outbound.startswith("tap"):
            try:
                invoice_outbound_dict = decode_invoice(invoice_outbound)

                asset_id = invoice_outbound_dict["asset_id"]

            except Exception as e:
                raise ValidationError(
                    "Cannot decode the invoice_outbound field: " + str(e)
                )

            if not Currencies.objects.filter(asset_id=asset_id).exists():
                raise ValidationError(
                    "Please register the currency"
                    f" '{asset_id['tag']}' for the supplied invoice"
                    f" with asset_id={asset_id}"
                )

            if Transactions.objects.filter(invoice_outbound=invoice_outbound).exists():
                raise ValidationError(f"This invoice already exists in our records.")

            # if Transactions.objects.filter(invoice_inbound=invoice_outbound).exists():
            #     raise ValidationError(f"This invoice already exists in our records.")

            amount = invoice_outbound_dict["amt"]

            currency = Currencies.objects.get(asset_id=asset_id)

            if not Balances.objects.filter(user=self.user, currency=currency).exists():
                raise ValidationError(
                    f"You do not have any {currency.name} in your wallet"
                )

            balance = self.user.get_balances(currency=currency).balance

            if amount > balance:
                raise ValidationError(
                    f"You do not have enough {currency.name} in your wallet. You want"
                    f" to pay {amount} {currency.acronym} while only having"
                    f" {balance} {currency.acronym}. "
                )

        else:
            raise ValidationError(
                "This is not a valid taro invoice. Cannot decode the address: "
                + invoice_outbound
                + " "
            )

        if get_fee_sat_estimate_onchain() >= self.user.get_btc_balance():
            raise ValidationError(
                "You do not have enough BTC balance to cover the on-chain fees that"
                f" are expected to be {get_fee_sat_estimate_onchain()} SAT"
            )

        return invoice_outbound


class TransactionSendBtcForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(TransactionSendBtcForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Transactions

        fields = ["invoice_outbound", "amount"]

        widgets = {
            "invoice_outbound": forms.Textarea(attrs={"cols": 40, "rows": 1}),
        }

    def clean_invoice_outbound(self):
        invoice_outbound = self.cleaned_data["invoice_outbound"]

        if invoice_outbound is None:
            raise ValidationError(
                "The value you have provided is too short to be correct"
            )

        try:
            decode_btc_address(str(invoice_outbound))

        except Exception as e:
            raise ValidationError(
                "Cannot decode the address: " + str(invoice_outbound) + " " + str(e)
            )

        return invoice_outbound

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount > get_max_withdrawal_onchain():
            self.add_error(
                "amount",
                "Please select an amount smaller than"
                f" {get_max_withdrawal_onchain()} SAT. This is a safety feature.",
            )

        if (
            get_fee_sat_estimate_onchain(amount) + amount
        ) > self.user.get_btc_balance():
            self.add_error(
                "amount",
                "You do not have enough BTC balance to cover the payment amount plus"
                " on-chain fees that are expected to be"
                f" {get_fee_sat_estimate_onchain(amount)} SAT + {amount} SAT ="
                f" {get_fee_sat_estimate_onchain(amount)+amount} SAT",
            )

        return amount

    def clean(self):
        cleaned_data = super(TransactionSendBtcForm, self).clean()

        amount = cleaned_data["amount"]

        if get_fee_sat_estimate_onchain(amount) + amount >= self.user.get_btc_balance():
            raise ValidationError(
                "You do not have enough BTC balance to cover the on-chain fees that"
                f" are expected to be {get_fee_sat_estimate_onchain(amount)} SAT plus"
                f" the amount {amount} SATs"
            )

        return cleaned_data


class TransactionSendBtcLndForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(TransactionSendBtcLndForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Transactions

        fields = ["invoice_outbound"]

        widgets = {
            "invoice_outbound": forms.Textarea(attrs={"cols": 40, "rows": 1}),
        }

    def clean_invoice_outbound(self):
        invoice_outbound = self.cleaned_data["invoice_outbound"]

        if invoice_outbound is None:
            raise ValidationError(
                "The value you have provided is too short to be correct"
            )

        try:
            check_invoice_lnd(invoice_outbound)

        except Exception as e:
            raise ValidationError(e)

        invoice_dict = decode_invoice_lnd(invoice_outbound)

        amount = invoice_dict["amount_sat"]

        if Transactions.objects.filter(invoice_outbound=invoice_outbound).exists():
            raise ValidationError(
                "This invoice already exists in our records. Please select a different"
                " one.",
            )

        if amount > get_max_withdrawal_lnd():
            raise ValidationError(
                f"Please select an amount smaller than {get_max_withdrawal_lnd()} SAT."
                " This is a safety feature.",
            )

        if amount <= 0:
            raise ValidationError(
                "Please submit and invoice with populated non-zero amount.",
            )

        if (get_fee_sat_estimate_lnd(amount) + amount) > self.user.get_btc_balance():
            raise ValidationError(
                "You do not have enough BTC balance to cover the payment amount plus"
                " on-chain fees that are expected to be"
                f" {get_fee_sat_estimate_onchain(amount)} SAT + {amount} SAT ="
                f" {get_fee_sat_estimate_onchain(amount)+amount} SAT",
            )

        return invoice_outbound


class TransactionSendInternalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(TransactionSendInternalForm, self).__init__(*args, **kwargs)
        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Balances.objects.filter(
                user=self.user, currency__status="minted", balance__gt=0
            )
        ]
        # allows for init
        if self.user:
            self.fields["destination_user"].choices = [
                (o.id, str(o.username))
                for o in User.objects.filter(~Q(id=self.user.id))
            ]
        else:
            self.fields["destination_user"].choices = []

    class Meta:
        model = Transactions

        fields = ["destination_user", "currency", "amount", "description"]

    destination_user = AutoCompleteSelectField("users", required=True)

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description

    def clean_currency(self):
        currency = self.cleaned_data["currency"]

        if not Balances.objects.filter(user=self.user, currency=currency).exists():
            raise ValidationError(
                "Please submit and invoice with populated non-zero amount.",
            )

        return currency

    def clean(self):
        cleaned_data = super(TransactionSendInternalForm, self).clean()
        amount = cleaned_data["amount"]
        currency = cleaned_data["currency"]

        balance = self.user.get_balances(currency=currency).balance

        if (amount > balance) or (amount <= 0):
            self.add_error(
                "amount",
                f"Please provide amount smaller than {balance} and larger than 0",
            )

        return cleaned_data


class FaucetSendForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.currency_id = kwargs.pop("currency_id", None)
        super(FaucetSendForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Transactions

        fields = ["invoice_outbound"]

        widgets = {
            "invoice_outbound": forms.Textarea(attrs={"cols": 40, "rows": 1}),
        }

    def clean_invoice_outbound(self):
        invoice_outbound = self.cleaned_data["invoice_outbound"]

        if len(invoice_outbound) < 10:
            raise ValidationError(
                "The address: '" + invoice_outbound + "' is too short" + str(e)
            )

        try:
            invoice_outbound_dict = decode_invoice(invoice_outbound)

        except Exception as e:
            raise ValidationError(
                "Cannot decode the address: " + str(invoice_outbound) + " " + str(e)
            )

        if not invoice_outbound.startswith("tap"):
            raise ValidationError(
                f"Please submit a valid Taproot Asset invoice starting with 'tap'."
            )

        else:
            if invoice_outbound_dict["amt"] > 100:
                raise ValidationError(
                    f"Please submit a Taproot Asset invoice for amount smaller or equal"
                    f" than 100."
                )
        currency = Currencies.objects.get(id=self.currency_id)
        asset_id = currency.asset_id
        asset_name = currency.name

        if not invoice_outbound_dict["asset_id"] == asset_id:
            raise ValidationError(
                f"Asset id from provided asset_id '{invoice_outbound_dict['asset_id']}'"
                f" does not match the asset '{asset_name}' id '{asset_id}'"
            )

        return invoice_outbound


class CurrencyMintForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(CurrencyMintForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]

        if name == "Bitcoin":
            raise ValidationError(
                "Please call your currency something else than Bitcoin"
            )

        return name

    def clean(self):
        cleaned_data = super(CurrencyMintForm, self).clean()

        if (get_fee_sat_estimate_onchain()) > self.user.get_btc_balance():
            self.add_error(
                "supply",
                "You do not have enough BTC balance to cover the on-chain fees that"
                f" are expected to be {get_fee_sat_estimate_onchain()} SAT",
            )

        return cleaned_data

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description

    class Meta:
        model = Currencies

        fields = ["acronym", "name", "description", "supply", "picture_orig"]

        widgets = {
            "description": forms.Textarea(attrs={"cols": 40, "rows": 3}),
        }


class CurrencyMintMultipleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(CurrencyMintMultipleForm, self).__init__(*args, **kwargs)

    # file_field = forms.FileField(
    #     widget=forms.ClearableFileInput(attrs={"multiple": True})
    # )

    # file_field = forms.FileField()

    def clean(self):
        cleaned_data = super(CurrencyMintMultipleForm, self).clean()

        if (get_fee_sat_estimate_onchain()) > self.user.get_btc_balance():
            self.add_error(
                "name",
                "You do not have enough BTC balance to cover the on-chain fees that"
                f" are expected to be {get_fee_sat_estimate_onchain()} SAT",
            )

        return cleaned_data

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description

    def clean_images_zip_file(self):
        images_zip_file = self.cleaned_data["images_zip_file"]

        found = False
        try:
            # with open(collection_zip_file, "rb") as f:
            with ZipFile(images_zip_file) as myzipfile:
                for name in myzipfile.namelist():
                    if name.split(".")[0].isnumeric() and name.split(".")[1] in [
                        "jpeg",
                        "jpg",
                        "png",
                        "bmp",
                    ]:
                        found = True
        except Exception as e:
            raise ValidationError(
                f"The .zip file that you have submitted cannot be processed. Please"
                f" provide a valid zip file."
            )

        if not found:
            raise ValidationError(
                f"No jpeg, jpg, png or bmp image files were found that would have"
                f" numbers as their filename e.g. 1.jpg, 2.jpg, etc !"
            )

        return images_zip_file

    class Meta:
        model = Collections

        fields = ["name", "description", "images_zip_file"]


class NftMintForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(NftMintForm, self).__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"]

        if Currencies.objects.filter(name=name).exists():
            raise ValidationError(f"An asset with the name '{name}' already exists.")

        if name == "Bitcoin":
            raise ValidationError(
                "Please call your currency something else than Bitcoin"
            )

        return name

    def clean(self):
        cleaned_data = super(NftMintForm, self).clean()

        if (get_fee_sat_estimate_onchain()) > self.user.get_btc_balance():
            self.add_error(
                "name",
                "You do not have enough BTC balance to cover the on-chain fees that"
                f" are expected to be {get_fee_sat_estimate_onchain()} SAT",
            )

        return cleaned_data

    def clean_description(self):
        description = self.cleaned_data["description"]

        check_alphanumeric(description)

        return description

    class Meta:
        model = Currencies

        fields = ["name", "description", "picture_orig"]

        widgets = {
            "description": forms.Textarea(attrs={"cols": 40, "rows": 3}),
        }


class ListingCurrencyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(ListingCurrencyForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Balances.objects.filter(
                user=self.user,
                balance__gt=0,
                currency__owner=self.user,
                currency__status="minted",
                currency__is_nft=False,
            )
            if o.currency
        ]

    class Meta:
        model = Listings

        fields = ["currency"]

    def clean_currency(self):
        currency = self.cleaned_data["currency"]

        if Listings.objects.filter(currency=currency, type="lp").exists():
            raise ValidationError(f"The currency {currency.name} is already listed.")

        if Listings.objects.filter(
            user=self.user, type="lp", currency__is_nft=False
        ).exists():
            raise ValidationError(f"You have already listed a currency.")

        return currency


class ListingOrderCurrencyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(ListingOrderCurrencyForm, self).__init__(*args, **kwargs)

        self.fields["type"].choices = [
            ("order_bid", "Offering SATs for currency"),
            ("order_ask", "Asking for amount in exchange for currency"),
        ]

        self.fields["currency"].choices = [
            (o.id, str(o.name))
            for o in Currencies.objects.filter(
                status="minted",
                is_nft=False,
            )
        ]

    class Meta:
        model = Listings

        fields = ["type", "currency", "amount", "price_sat"]

    def clean(self):
        cleaned_data = super(ListingOrderCurrencyForm, self).clean()
        amount = cleaned_data["amount"]
        currency = cleaned_data["currency"]
        type = cleaned_data["type"]
        price_sat = cleaned_data["price_sat"]

        if self.user == currency.owner:
            self.add_error(
                "currency",
                f"You cannot bid on your own asset {currency.acronym}.",
            )

        if type == "order_ask":
            if Listings.objects.filter(
                user=self.user, currency=currency, type="order_ask"
            ).exists():
                self.add_error(
                    "currency",
                    "You have already created an ask for the currency"
                    f" {currency.name}.",
                )

            if Balances.objects.filter(user=self.user, currency=currency).exists():
                bal = Balances.objects.get(user=self.user, currency=currency).balance
                if bal < amount:
                    self.add_error(
                        "amount",
                        "You can only ask for SATs for the maximum of"
                        f" {bal} {currency.acronym}.",
                    )
            else:
                self.add_error(
                    "amount",
                    f"You do not have any {currency.name} to ask for SATs in exchange.",
                )

        elif type == "order_bid":
            if Listings.objects.filter(
                user=self.user, currency=currency, type="order_bid"
            ).exists():
                self.add_error(
                    "currency",
                    f"You have already created a bid for the currency {currency.name}.",
                )

            bal = self.user.get_btc_balance()
            if bal < int(amount * price_sat):
                self.add_error(
                    "amount",
                    f"You are trying to bid {amount*price_sat} SATs for"
                    f" {amount} {currency.acronym} cannot bid more than {bal} SATs.",
                )

        else:
            raise Exception(f"Incorrect type '{type}'")

        if int(amount * price_sat) < 10:
            self.add_error(
                "amount",
                "The total amount of SATs you bid/ask has to be at least 10 SATs. You"
                f" are asking {int(amount*price_sat)} SATs.",
            )

        return cleaned_data


class ListingOrderNftForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(ListingOrderNftForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.id, str(o.name))
            for o in Currencies.objects.filter(
                status="minted",
                is_nft=True,
            )
        ]

    class Meta:
        model = Listings

        fields = ["currency", "price_sat"]

    def clean(self):
        cleaned_data = super(ListingOrderNftForm, self).clean()
        currency = cleaned_data["currency"]
        price_sat = cleaned_data["price_sat"]

        if (
            self.user == currency.owner
            or Balances.objects.filter(
                user=self.user, currency=currency, balance__gt=0
            ).exists()
        ):
            self.add_error(
                "currency",
                f"You cannot bid on the asset {currency.name} because you either minted"
                " it or currently own it.",
            )

        if Listings.objects.filter(
            user=self.user, currency=currency, type="order_bid"
        ).exists():
            self.add_error(
                "currency",
                f"You have already created a bid for the currency {currency.name}.",
            )

        bal = self.user.get_btc_balance()
        if bal < (price_sat):
            self.add_error(
                "price_sat",
                f"You are trying to bid {price_sat} SATs for {currency.name} cannot bid"
                f" more than {bal} SATs..",
            )

        if price_sat == 0:
            self.add_error(
                "price_sat",
                f"Please select a value larger than 0.",
            )

        return cleaned_data


class ListingNftForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(ListingNftForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Balances.objects.filter(
                user=self.user,
                balance__gt=0,
                currency__status="minted",
                currency__is_nft=True,
            )
        ]

    class Meta:
        model = Listings

        fields = ["currency", "price_sat"]

    def clean_currency(self):
        currency = self.cleaned_data["currency"]

        if Listings.objects.filter(currency=currency, type="lp").exists():
            raise ValidationError(f"The currency {currency.name} is already listed.")

        return currency

    def clean_price_sat(self):
        price_sat = self.cleaned_data["price_sat"]

        if price_sat <= 1:
            raise ValidationError(f"Please select a value larger than 0.")

        return price_sat


class CreateExchangeTransactionBuyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(CreateExchangeTransactionBuyForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Listings.objects.filter(
                ~Q(user=self.user),
                # currency__is_nft=False,
            )
        ]

    class Meta:
        model = Transactions

        fields = ["currency", "amount"]

    def clean(self):
        cleaned_data = super(CreateExchangeTransactionBuyForm, self).clean()
        amount = cleaned_data["amount"]
        currency = cleaned_data["currency"]

        listing = Listings.objects.get(currency=currency, type="lp")

        max_available = int(
            Balances.objects.get(user=listing.user, currency=currency).balance / 4
        )

        if amount >= max_available:
            self.add_error(
                "amount",
                "Please enter an amount smaller than"
                f" {max_available} {currency.acronym} as you can only buy an amount"
                " smaller than 1/4 of whats in the LP.",
            )
        else:
            transaction_fee = get_fee_sat_estimate_exchange(
                amount * listing.get_price_sat(-amount)
            )

            min_purchase_to_be_10_sats = max(
                int(get_min_exchange_sats() / listing.get_price_sat(-amount)), 1
            )

            if amount < min_purchase_to_be_10_sats:
                self.add_error(
                    "amount",
                    f"Please purchase at least the amount {min_purchase_to_be_10_sats}."
                    "  This is to ensure the amount exchanges to at least"
                    f" {get_min_exchange_sats()} SATs",
                )

            if self.user.get_btc_balance() < transaction_fee:
                self.add_error(
                    "amount",
                    f"Your BTC balance {self.user.get_btc_balance()} SAT is too low to"
                    " pay"
                    f" {get_fee_sat_estimate_exchange(amount * listing.get_price_sat(-amount))} SAT"
                    f" for {amount}  the transaction fee.",
                )
            max_purchase = int(
                (self.user.get_btc_balance() - transaction_fee)
                / listing.get_price_sat(-amount)
            )
            if max_purchase <= 0:
                max_purchase = 0

            if amount > max_purchase:
                self.add_error(
                    "amount",
                    f"Your BTC balance {self.user.get_btc_balance()} SAT is too low to"
                    f" pay {amount * listing.get_price_sat(-amount)} SAT for"
                    f" {amount} {currency.acronym} and the transaction fee"
                    f" {transaction_fee} SAT. You can afford to buy"
                    f" {max_purchase} {currency.acronym} at the current rate"
                    f" {listing.get_price_sat(-amount)} / 1 {currency.acronym}",
                )

        return cleaned_data


class CreateExchangeTransactionSellForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(CreateExchangeTransactionSellForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Listings.objects.filter(
                ~Q(user=self.user),
                currency__is_nft=False,
            )
        ]

    class Meta:
        model = Transactions

        fields = ["currency", "amount"]

    def clean(self):
        cleaned_data = super(CreateExchangeTransactionSellForm, self).clean()
        amount = cleaned_data["amount"]
        currency = cleaned_data["currency"]

        listing = Listings.objects.get(currency=currency, type="lp")

        bal_btc = listing.user.get_btc_balance()

        max_available_lp = Balances.objects.get(
            user=listing.user, currency=currency
        ).balance

        max_available = Balances.objects.get(user=self.user, currency=currency).balance

        # if self.user.get_btc_balance() < get_fee_sat_estimate_exchange(amount):
        #     self.add_error(
        #         "amount",
        #         "You do not have enough to pay"
        #         f" {get_fee_sat_estimate_exchange(amount)} SATs for the transaction"
        #         " fee.",
        #     )

        if amount > max_available:
            self.add_error(
                "amount",
                f"You only have {max_available} {currency.acronym}. Please enter an"
                " amount smaller than that.",
            )

        max_purchase = int(max_available_lp / 4)

        if amount > max_purchase:
            self.add_error(
                "amount",
                f"Please enter an amount larger than 0 {currency.acronym} and smaller"
                f" than {max_purchase} {currency.acronym} "
                " as you can only buy an amount smaller than 1/4 of whats in the LP.",
            )
        else:
            min_purchase_to_be_10_sats = (
                int(get_min_exchange_sats() / listing.get_price_sat(amount)) + 1
            )

            if amount < min_purchase_to_be_10_sats:
                self.add_error(
                    "amount",
                    "Please purchase at least the amount"
                    f" {min_purchase_to_be_10_sats}.This is to ensure you are paying at"
                    f" least {get_min_exchange_sats()} SATs",
                )

        return cleaned_data


class CreateExchangeTransactionBuyNftForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super(CreateExchangeTransactionBuyNftForm, self).__init__(*args, **kwargs)

        self.fields["currency"].choices = [
            (o.currency.id, str(o.currency))
            for o in Listings.objects.filter(
                ~Q(user=self.user),
                currency__is_nft=True,
            )
        ]

    class Meta:
        model = Transactions

        fields = ["currency"]

    def clean(self):
        cleaned_data = super(CreateExchangeTransactionBuyNftForm, self).clean()

        listing = Listings.objects.get(currency=cleaned_data["currency"])

        if self.user.get_btc_balance() < listing.price_sat:
            self.add_error(
                "currency",
                f"You do not have the required {listing.price_sat} SAT to buy"
                f" {listing.currency.name}",
            )

        return cleaned_data
