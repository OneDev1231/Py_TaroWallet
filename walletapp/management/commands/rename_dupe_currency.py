from django.core.management.base import BaseCommand
from walletapp.models import Balances, Transactions, User, Currencies

from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Delete duplicate btc"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        # curr = Currencies.objects.get(id=477)
        # print(curr.name)
        # curr.name = "AdamCoin2"
        # curr.acronym = "AC2"
        # curr.save()

        curr_list = Currencies.objects.all()

        names = list(set([curr.name for curr in curr_list]))

        for i, curr_name in enumerate(names):
            print(f"Checking {curr_name}")
            curr_list = Currencies.objects.filter(name=curr_name).order_by(
                "created_timestamp"
            )

            if len(curr_list) > 1:
                print(f"Found dupe for {curr_name}")
                for i, curr in enumerate(curr_list):
                    if i > 0:
                        curr.name = str(i) + curr.name
                        print(f"New name {curr.name} {curr.created_timestamp}")
                        curr.save()
                    else:
                        print(f"keeping original {curr.name} {curr.created_timestamp}")

        curr_list = Currencies.objects.filter(is_nft=False)

        acronyms = list(set([curr.acronym for curr in curr_list]))

        for i, curr_acr in enumerate(acronyms):
            print(f"Checking {curr_acr}")
            curr_list = Currencies.objects.filter(acronym=curr_acr).order_by(
                "created_timestamp"
            )

            if len(curr_list) > 1:
                print(f"Found dupe for {curr_acr}")
                for i, curr in enumerate(curr_list):
                    if i > 0:
                        curr.name = (str(i) + curr.acronym)[:5]
                        print(f"New acronym {curr.acronym} {curr.created_timestamp}")
                        curr.save()
                    else:
                        print(
                            f"keeping original {curr.acronym} {curr.created_timestamp}"
                        )
