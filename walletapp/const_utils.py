from django.apps import apps


def get_constant(constant_name):
    ConstantsNumeric = apps.get_model("walletapp.ConstantsNumeric")
    constant = ConstantsNumeric.objects.get(name=constant_name)
    return int(constant.value)


def set_constant(constant_name, value):
    ConstantsNumeric = apps.get_model("walletapp.ConstantsNumeric")
    if ConstantsNumeric.objects.filter(name=constant_name).exists():

        constant = ConstantsNumeric.objects.get(name=constant_name)
        constant.value = value
        constant.save()

    else:

        constant = ConstantsNumeric.objects.create(name=constant_name, value=value)
        constant.save()


def get_min_exchange_sats():
    return get_constant("min_exchange_sats")
    # return 10


def get_initial_free_btc_balance():
    return get_constant("initial_free_btc_balance")
    # return 500


def get_max_withdrawal_onchain():
    return get_constant("max_withdrawal_onchain")
    # return 10000000


def get_max_withdrawal_lnd():
    return get_constant("max_withdrawal_lnd")
    # return 5000000


def get_fee_sat_per_vbyte():
    return get_constant("fee_sat_per_vbyte")
    # return 110


def get_fee_sat_per_wu():
    return int(0.25 * 1000 * get_fee_sat_per_vbyte())


def get_fee_sat_estimate_onchain(amount: int = None):
    onchain_fee = int(get_fee_sat_per_vbyte() * 265)

    # if amount:
    #     return int(max(20, 0.005 * amount) + onchain_fee)
    # else:
    #     return int(max(10, onchain_fee))

    return int(max(10, onchain_fee))


def get_final_fee(onchain_fee: int, amount: int = None) -> int:
    if amount:
        return int(max(20, 0.005 * amount) + onchain_fee)
    else:
        return int(max(10, 2 * onchain_fee))


def get_fee_sat_estimate_lnd(amount=0):
    return int(max(10, 0.03 * amount))
    # return 0


def get_fee_sat_estimate_exchange(amount: int):
    # return int(max(3, 0.03 * amount))
    return 0
