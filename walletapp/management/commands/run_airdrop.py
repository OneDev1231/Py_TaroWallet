import time
from datetime import timedelta

import schedule
from django.core.management.base import BaseCommand
from django.utils import timezone, dateformat
from walletapp.models import (
    Balances,
    Listings,
    PriceHistory,
    Transactions,
    Currencies,
    User,
)
from walletapp.utils import (
    decode_invoice_lnd,
    decode_metadata,
    encode_metadata,
    get_currency_btc,
    get_fee_sat_per_vbyte,
    get_fee_sat_per_wu,
    get_fee_user,
    get_faucet_user,
)


class Command(BaseCommand):
    help = "Update price history"

    def handle(self, *args, **options):
        #faucet_user = get_faucet_user()
        
        #usda_user = User.objects.get(username="usda_user_reserve")
        faucet_user = get_faucet_user()

        curr = Currencies.objects.get(name="MAXImalists")

        amount_total = 1406325238 # Balances.objects.get(currency=curr, user=faucet_user).balance

        user_list = User.objects.all()
        
        amount =  int(amount_total / len(user_list)) - 1

        print(
            f"Sending the total of {amount_total} {curr.acronym} to the total of"
            f" {len(user_list)} users."
        )

        for usr in user_list:
            
            print(f"Sending {amount} {curr.acronym} to user {usr.username}")

            trn = Transactions.objects.create(
                user=faucet_user,
                destination_user=usr,
                amount=amount,
                currency=curr,
                direction="outbound",
                type="internal",
                status="internal_stated",
            )
            trn.save()
