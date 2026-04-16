
class ThemeCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Set cookie with the username for consistency across all accounts
            response.set_cookie('theme_user_id', str(request.user.username), httponly=False, samesite='Lax', path='/')
        else:
            response.set_cookie('theme_user_id', 'guest', httponly=False, samesite='Lax', path='/')
        return response
