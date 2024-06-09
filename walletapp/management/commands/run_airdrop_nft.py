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
    Collections,
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
    help = "Run NFT airdrop"

    def handle(self, *args, **options):
        
        pokemon_collection_user = User.objects.get(username="pokemon_collection_user")

        bal_list = Balances.objects.filter(currency__acronym="AC", balance__gt=0, user__username='yhuntsman123@gmail.com').order_by("-balance")
        
        collection = Collections.objects.get(name='TaprootAdam')

        nft_list = Balances.objects.filter(currency__collection=collection, user=pokemon_collection_user, balance__gt=0)

        for i, bal in enumerate(bal_list):
            print(i)
            usr = bal.user
            nft = nft_list[i].currency
            print(nft.name)
            if not Balances.objects.filter(currency=nft, user=pokemon_collection_user, balance__gt=0).exists():
                print(f"Zero balance.")
                continue
            
            if usr==pokemon_collection_user:
                continue
            
            print(f"Sending {nft.name} to user {usr.username}")
            
            trn = Transactions.objects.create(
                user=pokemon_collection_user,
                destination_user=usr,
                amount=1,
                currency=nft,
                direction="outbound",
                type="internal",
                status="internal_stated",
            )
            trn.save()

        for i, bal in enumerate(bal_list):
            print(i)
            usr = bal.user
            print(f"Creating order for user {usr.username}")
            nft = nft_list[i].currency
            try:
                listing = Listings.objects.create(
                    currency=nft,
                    user=pokemon_collection_user,
                    amount = 1,
                    price_sat=300,
                    type = "order_bid"
                )
                listing.save()
            except Exception as e:
                print(e)
