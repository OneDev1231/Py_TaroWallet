import rest_framework.permissions as permissions
import rest_framework.renderers as renderers
from ajax_select import urls as ajax_select_urls
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.schemas import get_schema_view

from . import views, views_api

urlpatterns = [
    path("", views.index, name="index"),
    path(
        "public_currencies",
        views.PublicCurrencyListView.as_view(),
        name="public-currencies",
    ),
    path(
        "public_collections",
        views.PublicCollectionsListView.as_view(),
        name="public-collections",
    ),
    path("user/login/", views.LoginView.as_view(), name="login"),
    path("user/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("user/create/", views.UserCreate.as_view(), name="user-create"),
    path(
        "balance/create/",
        views.BalanceCreateView.as_view(),
        name="balance-create",
    ),
    path(
        "balance/create_one_click/<int:currency_pk>",
        views.add_wallet,
        name="balance-create-one-click",
    ),
    path("balances", views.BalanceListView.as_view(), name="balances"),
    path("balances-nft", views.NftListView.as_view(), name="balances-nft"),
    path(
        "currency/create/",
        views.AssetCreate.as_view(),
        name="currency-create",
    ),
    path("currencies/mint/", views.CurrencyMint.as_view(), name="currency-mint"),
    path("currencies/mint-nft/", views.NftMint.as_view(), name="currency-mint-nft"),
    path(
        "currencies/mint-nft-collection/",
        views.CurrencyMintMultiple.as_view(),
        name="currency-mint-nft-collection",
    ),
    path(
        "collections/<int:pk>/",
        views.CollectionDetailView.as_view(),
        name="collection-detail",
    ),
    path("currencies/", views.CurrencyListView.as_view(), name="currencies"),
    path("collections/", views.CollectionsListView.as_view(), name="collections"),
    path("nfts/", views.NFTListView.as_view(), name="currencies-nfts"),
    path(
        "currencies/<int:pk>",
        views.AssetDetailView.as_view(),
        name="currency-detail",
    ),
    path(
        "orders/<int:currency_pk>/asks",
        views.OrdersAsksListView.as_view(),
        name="orders-asks",
    ),
    path(
        "orders/<int:currency_pk>/bids",
        views.OrdersBidsListView.as_view(),
        name="orders-bids",
    ),
    path(
        "currencies_public/<int:pk>",
        views.AssetDetailPublicView.as_view(),
        name="currency-detail-public",
    ),
    path(
        "transactions/send_taro/",
        views.TransactionSendTaroCurrency.as_view(),
        name="transaction-send-taro",
    ),
    path(
        "transactions/send_btc/",
        views.TransactionSendBtc.as_view(),
        name="transaction-send-btc",
    ),
    path(
        "transactions/send_btc_lnd/",
        views.TransactionSendBtcLnd.as_view(),
        name="transaction-send-btc-lnd",
    ),
    path(
        "transactions/send_internal/",
        views.TransactionSendInternal.as_view(),
        name="transaction-send-internal",
    ),
    path(
        "transactions/receive_taro/",
        views.TransactionReceiveTaro.as_view(),
        name="transaction-receive-taro",
    ),
    path(
        "transactions/receive_btc/",
        views.TransactionReceiveBtc.as_view(),
        name="transaction-receive-btc",
    ),
    path(
        "transactions/receive_btc_lnd/",
        views.TransactionReceiveBtcLnd.as_view(),
        name="transaction-receive-btc-lnd",
    ),
    path(
        "transactions/",
        views.TransactionListView.as_view(),
        name="transactions",
    ),
    path(
        "transactions/<int:pk>",
        views.TransactionDetailView.as_view(),
        name="transaction-detail",
    ),
    # path(
    #     "faucet/",
    #     views.FaucetSend.as_view(),
    #     name="faucet",
    # ),
    path(
        "list_asset/",
        views.ListingCurrencyCreate.as_view(),
        name="listing-create",
    ),
    path(
        "list_nft_asset/",
        views.ListingNFTCreate.as_view(),
        name="listing-nft-create",
    ),
    path(
        "listings_my/",
        views.ListingsMyListView.as_view(),
        name="listings-my",
    ),
    path(
        "buy_taro_asset/",
        views.CreateExchangeTransactionBuy.as_view(),
        name="buy-currency-asset",
    ),
    path(
        "buy_nft_asset/",
        views.CreateExchangeTransactionNftBuy.as_view(),
        name="buy-nft-asset",
    ),
    path(
        "sell_taro_asset/",
        views.CreateExchangeTransactionSell.as_view(),
        name="sell-taro-asset",
    ),
    path(
        "delete_listing/<int:listing_pk>",
        views.delete_listing,
        name="listing-delete",
    ),
    path(
        "get_currency_preview_image/<int:currency_pk>",
        views.get_currency_image,
        name="currency-detail-preview-image",
    ),
    path(
        "get_collection_preview_image/<int:collection_pk>/<int:num_side>",
        views.get_collection_image,
        name="collection-detail-preview-image",
    ),
    path(
        "get_chart_image/<int:currency_pk>",
        views.get_chart_image,
        name="get-chart-image",
    ),
    path(
        "get_collection_preview_gif_image/<int:collection_pk>/<int:num>",
        views.get_collection_gif_image,
        name="collection-detail-preview-gif-image",
    ),
    path(
        "get_currency_price_history/<int:currency_pk>/<str:period>",
        views.get_currency_price_history,
        name="currency-price-history",
    ),
    path(
        "listing_currency_order_create/",
        views.ListingCurrencyOrderCreate.as_view(),
        name="listing-currency-order-create",
    ),
    path(
        "listing_currency_order_nft_create/",
        views.ListingCurrencyOrderNftCreate.as_view(),
        name="listing-currency-order-nft-create",
    ),
    path(
        "execute_order_listing/<int:listing_pk>",
        views.execute_order_listing,
        name="execute-order-listing",
    ),
    path(
        "my_orders/",
        views.OrdersMyListView.as_view(),
        name="orders-my",
    ),
    path(
        "transactions/<int:transaction_pk>/qr_code",
        views.get_qr_code,
        name="qr-code-invoice",
    ),
    re_path(r"^ajax_select/", include(ajax_select_urls)),
]


urlpatterns = urlpatterns + [
    # re_path(r'^rest-auth/', include('rest_auth.urls')),
    # re_path(
    #     r"^rest-auth/google/$", views_api.GoogleLogin.as_view(), name="google_login"
    # ),
    path("api/token-auth/", obtain_auth_token, name="api_token_auth"),
    path(
        "api/balance/create/",
        views_api.BalanceCreateView.as_view(),
        name="api-balance-create",
    ),
    path("api/balances/", views_api.BalanceListView.as_view(), name="api-balances"),
    path(
        "api/balances-nft/",
        views_api.NftListView.as_view(),
        name="api-balances-nft",
    ),
    path(
        "api/currency/create/",
        views_api.AssetCreateView.as_view(),
        name="api-currency-create",
    ),
    path(
        "api/currencies/mint/",
        views_api.CurrencyMintView.as_view(),
        name="api-currency-mint",
    ),
    path(
        "api/currencies/mint-nft/",
        views_api.NftMintView.as_view(),
        name="api-currency-mint-nft",
    ),
    path(
        "api/currencies/",
        views_api.CurrencyListView.as_view(),
        name="api-currencies",
    ),
    path("api/nfts/", views_api.NFTListView.as_view(), name="api-nfts"),
    path(
        "api/collections/",
        views_api.CollectionsListView.as_view(),
        name="api-collections",
    ),
    path(
        "api/notifications/",
        views_api.NotificationsListView.as_view(),
        name="api-notifications",
    ),
    path(
        "api/transactions/send_taro/",
        views_api.TransactionSendTaroCurrencyView.as_view(),
        name="api-transaction-send-taro",
    ),
    path(
        "api/transactions/send_btc/",
        views_api.TransactionSendBtcView.as_view(),
        name="api-transaction-send-btc",
    ),
    path(
        "api/transactions/send_internal/",
        views_api.TransactionSendInternal.as_view(),
        name="api-transaction-send-internal",
    ),
    path(
        "api/transactions/send_btc_lnd/",
        views_api.TransactionSendBtcLnd.as_view(),
        name="api-transaction-send-btc-lnd",
    ),
    path(
        "api/transactions/receive_taro/",
        views_api.TransactionReceiveTaro.as_view(),
        name="api-transaction-receive-taro",
    ),
    path(
        "api/transactions/receive_btc/",
        views_api.TransactionReceiveBtc.as_view(),
        name="api-transaction-receive-btc",
    ),
    path(
        "api/transactions/receive_btc_lnd/",
        views_api.TransactionReceiveBtcLnd.as_view(),
        name="api-transaction-receive-btc-lnd",
    ),
    path(
        "api/transactions/",
        views_api.TransactionListView.as_view(),
        name="api-transactions",
    ),
    path(
        "api/list_asset/",
        views_api.ListingCurrencyCreate.as_view(),
        name="api-listing-create",
    ),
    path(
        "api/list_nft_asset/",
        views_api.ListingNFTCreate.as_view(),
        name="api-listing-nft-create",
    ),
    path(
        "api/listings_my/",
        views_api.ListingsMyListView.as_view(),
        name="api-listings-my",
    ),
    path(
        "api/buy_taro_asset/",
        views_api.CreateExchangeTransactionBuy.as_view(),
        name="api-buy-currency-asset",
    ),
    path(
        "api/buy_nft_asset/",
        views_api.CreateExchangeTransactionNftBuy.as_view(),
        name="api-buy-nft-asset",
    ),
    path(
        "api/sell_taro_asset/",
        views_api.CreateExchangeTransactionSell.as_view(),
        name="api-sell-taro-asset",
    ),
    path(
        "api/transactions/<int:pk>",
        views_api.TransactionDetailView.as_view(),
        name="api-buy-nft-asset",
    ),
    path(
        "api/currencies/<int:pk>",
        views_api.AssetDetailView.as_view(),
        name="api-sell-taro-asset",
    ),
    path(
        "swagger-ui/",
        TemplateView.as_view(
            template_name="swagger-ui.html",
            extra_context={"schema_url": "openapi-schema-json"},
        ),
        name="swagger-ui",
    ),
    path(
        "openapi.json",
        get_schema_view(
            title="Tiramisu Wallet Rest API documentation",
            description=(
                "This is an API for Tiramisu wallet. Tiramisu is a platform for"
                " taproot assets on Bitcoin blockchain."
            ),
            renderer_classes=[renderers.JSONOpenAPIRenderer],
            public=True,
            permission_classes=(permissions.AllowAny,),
        ),
        name="openapi-schema-json",
    ),
]

# DEV_ENV = os.getenv("DEV_ENV")

# if DEV_ENV == "DEV":

#     urlpatterns = urlpatterns + [
#         path(
#             "api/user/register/",
#             views_api.CreateUserView.as_view(),
#             name="api-balance-create",
#         )
#     ]
