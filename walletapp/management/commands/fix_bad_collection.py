from django.core.management.base import BaseCommand
from walletapp.models import Balances, Currencies, User, Collections


class Command(BaseCommand):
    help = "Fix bad collection of NFTs"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
      
      
        col_list = Collections.objects.all()
        
        for col in col_list:
        
            asset_list = Currencies.objects.filter(collection=col)

            if len(asset_list)==0:
                print(col.name)
                col.delete()
