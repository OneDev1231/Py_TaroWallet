from django import template

from ..const_utils import get_fee_sat_estimate_onchain

register = template.Library()


@register.simple_tag
def get_fee_sat_estimate_onchain_tag():
    return get_fee_sat_estimate_onchain()
