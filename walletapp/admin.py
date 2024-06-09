from django.contrib import admin

from .models import Balances, ConstantsNumeric, Currencies, Notifications, Transactions

admin.site.register(Currencies)
admin.site.register(Transactions)
admin.site.register(Balances)
admin.site.register(ConstantsNumeric)
admin.site.register(Notifications)
