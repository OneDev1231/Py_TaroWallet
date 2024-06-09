from django.contrib.auth.models import User
from walletapp.utils import get_currency_btc
from django.core.files.base import ContentFile
from walletapp.models import Listings, Currencies
import io
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fix currency image"

    # def add_arguments(self, parser):
    #     parser.add_argument('poll_ids', nargs='+', type=int)

    def handle(self, *args, **options):
        currency = Currencies.objects.get(name="PePe")

        with open(
            "/Users/adamivansky/Downloads/correct_pepe.jpg", "rb"
        ) as picture_orig_file:
            cf = ContentFile(picture_orig_file.read())

        data_format = "jpg"

        if currency.is_nft:
            filename = currency.name
        else:
            filename = currency.acronym

        currency.picture_orig.save(name=filename + "." + data_format, content=cf)
