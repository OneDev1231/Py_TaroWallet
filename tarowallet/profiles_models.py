from allauth.account.utils import perform_login
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.models import User


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        user = sociallogin.user
        if user.id:
            return
        try:
            usr = User.objects.get(
                email=user.email
            )  # if user exists, connect the account to the existing account and login
            sociallogin.state["process"] = "connect"
            perform_login(request, usr, "none")
        except User.DoesNotExist:
            pass

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.username = user.email
        return user
