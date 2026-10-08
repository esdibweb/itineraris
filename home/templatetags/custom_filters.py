from django import template

register = template.Library()


@register.filter
def startswith(value, arg):
    """
    Checks if the given value starts with the specified argument.
    """
    return value.startswith(arg)
