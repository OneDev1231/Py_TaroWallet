from django.core.management.base import BaseCommand
from walletapp.models import Listings, Currencies
from django.contrib.auth.models import User
from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Fix listings"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        Listings.objects.get(pk=512).delete()
