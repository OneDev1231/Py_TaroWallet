from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User, Currencies

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Delete currency"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        # curr = Currencies.objects.get(id=477)
        # print(curr.name)
        # curr.name = "AdamCoin2"
        # curr.acronym = "AC2"
        # curr.save()
        curr = Currencies.objects.get(name='e83026c32e')

        trn = Transactions.objects.get(currency=curr)
        trn.delete()

        bal_list = Balances.objects.filter(currency=curr)
        
        for bal in bal_list:
            bal.delete()

        curr.delete()
