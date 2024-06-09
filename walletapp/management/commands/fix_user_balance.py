from django.core.management.base import BaseCommand
from walletapp.models import Listings, Currencies, Balances
from django.contrib.auth.models import User
from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Fix user balance"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        
        user = User.objects.get(id=394)
        currency = Currencies.objects.get(name="AdamUSD")
        
        
        bal = Balances.objects.get(user=user,currency=currency)
        
        print(bal.balance)
        print(bal.pending_balance)
        
        bal.pending_balance=bal.pending_balance+1
        bal.save()
