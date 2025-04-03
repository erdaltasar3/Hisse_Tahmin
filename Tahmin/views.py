from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.views import LoginView
from .models import Stock, StockPrice, StockAnalysis, StockFile
from django.urls import reverse
from django.http import JsonResponse
from django.template.loader import render_to_string
import pandas as pd
from django.core.exceptions import ValidationError
import os
from django.conf import settings
import json

# Create your views here.


from django.http import HttpResponse

def is_staff_user(user):
    return user.is_staff

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
        print("Gelen veri:", request.POST)  # POST verilerini görüntüle
        print("Password:", request.POST.get('password1'))   # Kullanıcı bilgisini görüntüle
        username = request.POST.get('username')
        password = request.POST.get('password1')
        email = request.POST.get('email')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Bu kullanıcı adı zaten kullanılıyor.')
            return redirect('register')
            
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Bu e-posta adresi zaten kullanılıyor.')
            return redirect('register')
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            messages.success(request, 'Kayıt başarılı! Şimdi giriş yapabilirsiniz.')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Kayıt sırasında bir hata oluştu: {str(e)}')
            return redirect('register')
        
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
        try:
            name = request.POST.get('name')
            symbol = request.POST.get('symbol')
            sector = request.POST.get('sector')
            
            if not name or not symbol:
                return JsonResponse({
                    'success': False,
                    'error': 'Hisse adı ve sembol zorunludur!'
                })
            
            if Stock.objects.filter(symbol=symbol.upper()).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'{symbol.upper()} sembolü ile kayıtlı bir hisse zaten mevcut!'
                })
            
            Stock.objects.create(
                name=name,
                symbol=symbol.upper(),
                sector=sector
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Hisse başarıyla eklendi.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu'
    })

@login_required
@user_passes_test(is_staff_user)
def edit_stock(request, stock_id):
    if request.method == 'POST':
        try:
            stock = Stock.objects.get(id=stock_id)
            stock.name = request.POST.get('name')
            stock.symbol = request.POST.get('symbol').upper()
            stock.sector = request.POST.get('sector')
            stock.save()
            return JsonResponse({'success': True})
        except Stock.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Hisse bulunamadı.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Geçersiz istek.'})

@login_required
@user_passes_test(is_staff_user)
def delete_stock(request, stock_id):
    if request.method == 'POST':
        try:
            stock = Stock.objects.get(id=stock_id)
            stock.delete()
            return JsonResponse({'success': True})
        except Stock.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Hisse bulunamadı.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Geçersiz istek.'})

@login_required
@user_passes_test(is_staff_user)
def toggle_stock_status(request, stock_id):
    if request.method == 'POST':
        try:
            stock = Stock.objects.get(id=stock_id)
            stock.is_active = not stock.is_active
            stock.save()
            return JsonResponse({'success': True})
        except Stock.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Hisse bulunamadı.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Geçersiz istek.'})

@login_required
@user_passes_test(is_staff_user)
def add_stock_price(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    
    if request.method == 'POST':
        try:
            date = request.POST.get('date')
            
            # Tüm mevcut mesajları temizle
            messages.get_messages(request).used = True
            
            # Aynı tarih için kayıt var mı kontrol et
            if StockPrice.objects.filter(stock=stock, date=date).exists():
                messages.error(request, f'{date} tarihi için fiyat verisi zaten mevcut.')
                return redirect('add_stock_price', stock_id=stock_id)
            
            opening_price = request.POST.get('opening_price')
            closing_price = request.POST.get('closing_price')
            highest_price = request.POST.get('highest_price')
            lowest_price = request.POST.get('lowest_price')
            volume = request.POST.get('volume')
            
            # Günlük değişim yüzdesini hesapla
            daily_change = ((float(closing_price) - float(opening_price)) / float(opening_price)) * 100
            
            StockPrice.objects.create(
                stock=stock,
                date=date,
                opening_price=opening_price,
                closing_price=closing_price,
                highest_price=highest_price,
                lowest_price=lowest_price,
                volume=volume,
                daily_change=daily_change
            )
            return redirect('stock_management')
            
        except Exception as e:
            messages.error(request, f'Hata oluştu: {str(e)}')
            return redirect('add_stock_price', stock_id=stock_id)
    
    # GET isteği için tüm mesajları temizle
    messages.get_messages(request).used = True
    
    context = {
        'stock': stock,
        'today': timezone.now().date().isoformat()
    }
    return render(request, 'Tahmin/add_stock_price.html', context)

@login_required
def bulk_add_stock_prices(request):
    stocks = Stock.objects.all().order_by('symbol')
    context = {
        'stocks': stocks,
    }
    return render(request, 'Tahmin/bulk_add_stock_prices.html', context)

@login_required
def add_stock_price_api(request):
    if request.method == 'POST':
        stock_id = request.POST.get('stock_id')
        date = request.POST.get('date')
        
        # Aynı tarihte kayıt var mı kontrol et
        if StockPrice.objects.filter(stock_id=stock_id, date=date).exists():
            return JsonResponse({
                'success': False,
                'error': f"{date} tarihinde zaten bir kayıt mevcut!"
            })
        
        try:
            stock = Stock.objects.get(id=stock_id)
            
            # Günlük değişim yüzdesini hesapla
            opening = float(request.POST.get('opening_price'))
            closing = float(request.POST.get('closing_price'))
            daily_change = ((closing - opening) / opening) * 100
            
            StockPrice.objects.create(
                stock=stock,
                date=date,
                opening_price=request.POST.get('opening_price'),
                closing_price=request.POST.get('closing_price'),
                highest_price=request.POST.get('highest_price'),
                lowest_price=request.POST.get('lowest_price'),
                volume=request.POST.get('volume'),
                daily_change=daily_change
            )
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu'
    })

@login_required
@user_passes_test(is_staff_user)
def upload_stock_data(request):
    if request.method == 'POST':
        try:
            stock_id = request.POST.get('stock_id')
            stock = get_object_or_404(Stock, id=stock_id)
            file = request.FILES.get('file')
            
            if not file:
                return JsonResponse({
                    'success': False,
                    'error': 'Dosya yüklenmedi!'
                })
            
            # Dosya uzantısını kontrol et
            file_extension = file.name.split('.')[-1].lower()
            if file_extension not in ['csv', 'xlsx']:
                return JsonResponse({
                    'success': False,
                    'error': 'Sadece CSV ve Excel dosyaları desteklenmektedir!'
                })
            
            # Dosyayı kaydet
            try:
                # Ana dizini oluştur
                base_upload_dir = os.path.join('uploads', 'stock_data')
                if not os.path.exists(base_upload_dir):
                    os.makedirs(base_upload_dir)
                
                # Hisse için özel klasör oluştur
                stock_upload_dir = os.path.join(base_upload_dir, stock.symbol)
                if not os.path.exists(stock_upload_dir):
                    os.makedirs(stock_upload_dir)
                
                # Dosya adını oluştur: YYYY-MM-DD_HHMMSS.extension
                timestamp = timezone.now().strftime('%Y-%m-%d_%H%M%S')
                filename = f"{timestamp}.{file_extension}"
                
                # Dosya yolunu oluştur
                file_path = os.path.join(stock_upload_dir, filename)
                
                # Dosyayı kaydet
                with open(file_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                
                return JsonResponse({
                    'success': True,
                    'message': f'Dosya başarıyla yüklendi: {filename}',
                    'file_path': file_path
                })
                    
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Dosya kaydetme hatası: {str(e)}'
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu'
    })

@login_required
@user_passes_test(is_staff_user)
def process_stock_data(request, file_id):
    if request.method == 'POST':
        try:
            stock_file = StockFile.objects.get(id=file_id)
            
            if stock_file.is_processed:
                return JsonResponse({
                    'success': False,
                    'error': 'Bu dosya zaten işlenmiş!'
                })
            
            file_path = stock_file.file_path
            stock = stock_file.stock

            if not os.path.exists(file_path):
                return JsonResponse({
                    'success': False,
                    'error': 'Dosya bulunamadı.'
                })

            try:
                # CSV dosyasını oku ve ilk satırı atlayarak sütun isimlerini manuel belirt
                df = pd.read_csv(file_path, encoding='utf-8', skiprows=1, 
                               names=['Tarih', 'Açılış', 'Son', 'Yüksek', 'Düşük', 'Hacim', 'Değişim %'])
                
                # Tarih sütununu temizle ve dönüştür
                df['Tarih'] = df['Tarih'].str.strip().str.replace('"', '')
                df['Tarih'] = pd.to_datetime(df['Tarih'], format='%d.%m.%Y')
                
                success_count = 0
                error_count = 0
                errors = []
                
                # Verileri veritabanına kaydet
                for index, row in df.iterrows():
                    try:
                        # Hacim değerini düzelt (M, B gibi son ekleri kaldır ve sayıya çevir)
                        volume = str(row['Hacim']).strip().replace('"', '')
                        if 'M' in volume:
                            volume = float(volume.replace('M', '').replace(',', '.')) * 1_000_000
                        elif 'B' in volume:
                            volume = float(volume.replace('B', '').replace(',', '.')) * 1_000
                        else:
                            volume = float(volume.replace(',', '.'))
                        
                        # Yüzde değişimi düzelt
                        change_str = str(row['Değişim %']).strip().replace('"', '').replace('%', '').replace(',', '.')
                        change_percent = float(change_str) if change_str else 0.0
                        
                        # Fiyat değerlerini float'a çevir
                        closing_price = float(str(row['Son']).strip().replace('"', '').replace(',', '.'))
                        opening_price = float(str(row['Açılış']).strip().replace('"', '').replace(',', '.'))
                        highest_price = float(str(row['Yüksek']).strip().replace('"', '').replace(',', '.'))
                        lowest_price = float(str(row['Düşük']).strip().replace('"', '').replace(',', '.'))
                        
                        # Eğer bu tarih için kayıt varsa güncelle, yoksa yeni kayıt oluştur
                        stock_price, created = StockPrice.objects.update_or_create(
                            stock=stock,
                            date=row['Tarih'].date(),
                            defaults={
                                'closing_price': closing_price,
                                'opening_price': opening_price,
                                'highest_price': highest_price,
                                'lowest_price': lowest_price,
                                'volume': volume,
                                'daily_change': change_percent
                            }
                        )
                        success_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        error_detail = f"Satır {index + 2}: {str(e)}"
                        errors.append(error_detail)
                        continue
                
                # Eğer hiç başarılı kayıt yoksa ve hata varsa
                if success_count == 0 and error_count > 0:
                    error_message = "Hiçbir veri kaydedilemedi!\n\nHata Detayları:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        error_message += f"\n\n... ve {len(errors) - 5} hata daha."
                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    })
                
                # En az bir başarılı kayıt varsa dosyayı işlenmiş olarak işaretle
                if success_count > 0:
                    stock_file.is_processed = True
                    stock_file.save()
                
                # Başarı mesajı döndür
                message = f'{success_count} kayıt başarıyla eklendi/güncellendi.'
                if error_count > 0:
                    message += f'\n{error_count} kayıt işlenemedi.'
                    if errors:
                        message += '\n\nHata Detayları:\n' + '\n'.join(errors[:3])
                        if len(errors) > 3:
                            message += f'\n\n... ve {len(errors) - 3} hata daha.'
                
                return JsonResponse({
                    'success': True,
                    'message': message,
                    'success_count': success_count,
                    'error_count': error_count
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'CSV okuma hatası: {str(e)}'
                })
            
        except StockFile.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dosya bulunamadı.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Veri işleme hatası: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu.'
    })

@login_required
@user_passes_test(is_staff_user)
def stock_files(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    files = stock.files.all()
    return render(request, 'Tahmin/stock_files.html', {
        'stock': stock,
        'files': files
    })

@login_required
@user_passes_test(is_staff_user)
def upload_stock_file(request, stock_id):
    if request.method == 'POST':
        try:
            stock = get_object_or_404(Stock, id=stock_id)
            file = request.FILES.get('file')
            note = request.POST.get('note')
            
            if not file:
                return JsonResponse({
                    'success': False,
                    'error': 'Dosya yüklenmedi!'
                })
            
            # Dosya uzantısını kontrol et
            file_extension = file.name.split('.')[-1].lower()
            if file_extension not in ['csv', 'xlsx']:
                return JsonResponse({
                    'success': False,
                    'error': 'Sadece CSV ve Excel dosyaları desteklenmektedir!'
                })
            
            # Dosyayı kaydet
            try:
                # Ana dizini oluştur
                base_upload_dir = os.path.join('uploads', 'stock_data')
                if not os.path.exists(base_upload_dir):
                    os.makedirs(base_upload_dir)
                
                # Hisse için özel klasör oluştur
                stock_upload_dir = os.path.join(base_upload_dir, stock.symbol)
                if not os.path.exists(stock_upload_dir):
                    os.makedirs(stock_upload_dir)
                
                # Dosya adını oluştur: YYYY-MM-DD_HHMMSS.extension
                timestamp = timezone.now().strftime('%Y-%m-%d_%H%M%S')
                filename = f"{timestamp}.{file_extension}"
                
                # Dosya yolunu oluştur
                file_path = os.path.join(stock_upload_dir, filename)
                
                # Dosyayı kaydet
                with open(file_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)
                
                # Veritabanına kaydet
                stock_file = StockFile.objects.create(
                    stock=stock,
                    filename=filename,
                    file_path=file_path,
                    note=note,
                    uploaded_by=request.user
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Dosya başarıyla yüklendi.',
                    'file_id': stock_file.id
                })
                    
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Dosya kaydetme hatası: {str(e)}'
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu'
    })

@login_required
@user_passes_test(is_staff_user)
def update_file_note(request, file_id):
    if request.method == 'POST':
        try:
            stock_file = get_object_or_404(StockFile, id=file_id)
            note = request.POST.get('note')
            
            stock_file.note = note
            stock_file.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Not başarıyla güncellendi.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu'
    })

@login_required
@user_passes_test(is_staff_user)
def delete_file(request, file_id):
    if request.method == 'POST':
        try:
            stock_file = get_object_or_404(StockFile, id=file_id)
            
            # Dosyayı diskten sil
            if os.path.exists(stock_file.file_path):
                os.remove(stock_file.file_path)
            
            # Veritabanından sil
            stock_file.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Dosya başarıyla silindi.'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Geçersiz istek metodu'
    })

@login_required
def profile_view(request):
    return render(request, 'Tahmin/profile.html', {
        'user': request.user,
        'user_role': 'Yetkili Kullanıcı' if request.user.is_staff else 'Normal Kullanıcı'
    })

def logout_view(request):
    logout(request)
    return redirect('home')

def login_view(request):
        
    print("Gelen veri:", request.POST)  # POST verilerini görüntüle
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Başarıyla giriş yaptınız.')
            
            if user.is_staff:
                return redirect('admin_dashboard')
            return redirect('dashboard')
        else:
            messages.error(request, 'Kullanıcı adı veya şifre hatalı.')
    
    return render(request, 'Tahmin/login.html')



