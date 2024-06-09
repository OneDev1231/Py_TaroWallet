import os


def load_nav_obj(request):
    return {"DEV_ENV": os.getenv("DEV_ENV")}
