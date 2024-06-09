from django.core.management.base import BaseCommand
from walletapp.models import Balances
from walletapp.utils import get_currency_btc
from walletapp.models import User


class Command(BaseCommand):
    help = "Reset user pwd"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        user = User.objects.get(username="ethan2")
        user.username = "ethan5"
        user.save()
