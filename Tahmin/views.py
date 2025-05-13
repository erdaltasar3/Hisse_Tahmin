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
from django.db import transaction

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

def convert_volume(volume_str):
    """
    Hacim değerini float'a çevirir.
    Örnek: '555.01K' -> 555010.0, '1.5M' -> 1500000.0
    """
    try:
        if isinstance(volume_str, str):
            # Virgülü noktaya çevir
            volume_str = volume_str.replace(',', '.')
            
            # 'K' harfini kaldır ve 1000 ile çarp
            if volume_str.endswith('K'):
                return float(volume_str.replace('K', '')) * 1000
            # 'M' harfini kaldır ve 1,000,000 ile çarp
            elif volume_str.endswith('M'):
                return float(volume_str.replace('M', '')) * 1000000
            # 'B' harfini kaldır ve 1,000,000,000 ile çarp
            elif volume_str.endswith('B'):
                return float(volume_str.replace('B', '')) * 1000000000
            # Sadece sayı ise direkt dönüştür
            else:
                return float(volume_str)
        return float(volume_str)
    except (ValueError, TypeError):
        return None

@login_required
@user_passes_test(is_staff_user)
def process_stock_data(request, file_id):
    try:
        stock_file = StockFile.objects.get(id=file_id, uploaded_by=request.user)
        
        if not os.path.exists(stock_file.file_path):
            return JsonResponse({
                'success': False,
                'error': 'Dosya bulunamadı.'
            })
            
        success_count = 0
        error_count = 0
        error_details = []
        duplicate_count = 0
        total_rows = 0

        try:
            # CSV dosyasını oku ve sütun isimlerini belirt
            df = pd.read_csv(stock_file.file_path, encoding='utf-8')
            total_rows = len(df)
            
            # Sütun isimlerini kontrol et ve gerekirse değiştir
            column_mappings = {
                'Tarih': 'Date',
                'Date': 'Date',
                'Açılış': 'Open',
                'Open': 'Open',
                'Yüksek': 'High',
                'High': 'High',
                'Düşük': 'Low',
                'Low': 'Low',
                'Şimdi': 'Close',  # Kapanış fiyatı
                'Kapanış': 'Close',
                'Close': 'Close',
                'Hacim': 'Volume',
                'Volume': 'Volume',
                'Vol.': 'Volume',
                'Vol': 'Volume',
                'Hac.': 'Volume',  # Hacim sütunu
                'Hacim.': 'Volume',
                'Fark %': 'Change'  # Günlük değişim yüzdesi
            }
            
            # Sütun isimlerini değiştir
            df = df.rename(columns=column_mappings)
            
            # Gerekli sütunların varlığını kontrol et
            required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"CSV dosyasında gerekli sütunlar eksik: {', '.join(missing_columns)}")
                
            # Sütun isimlerini göster (debug için)
            print("Mevcut sütunlar:", df.columns.tolist())
            
            for index, row in df.iterrows():
                try:
                    date = pd.to_datetime(row['Date'], dayfirst=True).date()
                    
                    # Aynı tarihli kayıt var mı kontrol et
                    existing_record = StockPrice.objects.filter(
                        stock=stock_file.stock,
                        date=date
                    ).first()
                    
                    if existing_record:
                        duplicate_count += 1
                        continue

                    # Hacim verisini dönüştür
                    volume = convert_volume(row['Volume'])
                    
                    if volume is None:
                        error_count += 1
                        error_details.append(f"Satır {index + 2}: Geçersiz hacim değeri: {row['Volume']}")
                        continue
                
                    # StockPrice nesnesini oluştur
                    stock_price = StockPrice(
                        stock=stock_file.stock,
                        date=date,
                        opening_price=float(row['Open'].replace(',', '.')),
                        highest_price=float(row['High'].replace(',', '.')),
                        lowest_price=float(row['Low'].replace(',', '.')),
                        closing_price=float(row['Close'].replace(',', '.')),
                        volume=volume,
                        daily_change=float(row.get('Change', '0').replace('%', '').replace(',', '.'))
                    )
                    stock_price.save()
                    success_count += 1

                except Exception as e:
                    error_count += 1
                    error_details.append(f"Satır {index + 2}: {str(e)}")

            # İşleme sonuçlarını kaydet
            stock_file.is_processed = True
            stock_file.success_count = success_count
            stock_file.error_count = error_count
            stock_file.error_details = '\n'.join(error_details)
            stock_file.processed_at = timezone.now()
            stock_file.save()
                
            # Detaylı rapor mesajı oluştur
            message = f'Dosya işleme tamamlandı:\n'
            message += f'• Toplam satır sayısı: {total_rows}\n'
            message += f'• Başarıyla eklenen yeni kayıt: {success_count}\n'
            message += f'• Zaten mevcut olan kayıt: {duplicate_count}\n'
            if error_count > 0:
                message += f'• Hatalı kayıt: {error_count}\n'
                message += f'• İşlenemeyen satır oranı: %{(error_count/total_rows*100):.1f}\n'
            
            # Başarı durumunu hesapla
            processed_ratio = ((success_count + duplicate_count) / total_rows * 100)
            message += f'\nGenel başarı oranı: %{processed_ratio:.1f}'
                
            return JsonResponse({
                'success': True,
                'message': message,
                'details': {
                    'total_rows': total_rows,
                    'success_count': success_count,
                    'duplicate_count': duplicate_count,
                    'error_count': error_count,
                    'processed_ratio': processed_ratio
                }
            })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Dosya işlenirken hata oluştu: {str(e)}'
            })
            
    except StockFile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Dosya bulunamadı.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@user_passes_test(is_staff_user)
def stock_files(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    
    # Upload klasörünü kontrol et
    stock_upload_dir = os.path.join('uploads', 'stock_data', stock.symbol)
    existing_files = set()
    
    if os.path.exists(stock_upload_dir):
        # Klasördeki mevcut dosyaları listele
        existing_files = {f for f in os.listdir(stock_upload_dir) if os.path.isfile(os.path.join(stock_upload_dir, f))}
    
    # Veritabanındaki dosya kayıtlarını kontrol et
    db_files = stock.files.all()
    
    for db_file in db_files:
        file_name = os.path.basename(db_file.file_path)
        
        # Eğer dosya fiziksel olarak yoksa, veritabanından da sil
        if file_name not in existing_files:
            # Önce bu dosyadan yüklenmiş verileri sil
            if db_file.is_processed:
                try:
                    # Dosyadan tarihleri oku ve o tarihlerdeki verileri sil
                    df = pd.read_csv(db_file.file_path, encoding='utf-8')
                    column_mappings = {
                        'Tarih': 'Date',
                        'Date': 'Date'
                    }
                    df = df.rename(columns=column_mappings)
                    dates = pd.to_datetime(df['Date'], dayfirst=True).dt.date.tolist()
                    
                    # Bu tarihlerdeki kayıtları sil
                    StockPrice.objects.filter(
                        stock=stock,
                        date__in=dates
                    ).delete()
                except:
                    # Dosya okunamıyorsa veya başka bir hata olursa, sadece dosya kaydını sil
                    pass
            
            # Dosya kaydını veritabanından sil
            db_file.delete()
    
    # Güncel dosya listesini getir
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
            
            # İlgili StockPrice kayıtlarını sil
            if stock_file.is_processed:
                # Dosyadan yüklenen tüm fiyat verilerini sil
                df = pd.read_csv(stock_file.file_path, encoding='utf-8')
                
                # Sütun isimlerini kontrol et ve gerekirse değiştir
                column_mappings = {
                    'Tarih': 'Date',
                    'Date': 'Date'
                }
                df = df.rename(columns=column_mappings)
                
                # Tarihleri datetime formatına çevir (dayfirst=True ile gün.ay.yıl formatını belirt)
                dates = pd.to_datetime(df['Date'], dayfirst=True).dt.date.tolist()
                
                # Bu tarihlerdeki kayıtları sil
                StockPrice.objects.filter(
                    stock=stock_file.stock,
                    date__in=dates
                ).delete()
            
            # Dosyayı diskten sil
            if os.path.exists(stock_file.file_path):
                os.remove(stock_file.file_path)
            
            # Veritabanından dosya kaydını sil
            stock_file.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Dosya ve ilgili veriler başarıyla silindi.'
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

@login_required
def file_report(request, file_id):
    try:
        stock_file = StockFile.objects.get(id=file_id, uploaded_by=request.user)
        
        if not stock_file.is_processed:
            return JsonResponse({
                'success': False,
                'error': 'Bu dosya henüz işlenmemiş.'
            })
        
        # Detaylı rapor bilgilerini hazırla
        total_rows = stock_file.success_count + stock_file.error_count
        if total_rows > 0:
            processed_ratio = ((stock_file.success_count) / total_rows * 100)
            error_ratio = (stock_file.error_count / total_rows * 100) if stock_file.error_count > 0 else 0
        else:
            processed_ratio = 0
            error_ratio = 0
            
        return JsonResponse({
            'success': True,
            'report': {
                'file_name': stock_file.filename,
                'processed_at': stock_file.processed_at.strftime('%d.%m.%Y %H:%M:%S') if stock_file.processed_at else None,
                'total_rows': total_rows,
                'success_count': stock_file.success_count,
                'error_count': stock_file.error_count,
                'processed_ratio': f'%{processed_ratio:.1f}',
                'error_ratio': f'%{error_ratio:.1f}',
                'error_details': stock_file.error_details.split('\n') if stock_file.error_details else []
            }
        })
        
    except StockFile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Dosya bulunamadı.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
@user_passes_test(is_staff_user)
def process_all_files(request):
    if request.method == 'POST':
        try:
            # Upload ana dizini
            base_upload_dir = os.path.join('uploads', 'stock_data')
            if not os.path.exists(base_upload_dir):
                return JsonResponse({
                    'success': False,
                    'error': 'İşlenecek dosya bulunamadı!'
                })

            results = []
            
            # Her bir hisse klasörünü kontrol et
            for stock_folder in os.listdir(base_upload_dir):
                stock_path = os.path.join(base_upload_dir, stock_folder)
                if not os.path.isdir(stock_path):
                    continue

                # Hisse sembolüne göre Stock nesnesini bul
                try:
                    stock = Stock.objects.get(symbol=stock_folder)
                except Stock.DoesNotExist:
                    continue

                # Hisse klasöründeki her dosyayı kontrol et
                for filename in os.listdir(stock_path):
                    file_path = os.path.join(stock_path, filename)
                    
                    # Sadece CSV dosyalarını işle
                    if not filename.endswith('.csv'):
                        continue

                    try:
                        success_count = 0
                        error_count = 0
                        error_details = []
                        duplicate_count = 0
                        total_rows = 0

                        # CSV dosyasını oku
                        df = pd.read_csv(file_path, encoding='utf-8')
                        total_rows = len(df)
                        
                        # Sütun isimlerini kontrol et ve gerekirse değiştir
                        column_mappings = {
                            'Tarih': 'Date',
                            'Date': 'Date',
                            'Açılış': 'Open',
                            'Open': 'Open',
                            'Yüksek': 'High',
                            'High': 'High',
                            'Düşük': 'Low',
                            'Low': 'Low',
                            'Şimdi': 'Close',
                            'Kapanış': 'Close',
                            'Close': 'Close',
                            'Hacim': 'Volume',
                            'Volume': 'Volume',
                            'Vol.': 'Volume',
                            'Vol': 'Volume',
                            'Hac.': 'Volume',
                            'Hacim.': 'Volume',
                            'Fark %': 'Change'
                        }
                        
                        # Sütun isimlerini değiştir
                        df = df.rename(columns=column_mappings)
                        
                        # Gerekli sütunların varlığını kontrol et
                        required_columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
                        missing_columns = [col for col in required_columns if col not in df.columns]
                        
                        if missing_columns:
                            results.append({
                                'stock': stock.symbol,
                                'status': 'error',
                                'message': f"Gerekli sütunlar eksik: {', '.join(missing_columns)}"
                            })
                            continue

                        # Her bir satırı işle
                        for index, row in df.iterrows():
                            try:
                                date = pd.to_datetime(row['Date'], dayfirst=True).date()
                                
                                # Aynı tarihli kayıt var mı kontrol et
                                if StockPrice.objects.filter(stock=stock, date=date).exists():
                                    duplicate_count += 1
                                    continue

                                # Hacim verisini dönüştür
                                volume = convert_volume(row['Volume'])
                                
                                if volume is None:
                                    error_count += 1
                                    error_details.append(f"Satır {index + 2}: Geçersiz hacim değeri: {row['Volume']}")
                                    continue
                            
                                # StockPrice nesnesini oluştur ve kaydet
                                stock_price = StockPrice(
                                    stock=stock,
                                    date=date,
                                    opening_price=float(row['Open'].replace(',', '.')),
                                    highest_price=float(row['High'].replace(',', '.')),
                                    lowest_price=float(row['Low'].replace(',', '.')),
                                    closing_price=float(row['Close'].replace(',', '.')),
                                    volume=volume,
                                    daily_change=float(row.get('Change', '0').replace('%', '').replace(',', '.'))
                                )
                                stock_price.save()
                                success_count += 1

                            except Exception as e:
                                error_count += 1
                                error_details.append(f"Satır {index + 2}: {str(e)}")

                        # StockFile nesnesini güncelle veya oluştur
                        stock_file, created = StockFile.objects.get_or_create(
                            stock=stock,
                            file_path=file_path,
                            defaults={
                                'filename': filename,
                                'uploaded_by': request.user
                            }
                        )
                        
                        stock_file.is_processed = True
                        stock_file.success_count = success_count
                        stock_file.error_count = error_count
                        stock_file.error_details = '\n'.join(error_details)
                        stock_file.processed_at = timezone.now()
                        stock_file.save()

                        results.append({
                            'stock': stock.symbol,
                            'status': 'success',
                            'total_rows': total_rows,
                            'success_count': success_count,
                            'error_count': error_count,
                            'duplicate_count': duplicate_count,
                            'message': f"Başarıyla işlendi"
                        })

                    except Exception as e:
                        results.append({
                            'stock': stock.symbol,
                            'status': 'error',
                            'message': str(e)
                        })

            if not results:
                return JsonResponse({
                    'success': False,
                    'error': 'İşlenecek dosya bulunamadı!'
                })

            return JsonResponse({
                'success': True,
                'results': results
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
def delete_all_stock_prices(request):
    if request.method == 'POST':
        try:
            # Tüm StockPrice kayıtlarını sil
            deleted_count = StockPrice.objects.all().delete()[0]
            
            return JsonResponse({
                'success': True,
                'message': f'Toplam {deleted_count} hisse fiyat verisi başarıyla silindi.'
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
def stock_detail(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    prices = stock.prices.order_by('-date')[:30]
    return render(request, 'Tahmin/stock_detail.html', {'stock': stock, 'prices': prices})

@login_required
@user_passes_test(is_staff_user)
@transaction.atomic
def calculate_analysis(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    prices = StockPrice.objects.filter(stock=stock).order_by('date')
    StockAnalysis.objects.filter(stock=stock).delete()

    # Eğer fiyat verisi yoksa uyarı ver
    if not prices.exists():
        messages.error(request, f"{stock.name} için fiyat verisi bulunamadı. Önce fiyat verilerini yükleyin.")
        return JsonResponse({
            'success': False,
            'message': f"{stock.name} için fiyat verisi bulunamadı. Önce fiyat verilerini yükleyin."
        })

    # Günlük, haftalık ve aylık veri dizileri
    closing_prices = [float(p.closing_price) for p in prices]
    dates = [p.date for p in prices]
    
    # Haftalık ve aylık gruplandırma için pandas kullan
    df = pd.DataFrame({
        'date': dates,
        'price': closing_prices
    })
    
    # Haftanın son günü için haftalık veri oluştur
    df['year_week'] = df['date'].apply(lambda x: f"{x.year}-{x.isocalendar()[1]}")
    weekly_df = df.groupby('year_week').last().reset_index()
    weekly_prices = weekly_df['price'].tolist()
    
    # Ayın son günü için aylık veri oluştur
    df['year_month'] = df['date'].apply(lambda x: f"{x.year}-{x.month}")
    monthly_df = df.groupby('year_month').last().reset_index()
    monthly_prices = monthly_df['price'].tolist()
        
    # Her bir gün için hareketli ortalamaları hesapla
    for i, price in enumerate(prices):
        # Günlük hareketli ortalamalar
        ma_5 = sum(closing_prices[max(0, i-4):i+1]) / min(i+1, 5)
        ma_10 = sum(closing_prices[max(0, i-9):i+1]) / min(i+1, 10)
        ma_20 = sum(closing_prices[max(0, i-19):i+1]) / min(i+1, 20)
        ma_50 = sum(closing_prices[max(0, i-49):i+1]) / min(i+1, 50)
        ma_100 = sum(closing_prices[max(0, i-99):i+1]) / min(i+1, 100)
        ma_200 = sum(closing_prices[max(0, i-199):i+1]) / min(i+1, 200)
        
        # Bu günün hangi hafta ve ay içinde olduğunu bul
        current_date = price.date
        week_index = weekly_df[weekly_df['date'] <= current_date].index.max()
        month_index = monthly_df[monthly_df['date'] <= current_date].index.max()
        
        # Haftalık hareketli ortalamalar (Eğer haftalık veri yeterliyse)
        weekly_ma_30 = None
        weekly_ma_50 = None
        weekly_ma_100 = None
        weekly_ma_200 = None
        
        if week_index is not None and week_index >= 0:
            if week_index >= 29:  # 30 haftalık veri varsa
                weekly_ma_30 = sum(weekly_prices[week_index-29:week_index+1]) / 30
            if week_index >= 49:  # 50 haftalık veri varsa
                weekly_ma_50 = sum(weekly_prices[week_index-49:week_index+1]) / 50
            if week_index >= 99:  # 100 haftalık veri varsa
                weekly_ma_100 = sum(weekly_prices[week_index-99:week_index+1]) / 100
            if week_index >= 199:  # 200 haftalık veri varsa
                weekly_ma_200 = sum(weekly_prices[week_index-199:week_index+1]) / 200
        
        # Aylık hareketli ortalamalar (Eğer aylık veri yeterliyse)
        monthly_ma_12 = None
        monthly_ma_24 = None
        monthly_ma_36 = None
        
        if month_index is not None and month_index >= 0:
            if month_index >= 11:  # 12 aylık veri varsa
                monthly_ma_12 = sum(monthly_prices[month_index-11:month_index+1]) / 12
            if month_index >= 23:  # 24 aylık veri varsa
                monthly_ma_24 = sum(monthly_prices[month_index-23:month_index+1]) / 24
            if month_index >= 35:  # 36 aylık veri varsa
                monthly_ma_36 = sum(monthly_prices[month_index-35:month_index+1]) / 36
        
        # Analiz nesnesini oluştur ve kaydet
        StockAnalysis.objects.create(
            stock=stock,
            date=price.date,
            # Günlük hareketli ortalamalar
            ma_5=ma_5,
            ma_10=ma_10,
            ma_20=ma_20,
            ma_50=ma_50,
            ma_100=ma_100,
            ma_200=ma_200,
            
            # Haftalık hareketli ortalamalar
            weekly_ma=weekly_ma_30,  # Varsayılan weekly_ma alanına 30 haftalık değeri kaydediyoruz
            
            # Ek haftalık ortalamalar için özel alanlar oluşturabiliriz
            # Şu anda weekly_ma_50, weekly_ma_100 vb. alanlar modelde yok
            
            # Aylık hareketli ortalamalar
            monthly_ma=monthly_ma_12,  # Varsayılan monthly_ma alanına 12 aylık değeri kaydediyoruz
            
            # Yıllık hareketli ortalama
            yearly_ma=monthly_ma_36  # 36 aylık (3 yıllık) ortalamayı yearly_ma olarak kaydediyoruz
        )
    
    # AJAX isteği ise JSON yanıt döndür
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"{stock.name} için tüm hareketli ortalamalar (günlük, haftalık, aylık) başarıyla hesaplandı."
        })
    
    # Normal istek ise mesaj göster ve aynı sayfaya yönlendir
    messages.success(request, f"{stock.name} için tüm hareketli ortalamalar başarıyla hesaplandı.")
    return redirect('view_stock_analysis', stock_id=stock.id)

@login_required
@user_passes_test(is_staff_user)
def view_stock_analysis(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    # İstatistikleri hesaplamaya gerek yok, sadece veritabanından oku
    analysis_exists = StockAnalysis.objects.filter(stock=stock).exists()
    
    if not analysis_exists:
        messages.warning(request, f"{stock.name} için henüz hesaplanmış istatistik bulunmuyor. Lütfen önce 'İstatistikleri Güncelle' butonuna tıklayın.")
        return redirect('stock_detail', stock_id=stock.id)
    
    # Burada analiz sayfasını render edecek kodunuzu yazın
    # Örnek olarak:
    analysis = StockAnalysis.objects.filter(stock=stock).order_by('date')
    
    # Tarih ve değerleri listele
    dates = [a.date.strftime('%d.%m.%Y') for a in analysis]
    ma_5_values = [float(a.ma_5) for a in analysis]
    ma_10_values = [float(a.ma_10) for a in analysis]
    ma_20_values = [float(a.ma_20) for a in analysis]
    ma_50_values = [float(a.ma_50) for a in analysis] if analysis.filter(ma_50__isnull=False).exists() else []
    ma_100_values = [float(a.ma_100) for a in analysis] if analysis.filter(ma_100__isnull=False).exists() else []
    ma_200_values = [float(a.ma_200) for a in analysis] if analysis.filter(ma_200__isnull=False).exists() else []
    
    # Haftalık ve aylık hareketli ortalama değerlerini hazırla
    weekly_ma_values = [float(a.weekly_ma) for a in analysis if a.weekly_ma is not None]
    monthly_ma_values = [float(a.monthly_ma) for a in analysis if a.monthly_ma is not None]
    yearly_ma_values = [float(a.yearly_ma) for a in analysis if a.yearly_ma is not None]
    
    # Hisse fiyatlarını da al
    prices = StockPrice.objects.filter(stock=stock).order_by('date')
    price_dates = [p.date.strftime('%d.%m.%Y') for p in prices]
    price_values = [float(p.closing_price) for p in prices]
    
    return render(request, 'Tahmin/stock_analysis_view.html', {
        'stock': stock,
        'dates': dates,
        'price_dates': price_dates,
        'price_values': price_values,
        'ma_5_values': ma_5_values,
        'ma_10_values': ma_10_values, 
        'ma_20_values': ma_20_values,
        'ma_50_values': ma_50_values,
        'ma_100_values': ma_100_values,
        'ma_200_values': ma_200_values,
        # Haftalık ve aylık ortalamalar
        'weekly_ma_30_values': weekly_ma_values,  # 30 haftalık (model alanında weekly_ma olarak saklanıyor)
        'monthly_ma_12_values': monthly_ma_values, # 12 aylık (model alanında monthly_ma olarak saklanıyor)
        'monthly_ma_36_values': yearly_ma_values, # 36 aylık (model alanında yearly_ma olarak saklanıyor)
    })

@login_required
@user_passes_test(is_staff_user)
def stock_analysis_detail(request, stock_id):
    stock = get_object_or_404(Stock, id=stock_id)
    prices = StockPrice.objects.filter(stock=stock).order_by('date')
    price_dates = [p.date.strftime('%d.%m.%Y') for p in prices]
    price_values = [float(p.closing_price) for p in prices]
    return render(request, 'Tahmin/stock_analysis_detail.html', {
        'stock': stock,
        'price_dates': price_dates,
        'price_values': price_values,
    })

@login_required
@user_passes_test(is_staff_user)
def start_prediction(request, stock_id):
    """
    Hisse tahmini başlatma sayfasını gösterir.
    Bu sayfada, hisse hakkında temel bilgiler ve tahmin seçenekleri yer alır.
    """
    stock = get_object_or_404(Stock, id=stock_id)
    
    # Son fiyat verilerini al
    latest_prices = StockPrice.objects.filter(stock=stock).order_by('-date')[:30]
    
    # Son fiyat ve değişim 
    current_price = latest_prices.first().closing_price if latest_prices.exists() else None
    
    # Hareketli ortalama verileri
    latest_analysis = StockAnalysis.objects.filter(stock=stock).order_by('-date').first()
    
    # Temel istatistikler
    if current_price and latest_analysis:
        # 50, 100, 200 günlük ortalamalara göre durum
        vs_ma50 = float(current_price) - float(latest_analysis.ma_50) if latest_analysis.ma_50 else 0
        vs_ma100 = float(current_price) - float(latest_analysis.ma_100) if latest_analysis.ma_100 else 0
        vs_ma200 = float(current_price) - float(latest_analysis.ma_200) if latest_analysis.ma_200 else 0
        
        # Ortalamalara göre yüzdesel durum
        vs_ma50_percent = (vs_ma50 / float(latest_analysis.ma_50)) * 100 if latest_analysis.ma_50 else 0
        vs_ma100_percent = (vs_ma100 / float(latest_analysis.ma_100)) * 100 if latest_analysis.ma_100 else 0
        vs_ma200_percent = (vs_ma200 / float(latest_analysis.ma_200)) * 100 if latest_analysis.ma_200 else 0
    else:
        vs_ma50 = vs_ma100 = vs_ma200 = 0
        vs_ma50_percent = vs_ma100_percent = vs_ma200_percent = 0
    
    context = {
        'stock': stock,
        'latest_prices': latest_prices,
        'current_price': current_price,
        'latest_analysis': latest_analysis,
        'vs_ma50': vs_ma50,
        'vs_ma100': vs_ma100,
        'vs_ma200': vs_ma200,
        'vs_ma50_percent': vs_ma50_percent,
        'vs_ma100_percent': vs_ma100_percent,
        'vs_ma200_percent': vs_ma200_percent,
    }
    
    return render(request, 'Tahmin/start_prediction.html', context)
