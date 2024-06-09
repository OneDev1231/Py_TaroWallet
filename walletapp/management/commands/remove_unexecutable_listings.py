from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User, Currencies, Listings

from walletapp.utils import get_currency_btc
import time 
from walletapp.xray_utils import run_patch_all, wrap_in_xray

run_patch_all()

@wrap_in_xray
def remove_unexecutable_listings():
    
    listings = Listings.objects.filter(type="order_ask")

    for listing in listings:
        
        balance = Balances.objects.get(user=listing.user, currency=listing.currency)
        
        if balance.balance < listing.amount:
            print("Curreency amount too small for ask")
            print(listing.user.username)
            print(listing.currency.name)
            print(balance.balance)
            print(listing.amount)
            
            listing.delete()

    
    listings = Listings.objects.filter(type="order_bid")

    for listing in listings:
        
        balance = Balances.objects.get(user=listing.user, currency=get_currency_btc())
        
        if balance.balance < int(listing.amount*listing.get_price_sat()):
            print("BTC amount too small for bid")
            print(listing.user.username)
            print(listing.currency.name)
            print(balance.balance)
            print(int(listing.amount*listing.get_price_sat()))
            
            listing.delete()

class Command(BaseCommand):
    help = "Delete unelectable listing"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        
        
        while True:
            remove_unexecutable_listings()
            time.sleep(60)