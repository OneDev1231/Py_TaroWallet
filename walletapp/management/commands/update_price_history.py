import time
from datetime import timedelta

import schedule
from django.core.management.base import BaseCommand
from django.utils import timezone
from walletapp.models import (
    Balances,
    Collections,
    Currencies,
    Listings,
    PriceHistory,
    Transactions,
)
from walletapp.xray_utils import run_patch_all, wrap_in_xray

run_patch_all()


class Command(BaseCommand):
    help = "Update price history"

    def handle(self, *args, **options):
        schedule.every().minute.at(":01").do(update_price_history_1m)
        schedule.every().hour.at(":01").do(update_price_history_1h)
        schedule.every().day.at("00:01").do(update_price_history_1d)

        while True:
            schedule.run_pending()
            time.sleep(1)


@wrap_in_xray
def update_price_history(period):
    print(f"{period} interval")
    now = timezone.now()

    if period == "1h":
        collections_list = Collections.objects.all()

        for collection in collections_list:
            period_mins = 60

            earlier = now - timedelta(minutes=period_mins)

            trns = Transactions.objects.filter(
                created_timestamp__range=(earlier, now),
                type="exchange",
                currency__collection=collection,
            )

            volume = sum([trn.amount for trn in trns])
            transaction_num = len([trn.amount for trn in trns])
            holders_num = len(
                set(
                    [
                        bal.user
                        for bal in Balances.objects.filter(
                            currency__collection=collection
                        )
                    ]
                )
            )
            orders_num = len(
                Listings.objects.filter(
                    currency__collection=collection,
                    type__in=["order_bid", "order_ask"],
                )
            )
            print(
                f"Updating collection {collection.name}: volume"
                f" {volume} {collection.name}, transaction_num {transaction_num},"
                f" holders_num {holders_num}, orders_num {orders_num}"
            )
            # if period == "1h":
            # if True:
            collection.volume = volume
            collection.transaction_num = transaction_num
            collection.holders_num = holders_num
            collection.orders_num = orders_num
            collection.save()

    if period == "1d":
        currency_list = Currencies.objects.all()
    else:
        currency_list = Currencies.objects.filter(is_nft=False)

    for currency in currency_list:
        if not Listings.objects.filter(currency=currency).exists():
            continue
        elif Listings.objects.filter(currency=currency, type="lp").exists():
            listing = Listings.objects.get(currency=currency, type="lp")
            price_sat = listing.get_price_sat()
        else:
            price_sat = 0

        if period == "1m":
            period_mins = 1
        elif period == "1h":
            period_mins = 60
        elif period == "1d":
            period_mins = 60 * 24

        earlier = now - timedelta(minutes=period_mins)

        trns = Transactions.objects.filter(
            created_timestamp__range=(earlier, now),
            type="exchange",
            currency=currency,
        )

        hist_prices = PriceHistory.objects.filter(
            currency=currency, period="1m", created_timestamp__range=(earlier, now)
        ).order_by("created_timestamp")

        if len(hist_prices) > 2:
            if hist_prices.first().price_sat > 0:
                price_change = int(
                    (hist_prices.last().price_sat - hist_prices.first().price_sat)
                    * 100
                    / hist_prices.first().price_sat
                )
            else:
                price_change = 0
        else:
            price_change = 0

        volume = sum([trn.amount for trn in trns])
        transaction_num = len([trn.amount for trn in trns])
        holders_num = len(Balances.objects.filter(currency=currency, balance__gt=0))
        orders_num = len(
            Listings.objects.filter(
                currency=currency,
                type__in=["order_bid", "order_ask"],
            )
        )

        print(
            f"Updating currency {currency.name}: price {price_sat} SAT, volume"
            f" {volume} {currency.acronym}, transaction_num {transaction_num},"
            f" holders_num {holders_num}, orders_num {orders_num}, price_change"
            f" {price_change}"
        )

        price_hist_item = PriceHistory.objects.create(
            currency=currency, price_sat=price_sat, period=period, volume=volume
        )

        price_hist_item.save()

        if period == "1d":
            curr = currency
            curr.volume = volume
            curr.price_change = price_change
            curr.transaction_num = transaction_num
            curr.holders_num = holders_num
            curr.orders_num = orders_num
            curr.save()

        # if period == "1m":
        #     hist_to_delete = PriceHistory.objects.filter(created_timestamp__lt=(now - timedelta(days=7)))
        # elif period == "1h":
        #     hist_to_delete = PriceHistory.objects.filter(created_timestamp__lt=(now - timedelta(days=30)))
        # elif period == "1d":
        #     hist_to_delete = []

        # for p in hist_to_delete:
        #     #p.delete()
        #     print(p.created_timestamp)
        #     dasaas


def update_price_history_1m():
    update_price_history("1m")


def update_price_history_1h():
    update_price_history("1h")


def update_price_history_1d():
    update_price_history("1d")
