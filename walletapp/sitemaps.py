from django.contrib import sitemaps

from .models import Currencies


class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = "daily"

    def items(self):
        currency_cnt = Currencies.objects.all().count()

        sm = [""]

        currencies = ["currency_" + str(i) for i in range(1, currency_cnt)]

        sm = sm + currencies

        return sm

    def location(self, item):
        sm = {
            "": ".tiramisuwallet.com/walletapp/",
        }

        currency_cnt = Currencies.objects.all().count()

        currencies = {
            "currency_" + str(i): f".tiramisuwallet.com/walletapp/currencies_public/{i}"
            for i in range(1, currency_cnt)
        }

        sm = {**sm, **currencies}

        return sm[item]
