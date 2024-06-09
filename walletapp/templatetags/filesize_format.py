from django import template
from numerize import numerize

register = template.Library()


@register.filter
def filesize_format(num):
    return numerize.numerize(num)
