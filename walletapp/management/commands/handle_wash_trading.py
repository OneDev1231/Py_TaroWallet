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
    BalanceException
)
from walletapp.const_utils import (
    get_fee_sat_per_vbyte,
    get_fee_sat_per_wu,
)

from walletapp.utils import (
    decode_invoice_lnd,
    decode_metadata,
    encode_metadata,
    get_currency_btc,

    get_fee_user,
    get_faucet_user,
    get_wash_users
)
from django.db.models import Q
import random
import time
from walletapp.xray_utils import run_patch_all, wrap_in_xray

run_patch_all()


def order_listing_can_afford(listing, user):

        if listing.type not in ['order_bid','order_ask']:
            raise Exception("Can only handle bids or asks")

def lp_buy_listing_can_afford(listing, user):

        if listing.type not in ['lp']:
            raise Exception("Can only handle bids or asks")
        
        user_balance = Balances.objects.get(currency=get_currency_btc(), user=user)
        
        price = listing.get_price_sat()
        
        amount = user_balance.balance / price
        
        return amount

def lp_sell_listing_can_afford(listing, user):

        if listing.type not in ['lp']:
            raise Exception("Can only handle bids or asks")
        
        user_balance = Balances.objects.get(currency=listing.currency, user=user)
        
        return user_balance

def buy_from_order_ask(listing, user):
    
    if listing.type == "order_ask":
        trn = Transactions.objects.create(
            user=listing.user,
            listing=listing,
            destination_user=user,
            currency=listing.currency,
            amount=listing.amount,
            direction="outbound",
            type="exchange",
            status="exchange_started",
        )
        trn.save()
    else:
        raise Exception("only works for asks")

def sell_to_order_bid(listing, user):
    
    print(f"Selling to bid {listing.amount} {listing.currency.name} for {listing.get_price_sat()} by {user.username}")
    
    if listing.type == "order_bid":
        trn = Transactions.objects.create(
            user=listing.user,
            listing=listing,
            currency=listing.currency,
            destination_user=user,
            amount=listing.amount,
            direction="inbound",
            type="exchange",
            status="exchange_started",
        )
        trn.save()
    else:
        raise Exception("only works for asks")

def create_bid(currency, user, price_sat, amount):
    
    print(f"Creating {price_sat} SAT bid for {amount} {currency.name} by {user.username}")
    
    l = Listings.objects.create(
        user=user,
        currency=currency,
        price_sat=price_sat,
        amount=amount,
        type="order_bid",
    )
    l.save()

def sell(listing, user, amount):
    
    print(f"Selling {amount} {listing.currency.name} by {user.username}")
    
    if listing.type == "lp":
        trn = Transactions.objects.create(
            currency = listing.currency,
            amount = amount,
            user = listing.user,
            listing = listing,
            destination_user = user,
            direction = "inbound",
            type = "exchange",
            status = "exchange_started"
        )
        trn.save()
    else:
        raise Exception("only works for lp")
    
def buy(listing, user, amount):
    
    print(f"Buying {amount} {listing.currency.name} by {user.username}")
    
    if listing.type == "lp":
        trn = Transactions.objects.create(
            currency = listing.currency,
            amount = amount,
            user = listing.user,
            listing = listing,
            destination_user = user,
            direction = "outbound",
            type = "exchange",
            status = "exchange_started"
        )
        trn.save()
    else:
        raise Exception("only works for lp")

def get_eligible_currs():
    
    names = [
        "AdamCoin",
        "MAXImalists",
        "SunLight",
        "PePe",
        "AdamUSD",
        "ButtcoinKjoq",
        "BeckycoinKjoq",
        "MemecoinKjoq",
        "AnimeCoinKjoq"
    ]
    
    return Currencies.objects.filter(name__in=names)

def get_eligible_nfts():
    
    names = [
        "TaprootEve",
        "TaprootAdam",
        "CryptoGirls8",
        "CryptoAnimals3",
        "TestCollection"
    ]
    
    return Currencies.objects.filter(collection__name__in=names)

@wrap_in_xray
def run_wash_trading():

    for user in get_wash_users():
        
        # currency LP sell
        
        balance_list = Balances.objects.filter(~Q(currency=get_currency_btc()), user=user, balance__gt=0)
        
        listings_lps = Listings.objects.filter(type__in=['lp'], currency__in=[b.currency for b in balance_list])
        
        if listings_lps:
            
            l = random.choice(listings_lps)
            
            b = Balances.objects.get(user=user, currency=l.currency)
            
            max_amt = min(b.balance, int(l.get_lp_btc()/4))
            if max_amt>0:
                amount = random.randint(1, b.balance)
                try:
                    sell(l, user, amount)
                except BalanceException as e:
                    print(f"got error {e}")
            else:
                print(f"Cant afford to buy any {l.currency.name}")
        else:
            print(f"No LP listings found")
            
        # currency LP buy
        
        listings_lps = Listings.objects.filter(type__in=['lp'], currency__in=get_eligible_currs())
        # print(len(listings_lps))
        l = random.choice(listings_lps)
        
        b = Balances.objects.get(user=user, currency=get_currency_btc())
        
        max_amt = min(int(b.balance / l.get_price_sat())-1, int(l.get_lp_curr()/4))
        
        if max_amt>0:
            
            amount = random.randint(1, max_amt) 
            
            try:
                buy(l, user, amount)
            except BalanceException as e:
                print(f"got error {e}")
            
        else:
            print(f"Cant afford to buy any {l.currency.name}")
        
        # execute my bids
        
        balance_list = Balances.objects.filter(~Q(currency=get_currency_btc()), user=user, balance__gt=0, currency__is_nft=True, currency__in=get_eligible_nfts())
        # print(balance_list)
        listings_bids = Listings.objects.filter(~Q(user=user),type__in=['order_bid'], user__in=get_wash_users(), currency__is_nft=True, currency__in=[bal.currency for bal in balance_list])
        # print(listings_bids)
        
        if listings_bids:
            
            l = random.choice(listings_bids)
            
            try:
                sell_to_order_bid(l, user)
            except BalanceException as e:
                print(f"got error {e}")
        # create bids
        
        listings_bids = Listings.objects.filter(user=user,type__in=['order_bid'], currency__is_nft=True, currency__in=get_eligible_nfts())
        
        #print(listings_bids)
        
        balance_no_bids_list = Balances.objects.filter(~Q(currency=get_currency_btc()),~Q(currency__in=[li.currency for li in listings_bids]),~Q(user=user), user__in=get_wash_users(), balance__gt=0, currency__is_nft=True, currency__in=get_eligible_nfts())
        
        #print(balance_no_bids_list)
        
        
        b_btc = Balances.objects.get(user=user, currency=get_currency_btc())
        
        max_price_sat = b_btc.balance
        
        if balance_no_bids_list and max_price_sat>0:
            
            price_sat = random.randint(1, max_price_sat) 
            
            b = random.choice(balance_no_bids_list)
            
            create_bid(b.currency, user, price_sat, 1)
        


class Command(BaseCommand):
    help = "Create website activity"

    def handle(self, *args, **options):
        
        while True:
            
            run_wash_trading()
            
            sleep_interval = random.randint(60*1, 60*5)
            
            print(f"Sleeping for {sleep_interval}s...")
            time.sleep(sleep_interval )
            
        
