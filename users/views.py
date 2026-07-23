from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser
import json

@csrf_exempt
def register_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            name = data.get('name')
            
            if not username or not password or not name:
                return JsonResponse({"error": "모든 필드를 입력해야 합니다."}, status=400)
                
            if CustomUser.objects.filter(username=username).exists():
                return JsonResponse({"error": "이미 존재하는 아이디입니다."}, status=400)
                
            user = CustomUser.objects.create_user(username=username, password=password, name=name)
            
            return JsonResponse({
                "message": "회원가입이 완료되었습니다.",
                "unique_code": str(user.unique_code)
            }, status=201)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method Not Allowed"}, status=405)

@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return JsonResponse({
                    "message": "로그인 성공",
                    "unique_code": str(user.unique_code)
                })
            else:
                return JsonResponse({"error": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=401)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Method Not Allowed"}, status=405)

def check_auth_view(request):
    if request.user.is_authenticated:
        return JsonResponse({
            "is_authenticated": True,
            "username": request.user.username,
            "name": request.user.name,
            "unique_code": str(request.user.unique_code)
        })
    else:
        return JsonResponse({"is_authenticated": False})
        
def logout_view(request):
    logout(request)
    return JsonResponse({"message": "로그아웃 되었습니다."})
