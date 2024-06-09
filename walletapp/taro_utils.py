from django.core.management import setup_environ

from tarowallet import settings

from .models import Currencies

setup_environ(settings)


def process_send_currency():
    print(Currencies.objects.all().count())


def process_receive_currency():
    pass


process_send_currency()
