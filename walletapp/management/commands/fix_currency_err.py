from django.core.management.base import BaseCommand
from walletapp.models import Listings, Currencies
from django.contrib.auth.models import User, Balances
from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Fix listings"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        balances_below_zero = Balances.objects.filter(balance__lt=0)

        print(balances_below_zero)
