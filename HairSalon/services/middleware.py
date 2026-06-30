from django.shortcuts import redirect
from django.urls import resolve, Resolver404
from django.contrib import messages
from django.conf import settings

class RoleRequiredMiddleware:
    """
    Middleware that ensures authenticated users have selected a role.
    If they haven't selected a role, redirect them to the onboarding choice page.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info
        
        # 1. Skip role check for admin and static/media files
        is_admin = path.startswith('/admin/')
        static_url = getattr(settings, 'STATIC_URL', '/static/')
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        is_static = (static_url and path.startswith(static_url)) or (media_url and path.startswith(media_url)) or path.startswith('/static/') or path.startswith('/media/')
        
        if is_admin or is_static:
            return self.get_response(request)

        # 2. Exclude onboarding/auth paths based on URL path prefixes
        allowed_path_prefixes = [
            '/services/onboarding/',
            '/services/choose-role/',
            '/services/register/',
            '/services/accounts/',
            '/services/forgot-password/',
            '/services/verify-otp/',
        ]
        if any(path.startswith(prefix) for prefix in allowed_path_prefixes):
            return self.get_response(request)

        # 3. Exclude onboarding/auth paths based on resolved URL names
        try:
            resolved = resolve(path)
            url_name = resolved.url_name
        except Resolver404:
            url_name = None

        allowed_url_names = {
            'onboarding_choice',
            'choose_role',
            'logout',
            'login',
            'register',
            'forgot_password',
            'verify_otp',
        }
        if url_name in allowed_url_names:
            return self.get_response(request)

        # 4. For authenticated users, check if they have a role
        if request.user.is_authenticated:
            if not request.user.role:
                messages.info(request, "Please select your account role before continuing.")
                return redirect('onboarding_choice')

        response = self.get_response(request)
        return response
