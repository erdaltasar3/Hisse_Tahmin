from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login

# Create your views here.


from django.http import HttpResponse

def home(request):
    return HttpResponse("Hisse Tahmin Projesine Hoş Geldiniz!")

from django.shortcuts import render

def home(request):
    return render(request, 'Tahmin/home.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # Boş alan kontrolü
        if not all([username, email, password1, password2]):
            messages.error(request, 'Lütfen tüm alanları doldurun!')
            return redirect('register')

        # Kontroller
        if password1 != password2:
            messages.error(request, 'Şifreler eşleşmiyor!')
            return redirect('register')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Bu kullanıcı adı zaten kullanımda!')
            return redirect('register')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Bu e-posta adresi zaten kullanımda!')
            return redirect('register')

        # Kullanıcı oluşturma
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            login(request, user)  # Kullanıcıyı otomatik giriş yaptır
            messages.success(request, 'Hesabınız başarıyla oluşturuldu!')
            return redirect('home')
        except Exception as e:
            messages.error(request, f'Kayıt sırasında bir hata oluştu: {str(e)}')
            return redirect('register')

    return render(request, 'Tahmin/register.html')
