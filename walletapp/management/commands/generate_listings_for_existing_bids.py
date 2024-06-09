




from django.core.management.base import BaseCommand
from walletapp.models import Listings, Currencies, Balances, Notifications
from django.contrib.auth.models import User
from walletapp.utils import get_currency_btc


class Command(BaseCommand):
    help = "Generate notification for existing bids and asks"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):


        listing_list = Listings.objects.all()

        for instance in listing_list:

            if instance.currency.is_nft:
                balance = Balances.objects.get(currency=instance.currency, balance__gt=0)
                if instance.type in ["order_bid", "order_ask"]:
                    notification = Notifications.objects.create(
                        destination_user=balance.user,
                        message=(
                            "There is a new"
                            f" {'bid' if instance.type=='order_bid' else 'ask'} order on"
                            f" your NFT {instance.currency.name} {instance.user.username}"
                        ),
                        read=False,
                        type="success",
                        object_name="Listings",
                        listing=instance,
                    )
                    notification.save()