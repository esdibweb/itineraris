def client_ip(request):
    """
    Client address for login throttling (django-axes).

    The app runs behind one reverse proxy, which appends the address it received the
    request from to X-Forwarded-For. Only that last entry is trustworthy: earlier
    entries come from the client and can be forged.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR')
