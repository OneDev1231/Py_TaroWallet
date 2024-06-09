from django import template

register = template.Library()


@register.filter
def to_sigdigits(obj, sigdigits):
    if obj:
        return "{0:.{sigdigits}}".format(obj, sigdigits=sigdigits)
    else:
        return obj
