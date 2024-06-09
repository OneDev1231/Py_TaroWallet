import os

from django import template

register = template.Library()


@register.filter
def get_link_from_txid(td_ix: str):
    if os.getenv("DEV_ENV") == "DEV":
        return f"https://mempool.space/testnet/tx/{td_ix}"
    else:
        return f"https://mempool.space/tx/{td_ix}"
