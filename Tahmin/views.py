from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.views import LoginView
from .models import Stock, StockPrice, StockAnalysis
from django.urls import reverse
from django.http import JsonResponse

# Create your views here.


from django.http import HttpResponse

def is_staff_user(user):
    return user.is_staff

class CustomLoginView(LoginView):
    template_name = 'Tahmin/login.html'
    
    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')

def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')
    return render(request, 'Tahmin/home.html')

@login_required
@user_passes_test(is_staff_user)
def admin_dashboard(request):
    # İstatistikleri hesapla
    total_users = User.objects.count()
    total_predictions = 0  # Tahmin modeli oluşturulduğunda güncellenecek
    today_predictions = 0  # Tahmin modeli oluşturulduğunda güncellenecek
    total_stocks = Stock.objects.count()  # Toplam hisse sayısını Stock modelinden al
    
    context = {
        'total_users': total_users,
        'total_predictions': total_predictions,
        'today_predictions': today_predictions,
        'total_stocks': total_stocks,
    }
    return render(request, 'Tahmin/admin_dashboard.html', context)

@login_required
def dashboard(request):
    if request.user.is_staff:
        return redirect('admin_dashboard')
    return render(request, 'Tahmin/dashboard.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        email = request.POST.get('email')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Bu kullanıcı adı zaten kullanılıyor.')
            return redirect('register')
            
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Bu e-posta adresi zaten kullanılıyor.')
            return redirect('register')
        
        user = User.objects.create_user(username=username, password=password, email=email)
        login(request, user)
        messages.success(request, 'Kayıt başarılı! Hoş geldiniz.')
        return redirect('dashboard')
        
    return render(request, 'Tahmin/register.html')

@login_required
@user_passes_test(is_staff_user)
def stock_management(request):
    stocks = Stock.objects.all().order_by('symbol')
    context = {
        'stocks': stocks,
        'total_stocks': stocks.count(),
        'active_stocks': stocks.filter(is_active=True).count(),
    }
    return render(request, 'Tahmin/stock_management.html', context)

@login_required
@user_passes_test(is_staff_user)
def add_stock(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        symbol = request.POST.get('symbol')
        sector = request.POST.get('sector')
        description = request.POST.get('description')
        
        if not Stock.objects.filter(symbol=symbol).exists():
            Stock.objects.create(
                name=name,
                symbol=symbol.upper(),
                sector=sector,
                description=description
            )
        return redirect('stock_management')
    return redirect('stock_management')

@login_required
@user_passes_test(is_staff_user)
def edit_stock(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    
    if request.method == 'POST':
        stock.name = request.POST.get('name')
        stock.symbol = request.POST.get('symbol').upper()
        stock.sector = request.POST.get('sector')
        stock.description = request.POST.get('description')
        stock.save()
        return redirect('stock_management')
    return redirect('stock_management')

@login_required
@user_passes_test(is_staff_user)
def delete_stock(request, stock_id):
    if request.method == 'POST':
        stock = get_object_or_404(Stock, id=stock_id)
        stock.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('stock_management')
    return redirect('stock_management')

@login_required
@user_passes_test(is_staff_user)
def toggle_stock_status(request, stock_id):
    if request.method == 'POST':
        stock = get_object_or_404(Stock, id=stock_id)
        stock.is_active = not stock.is_active
        stock.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('stock_management')
    return redirect('stock_management')



