import time

import yfinance as yf
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from walletapp.models import Balances, Currencies, Transactions
from walletapp.utils import get_currency_btc
from walletapp.xray_utils import run_patch_all, wrap_in_xray

run_patch_all()


@wrap_in_xray
def handle_usda():

    curr_btc = get_currency_btc()
    curr_usda = Currencies.objects.get(name="AdamUSD")

    usda_user = User.objects.get(username="usda_user")
    usda_user_reserve = User.objects.get(username="usda_user_reserve")

    usda_user_bal_usda = Balances.objects.get(
        user=usda_user, currency=curr_usda
    ).balance
    usda_user_bal_btc = Balances.objects.get(user=usda_user, currency=curr_btc).balance

    ticker_yahoo = yf.Ticker("BTC-USD")
    data = ticker_yahoo.history()
    last_quote = data["Close"].iloc[-1]
    print("BTC-USD", last_quote)

    usda_bal_desired = int(usda_user_bal_btc / 100e6 * last_quote)
    print(f"Balance desired {usda_bal_desired}")
    print(f"Balance current {usda_user_bal_usda}")

    amount_sgn = usda_bal_desired - usda_user_bal_usda
    amount_sgn = 3
    trn = None

    if amount_sgn > 0:
        print(f"Send {amount_sgn} USDA to usda_user")
        amount = amount_sgn

        trn = Transactions.objects.create(
            user=usda_user_reserve,
            destination_user=usda_user,
            amount=amount,
            currency=curr_usda,
            direction="outbound",
            type="internal",
            status="internal_stated",
        )
        trn.save()

    elif amount_sgn < 0:
        amount = -amount_sgn
        print(f"Send {amount} USDA to usda_user_reserve")

        trn = Transactions.objects.create(
            user=usda_user,
            destination_user=usda_user_reserve,
            amount=amount,
            currency=curr_usda,
            direction="outbound",
            type="internal",
            status="internal_stated",
        )
        trn.save()

    if trn:
        while trn.status == "internal_stated":
            print(f"status = {trn.status}")
            trn.refresh_from_db()
            time.sleep(1)
        print(trn.status)


class Command(BaseCommand):
    help = "Update USDA Coin"

    def handle(self, *args, **options):
        while True:
            handle_usda()
            time.sleep(60)
