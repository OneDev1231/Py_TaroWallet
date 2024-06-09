import time
from datetime import timedelta

import schedule
from django.core.management.base import BaseCommand
from django.utils import dateformat, timezone
from walletapp.models import Currencies, Transactions
from walletapp.utils import get_currency_btc, get_faucet_user, get_fee_user
from walletapp.xray_utils import run_patch_all, wrap_in_xray

run_patch_all()


class Command(BaseCommand):
    help = "Send out minter payouts"

    def handle(self, *args, **options):
        schedule.every().hour.at(":01").do(send_minter_payouts)

        while True:
            schedule.run_pending()
            time.sleep(1)


@wrap_in_xray
def send_minter_payouts():
    now = timezone.now()
    formatted_now = dateformat.format(now, "Y-m-d H:i:s")
    earlier = now - timedelta(minutes=60)
    formatted_earlier = dateformat.format(earlier, "Y-m-d H:i:s")

    curr_list = Currencies.objects.all()

    fee_user = get_fee_user()

    faucet_user = get_faucet_user()

    for currency in curr_list:
        # if currency.name == "Bitcoin" or currency.name == "AdamCoin":
        #     continue

        trn_list = Transactions.objects.filter(
            currency=currency,
            type="exchange",
            status="exchange_finished",
            created_timestamp__range=(earlier, now),
        )

        amount_total = sum(
            [
                trn.fee_transaction.amount if trn.fee_transaction else 0
                for trn in trn_list
            ]
        )
        amount_volume = sum(
            [
                (
                    trn.associated_exchange_transaction.amount
                    if trn.associated_exchange_transaction
                    else 0
                )
                for trn in trn_list
            ]
        )

        num_trans = len(trn_list)

        minter_payout = int(amount_total / 3)

        if minter_payout > 0:
            print(
                f"Sending a payout of {minter_payout} SATs to {currency.owner.username}"
            )

            trn = Transactions.objects.create(
                user=fee_user,
                destination_user=currency.owner,
                amount=minter_payout,
                currency=get_currency_btc(),
                direction="outbound",
                type="internal",
                status="internal_stated",
                description=(
                    f"Compensation for generating {num_trans} exchange transactions"
                    f" totalling {amount_volume} SATs for time period from"
                    f" {formatted_earlier} - {formatted_now}"
                ),
            )
            trn.save()

            trn = Transactions.objects.create(
                user=fee_user,
                destination_user=faucet_user,
                amount=minter_payout,
                currency=get_currency_btc(),
                direction="outbound",
                type="internal",
                status="internal_stated",
                description=(
                    f"Compensation for generating {num_trans} exchange transactions"
                    f" totalling {amount_volume} SATs for time period from"
                    f" {formatted_earlier} - {formatted_now}"
                ),
            )
            trn.save()
