from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer, ValidationError

from . import views
from .models import Listings

# from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
# from rest_auth.registration.views import SocialLoginView

# CurrenciesList


# class CustumAuthentication(TokenAuthentication):
#     def authenticate(self, request):
#         username, val = super().authenticate(request)

#         try:
#             user = User.objects.get(username=username)  # get the user
#         except User.DoesNotExist:
#             raise exceptions.AuthenticationFailed(
#                 "No such user"
#             )  # raise exception if user does not exist

#         return (user, None)  # authentication successful

# class GoogleLogin(SocialLoginView):
#     adapter_class = GoogleOAuth2Adapter


# class UserSerializer(ModelSerializer):
#     def create(self, validated_data):

#         user = User.objects.create_user(
#             username=validated_data["username"],
#             password=validated_data["password"],
#         )

#         return user

#     class Meta:
#         model = User
#         # Tuple of serialized model fields (see link [2])
#         fields = (
#             "username",
#             "password",
#         )


# class CreateUserView(CreateAPIView):

#     authentication_classes = []
#     permission_classes = [permissions.AllowAny]

#     serializer_class = UserSerializer


def get_all_fields_from_form(instance):
    """
    Return names of all available fields from given Form instance.

    :arg instance: Form instance
    :returns list of field names
    :rtype: list
    """

    fields = list(instance.base_fields)

    for field in list(instance.declared_fields):

        if field not in fields:
            fields.append(field)

    return fields


class RetrieveView(RetrieveAPIView):
    authentication_classes = [TokenAuthentication]

    def get_queryset(self):
        self.view.request = self.request

        return self.view.get_queryset()

    # def get_object(self):

    #     self.view.request = self.context["request"]

    #     super().get_object(self)


class ListView(ListAPIView):
    authentication_classes = [TokenAuthentication]

    paginate_by = 100

    def get_queryset(self):
        self.view.request = self.request

        return self.view.get_queryset()

    def get_object(self):
        self.view.request = self.context["request"]

        super().get_object(self)


class CreateSerializer(ModelSerializer):
    form = None

    def validate(self, data):
        data_req = {}
        file_dat_reqa = {}
        for key, val in data.items():
            if key == "picture_orig":
                file_dat_reqa[key] = val

            if key == "destination_user":
                data_req[key] = val.id
            else:
                data_req[key] = val

        self.form = self.view.form_class(data=data_req, files=file_dat_reqa)

        self.form.user = self.context["request"].user

        if not self.form.is_valid():
            raise ValidationError(self.form.errors)

        self.view.request = self.context["request"]

        data_out = {
            k: self.form.cleaned_data[k]
            for k in get_all_fields_from_form(self.view.form_class)
        }

        return data_out

    def create(self, validated_data):
        print("create")
        self.view.get_form_kwargs()
        self.view.form_valid(self.form)

        return self.view.get_context_data()["object"]


class CreateViewPublic(CreateAPIView):

    serializer_class = CreateSerializer


class CreateView(CreateAPIView):
    authentication_classes = [TokenAuthentication]

    serializer_class = CreateSerializer


class CurrenciesListSerializer(ModelSerializer):
    class Meta:
        model = views.CurrencyListView.model
        fields = "__all__"


class CurrencyListView(ListView):
    """
    List all currencies available in Tiramisu Wallet
    """

    view = views.CurrencyListView()
    serializer_class = CurrenciesListSerializer


class NFTListSerializer(ModelSerializer):
    class Meta:
        model = views.NFTListView.model
        fields = "__all__"


class NFTListView(ListView):
    """
    List all currencies available in Tiramisu Wallet
    """

    view = views.NFTListView()
    serializer_class = NFTListSerializer


class TransactionListViewSerializer(ModelSerializer):
    class Meta:
        model = views.TransactionListView.model
        fields = "__all__"


class TransactionListView(ListView):
    """
    List all transactions under our account
    """

    view = views.TransactionListView()
    serializer_class = TransactionListViewSerializer


class BalanceListViewSerializer(ModelSerializer):
    class Meta:
        model = views.BalanceListView.model
        depth = 1
        fields = [
            "id",
            "balance",
            "pending_balance",
            "created_timestamp",
            "updated_timestamp",
            "currency",
            "user_id",
        ]


class BalanceListView(ListView):
    """
    List all balances under your account
    """

    view = views.BalanceListView()
    serializer_class = BalanceListViewSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset.select_related("currency__name"), many=True
        )

        return Response(serializer.data)


class NftListViewSerializer(ModelSerializer):
    class Meta:
        model = views.NftListView.model
        fields = "__all__"
        depth = 1
        fields = [
            "id",
            "balance",
            "pending_balance",
            "created_timestamp",
            "updated_timestamp",
            "currency",
            "user_id",
        ]


class NftListView(ListView):
    """
    List all NFTs available in Tiramisu Wallet
    """

    view = views.NftListView()
    serializer_class = NftListViewSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset.select_related("currency__name"), many=True
        )

        return Response(serializer.data)


class ListingsMyListViewSerializer(ModelSerializer):
    class Meta:
        model = views.ListingsMyListView.model
        fields = "__all__"


class ListingsMyListView(ListView):
    """
    List all exchange listings under the current account
    """

    view = views.ListingsMyListView()
    serializer_class = ListingsMyListViewSerializer


class AssetCreateSerializer(CreateSerializer):
    view = views.AssetCreate()

    class Meta:
        model = views.AssetCreate.model
        fields = get_all_fields_from_form(views.AssetCreate.form_class) + ["id"]


class AssetCreateView(CreateView):
    """
    Register a new currency asset
    """

    serializer_class = AssetCreateSerializer


class NftMintViewSerializer(CreateSerializer):
    view = views.NftMint()

    class Meta:
        model = views.NftMint.model
        fields = get_all_fields_from_form(views.NftMint.form_class) + ["id"]


class NftMintView(CreateView):
    """
    Mint new NFT and add it under your account
    """

    serializer_class = NftMintViewSerializer


class CurrencyMintSerializer(CreateSerializer):
    view = views.CurrencyMint()

    class Meta:
        model = views.CurrencyMint.model
        fields = get_all_fields_from_form(views.CurrencyMint.form_class) + ["id"]


class CurrencyMintView(CreateView):
    """
    Mint new currency and add it under your account
    """

    serializer_class = CurrencyMintSerializer


class TransactionSendBtcSerializer(CreateSerializer):
    view = views.TransactionSendBtc()

    class Meta:
        model = views.TransactionSendBtc.model
        fields = get_all_fields_from_form(views.TransactionSendBtc.form_class) + ["id"]


class TransactionSendBtcView(CreateView):
    """
    Send BTC to a BTC address
    """

    serializer_class = TransactionSendBtcSerializer


class TransactionSendTaroCurrencySerializer(CreateSerializer):
    view = views.TransactionSendTaroCurrency()

    class Meta:
        model = views.TransactionSendTaroCurrency.model
        fields = get_all_fields_from_form(
            views.TransactionSendTaroCurrency.form_class
        ) + ["id"]


class TransactionSendTaroCurrencyView(CreateView):
    """
    Send Taro currency to a taro invoice
    """

    serializer_class = TransactionSendTaroCurrencySerializer


class TransactionSendInternalSerializer(CreateSerializer):
    view = views.TransactionSendInternal()

    class Meta:
        model = views.TransactionSendInternal.model
        fields = get_all_fields_from_form(views.TransactionSendInternal.form_class) + [
            "id"
        ]


class TransactionSendInternal(CreateView):
    """
    Send taro currency or BTC to a under of Tiramisu Wallet
    """

    serializer_class = TransactionSendInternalSerializer


class TransactionReceiveTaroSerializer(CreateSerializer):
    view = views.TransactionReceiveTaro()

    class Meta:
        model = views.TransactionReceiveTaro.model
        fields = get_all_fields_from_form(views.TransactionReceiveTaro.form_class) + [
            "id"
        ]


class TransactionReceiveTaro(CreateView):
    """
    Generate an invoice to receive Taro
    """

    serializer_class = TransactionReceiveTaroSerializer


class TransactionReceiveBtcSerializer(CreateSerializer):
    view = views.TransactionReceiveBtc()

    class Meta:
        model = views.TransactionReceiveBtc.model
        fields = get_all_fields_from_form(views.TransactionReceiveBtc.form_class) + [
            "id"
        ]


class TransactionReceiveBtc(CreateView):
    """
    Generate a BTC address to receive BTC
    """

    serializer_class = TransactionReceiveBtcSerializer


class TransactionReceiveBtcLndSerializer(CreateSerializer):
    view = views.TransactionReceiveBtcLnd()

    class Meta:
        model = views.TransactionReceiveBtcLnd.model
        fields = get_all_fields_from_form(views.TransactionReceiveBtcLnd.form_class) + [
            "id"
        ]


class TransactionReceiveBtcLnd(CreateView):
    """
    Generate a BTC address to receive BTC
    """

    serializer_class = TransactionReceiveBtcLndSerializer


class BalanceCreateViewSerializer(CreateSerializer):
    view = views.BalanceCreateView()

    class Meta:
        model = views.BalanceCreateView.model
        fields = get_all_fields_from_form(views.BalanceCreateView.form_class) + ["id"]


class BalanceCreateView(CreateView):
    """
    Register a new balance under your account
    """

    serializer_class = BalanceCreateViewSerializer


class ListingCurrencyCreateSerializer(CreateSerializer):
    view = views.ListingCurrencyCreate()

    class Meta:
        model = views.ListingCurrencyCreate.model
        fields = get_all_fields_from_form(views.ListingCurrencyCreate.form_class) + [
            "id"
        ]


class ListingCurrencyCreate(CreateView):
    """
    List a currency on an exchange
    """

    serializer_class = ListingCurrencyCreateSerializer


class ListingNFTCreateSerializer(CreateSerializer):
    view = views.ListingNFTCreate()

    class Meta:
        model = views.ListingNFTCreate.model
        fields = get_all_fields_from_form(views.ListingNFTCreate.form_class) + ["id"]


class ListingNFTCreate(CreateView):
    """
    List an NFT on an exchange
    """

    serializer_class = ListingNFTCreateSerializer


class CreateExchangeTransactionBuySerializer(CreateSerializer):
    view = views.CreateExchangeTransactionBuy()

    class Meta:
        model = views.CreateExchangeTransactionBuy.model
        fields = get_all_fields_from_form(
            views.CreateExchangeTransactionBuy.form_class
        ) + ["id"]


class CreateExchangeTransactionBuy(CreateView):
    """
    Buy a currency asset on an exchange
    """

    serializer_class = CreateExchangeTransactionBuySerializer


class CreateExchangeTransactionSellSerializer(CreateSerializer):
    view = views.CreateExchangeTransactionSell()

    class Meta:
        model = views.CreateExchangeTransactionSell.model
        fields = get_all_fields_from_form(
            views.CreateExchangeTransactionSell.form_class
        ) + ["id"]


class CreateExchangeTransactionSell(CreateView):
    """
    Sell a currency asset on an exchange
    """

    serializer_class = CreateExchangeTransactionSellSerializer


class CreateExchangeTransactionNftBuySerializer(CreateSerializer):
    view = views.CreateExchangeTransactionNftBuy()

    class Meta:
        model = views.CreateExchangeTransactionNftBuy.model
        fields = get_all_fields_from_form(
            views.CreateExchangeTransactionNftBuy.form_class
        ) + ["id"]
        # fields = ['currency', 'price_sat']+ ["id"]


class CreateExchangeTransactionNftBuy(CreateView):
    """
    Buy NFT on exchange
    """

    serializer_class = CreateExchangeTransactionNftBuySerializer


class AssetDetailViewSerializer(ModelSerializer):
    class Meta:
        model = views.AssetDetailView.model
        fields = "__all__"


class AssetDetailView(RetrieveView):
    """
    List all exchange listings under the current account
    """

    view = views.AssetDetailView()
    serializer_class = AssetDetailViewSerializer

    def get(self, request, pk):

        get = self.get_object()

        serializer = AssetDetailViewSerializer(get)

        res = serializer.data

        listing = Listings.objects.get(currency=get, type="lp")

        res["lp_listing_id"] = listing.id

        return Response(res)


class TransactionDetailViewSerializer(ModelSerializer):
    class Meta:
        model = views.TransactionDetailView.model
        depth = 1
        fields = [
            "id",
            "invoice_inbound",
            "invoice_outbound",
            "tx_id",
            "description",
            "amount",
            "balance",
            "pending_balance",
            "type",
            "direction",
            "created_timestamp",
            "updated_timestamp",
            "status",
            "status_description",
            "user",
            "currency",
            "listing",
            "fee_transaction",
            "associated_exchange_transaction",
            "destination_user",
        ]


class TransactionDetailView(RetrieveView):
    """
    List all exchange listings under the current account
    """

    view = views.TransactionDetailView()
    serializer_class = TransactionDetailViewSerializer

    def check_object_permissions(self, request, obj):
        """
        Check if the request should be permitted for a given object.
        Raises an appropriate exception if the request is not permitted.
        """

        if not (
            obj.user.id == request.user.id or obj.destination_user.id == request.user.id
        ):
            self.permission_denied(
                request,
                message="You dont have permission to access this transaction.",
                code=405,
            )

    def get(self, request, pk):

        get = self.get_object()

        serializer = TransactionDetailViewSerializer(get)

        res = serializer.data

        return Response(res)


class CurrencyMintMultipleViewSerializer(CreateSerializer):
    view = views.NftMint()

    class Meta:
        model = views.CurrencyMintMultiple.model
        fields = get_all_fields_from_form(views.CurrencyMintMultiple.form_class) + [
            "id"
        ]


class CurrencyMintMultipleView(CreateView):
    """
    Mint new NFT and add it under your account
    """

    serializer_class = CurrencyMintMultipleViewSerializer


class TransactionSendBtcLndSerializer(CreateSerializer):
    view = views.TransactionSendBtcLnd()

    class Meta:
        model = views.TransactionSendBtcLnd.model
        fields = get_all_fields_from_form(views.TransactionSendBtcLnd.form_class) + [
            "id"
        ]


class TransactionSendBtcLnd(CreateView):
    """
    Mint new NFT and add it under your account
    """

    serializer_class = TransactionSendBtcLndSerializer


class TransactionReceiveBtcLndViewSerializer(CreateSerializer):
    view = views.TransactionReceiveBtcLnd()

    class Meta:
        model = views.TransactionReceiveBtcLnd.model
        fields = get_all_fields_from_form(views.TransactionReceiveBtcLnd.form_class) + [
            "id"
        ]


class TransactionReceiveBtcLndView(CreateView):
    """
    Mint new NFT and add it under your account
    """

    serializer_class = TransactionReceiveBtcLndViewSerializer


class CollectionsListViewSerializer(ModelSerializer):
    class Meta:
        model = views.CollectionsListView.model
        fields = "__all__"


class CollectionsListView(ListView):
    """
    List all collections available in Tiramisu Wallet
    """

    view = views.CollectionsListView()
    serializer_class = CollectionsListViewSerializer


class OrdersMyListViewSerializer(ModelSerializer):
    class Meta:
        model = views.OrdersMyListView.model
        fields = "__all__"


class OrdersMyListView(ListView):
    """
    List all currencies available in Tiramisu Wallet
    """

    view = views.OrdersMyListView()
    serializer_class = OrdersMyListViewSerializer


class OrdersAsksListViewSerializer(ModelSerializer):
    class Meta:
        model = views.OrdersAsksListView.model
        fields = "__all__"


class OrdersAsksListView(ListView):
    """
    List all currencies available in Tiramisu Wallet
    """

    view = views.OrdersAsksListView()
    serializer_class = OrdersAsksListViewSerializer


class OrdersBidsListViewSerializer(ModelSerializer):
    class Meta:
        model = views.OrdersBidsListView.model
        fields = "__all__"


class OrdersBidsListView(ListView):
    """
    List all currencies available in Tiramisu Wallet
    """

    view = views.OrdersBidsListView()
    serializer_class = OrdersBidsListViewSerializer


class PriceHistoryListViewSerializer(ModelSerializer):
    class Meta:
        model = views.PriceHistoryListView.model
        fields = "__all__"


class PriceHistoryListView(ListView):
    """
    List all currencies available in Tiramisu Wallet
    """

    view = views.PriceHistoryListView()
    serializer_class = PriceHistoryListViewSerializer


class CollectionDetailViewSerializer(ModelSerializer):
    class Meta:
        model = views.CollectionDetailView.model
        fields = "__all__"


class CollectionDetailView(RetrieveView):
    """
    List all exchange listings under the current account
    """

    view = views.CollectionDetailView()
    serializer_class = CollectionDetailViewSerializer


class NotificationsListViewSerializer(ModelSerializer):
    class Meta:
        model = views.NotificationsListView.model
        fields = "__all__"


class NotificationsListView(ListView):
    """
    List all user notifications
    """

    view = views.NotificationsListView()
    serializer_class = NotificationsListViewSerializer
