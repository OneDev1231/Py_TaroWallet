import datetime
import io
import json

import qrcode
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin

# Create your views here.
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView

from .const_utils import get_fee_sat_estimate_exchange
from .forms import (
    BalanceForm,
    CreateExchangeTransactionBuyForm,
    CreateExchangeTransactionBuyNftForm,
    CreateExchangeTransactionSellForm,
    CreateUserForm,
    CurrencyForm,
    CurrencyMintForm,
    CurrencyMintMultipleForm,
    FaucetSendForm,
    ListingCurrencyForm,
    ListingNftForm,
    ListingOrderCurrencyForm,
    ListingOrderNftForm,
    LoginForm,
    NftMintForm,
    TransactionReceiveBtcForm,
    TransactionReceiveBtcLndForm,
    TransactionReceiveTaroForm,
    TransactionSendBtcForm,
    TransactionSendBtcLndForm,
    TransactionSendInternalForm,
    TransactionSendTaroForm,
)
from .models import (
    Balances,
    Collections,
    Currencies,
    Listings,
    Notifications,
    PriceHistory,
    Transactions,
    mark_notifications_as_read,
)
from .preview_utils import (
    collection_card,
    collection_gif,
    currency_card,
    draw_week_chart,
)
from .utils import decode_invoice, decode_invoice_lnd, get_currency_btc, get_wash_users


def index(request):
    """View function for home page of site."""

    try:
        user = User.objects.get(username="faucet_user_1")

        faucet_balances = Balances.objects.filter(
            ~Q(currency__name="Bitcoin"),
            user=user,
            balance__gt=0,
            currency__is_nft=False,
        )
        faucet_currencies = [b.currency for b in faucet_balances]
        faucet_nft_balances = Balances.objects.filter(
            user=user, balance__gt=0, currency__is_nft=True
        )
        nft_asset_list = [b.currency for b in faucet_nft_balances]

        if nft_asset_list:
            nft_asset = nft_asset_list[0]
        else:
            nft_asset = None

        num_wallets = Balances.objects.all().count()
        num_transactions = Transactions.objects.all().count()

    except Exception as e:
        print(e)
        print("error getting faucet currencies")
        faucet_currencies = []
        nft_asset = None

    context = {
        "faucet_currencies": faucet_currencies,
        "nft_asset": nft_asset,
        "num_wallets": num_wallets,
        "num_transactions": num_transactions,
    }

    # Render the HTML template index.html with the data in the context variable
    return render(request, "index.html", context=context)


class PublicCurrencyListView(ListView):
    model = Currencies
    context_object_name = (  # your own name for the list as a template variable
        "currencies_list"
    )
    template_name = "currencies.html"
    paginate_by = 4 * 20

    def get_queryset(self):

        asset_type = self.request.GET.get("asset_type")
        collection = self.request.GET.get("collection")

        if asset_type == "nft":

            if collection:
                return Currencies.objects.filter(
                    status="minted", collection__name=collection, is_nft=True
                )
            else:
                return Currencies.objects.filter(status="minted", is_nft=True)
        else:

            return Currencies.objects.filter(
                ~Q(name="Bitcoin"), status="minted", is_nft=False
            )

    def get_form_kwargs(self):
        kwargs = super(PublicCurrencyListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(PublicCurrencyListView, self).get_context_data(**kwargs)

        ctx["asset_type"] = self.request.GET.get("asset_type", "")
        ctx["preview_type"] = self.request.GET.get("preview_type", "")
        collection_name = self.request.GET.get("collection", "")

        if collection_name:
            ctx["collection"] = Collections.objects.get(name=collection_name)
        else:
            ctx["collection"] = None

        return ctx


class PublicCollectionsListView(ListView):
    model = Collections
    context_object_name = (  # your own name for the list as a template variable
        "collections_list"
    )
    template_name = "collections.html"
    paginate_by = 3 * 20

    def get_queryset(self):

        return Collections.objects.filter(status="minted")


class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    form_class = LoginForm


class UserCreate(CreateView):
    model = User
    form_class = CreateUserForm
    # fields = ['username', 'email', 'password']
    success_url = reverse_lazy("login")

    # def form_valid(self, form):

    #     try:
    #         # currency_bitcoin = Currencies.objects.filter(name='Bitcoin').first()
    #         # bitcoin_balance = Balances.objects.create(currency=currency_bitcoin, balance=30000)
    #         # bitcoin_balance.save()

    #         currency_adambucks = Currencies.objects.filter(name='adambucks').first()
    #         adambucks_balance = Balances.objects.create(currency=currency_adambucks,user=self.request.user, balance=10)
    #         adambucks_balance.save()
    #     except Exception as e:
    #         raise ValueError(e)

    #     return super().form_valid(form)


@method_decorator(login_required(login_url="login"), name="dispatch")
class AssetCreate(CreateView):
    model = Currencies
    form_class = CurrencyForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.name = form.instance.asset_id[0:10]
        form.instance.status = "waiting_for_create_transaction"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(AssetCreate, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class CurrencyMint(CreateView):
    model = Currencies
    form_class = CurrencyMintForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/currencies_mint.html"

    def form_valid(self, form):
        form.instance.genesis_bootstrap_info = "placeholder_" + form.instance.name
        form.instance.owner = self.request.user
        form.instance.status = "waiting_for_miting_transaction"
        form.instance.is_nft = False

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(CurrencyMint, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class CurrencyMintMultiple(CreateView):
    model = Collections
    form_class = CurrencyMintMultipleForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/currencies_mint_multiple.html"

    def form_valid(self, form):

        form.instance.status = "waiting_for_miting_transaction"
        form.instance.owner = self.request.user

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(CurrencyMintMultiple, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_success_url(self):
        return reverse_lazy("collection-detail", args=[str(self.object.id)])


@method_decorator(login_required(login_url="login"), name="dispatch")
class CollectionDetailView(DetailView):
    model = Collections

    def dispatch(self, *args, **kwargs):
        currs = Currencies.objects.filter(collection=self.get_object())
        if currs:
            if currs[0].status not in ["minted"]:
                return redirect(currs[0].minting_transaction.get_absolute_url())

        return redirect(
            reverse_lazy("currencies-nfts") + "?collection=" + self.get_object().name
        )


@method_decorator(login_required(login_url="login"), name="dispatch")
class NftMint(CreateView):
    model = Currencies
    form_class = NftMintForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/currencies_nft_mint.html"

    def form_valid(self, form):
        form.instance.genesis_bootstrap_info = "placeholder_" + form.instance.name
        form.instance.owner = self.request.user
        form.instance.status = "waiting_for_miting_transaction"
        form.instance.is_nft = True
        form.instance.supply = 1

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(NftMint, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class CurrencyListView(ListView):
    model = Currencies
    context_object_name = (  # your own name for the list as a template variable
        "currencies_list"
    )
    template_name = "walletapp/currencies_list.html"
    paginate_by = 12

    def get_queryset(self):
        return Currencies.objects.filter(status="minted", is_nft=False)

    def get_form_kwargs(self):
        kwargs = super(CurrencyListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class CollectionsListView(ListView):
    model = Collections
    context_object_name = (  # your own name for the list as a template variable
        "collections_list"
    )
    template_name = "walletapp/collections_list.html"
    paginate_by = 12

    def get_queryset(self):
        return Collections.objects.all()

    def get_form_kwargs(self):
        kwargs = super(CollectionsListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class NFTListView(ListView):
    model = Currencies
    context_object_name = (  # your own name for the list as a template variable
        "currencies_list"
    )
    template_name = "walletapp/currencies_nfts_list.html"
    paginate_by = 12

    def get_queryset(self):
        collection = self.request.GET.get("collection")
        if collection:
            collection = Collections.objects.get(name=collection)
            return collection.get_assets()

        return Currencies.objects.filter(status="minted", is_nft=True)

    def get_context_data(self, **kwargs):
        ctx = super(NFTListView, self).get_context_data(**kwargs)

        collection = self.request.GET.get("collection")
        if collection:
            collection = Collections.objects.get(name=collection)
            ctx["collection"] = collection

        return ctx


class AssetDetailPublicView(DetailView):
    model = Currencies

    template_name = "walletapp/currencies_detail_public.html"

    def dispatch(self, *args, **kwargs):
        currency = self.get_object()
        if currency.status != "minted":
            return redirect(currency.minting_transaction.get_absolute_url())

        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(AssetDetailView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class AssetDetailView(DetailView):
    model = Currencies

    def dispatch(self, *args, **kwargs):
        currency = self.get_object()
        mark_notifications_as_read("Currencies", currency, self.request.user)
        if currency.status not in ["minted"]:
            return redirect(currency.minting_transaction.get_absolute_url())

        return super().dispatch(*args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(AssetDetailView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(AssetDetailView, self).get_context_data(**kwargs)

        message = None
        if "message" in self.request.session:
            message = self.request.session["message"]
            del self.request.session["message"]
            messages.success(self.request, message)
            ctx["message"] = message

        period = self.request.GET.get("period")
        if period:
            ctx["period"] = period
        else:
            ctx["period"] = "1m"

        return ctx


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionSendBtc(CreateView):
    model = Transactions

    form_class = TransactionSendBtcForm

    template_name = "walletapp/transactions_send_btc.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        form.instance.currency = Currencies.objects.filter(name="Bitcoin").first()

        form.instance.direction = "outbound"
        form.instance.type = "user"
        form.instance.status = "outbound_invoice_received"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionSendBtc, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionSendBtcLnd(CreateView):
    model = Transactions

    form_class = TransactionSendBtcLndForm

    template_name = "walletapp/transactions_send_btc_lnd.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        invoice_dict = decode_invoice_lnd(form.instance.invoice_outbound)

        form.instance.currency = Currencies.objects.filter(name="Bitcoin").first()

        form.instance.direction = "outbound"
        form.instance.type = "user"
        form.instance.amount = invoice_dict["amount_sat"]
        form.instance.status = "lnd_outbound_invoice_received"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionSendBtcLnd, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionSendTaroCurrency(CreateView):
    model = Transactions

    form_class = TransactionSendTaroForm

    template_name = "walletapp/transactions_send_taro.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        invoice_dict = decode_invoice(form.instance.invoice_outbound)
        asset_id = invoice_dict["asset_id"]
        form.instance.amount = invoice_dict["amt"]

        form.instance.currency = Currencies.objects.filter(asset_id=asset_id).first()

        # invoice exists, do user-to-user
        if Transactions.objects.filter(
            invoice_inbound=form.instance.invoice_outbound
        ).exists():
            transaction = Transactions.objects.get(
                invoice_inbound=form.instance.invoice_outbound
            )

            form.instance.invoice_outbound = None
            form.instance.destination_user = transaction.user
            form.instance.direction = "outbound"
            form.instance.type = "internal"
            form.instance.status = "internal_stated"
            form.instance.description = (
                transaction.description
                + "(originally sent to taro invoice, converted to internal transaction)"
            )
            print(f"replacing transaction {transaction}...")
            response = super().form_valid(form)

            transaction.status = "replaced_with_internal_transaction"
            transaction.status_description = f"replacing transaction {self.object.pk}"
            transaction.save()
            print(f"Transaction {transaction} finished...")
            return response

        form.instance.direction = "outbound"
        form.instance.type = "user"
        form.instance.status = "outbound_invoice_received"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionSendTaroCurrency, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(TransactionSendTaroCurrency, self).get_context_data(**kwargs)

        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            ctx["currency"] = currency

        return ctx


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionSendInternal(CreateView):
    model = Transactions

    form_class = TransactionSendInternalForm

    template_name = "walletapp/transactions_send_internal.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        form.instance.direction = "outbound"
        form.instance.type = "internal"
        form.instance.status = "internal_stated"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionSendInternal, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionReceiveTaro(CreateView):
    model = Transactions
    form_class = TransactionReceiveTaroForm

    template_name = "walletapp/transactions_receive_taro.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        form.instance.direction = "inbound"

        form.instance.type = "user"

        form.instance.status = "inbound_invoice_waiting_for"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionReceiveTaro, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            return {
                "currency": currency,
            }
        else:
            return {}


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionReceiveBtc(CreateView):
    model = Transactions
    form_class = TransactionReceiveBtcForm

    template_name = "walletapp/transactions_receive_btc.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        form.instance.direction = "inbound"
        form.instance.currency = get_currency_btc()
        form.instance.type = "user"
        form.instance.status = "inbound_invoice_waiting_for"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionReceiveBtc, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            return {
                "currency": currency,
            }
        else:
            return {}


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionReceiveBtcLnd(CreateView):
    model = Transactions
    form_class = TransactionReceiveBtcLndForm

    template_name = "walletapp/transactions_receive_btc_lnd.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        form.instance.direction = "inbound"
        form.instance.currency = get_currency_btc()
        form.instance.type = "user"
        form.instance.status = "lnd_inbound_invoice_waiting_for"

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(TransactionReceiveBtcLnd, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            return {
                "currency": currency,
            }
        else:
            return {}


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionListView(ListView):
    model = Transactions
    fields = ["amount", "currency", "status", "updated_timestamp"]
    context_object_name = (  # your own name for the list as a template variable
        "transactions_list"
    )
    paginate_by = 5

    def get_queryset(self):
        return Transactions.objects.filter(
            Q(user=self.request.user) | Q(destination_user=self.request.user),
            ~Q(user__in=get_wash_users()),
        )

    def get_form_kwargs(self):
        kwargs = super(TransactionListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


class TransactionOwnerMixin(UserPassesTestMixin):
    def test_func(self):
        obj = self.get_object()
        return (obj.user == self.request.user) | (
            obj.destination_user == self.request.user
        )


@method_decorator(login_required(login_url="login"), name="dispatch")
class TransactionDetailView(TransactionOwnerMixin, DetailView):
    model = Transactions

    def dispatch(self, *args, **kwargs):
        transaction = self.get_object()
        mark_notifications_as_read("Transactions", transaction, self.request.user)

        return super().dispatch(*args, **kwargs)


@method_decorator(login_required(login_url="login"), name="dispatch")
class BalanceListView(ListView):
    model = Balances
    fields = ["currency", "balance"]
    template_name = "walletapp/balances_list.html"
    context_object_name = "balances_list"
    paginate_by = 12

    def get_queryset(self):
        return Balances.objects.filter(
            user=self.request.user, currency__is_nft=False, currency__status="minted"
        )

    def get_form_kwargs(self):
        kwargs = super(BalanceListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class NftListView(ListView):
    model = Balances
    fields = ["currency", "balance"]
    template_name = "walletapp/balances_nft_list.html"
    context_object_name = "balances_list"
    paginate_by = 12

    def get_queryset(self):
        return Balances.objects.filter(
            user=self.request.user,
            currency__is_nft=True,
            currency__status="minted",
            balance__gt=0,
        )

    def get_form_kwargs(self):
        kwargs = super(BalanceListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class BalanceCreateView(CreateView):
    model = Balances
    form_class = BalanceForm

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.balance = 0

        return super().form_valid(form)

    success_url = reverse_lazy("balances")

    def get_form_kwargs(self):
        kwargs = super(BalanceCreateView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@login_required(login_url="login")
def add_wallet(request, currency_pk):
    currency = Currencies.objects.get(pk=currency_pk)
    balance = Balances(user=request.user, currency=currency, balance=0)
    balance.save()

    return redirect(reverse_lazy("balances"))


def health(request):
    return HttpResponse("success", status=200)


class FaucetSend(CreateView):
    model = Transactions

    template_name = "walletapp/fauset.html"

    form_class = FaucetSendForm

    def get_success_url(self) -> str:
        currency_id = self.request.GET.get("currency")

        if Currencies.objects.get(id=currency_id).is_nft:
            return reverse_lazy("faucet") + f"?currency=nft"
        else:
            return reverse_lazy("faucet") + f"?currency={currency_id}"

    def form_valid(self, form):
        form.instance.user = User.objects.get(username="faucet_user_1")

        invoice_dict = decode_invoice(form.instance.invoice_outbound)
        asset_id = invoice_dict["asset_id"]

        form.instance.amount = invoice_dict["amt"]

        currency = Currencies.objects.filter(asset_id=asset_id).first()

        form.instance.currency = currency

        if Transactions.objects.filter(
            invoice_inbound=form.instance.invoice_outbound
        ).exists():
            transaction = Transactions.objects.get(
                invoice_inbound=form.instance.invoice_outbound
            )
            form.instance.invoice_outbound = None
            form.instance.destination_user = transaction.user
            form.instance.direction = "outbound"
            form.instance.type = "internal"
            form.instance.status = "internal_stated"
            form.instance.description = (
                transaction.description
                + "(originally sent to taro invoice, converted to internal transaction)"
            )

            return super(FaucetSend, self).form_valid(form)

        form.instance.direction = "outbound"

        form.instance.type = "user"

        form.instance.status = "outbound_invoice_received"

        messages.success(
            self.request,
            f"Taproot Asset invoice for {invoice_dict['amt']} {currency.acronym} was"
            " successfully submitted",
        )

        return super(FaucetSend, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(FaucetSend, self).get_form_kwargs()
        currency_id = self.request.GET.get("currency")
        kwargs.update(
            {
                "user": User.objects.get(username="faucet_user_1"),
                "currency_id": currency_id,
            }
        )
        return kwargs

    def get_context_data(self, **kwargs):
        currency_id = self.request.GET.get("currency")
        if currency_id == "nft":
            balance = Balances.objects.filter(
                user=User.objects.get(username="faucet_user_1"),
                currency__is_nft=True,
                balance=1,
            ).first()
            currency = balance.currency
        else:
            currency = Currencies.objects.get(id=currency_id)

        ctx = super(FaucetSend, self).get_context_data(**kwargs)
        ctx["faucet_currency"] = currency

        success = self.request.GET.get("success", None)
        ctx["success"] = success

        return ctx


# def create_currency(request):

#     # If this is a POST request then process the Form data
#     if request.method == 'POST':

#         # Create a form instance and populate it with data from the request (binding):
#         form = CreateCurrencyForm(request.POST)

#         # Check if the form is valid:
#         if form.is_valid():

#             user = User.objects.create_user(form.cleaned_data['username'], form.cleaned_data['email'], form.cleaned_data['password'])
#             user.save()

#             # redirect to a new URL:
#             return redirect('/accounts/login')

#     # If this is a GET (or any other method) create the default form.
#     else:
#         form = CreateUserForm()

#     context = {
#         'form': form,
#     }

#     return render(request, 'create_user.html', context)


@method_decorator(login_required(login_url="login"), name="dispatch")
class ListingCurrencyCreate(CreateView):
    model = Listings
    form_class = ListingCurrencyForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/listings_form.html"

    def form_valid(self, form):
        form.instance.type = "lp"

        return super(ListingCurrencyCreate, self).form_valid(form)

    def get_success_url(self) -> str:
        return reverse_lazy("listings-my")

    def form_valid(self, form):
        form.instance.user = self.request.user

        return super(ListingCurrencyCreate, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(ListingCurrencyCreate, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class ListingNFTCreate(CreateView):
    model = Listings
    form_class = ListingNftForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/listings_nft_form.html"

    def form_valid(self, form):
        form.instance.type = "lp"

        return super(ListingNFTCreate, self).form_valid(form)

    def get_success_url(self) -> str:
        return reverse_lazy("listings-my")

    def form_valid(self, form):
        form.instance.user = self.request.user

        return super(ListingNFTCreate, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(ListingNFTCreate, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class ListingsMyListView(ListView):
    model = Listings
    fields = ["currency"]
    template_name = "walletapp/listings_my_list.html"
    context_object_name = "listings_list"
    paginate_by = 12

    def get_queryset(self):
        return Listings.objects.filter(
            currency__status="minted", user=self.request.user, type="lp"
        )

    def get_form_kwargs(self):
        kwargs = super(BalanceListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@method_decorator(login_required(login_url="login"), name="dispatch")
class OrdersMyListView(ListView):
    model = Listings
    fields = ["currency"]
    template_name = "walletapp/listings_my_orders_list.html"
    context_object_name = "listings_list"
    paginate_by = 12

    def get_queryset(self):
        return Listings.objects.filter(
            currency__status="minted",
            user=self.request.user,
            type__in=["order_bid", "order_ask"],
        )


@method_decorator(login_required(login_url="login"), name="dispatch")
class OrdersAsksListView(ListView):
    model = Listings
    fields = ["currency"]
    template_name = "walletapp/listings_orders_asks.html"
    context_object_name = "listings_list"
    paginate_by = 12

    def get_queryset(self):
        currency_id = self.kwargs["currency_pk"]

        return Listings.objects.filter(currency=currency_id, type="order_ask").order_by(
            "price_sat"
        )

    def get_context_data(self, **kwargs):
        ctx = super(OrdersAsksListView, self).get_context_data(**kwargs)

        currency_id = self.kwargs["currency_pk"]
        curr = Currencies.objects.get(pk=currency_id)

        ctx["currencies"] = curr

        return ctx


@method_decorator(login_required(login_url="login"), name="dispatch")
class OrdersBidsListView(ListView):
    model = Listings
    fields = ["currency"]
    template_name = "walletapp/listings_orders_bids.html"
    context_object_name = "listings_list"
    paginate_by = 12

    def get_queryset(self):
        currency_id = self.kwargs["currency_pk"]

        return Listings.objects.filter(currency=currency_id, type="order_bid").order_by(
            "-price_sat"
        )

    def get_context_data(self, **kwargs):
        ctx = super(OrdersBidsListView, self).get_context_data(**kwargs)

        currency_id = self.kwargs["currency_pk"]
        curr = Currencies.objects.get(pk=currency_id)

        ctx["currencies"] = curr

        return ctx


class PriceHistoryListView(ListView):
    model = PriceHistory
    fields = ["price_sat", "created_timestamp"]
    template_name = "walletapp/price_history_list.html"
    context_object_name = "price_history_list"
    paginate_by = 24 * 60

    def get_queryset(self):
        currency_id = self.request.GET.get("currency_id")
        period = self.request.GET.get("period", "1m")

        return PriceHistory.objects.filter(currency_id=currency_id, period=period)

    def get_form_kwargs(self):
        kwargs = super(BalanceListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs


@login_required(login_url="login")
def delete_listing(request, listing_pk):
    listing = Listings.objects.get(pk=listing_pk)

    if request.user != listing.user:
        request.session["message"] = {
            "title": "Order error",
            "body": f"You cannot delete this order as you did not create it.",
        }

        return redirect(reverse_lazy("orders-my"))

    listing.delete()
    if listing.type == "lp":
        return redirect(reverse_lazy("listings-my"))
    else:
        return redirect(reverse_lazy("orders-my"))


@method_decorator(login_required(login_url="login"), name="dispatch")
class CreateExchangeTransactionBuy(CreateView):
    model = Transactions
    form_class = CreateExchangeTransactionBuyForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/transaction_exchange_buy.html"

    def form_valid(self, form):
        listing = Listings.objects.get(currency=form.instance.currency, type="lp")

        form.instance.user = listing.user

        form.instance.listing = listing

        form.instance.destination_user = self.request.user

        form.instance.direction = "outbound"

        form.instance.type = "exchange"

        form.instance.status = "exchange_started"

        return super(CreateExchangeTransactionBuy, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(CreateExchangeTransactionBuy, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            return {
                "currency": currency,
            }
        else:
            return {}


@method_decorator(login_required(login_url="login"), name="dispatch")
class CreateExchangeTransactionSell(CreateView):
    model = Transactions
    form_class = CreateExchangeTransactionSellForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/transaction_exchange_sell.html"

    def form_valid(self, form):
        listing = Listings.objects.get(currency=form.instance.currency, type="lp")

        form.instance.user = listing.user

        form.instance.listing = listing

        form.instance.destination_user = self.request.user

        form.instance.direction = "inbound"

        form.instance.type = "exchange"

        form.instance.status = "exchange_started"

        return super(CreateExchangeTransactionSell, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(CreateExchangeTransactionSell, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            return {
                "currency": currency,
            }
        else:
            return {}


@method_decorator(login_required(login_url="login"), name="dispatch")
class CreateExchangeTransactionNftBuy(CreateView):
    model = Transactions
    form_class = CreateExchangeTransactionBuyNftForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/transaction_exchange_buy_nft.html"

    def form_valid(self, form):
        listing = Listings.objects.get(currency=form.instance.currency)

        form.instance.user = listing.user

        form.instance.listing = listing

        form.instance.destination_user = self.request.user

        form.instance.amount = 1

        form.instance.direction = "outbound"

        form.instance.type = "exchange"

        form.instance.status = "exchange_started"

        return super(CreateExchangeTransactionNftBuy, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(CreateExchangeTransactionNftBuy, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            return {
                "currency": currency,
            }
        else:
            return {}


def get_currency_price_history(request, currency_pk, period):
    if period == "1m":
        start_period = datetime.date.today() - datetime.timedelta(days=1)
    elif period == "1h":
        start_period = datetime.date.today() - datetime.timedelta(days=7)
    elif period == "1d":
        start_period = datetime.date.today() - datetime.timedelta(days=365)
    else:
        raise Exception("Unknown period value '{period}'")

    price_history = PriceHistory.objects.filter(
        currency_id=currency_pk, period=period, created_timestamp__gte=start_period
    )

    hist_list = price_history.values()
    chart_vals = [
        [
            f"Date({prc['created_timestamp'].year},"
            f" {prc['created_timestamp'].month-1}, {prc['created_timestamp'].day},"
            f" {prc['created_timestamp'].hour}, {prc['created_timestamp'].minute},"
            " 00, 00)",
            prc["price_sat"],
        ]
        for prc in list(hist_list)
    ]

    return HttpResponse(
        json.dumps(chart_vals, default=str), content_type="application/json"
    )


@method_decorator(login_required(login_url="login"), name="dispatch")
class ListingCurrencyOrderCreate(CreateView):
    model = Listings
    form_class = ListingOrderCurrencyForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/listings_order_create.html"

    def form_valid(self, form):
        form.instance.user = self.request.user

        return super(ListingCurrencyOrderCreate, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(ListingCurrencyOrderCreate, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")
        type_val = self.request.GET.get("type")

        res = {}

        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            res["currency"] = currency

        if type_val:
            res["type"] = type_val

        return res


@method_decorator(login_required(login_url="login"), name="dispatch")
class ListingCurrencyOrderNftCreate(CreateView):
    model = Listings
    form_class = ListingOrderNftForm
    # fields = ['acronym', 'description', 'genesis_bootstrap_info']

    template_name = "walletapp/listings_order_create_nft.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.amount = 1
        form.instance.type = "order_bid"

        return super(ListingCurrencyOrderNftCreate, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(ListingCurrencyOrderNftCreate, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def get_initial(self):
        currency_name = self.request.GET.get("currency")

        res = {}

        if currency_name:
            currency = Currencies.objects.get(name=currency_name)
            res["currency"] = currency

        return res


def get_currency_image(request, currency_pk):
    image_data = currency_card(currency_pk)
    return HttpResponse(image_data, content_type="image/png")


def get_collection_image(request, collection_pk, num_side):
    image_data = collection_card(collection_pk, num_side)
    return HttpResponse(image_data, content_type="image/png")


def get_chart_image(request, currency_pk):
    image_data = draw_week_chart(currency_pk)
    return HttpResponse(image_data, content_type="image/png")


def get_collection_gif_image(request, collection_pk, num):
    image_data = collection_gif(collection_pk, num)
    return HttpResponse(image_data, content_type="image/gif")


@login_required(login_url="login")
def execute_order_listing(request, listing_pk):
    listing = Listings.objects.get(pk=listing_pk)
    # if request.user==listing.currency.owner:
    #     request.session['message'] = {
    #         "title":"Order error",
    #         "body":"You can't bid/ask on your own currency."
    #     }
    #     return redirect(listing.currency.get_absolute_url())

    if request.user == listing.user:
        request.session["message"] = {
            "title": "Order error",
            "body": "You can't accept your own bids/asks.",
        }
        return redirect(listing.currency.get_absolute_url())

    if listing.type == "order_ask":
        balances_lising_user = Balances.objects.get(
            user=listing.user, currency=listing.currency
        ).balance
        if balances_lising_user < listing.amount:
            listing.delete()
            request.session["message"] = {
                "title": "Order error",
                "body": (
                    f"The user who created the order is no longer able to fullfil it."
                ),
            }
            return redirect(listing.currency.get_absolute_url())

        if (
            request.user.get_btc_balance()
            < listing.get_price_sat_total()
            + get_fee_sat_estimate_exchange(listing.get_price_sat_total())
        ):
            request.session["message"] = {
                "title": "Order error",
                "body": (
                    f"Your balance of {request.user.get_btc_balance()} SATs is not"
                    f" enough ot pay {listing.get_price_sat_total()} SATs for this"
                    " order."
                ),
            }
            return redirect(listing.currency.get_absolute_url())

    if listing.type == "order_bid":
        balances_lising_user = listing.user.get_btc_balance()

        if balances_lising_user < listing.amount:
            listing.delete()
            request.session["message"] = {
                "title": "Order error",
                "body": (
                    f"The user who created the order is no longer able to fullfil it."
                ),
            }
            return redirect(listing.currency.get_absolute_url())

        # if request.user.get_btc_balance() < get_fee_sat_estimate_exchange(
        #     listing.get_price_sat_total()
        # ):
        #     request.session["message"] = {
        #         "title": "Order error",
        #         "body": (
        #             f"Your balance of {request.user.get_btc_balance()} SATs is not"
        #             " enough ot the transaction fee"
        #             f" {get_fee_sat_estimate_exchange(listing.get_price_sat_total())} SATs."
        #         ),
        #     }
        #     return redirect(listing.currency.get_absolute_url())

        if not Balances.objects.filter(
            user=request.user, currency=listing.currency
        ).exists():
            balance = 0
        else:
            balance = Balances.objects.get(
                user=request.user, currency=listing.currency
            ).balance

        if balance < listing.amount:
            request.session["message"] = {
                "title": "Order error",
                "body": (
                    f"Your balance of {balance} {listing.currency.acronym} is not"
                    f" enough ot pay {listing.amount} {listing.currency.acronym} for"
                    " this order."
                ),
            }
            return redirect(listing.currency.get_absolute_url())

    if listing.type == "order_bid":
        trn = Transactions.objects.create(
            user=listing.user,
            listing=listing,
            currency=listing.currency,
            destination_user=request.user,
            amount=listing.amount,
            direction="inbound",
            type="exchange",
            status="exchange_started",
        )
    if listing.type == "order_ask":
        trn = Transactions.objects.create(
            user=listing.user,
            listing=listing,
            destination_user=request.user,
            currency=listing.currency,
            amount=listing.amount,
            direction="outbound",
            type="exchange",
            status="exchange_started",
        )
    trn.save()

    return redirect(trn.get_absolute_url())


def signup_redirect(request):
    print("signup_redirect")
    messages.error(
        request, "Something wrong here, it may be that you already have account!"
    )
    return redirect(reverse_lazy("login"))


@login_required(login_url="login")
def get_qr_code(request, transaction_pk):
    trn = Transactions.objects.get(id=transaction_pk)

    pic_data = io.BytesIO()

    img = qrcode.make(trn.invoice_inbound)
    # type(img)  # qrcode.image.pil.PilImage
    img.save(pic_data)

    return HttpResponse(pic_data.getvalue(), content_type="image/jpg")


@method_decorator(login_required(login_url="login"), name="dispatch")
class NotificationsListView(ListView):
    model = Notifications
    context_object_name = (  # your own name for the list as a template variable
        "notifications_list"
    )
    template_name = "walletapp/notifications_list.html"
    paginate_by = 12

    def get_queryset(self):
        return Notifications.objects.filter(
            destination_user=self.request.user,
        )

    def get_form_kwargs(self):
        kwargs = super(NotificationsListView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs
