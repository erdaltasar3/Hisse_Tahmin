from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.views import LoginView
from .models import Stock, StockPrice, StockAnalysis, StockFile, MacroeconomicData, InflationData, InterestRate, ExchangeRate, CompanyFinancial
from django.urls import reverse
from django.http import JsonResponse
from django.template.loader import render_to_string
import pandas as pd
from django.core.exceptions import ValidationError
import os
from django.conf import settings
import json
from django.db import transaction
import logging
import numpy as np
import time
from sklearn.model_selection import train_test_split
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import tempfile
import zipfile
import io
import PyPDF2
import re
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

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
        username = request.POST.get('username')
        password = request.POST.get('password1')
        email = request.POST.get('email')
        
        # Kullanıcı adı kontrolü
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Bu kullanıcı adı zaten kullanılıyor.')
            return redirect('register')
            
        # Email kontrolü
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Bu email adresi zaten kullanılıyor.')
            return redirect('register')
            
        # Yeni kullanıcı oluştur
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        messages.success(request, 'Kayıt başarılı! Şimdi giriş yapabilirsiniz.')
        return redirect('login')
    
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

                        # Hisse verisini DataFrame'e dönüştür
                        data = {
                            'closing_price': [float(p.closing_price) for p in prices],
                            'opening_price': [float(p.opening_price) if p.opening_price else 0 for p in prices],
                            'high_price': [float(p.highest_price) if p.highest_price else 0 for p in prices],
                            'low_price': [float(p.lowest_price) if p.lowest_price else 0 for p in prices],
                            'volume': [float(p.volume) if p.volume else 0 for p in prices],
                            'daily_change': [float(p.daily_change) if p.daily_change else 0 for p in prices],
                        }
                        
                        # Verileri DataFrame'e dönüştür
                        df = pd.DataFrame(data)
                        
                        # Her yerden erişilebilir tarih bilgisi (rapor oluşturma için gerekli olabilir)
                        date_strings = [p.date.strftime('%Y-%m-%d') for p in prices]
                        
                        # Model dizinini oluştur
                        model_dir = os.path.join(settings.BASE_DIR, 'models', f"{stock.symbol}")
                        os.makedirs(model_dir, exist_ok=True)
                        
                        # Rapor dizinini oluştur
                        report_dir = os.path.join(settings.BASE_DIR, 'reports', f"{stock.symbol}")
                        os.makedirs(report_dir, exist_ok=True)
                        
                        # Hisse bilgilerini hazırla
                        stock_info = {
                            'symbol': stock.symbol,
                            'name': stock.name,
                            'sector': stock.sector if stock.sector else "Genel",
                            'last_price': float(prices.last().closing_price) if prices.exists() else 0,
                            'last_update': prices.last().date.strftime('%d.%m.%Y') if prices.exists() else "",
                            'date_strings': date_strings,  # Tarih bilgilerini de ekleyelim
                        }
                        
                        # Seçilen modeli oluştur
                        if model_type == 'lstm':
                            model = LSTMModel(
                                model_name=f"{stock.symbol}_lstm",
                                time_horizon=time_horizon,
                                model_dir=model_dir,
                                sequence_length=60
                            )
                        elif model_type == 'xgboost':
                            model = XGBoostModel(
                                model_name=f"{stock.symbol}_xgb",
                                time_horizon=time_horizon,
                                model_dir=model_dir
                            )
                        else:  # hybrid model
                            model = HybridModel(
                                model_name=f"{stock.symbol}_hybrid",
                                time_horizon=time_horizon,
                                model_dir=model_dir,
                                sequence_length=60
                            )
                        
                        # Model LSTM veya Hybrid ise:
                        if model_type in ['lstm', 'hybrid']:
                            # Veriyi hazırla ve model mimarisini oluştur
                            X_train, y_train, _ = model.preprocess_data(df, target_column='closing_price')
                            
                            # input_shape parametresini tam olarak belirterek LSTM katmanı için uygun giriş şeklini sağla
                            input_shape = (X_train.shape[1], X_train.shape[2])
                            model.build_model(input_shape=input_shape)
                            
                            # Veriyi eğitim ve doğrulama kümelerine ayır
                            X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2, shuffle=False)
                            
                            # Modeli eğit
                            model.train(X_train, y_train, X_val, y_val, epochs=50, batch_size=32)
                        else:
                            # XGBoost modeli için farklı bir pipeline
                            X_train_scaled, X_val_scaled, y_train_scaled, y_val_scaled, _, _ = model.preprocess_data(df, target_column='closing_price')
                            model.build_model()
                            model.train(X_train_scaled, y_train_scaled, X_val_scaled, y_val_scaled)
                        
                        # Tahmin yap
                        predictions = model.predict_future(df, steps=time_horizon * 30)  # Ay başına ~30 gün
                        
                        # Rapor oluşturma
                        report = generate_prediction_report(model, df, stock_info=stock_info, report_type='detailed', output_dir=report_dir)
                        
                        # Rapor URL'si
                        report_url = reverse('view_stock_analysis', kwargs={'stock_id': stock.id})
                        
                        # Başarı mesajına tahmin sonucunu da ekleyelim
                        predicted_end_price = float(predictions[-1]) if len(predictions) > 0 else 0
                        current_price = float(prices.last().closing_price) if prices.exists() else 0
                        price_change = ((predicted_end_price - current_price) / current_price * 100) if current_price > 0 else 0
                        
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
    Modelleme ve eğitim işlemleri devre dışı olduğunu bildiren bir mesaj gösterir.
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
        'disabled_message': 'Model eğitimi ve raporlama işlevleri geçici olarak devre dışı bırakılmıştır.'
    }
    
    # Kullanıcıya bilgilendirme mesajı göster
    messages.info(request, 'Model eğitimi ve raporlama işlevleri geçici olarak devre dışı bırakılmıştır.')
    
    return render(request, 'Tahmin/start_prediction.html', context)

@login_required
@user_passes_test(is_staff_user)
def get_prediction_status(request, stock_id):
    """
    Modelleme ve eğitimin devre dışı olduğunu bildiren bir yanıt döndürür.
    AJAX isteği olarak çalışır.
    """
    stock = get_object_or_404(Stock, id=stock_id)
    
    return JsonResponse({
        'status': 'info',
        'message': 'Model eğitimi ve raporlama işlevleri geçici olarak devre dışı bırakılmıştır.',
        'step': 'none',
        'error': None
    })

@login_required
@user_passes_test(is_staff_user)
def run_prediction(request, stock_id):
    """
    Model eğitimi ve raporlama işlevleri iptal edilmiş versiyon.
    Bu fonksiyon sadece bilgi mesajı döndürür.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Yalnızca POST istekleri kabul edilir'})
    
    stock = get_object_or_404(Stock, id=stock_id)
    
    # Form verilerini al
    time_horizon = int(request.POST.get('selected_months', 12))
    model_type = request.POST.get('model_type', 'hybrid')
    
    # Logger başlat
    logger = logging.getLogger("TahminViews")
    logger.info(f"Tahmin işlevi iptal edildi: {stock.symbol}")
    
    # Bilgi mesajı döndür
    return JsonResponse({
        'status': 'info',
        'message': 'Model eğitimi ve raporlama işlevleri geçici olarak devre dışı bırakılmıştır.',
        'redirect_url': reverse('stock_management')
    })

@login_required
@user_passes_test(is_staff_user)
def prediction_data_sources(request):
    """
    Tahmin modeli için gerekli veri kaynaklarını gösteren bir sayfa.
    """
    # Sayfa içeriğini template'e gönder
    context = {
        'title': 'Tahmin Veri Kaynakları'
    }
    return render(request, 'Tahmin/prediction_data_sources.html', context)

@login_required
@user_passes_test(is_staff_user)
def macroeconomic_data(request):
    """
    Makroekonomik verileri listeleme sayfası
    """
    data_list = MacroeconomicData.objects.all().order_by('-date')
    context = {
        'data_list': data_list,
        'title': 'Makroekonomik Veriler'
    }
    return render(request, 'Tahmin/macroeconomic_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def add_macroeconomic_data(request):
    """
    Yeni makroekonomik veri ekleme
    """
    if request.method == 'POST':
        try:
            date = request.POST.get('date')
            
            # Enflasyon verileri
            tufe = request.POST.get('tufe') or None
            tufe_yillik = request.POST.get('tufe_yillik') or None
            ufe = request.POST.get('ufe') or None
            ufe_yillik = request.POST.get('ufe_yillik') or None
            
            # Faiz verileri
            policy_rate = request.POST.get('policy_rate') or None
            bond_yield_2y = request.POST.get('bond_yield_2y') or None
            bond_yield_10y = request.POST.get('bond_yield_10y') or None
            
            # Döviz kurları
            usd_try = request.POST.get('usd_try') or None
            eur_try = request.POST.get('eur_try') or None
            
            # Ekonomik büyüme verileri
            gdp_growth = request.POST.get('gdp_growth') or None
            unemployment_rate = request.POST.get('unemployment_rate') or None
            
            # Piyasa verileri
            bist100_close = request.POST.get('bist100_close') or None
            bist100_change = request.POST.get('bist100_change') or None
            market_volume = request.POST.get('market_volume') or None
            
            # Veriyi kaydet
            MacroeconomicData.objects.create(
                date=date,
                tufe=tufe,
                tufe_yillik=tufe_yillik,
                ufe=ufe,
                ufe_yillik=ufe_yillik,
                policy_rate=policy_rate,
                bond_yield_2y=bond_yield_2y,
                bond_yield_10y=bond_yield_10y,
                usd_try=usd_try,
                eur_try=eur_try,
                gdp_growth=gdp_growth,
                unemployment_rate=unemployment_rate,
                bist100_close=bist100_close,
                bist100_change=bist100_change,
                market_volume=market_volume
            )
            
            messages.success(request, 'Makroekonomik veri başarıyla eklendi.')
            return redirect('macroeconomic_data')
            
        except Exception as e:
            messages.error(request, f'Veri eklenirken bir hata oluştu: {str(e)}')
    
    context = {
        'title': 'Makroekonomik Veri Ekle'
    }
    return render(request, 'Tahmin/add_macroeconomic_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def edit_macroeconomic_data(request, data_id):
    """
    Makroekonomik veri düzenleme
    """
    data = get_object_or_404(MacroeconomicData, id=data_id)
    
    if request.method == 'POST':
        try:
            # Tarih verisi
            data.date = request.POST.get('date')
            
            # Enflasyon verileri
            data.tufe = request.POST.get('tufe') or None
            data.tufe_yillik = request.POST.get('tufe_yillik') or None
            data.ufe = request.POST.get('ufe') or None
            data.ufe_yillik = request.POST.get('ufe_yillik') or None
            
            # Faiz verileri
            data.policy_rate = request.POST.get('policy_rate') or None
            data.bond_yield_2y = request.POST.get('bond_yield_2y') or None
            data.bond_yield_10y = request.POST.get('bond_yield_10y') or None
            
            # Döviz kurları
            data.usd_try = request.POST.get('usd_try') or None
            data.eur_try = request.POST.get('eur_try') or None
            
            # Ekonomik büyüme verileri
            data.gdp_growth = request.POST.get('gdp_growth') or None
            data.unemployment_rate = request.POST.get('unemployment_rate') or None
            
            # Piyasa verileri
            data.bist100_close = request.POST.get('bist100_close') or None
            data.bist100_change = request.POST.get('bist100_change') or None
            data.market_volume = request.POST.get('market_volume') or None
            
            # Verileri kaydet
            data.save()
            
            messages.success(request, 'Makroekonomik veri başarıyla güncellendi.')
            return redirect('macroeconomic_data')
            
        except Exception as e:
            messages.error(request, f'Veri güncellenirken bir hata oluştu: {str(e)}')
    
    context = {
        'data': data,
        'title': 'Makroekonomik Veri Düzenle'
    }
    return render(request, 'Tahmin/edit_macroeconomic_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def delete_macroeconomic_data(request, data_id):
    """
    Makroekonomik veri silme
    """
    data = get_object_or_404(MacroeconomicData, id=data_id)
    
    if request.method == 'POST':
        try:
            data.delete()
            messages.success(request, 'Makroekonomik veri başarıyla silindi.')
            return redirect('macroeconomic_data')
        except Exception as e:
            messages.error(request, f'Veri silinirken bir hata oluştu: {str(e)}')
    
    context = {
        'data': data,
        'title': 'Makroekonomik Veri Sil'
    }
    return render(request, 'Tahmin/delete_macroeconomic_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def import_macroeconomic_data(request):
    """
    Makroekonomik verileri toplu olarak içe aktarma
    """
    # OCR ile enflasyon verilerini işleme
    if request.method == 'POST' and 'inflation_data' in request.POST:
        try:
            import json
            from datetime import datetime
            
            # JSON verisini al ve parse et
            inflation_data_json = request.POST.get('inflation_data')
            inflation_data = json.loads(inflation_data_json)
            
            success_count = 0
            error_count = 0
            error_details = []
            
            # OCR ile çıkarılan her ay için veri oluştur
            for item in inflation_data:
                try:
                    # Veriyi oluştur veya güncelle
                    inflation_obj, created = InflationData.objects.update_or_create(
                        month=item['month'],
                        year=item['year'],
                        defaults={
                            'tufe_monthly': item['tufe_monthly'],
                            'tufe_yearly': item['tufe_yearly'],
                            'ufe_monthly': item['ufe_monthly'],
                            'ufe_yearly': item['ufe_yearly'],
                            'source': request.POST.get('inflation_source', 'TÜİK')
                        }
                    )
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_details.append(f"{item['month']} {item['year']}: {str(e)}")
            
            # Sonucu bildir
            if success_count > 0:
                messages.success(request, f'{success_count} adet enflasyon verisi başarıyla kaydedildi.')
            
            if error_count > 0:
                messages.warning(request, f'{error_count} adet veri işlenirken hata oluştu.')
                for error in error_details[:5]:
                    messages.error(request, error)
                if error_count > 5:
                    messages.error(request, f'... ve {error_count - 5} hata daha.')
            
            return redirect('macroeconomic_data')
            
        except Exception as e:
            messages.error(request, f'Enflasyon verileri işlenirken bir hata oluştu: {str(e)}')
            return redirect('import_macroeconomic_data')
    
    # Faiz oranları - Ayrı dosyalar yükleme ve birleştirme
    elif request.method == 'POST' and request.POST.get('data_type') == 'interest' and request.POST.get('upload_method') == 'separate':
        try:
            import json
            import pandas as pd
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            import os
            from datetime import datetime
            
            # Politika faizi verilerini al (JSON)
            policy_rate_data_json = request.POST.get('policy_rate_data')
            
            # Tahvil faizi dosyasını al
            bond_yield_file = request.FILES.get('bond_yield_file')
            
            # En az birinin girilmiş olması gerekiyor - ARTIK GEREKLI DEĞIL
            # Her biri ayrı ayrı işlenebilir - politika faizi ve tahvil faizi bağımsız olabilir
            # if not policy_rate_data_json and not bond_yield_file:
            #     messages.error(request, 'Politika faizi veya tahvil faizi verilerinden en az birini girmelisiniz')
            #     return redirect('import_macroeconomic_data')
            
            combined_data = []
            
            # Politika faizi verilerini işle
            if policy_rate_data_json:
                try:
                    # JSON verisini parse et
                    policy_rate_data = json.loads(policy_rate_data_json)
                    
                    # Politika faizi verilerini DataFrame'e dönüştür
                    policy_rate_df = pd.DataFrame(policy_rate_data)
                    policy_rate_df.rename(columns={'date': 'tarih', 'policy_rate': 'policy_rate'}, inplace=True)
                    
                    # Tarih formatını kontrol et ve düzelt (string -> datetime)
                    policy_rate_df['tarih'] = pd.to_datetime(policy_rate_df['tarih'])
                    
                    # Verileri combined_data listesine ekle
                    for _, row in policy_rate_df.iterrows():
                        tarih_str = row['tarih'].strftime('%Y-%m-%d')
                        combined_data.append({
                            'tarih': tarih_str,
                            'policy_rate': row['policy_rate'] if not pd.isna(row['policy_rate']) else None,
                            'bond_yield_2y': None,
                            'bond_yield_10y': None
                        })
                except Exception as e:
                    messages.error(request, f'Politika faizi verileri işlenirken hata oluştu: {str(e)}')
                    return redirect('import_macroeconomic_data')
            
            # Tahvil faizi dosyasını işle
            if bond_yield_file:
                try:
                    # Dosyayı geçici olarak kaydet
                    file_path = default_storage.save(f'temp/bond_yield_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx', ContentFile(bond_yield_file.read()))
                    full_temp_path = os.path.join(default_storage.location, file_path)
                    
                    # Dosya uzantısını kontrol et (CSV veya Excel)
                    if bond_yield_file.name.lower().endswith('.csv'):
                        bond_yield_df = pd.read_csv(full_temp_path)
                    else:
                        bond_yield_df = pd.read_excel(full_temp_path)
                    
                    # Tahvil faizi DataFrame'in sütun isimlerini kontrol et
                    required_columns = ['tarih']
                    missing_columns = [col for col in required_columns if col not in bond_yield_df.columns]
                    
                    if missing_columns:
                        default_storage.delete(file_path)
                        messages.error(request, f'Tahvil faizi dosyasında gerekli sütunlar bulunamadı: {", ".join(missing_columns)}')
                        return redirect('import_macroeconomic_data')
                    
                    # En az bir faiz sütunu olmalı
                    has_yield_columns = False
                    if 'bond_yield_2y' in bond_yield_df.columns:
                        has_yield_columns = True
                    if 'bond_yield_10y' in bond_yield_df.columns:
                        has_yield_columns = True
                    
                    if not has_yield_columns:
                        default_storage.delete(file_path)
                        messages.error(request, 'Tahvil faizi dosyasında en az bir faiz sütunu (bond_yield_2y veya bond_yield_10y) bulunmalıdır')
                        return redirect('import_macroeconomic_data')
                    
                    # Tarih formatını kontrol et ve düzelt (string -> datetime)
                    bond_yield_df['tarih'] = pd.to_datetime(bond_yield_df['tarih'])
                    
                    # Eğer politika faizi verisi yoksa, tahvil verisinden combined_data'yı oluştur
                    if not policy_rate_data_json:
                        for _, row in bond_yield_df.iterrows():
                            tarih_str = row['tarih'].strftime('%Y-%m-%d')
                            bond_yield_2y = row.get('bond_yield_2y') if 'bond_yield_2y' in row and not pd.isna(row['bond_yield_2y']) else None
                            bond_yield_10y = row.get('bond_yield_10y') if 'bond_yield_10y' in row and not pd.isna(row['bond_yield_10y']) else None
                            
                            combined_data.append({
                                'tarih': tarih_str,
                                'policy_rate': None,
                                'bond_yield_2y': bond_yield_2y,
                                'bond_yield_10y': bond_yield_10y
                            })
                    else:
                        # Politika faizi verisi varsa, tarih kontrolü yapıp birleştir
                        for data in combined_data:
                            tarih = data['tarih']
                            # Tahvil verilerinde bu tarih var mı kontrol et
                            matching_rows = bond_yield_df[bond_yield_df['tarih'] == pd.to_datetime(tarih)]
                            
                            if not matching_rows.empty:
                                row = matching_rows.iloc[0]
                                data['bond_yield_2y'] = row.get('bond_yield_2y') if 'bond_yield_2y' in row and not pd.isna(row['bond_yield_2y']) else None
                                data['bond_yield_10y'] = row.get('bond_yield_10y') if 'bond_yield_10y' in row and not pd.isna(row['bond_yield_10y']) else None
                        
                        # Tahvil verilerindeki ek tarihleri de ekle
                        for _, row in bond_yield_df.iterrows():
                            tarih_str = row['tarih'].strftime('%Y-%m-%d')
                            # Bu tarih combined_data'da yoksa ekle
                            if not any(d['tarih'] == tarih_str for d in combined_data):
                                bond_yield_2y = row.get('bond_yield_2y') if 'bond_yield_2y' in row and not pd.isna(row['bond_yield_2y']) else None
                                bond_yield_10y = row.get('bond_yield_10y') if 'bond_yield_10y' in row and not pd.isna(row['bond_yield_10y']) else None
                                
                                combined_data.append({
                                    'tarih': tarih_str,
                                    'policy_rate': None,
                                    'bond_yield_2y': bond_yield_2y,
                                    'bond_yield_10y': bond_yield_10y
                                })
                    
                    # Geçici dosyayı sil
                    default_storage.delete(file_path)
                    
                except Exception as e:
                    if 'file_path' in locals():
                        default_storage.delete(file_path)
                    messages.error(request, f'Tahvil faizi dosyası işlenirken hata oluştu: {str(e)}')
                    return redirect('import_macroeconomic_data')
            
            # Veriler boş ise uyarı ver
            if not combined_data:
                messages.warning(request, 'İşlenecek veri bulunamadı. Lütfen politika faizi veya tahvil faizi verisi ekleyin.')
                return redirect('import_macroeconomic_data')
            
            # Veritabanına kaydet
            success_count = 0
            error_count = 0
            
            for data in combined_data:
                try:
                    if data['tarih'] and (data['policy_rate'] is not None or data['bond_yield_2y'] is not None or data['bond_yield_10y'] is not None):
                        # Mevcut kayıt var mı kontrol et
                        try:
                            existing_record = InterestRate.objects.get(date=data['tarih'])
                            
                            # Mevcut kaydı güncelle (sadece boş olmayan alanları)
                            if data['policy_rate'] is not None:
                                existing_record.policy_rate = data['policy_rate']
                            if data['bond_yield_2y'] is not None:
                                existing_record.bond_yield_2y = data['bond_yield_2y']
                            if data['bond_yield_10y'] is not None:
                                existing_record.bond_yield_10y = data['bond_yield_10y']
                                
                            existing_record.save()
                        except InterestRate.DoesNotExist:
                            # Yeni kayıt oluştur
                            InterestRate.objects.create(
                                date=data['tarih'],
                                policy_rate=data['policy_rate'] if data['policy_rate'] is not None else 0,
                                bond_yield_2y=data['bond_yield_2y'] if data['bond_yield_2y'] is not None else 0,
                                bond_yield_10y=data['bond_yield_10y'] if data['bond_yield_10y'] is not None else 0
                            )
                        
                        success_count += 1
                except Exception as e:
                    error_count += 1
                    print(f"Veri kaydedilemedi: {str(e)}")
            
            # Başarı mesajı göster
            if success_count > 0:
                messages.success(request, f'{success_count} faiz verisi başarıyla yüklendi/güncellendi. {error_count} veri yüklenemedi.')
            else:
                messages.warning(request, 'Hiçbir faiz verisi yüklenemedi. Lütfen dosyaları kontrol edin.')
            
            return redirect('import_macroeconomic_data')
                
        except Exception as e:
            messages.error(request, f'Faiz verileri işlenirken bir hata oluştu: {str(e)}')
            return redirect('import_macroeconomic_data')
    
    # Faiz oranları - Birleşik dosya yükleme
    elif request.method == 'POST' and request.POST.get('data_type') == 'interest' and request.POST.get('upload_method') == 'combined':
        try:
            # Dosyayı al
            if not request.FILES.get('interest_file'):
                messages.error(request, 'Faiz oranları dosyasını yüklemeniz gerekiyor.')
                return redirect('import_macroeconomic_data')
                
            # Standart yükleme işlemini yap
            import pandas as pd
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            import os
            from datetime import datetime
            
            interest_file = request.FILES['interest_file']
            
            # Dosyayı geçici olarak kaydet
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            path = default_storage.save(f'temp/interest_{timestamp}.xlsx', ContentFile(interest_file.read()))
            full_path = os.path.join(settings.MEDIA_ROOT, path)
            
            # Excel'i oku
            try:
                df = pd.read_excel(full_path)
            except Exception as e:
                # Excel okuma hatası
                default_storage.delete(path)
                messages.error(request, f'Excel dosyası okunamadı: {str(e)}')
                return redirect('import_macroeconomic_data')
            
            # Geçici dosyayı sil
            default_storage.delete(path)
            
            # Gerekli sütunları kontrol et
            required_columns = ['tarih', 'policy_rate', 'bond_yield_2y', 'bond_yield_10y']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                messages.error(request, f'Excel dosyasında {", ".join(missing_columns)} sütun(lar)ı bulunamadı.')
                return redirect('import_macroeconomic_data')
            
            # Verileri işle
            success_count = 0
            error_count = 0
            error_details = []
            
            for _, row in df.iterrows():
                try:
                    # Var olan veriyi kontrol et
                    try:
                        existing_data = MacroeconomicData.objects.get(date=row['tarih'])
                        
                        # Sadece faiz verilerini güncelle
                        if not pd.isna(row['policy_rate']):
                            existing_data.policy_rate = row['policy_rate']
                        if not pd.isna(row['bond_yield_2y']):
                            existing_data.bond_yield_2y = row['bond_yield_2y'] 
                        if not pd.isna(row['bond_yield_10y']):
                            existing_data.bond_yield_10y = row['bond_yield_10y']
                        
                        existing_data.save()
                        success_count += 1
                        
                    except MacroeconomicData.DoesNotExist:
                        # Yeni veri oluştur
                        macro_data = MacroeconomicData(
                            date=row['tarih'],
                            policy_rate=None if pd.isna(row['policy_rate']) else row['policy_rate'],
                            bond_yield_2y=None if pd.isna(row['bond_yield_2y']) else row['bond_yield_2y'],
                            bond_yield_10y=None if pd.isna(row['bond_yield_10y']) else row['bond_yield_10y']
                        )
                        macro_data.save()
                        success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_details.append(f"Satır {_ + 2}: {str(e)}")
            
            # Sonucu bildir
            if success_count > 0:
                messages.success(request, f'{success_count} adet faiz verisi başarıyla kaydedildi/güncellendi.')
            
            if error_count > 0:
                messages.warning(request, f'{error_count} adet veri işlenirken hata oluştu.')
                for error in error_details[:5]:
                    messages.error(request, error)
                if error_count > 5:
                    messages.error(request, f'... ve {error_count - 5} hata daha.')
            
            return redirect('macroeconomic_data')
            
        except Exception as e:
            messages.error(request, f'Faiz verileri işlenirken bir hata oluştu: {str(e)}')
            return redirect('import_macroeconomic_data')
    
    # Excel dosyası ile makroekonomik verileri içe aktarma
    elif request.method == 'POST' and request.FILES.get('data_file'):
        try:
            # Dosyayı al
            data_file = request.FILES['data_file']
            
            # Excel dosyasını pandas ile oku
            import pandas as pd
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            import os
            from datetime import datetime
            
            # Dosyayı geçici olarak kaydet
            path = default_storage.save(f'temp/macro_data_{datetime.now().strftime("%Y%m%d%H%M%S")}.xlsx', ContentFile(data_file.read()))
            full_path = os.path.join(settings.MEDIA_ROOT, path)
            
            # Excel'i oku
            try:
                df = pd.read_excel(full_path)
            except Exception as e:
                # Excel okuma hatası
                default_storage.delete(path)
                messages.error(request, f'Excel dosyası okunamadı: {str(e)}')
                return redirect('import_macroeconomic_data')
            
            # Geçici dosyayı sil
            default_storage.delete(path)
            
            # Verileri işle
            success_count = 0
            error_count = 0
            error_details = []
            
            for _, row in df.iterrows():
                try:
                    # Tarih alanını kontrol et
                    if 'tarih' not in row or pd.isna(row['tarih']):
                        error_count += 1
                        error_details.append(f"Satır {_ + 2}: Tarih alanı eksik")
                        continue
                    
                    # Veriyi oluştur
                    macro_data = MacroeconomicData(
                        date=row['tarih'],
                        tufe=row.get('tufe', None) if 'tufe' in row and not pd.isna(row['tufe']) else None,
                        tufe_yillik=row.get('tufe_yillik', None) if 'tufe_yillik' in row and not pd.isna(row['tufe_yillik']) else None,
                        ufe=row.get('ufe', None) if 'ufe' in row and not pd.isna(row['ufe']) else None,
                        ufe_yillik=row.get('ufe_yillik', None) if 'ufe_yillik' in row and not pd.isna(row['ufe_yillik']) else None,
                        policy_rate=row.get('policy_rate', None) if 'policy_rate' in row and not pd.isna(row['policy_rate']) else None,
                        bond_yield_2y=row.get('bond_yield_2y', None) if 'bond_yield_2y' in row and not pd.isna(row['bond_yield_2y']) else None,
                        bond_yield_10y=row.get('bond_yield_10y', None) if 'bond_yield_10y' in row and not pd.isna(row['bond_yield_10y']) else None,
                        usd_try=row.get('usd_try', None) if 'usd_try' in row and not pd.isna(row['usd_try']) else None,
                        eur_try=row.get('eur_try', None) if 'eur_try' in row and not pd.isna(row['eur_try']) else None,
                        gdp_growth=row.get('gdp_growth', None) if 'gdp_growth' in row and not pd.isna(row['gdp_growth']) else None,
                        unemployment_rate=row.get('unemployment_rate', None) if 'unemployment_rate' in row and not pd.isna(row['unemployment_rate']) else None,
                        bist100_close=row.get('bist100_close', None) if 'bist100_close' in row and not pd.isna(row['bist100_close']) else None,
                        bist100_change=row.get('bist100_change', None) if 'bist100_change' in row and not pd.isna(row['bist100_change']) else None,
                        market_volume=row.get('market_volume', None) if 'market_volume' in row and not pd.isna(row['market_volume']) else None,
                    )
                    
                    # Veriyi kaydet
                    macro_data.save()
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    error_details.append(f"Satır {_ + 2}: {str(e)}")
            
            # Sonucu bildir
            if success_count > 0:
                messages.success(request, f'{success_count} adet makroekonomik veri başarıyla içe aktarıldı.')
            
            if error_count > 0:
                messages.warning(request, f'{error_count} adet veri işlenirken hata oluştu.')
                for error in error_details[:5]:  # İlk 5 hatayı göster
                    messages.error(request, error)
                if error_count > 5:
                    messages.error(request, f'... ve {error_count - 5} hata daha.')
            
            return redirect('macroeconomic_data')
            
        except Exception as e:
            messages.error(request, f'Dosya işlenirken bir hata oluştu: {str(e)}')
    
    # Döviz kuru verilerini işleme (USD/TL ve EUR/TL ayrı dosyalar)
    elif request.method == 'POST' and request.POST.get('data_type') == 'exchange' and request.POST.get('upload_method') == 'separate':
        try:
            import pandas as pd
            from django.core.files.storage import default_storage
            from django.core.files.base import ContentFile
            import os
            from datetime import datetime
            from .models import ExchangeRate
            import logging
            
            logger = logging.getLogger(__name__)
            
            # Hangi döviz kuru verisi yükleniyor?
            currency_type = request.POST.get('currency_type')
            logger.info(f"Döviz kuru işleniyor: {currency_type}")
            
            if not currency_type or currency_type not in ['USD', 'EUR']:
                messages.error(request, 'Geçerli bir para birimi seçmelisiniz (USD veya EUR)')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'Tahmin/messages.html')
                return redirect('import_macroeconomic_data')
            
            # Döviz kuru dosyasını al
            exchange_file = request.FILES.get('exchange_file')
            if not exchange_file:
                messages.error(request, 'Döviz kuru dosyası yüklemelisiniz')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'Tahmin/messages.html')
                return redirect('import_macroeconomic_data')
            
            logger.info(f"Dosya adı: {exchange_file.name}, Boyut: {exchange_file.size} bytes")
            
            # Dosyayı geçici olarak kaydet
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_path = default_storage.save(f'temp/exchange_{currency_type}_{timestamp}.csv', ContentFile(exchange_file.read()))
            full_temp_path = os.path.join(default_storage.location, file_path)
            
            logger.info(f"Geçici dosya yolu: {full_temp_path}")
            
            # CSV dosyasını oku (CSV formatı: tarih,şimdi,açılış,yüksek,düşük,hacim,fark%)
            try:
                if exchange_file.name.lower().endswith('.csv'):
                    df = pd.read_csv(full_temp_path)
                else:
                    df = pd.read_excel(full_temp_path)
                    
                # İlk satırı kontrol et ve başlık satırı değilse kolonsuz olarak oku
                if 'tarih' not in df.columns and 'Tarih' not in df.columns and len(df.columns) >= 6:
                    # Başlık satırı olmadan okunan CSV/Excel dosyasını yeniden isimlendir
                    df.columns = ['Tarih', 'Şimdi', 'Açılış', 'Yüksek', 'Düşük', 'Hac.', 'Fark %']
                
                logger.info(f"DataFrame sütunları: {df.columns.tolist()}")
                logger.info(f"DataFrame boyutu: {df.shape}")
                
                # İlk satırın ham verilerini logla
                if len(df) > 0:
                    first_row = df.iloc[0]
                    logger.info(f"İlk satır (ham): {dict(first_row)}")
                    logger.info(f"Veri tipleri: {first_row.dtypes}")
                    
                    # Sayısal kolonların tiplerini kontrol et
                    for col in ['Şimdi', 'Açılış', 'Yüksek', 'Düşük']:
                        if col in first_row:
                            logger.info(f"{col} değeri: {first_row[col]}, tipi: {type(first_row[col])}, içerik: {repr(first_row[col])}")
                
            except Exception as e:
                logger.error(f"Dosya okuma hatası: {str(e)}")
                default_storage.delete(file_path)
                messages.error(request, f'Dosya okunamadı: {str(e)}')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'Tahmin/messages.html')
                return redirect('import_macroeconomic_data')
            
            # Sütun isimlerini standardize et
            column_mappings = {
                'Tarih': 'date',
                'tarih': 'date',
                'Date': 'date',
                'Şimdi': 'close',
                'Kapanış': 'close',
                'Close': 'close',
                'Açılış': 'open',
                'Open': 'open',
                'Yüksek': 'high',
                'High': 'high',
                'Düşük': 'low',
                'Low': 'low',
                'Hac.': 'volume',
                'Hacim': 'volume',
                'Volume': 'volume',
                'Vol.': 'volume',
                'Fark %': 'change',
                'Change %': 'change',
                'Change': 'change'
            }
            
            # Sütun isimlerini değiştir
            original_columns = df.columns.tolist()
            df = df.rename(columns=column_mappings)
            new_columns = df.columns.tolist()
            
            logger.info(f"Orijinal sütunlar: {original_columns}")
            logger.info(f"Yeni sütunlar: {new_columns}")
            
            # Gerekli sütunların varlığını kontrol et
            required_columns = ['date', 'open', 'high', 'low', 'close']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.error(f"Eksik sütunlar: {missing_columns}")
                default_storage.delete(file_path)
                messages.error(request, f'Dosyada gerekli sütunlar eksik: {", ".join(missing_columns)}')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'Tahmin/messages.html')
                return redirect('import_macroeconomic_data')
            
            # Tarih formatını düzelt
            try:
                df['date'] = pd.to_datetime(df['date'], dayfirst=True)
                logger.info(f"Tarih örnekleri: {df['date'].head().tolist()}")
            except Exception as e:
                logger.error(f"Tarih dönüştürme hatası: {str(e)}")
                default_storage.delete(file_path)
                messages.error(request, f'Tarih formatı tanımlanamadı: {str(e)}')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return render(request, 'Tahmin/messages.html')
                return redirect('import_macroeconomic_data')
            
            # Verileri veritabanına kaydet
            success_count = 0
            error_count = 0
            error_details = []
            duplicate_count = 0
            updated_count = 0
            
            # İlk birkaç satırı logla
            logger.info(f"İlk 3 satır: {df.head(3).to_dict('records')}")
            
            try:
                for _, row in df.iterrows():
                    try:
                        # Tarih ve döviz kuru için kontrol et
                        date_value = row['date'].date()
                        
                        # Değişim yüzdesini düzelt (% işareti varsa kaldır)
                        change_percent = None
                        if 'change' in row and not pd.isna(row['change']):
                            change_str = str(row['change']).replace('%', '').replace(',', '.')
                            try:
                                change_percent = float(change_str)
                            except:
                                change_percent = None
                        
                        # Veritabanında zaten var mı kontrol et
                        try:
                            existing_rate = ExchangeRate.objects.get(date=date_value, currency=currency_type)
                            # Mevcut kaydı güncelle
                            try:
                                # Sayısal değerlere dönüştürme
                                open_value = float(str(row['open']).replace(',', '.'))
                                high_value = float(str(row['high']).replace(',', '.'))
                                low_value = float(str(row['low']).replace(',', '.'))
                                close_value = float(str(row['close']).replace(',', '.'))
                                
                                existing_rate.open_price = open_value
                                existing_rate.high_price = high_value
                                existing_rate.low_price = low_value
                                existing_rate.close_price = close_value
                                
                                if 'volume' in row and not pd.isna(row['volume']):
                                    existing_rate.volume = str(row['volume'])
                                if change_percent is not None:
                                    existing_rate.change_percent = change_percent
                                
                                existing_rate.save()
                                updated_count += 1
                                logger.info(f"Kayıt güncellendi: {currency_type} - {date_value}")
                            except Exception as convert_err:
                                logger.error(f"Değer dönüştürme hatası (güncelleme): {str(convert_err)}")
                                logger.error(f"Problematik değerler: open={row['open']}, high={row['high']}, low={row['low']}, close={row['close']}")
                                error_count += 1
                                
                        except ExchangeRate.DoesNotExist:
                            # Yeni kayıt oluştur
                            try:
                                # Sayısal değerlere dönüştürme
                                open_value = float(str(row['open']).replace(',', '.'))
                                high_value = float(str(row['high']).replace(',', '.'))
                                low_value = float(str(row['low']).replace(',', '.'))
                                close_value = float(str(row['close']).replace(',', '.'))
                                
                                new_rate = ExchangeRate(
                                    date=date_value,
                                    currency=currency_type,
                                    open_price=open_value,
                                    high_price=high_value,
                                    low_price=low_value,
                                    close_price=close_value,
                                    volume=str(row['volume']) if 'volume' in row and not pd.isna(row['volume']) else None,
                                    change_percent=change_percent
                                )
                                new_rate.save()
                                success_count += 1
                                logger.info(f"Yeni kayıt eklendi: {currency_type} - {date_value}")
                            except Exception as convert_err:
                                logger.error(f"Değer dönüştürme hatası (yeni): {str(convert_err)}")
                                logger.error(f"Problematik değerler: open={row['open']}, high={row['high']}, low={row['low']}, close={row['close']}")
                                error_count += 1
                            
                    except Exception as e:
                        error_count += 1
                        error_msg = f"Satır {_ + 2}: {str(e)}"
                        error_details.append(error_msg)
                        logger.error(error_msg)
            except Exception as e:
                logger.error(f"Tüm verileri kaydetme hatası: {str(e)}")
            
            # Kayıt özeti
            logger.info(f"Kayıt özeti: {success_count} yeni, {updated_count} güncelleme, {error_count} hata")
            
            # Geçici dosyayı sil
            default_storage.delete(file_path)
            
            # Sonucu bildir
            status_message = f'{currency_type}/TRY döviz kuru verileri: '
            if success_count > 0:
                status_message += f'{success_count} yeni kayıt eklendi. '
            if updated_count > 0:
                status_message += f'{updated_count} kayıt güncellendi. '
            if error_count > 0:
                status_message += f'{error_count} işleme hatası. '
            
            messages.success(request, status_message)
            
            # Hata ayrıntılarını göster
            if error_count > 0:
                for error in error_details[:5]:
                    messages.error(request, error)
                if error_count > 5:
                    messages.error(request, f'... ve {error_count - 5} hata daha.')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return render(request, 'Tahmin/messages.html')
            return redirect('import_macroeconomic_data')
            
        except Exception as e:
            messages.error(request, f'Döviz kuru verileri işlenirken bir hata oluştu: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return render(request, 'Tahmin/messages.html')
            return redirect('import_macroeconomic_data')
    
    context = {
        'title': 'Makroekonomik Verileri İçe Aktar'
    }
    return render(request, 'Tahmin/import_macroeconomic_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def inflation_data(request):
    """
    TÜFE ve ÜFE enflasyon verilerini listeleme sayfası
    """
    # Enflasyon verilerini yıla göre gruplandır
    years = InflationData.objects.values_list('year', flat=True).distinct().order_by('-year')
    
    data_by_year = {}
    for year in years:
        data_by_year[year] = InflationData.objects.filter(year=year).order_by('month')
    
    context = {
        'data_by_year': data_by_year,
        'years': years,
        'title': 'Enflasyon Verileri (TÜFE/ÜFE)'
    }
    return render(request, 'Tahmin/inflation_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def delete_inflation_data(request, data_id):
    """
    Enflasyon verisi silme
    """
    data = get_object_or_404(InflationData, id=data_id)
    
    if request.method == 'POST':
        try:
            month = data.month
            year = data.year
            data.delete()
            messages.success(request, f'{year} {month} enflasyon verisi başarıyla silindi.')
            return redirect('inflation_data')
        except Exception as e:
            messages.error(request, f'Veri silinirken bir hata oluştu: {str(e)}')
    
    context = {
        'data': data,
        'title': 'Enflasyon Verisi Sil'
    }
    return render(request, 'Tahmin/delete_inflation_data.html', context)

@login_required
@user_passes_test(is_staff_user)
def import_company_financial(request):
    """
    Şirket finansal verilerini çeşitli dosya formatlarından (ZIP, PDF, XLS, XLSX) yükleme sayfası ve işlemleri
    """
    # Sistemdeki hisseleri getir
    stocks = Stock.objects.filter(is_active=True).order_by('symbol')
    
    # Yıllar için hazır bir liste (opsiyonel olarak veritabanından dinamik de getirilebilir)
    current_year = datetime.now().year
    years = list(range(current_year, current_year-5, -1))
    
    context = {
        'stocks': stocks,
        'years': years,
    }
    
    if request.method == 'POST':
        # Form verilerini al
        stock_id = request.POST.get('stock_id')
        year = request.POST.get('year')
        period = request.POST.get('period')
        uploaded_file = request.FILES.get('data_file')
        analyze_data = request.POST.get('analyze_data') == 'on'
        
        # Gerekli alanların kontrolünü yap
        if not stock_id or not year or not period or not uploaded_file:
            messages.error(request, 'Lütfen tüm alanları doldurun ve bir dosya yükleyin.')
            return render(request, 'Tahmin/import_company_financial.html', context)
        
        # Hisseyi kontrol et
        try:
            stock = Stock.objects.get(id=stock_id)
        except Stock.DoesNotExist:
            messages.error(request, 'Seçilen hisse bulunamadı.')
            return render(request, 'Tahmin/import_company_financial.html', context)
        
        # Dosya tipini kontrol et ve işle
        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension not in ['zip', 'pdf', 'xls', 'xlsx']:
            messages.error(request, 'Lütfen sadece ZIP, PDF, XLS veya XLSX dosyası yükleyin.')
            return render(request, 'Tahmin/import_company_financial.html', context)
        
        # Dosyayı işle ve finansal verileri çıkar
        try:
            # Klasör yapısını oluştur
            base_dir = os.path.join(settings.MEDIA_ROOT, 'financials', stock.symbol, year, period)
            os.makedirs(base_dir, exist_ok=True)
            
            # İşlenecek dosyaları tutacak liste
            files_to_process = []
            
            # ZIP dosyası ise içeriğini çıkar
            if file_extension == 'zip':
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                zip_path = os.path.join(base_dir, f"archive_{timestamp}.zip")
                
                # ZIP dosyasını kaydet
                with open(zip_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                # Geçici dizin oluştur
                extract_dir = os.path.join(base_dir, f"extracted_{timestamp}")
                os.makedirs(extract_dir, exist_ok=True)
                
                # ZIP dosyasını aç ve içeriği geçici dizine çıkar
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Çıkarılan dosyaları tara
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        file_ext = file.split('.')[-1].lower()
                        if file_ext in ['pdf', 'xls', 'xlsx']:
                            file_path = os.path.join(root, file)
                            files_to_process.append({
                                'path': file_path,
                                'type': file_ext,
                                'name': file
                            })
                
                messages.info(request, f"ZIP arşivinden {len(files_to_process)} dosya çıkarıldı.")
            else:
                # Tek dosya
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                file_path = os.path.join(base_dir, f"{file_extension}_{timestamp}.{file_extension}")
                
                # Dosyayı kaydet
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
                
                files_to_process.append({
                    'path': file_path,
                    'type': file_extension,
                    'name': uploaded_file.name
                })
            
            # Çıkarılan finansal verileri saklayacak konteyner
            financial_data = {
                'revenue': None,
                'ebitda': None,
                'net_income': None,
                'total_assets': None,
                'total_liabilities': None,
                'equity': None,
                'debt_to_equity': None,
                'roe': None,
                'eps': None,
                'dividend': None,
                'dividend_yield': None,
                'pe_ratio': None,
                'pb_ratio': None,
                'ev_ebitda': None,
            }
            
            # Her dosyayı işle
            for file_info in files_to_process:
                extracted_data = {}
                file_path = file_info['path']
                file_type = file_info['type']
                
                try:
                    if file_type == 'pdf':
                        # PDF dosyasını işle ve veri çıkar
                        extracted_data = extract_data_from_pdf(file_path)
                    elif file_type in ['xls', 'xlsx']:
                        # Excel dosyasını işle ve veri çıkar
                        extracted_data = extract_data_from_excel(file_path)
                    
                    # Çıkarılan verileri birleştir (None olmayanları al)
                    for key, value in extracted_data.items():
                        if value is not None and key in financial_data:
                            financial_data[key] = value
                except Exception as e:
                    messages.warning(request, f"{file_info['name']} dosyasından veri çıkarımı sırasında hata: {str(e)}")
            
            # Mevcut kaydı kontrol et ve güncelle ya da yeni oluştur
            financial, created = CompanyFinancial.objects.update_or_create(
                stock=stock,
                year=year,
                period=period,
                defaults={
                    'revenue': financial_data['revenue'] if financial_data['revenue'] is not None else 0,
                    'ebitda': financial_data['ebitda'] if financial_data['ebitda'] is not None else 0,
                    'net_income': financial_data['net_income'] if financial_data['net_income'] is not None else 0,
                    'total_assets': financial_data['total_assets'] if financial_data['total_assets'] is not None else 0,
                    'total_liabilities': financial_data['total_liabilities'] if financial_data['total_liabilities'] is not None else 0,
                    'equity': financial_data['equity'] if financial_data['equity'] is not None else 0,
                    'debt_to_equity': financial_data['debt_to_equity'] if financial_data['debt_to_equity'] is not None else None,
                    'roe': financial_data['roe'] if financial_data['roe'] is not None else None,
                    'eps': financial_data['eps'] if financial_data['eps'] is not None else None,
                    'dividend': financial_data['dividend'] if financial_data['dividend'] is not None else None,
                    'dividend_yield': financial_data['dividend_yield'] if financial_data['dividend_yield'] is not None else None,
                    'pe_ratio': financial_data['pe_ratio'] if financial_data['pe_ratio'] is not None else None,
                    'pb_ratio': financial_data['pb_ratio'] if financial_data['pb_ratio'] is not None else None,
                    'ev_ebitda': financial_data['ev_ebitda'] if financial_data['ev_ebitda'] is not None else None,
                }
            )
            
            # Başarılı mesajı göster
            action = "oluşturuldu" if created else "güncellendi"
            messages.success(request, f"{stock.symbol} hissesi için {year} {period} dönemi finansal verisi başarıyla {action}.")
            
            # Eğer analiz isteniyorsa finansal analizleri yap
            if analyze_data:
                try:
                    analysis_results = analyze_financial_data(financial)
                    # Analiz sonuçlarını göster
                    messages.info(request, f"Finansal analiz tamamlandı. Analiz sonuçlarını raporlardan görüntüleyebilirsiniz.")
                except Exception as e:
                    messages.warning(request, f"Finansal analiz sırasında hata oluştu: {str(e)}")
            
            # İşlem tamamlandı, detay sayfasına yönlendir
            return redirect('company_financial_detail', financial_id=financial.id)
            
        except Exception as e:
            # Hata durumunda
            messages.error(request, f"Dosya işlenirken bir hata oluştu: {str(e)}")
            return render(request, 'Tahmin/import_company_financial.html', context)
    
    # GET isteği için sayfayı göster
    return render(request, 'Tahmin/import_company_financial.html', context)

def extract_data_from_pdf(file_path):
    """
    PDF dosyasından finansal verileri çıkarır.
    """
    extracted_data = {}
    
    try:
        # PyPDF2 ile PDF'i aç
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            
            # Tüm sayfaları metin olarak çıkar
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
        
        # Finansal verileri metin içinden regexler ile çıkar
        
        # Gelir Tablosu Verileri
        revenue_match = re.search(r'(Hasılat|Satış Gelirleri|Net Satışlar)[:\s]*([0-9.,]+)', text)
        if revenue_match:
            extracted_data['revenue'] = convert_to_number(revenue_match.group(2))
        
        ebitda_match = re.search(r'(FAVÖK|EBITDA)[:\s]*([0-9.,]+)', text)
        if ebitda_match:
            extracted_data['ebitda'] = convert_to_number(ebitda_match.group(2))
        
        net_income_match = re.search(r'(Net Kar|Net Dönem Karı|Dönem Net Karı)[:\s]*([0-9.,]+)', text)
        if net_income_match:
            extracted_data['net_income'] = convert_to_number(net_income_match.group(2))
        
        # Bilanço Verileri
        total_assets_match = re.search(r'(Toplam Varlıklar|Aktif Toplam)[:\s]*([0-9.,]+)', text)
        if total_assets_match:
            extracted_data['total_assets'] = convert_to_number(total_assets_match.group(2))
        
        total_liabilities_match = re.search(r'(Toplam Yükümlülükler|Toplam Borçlar)[:\s]*([0-9.,]+)', text)
        if total_liabilities_match:
            extracted_data['total_liabilities'] = convert_to_number(total_liabilities_match.group(2))
        
        equity_match = re.search(r'(Özkaynaklar|Toplam Özkaynaklar)[:\s]*([0-9.,]+)', text)
        if equity_match:
            extracted_data['equity'] = convert_to_number(equity_match.group(2))
        
        # Oranlar
        eps_match = re.search(r'(Hisse Başına Kazanç|Pay Başına Kazanç)[:\s]*([0-9.,]+)', text)
        if eps_match:
            extracted_data['eps'] = convert_to_number(eps_match.group(2))
        
        pe_match = re.search(r'(F/K|Fiyat/Kazanç)[:\s]*([0-9.,]+)', text)
        if pe_match:
            extracted_data['pe_ratio'] = convert_to_number(pe_match.group(2))
        
        # Eğer bilanço verileri varsa, oranları hesapla
        if 'total_liabilities' in extracted_data and 'equity' in extracted_data and extracted_data['equity'] > 0:
            extracted_data['debt_to_equity'] = round(extracted_data['total_liabilities'] / extracted_data['equity'], 2)
        
        if 'net_income' in extracted_data and 'equity' in extracted_data and extracted_data['equity'] > 0:
            extracted_data['roe'] = round((extracted_data['net_income'] / extracted_data['equity']) * 100, 2)
        
        return extracted_data
        
    except Exception as e:
        print(f"PDF veri çıkarma hatası: {str(e)}")
        return {}

def extract_data_from_excel(file_path):
    """
    Excel dosyasından finansal verileri çıkarır.
    """
    extracted_data = {}
    
    try:
        # Pandas ile Excel'i oku
        df = pd.read_excel(file_path)
        
        # Sütun başlıklarını kontrol et 
        columns = df.columns.str.lower()
        
        # Gelir Tablosu Verileri
        if any(col for col in columns if 'hasılat' in col or 'satış' in col):
            revenue_col = next((col for col in columns if 'hasılat' in col or 'satış' in col), None)
            if revenue_col:
                revenue_value = df[df.columns[columns.get_loc(revenue_col)]].iloc[0]
                if not pd.isna(revenue_value):
                    extracted_data['revenue'] = convert_to_number(revenue_value)
        
        if any(col for col in columns if 'favök' in col or 'ebitda' in col):
            ebitda_col = next((col for col in columns if 'favök' in col or 'ebitda' in col), None)
            if ebitda_col:
                ebitda_value = df[df.columns[columns.get_loc(ebitda_col)]].iloc[0]
                if not pd.isna(ebitda_value):
                    extracted_data['ebitda'] = convert_to_number(ebitda_value)
        
        if any(col for col in columns if 'net kar' in col or 'dönem kar' in col):
            net_income_col = next((col for col in columns if 'net kar' in col or 'dönem kar' in col), None)
            if net_income_col:
                net_income_value = df[df.columns[columns.get_loc(net_income_col)]].iloc[0]
                if not pd.isna(net_income_value):
                    extracted_data['net_income'] = convert_to_number(net_income_value)
        
        # Bilanço Verileri
        if any(col for col in columns if 'varlık' in col or 'aktif' in col):
            assets_col = next((col for col in columns if 'varlık' in col or 'aktif' in col), None)
            if assets_col:
                assets_value = df[df.columns[columns.get_loc(assets_col)]].iloc[0]
                if not pd.isna(assets_value):
                    extracted_data['total_assets'] = convert_to_number(assets_value)
        
        if any(col for col in columns if 'yükümlülük' in col or 'borç' in col):
            liabilities_col = next((col for col in columns if 'yükümlülük' in col or 'borç' in col), None)
            if liabilities_col:
                liabilities_value = df[df.columns[columns.get_loc(liabilities_col)]].iloc[0]
                if not pd.isna(liabilities_value):
                    extracted_data['total_liabilities'] = convert_to_number(liabilities_value)
        
        if any(col for col in columns if 'özkaynak' in col):
            equity_col = next((col for col in columns if 'özkaynak' in col), None)
            if equity_col:
                equity_value = df[df.columns[columns.get_loc(equity_col)]].iloc[0]
                if not pd.isna(equity_value):
                    extracted_data['equity'] = convert_to_number(equity_value)
        
        # Oranlar
        if any(col for col in columns if 'f/k' in col or 'fiyat/kazanç' in col):
            pe_col = next((col for col in columns if 'f/k' in col or 'fiyat/kazanç' in col), None)
            if pe_col:
                pe_value = df[df.columns[columns.get_loc(pe_col)]].iloc[0]
                if not pd.isna(pe_value):
                    extracted_data['pe_ratio'] = convert_to_number(pe_value)
        
        if any(col for col in columns if 'pd/dd' in col or 'piyasa değeri/defter değeri' in col):
            pb_col = next((col for col in columns if 'pd/dd' in col or 'piyasa değeri/defter değeri' in col), None)
            if pb_col:
                pb_value = df[df.columns[columns.get_loc(pb_col)]].iloc[0]
                if not pd.isna(pb_value):
                    extracted_data['pb_ratio'] = convert_to_number(pb_value)
        
        if any(col for col in columns if 'fd/favök' in col or 'firma değeri/favök' in col):
            ev_ebitda_col = next((col for col in columns if 'fd/favök' in col or 'firma değeri/favök' in col), None)
            if ev_ebitda_col:
                ev_ebitda_value = df[df.columns[columns.get_loc(ev_ebitda_col)]].iloc[0]
                if not pd.isna(ev_ebitda_value):
                    extracted_data['ev_ebitda'] = convert_to_number(ev_ebitda_value)
        
        # Eğer bilanço verileri varsa, oranları hesapla
        if 'total_liabilities' in extracted_data and 'equity' in extracted_data and extracted_data['equity'] > 0:
            extracted_data['debt_to_equity'] = round(extracted_data['total_liabilities'] / extracted_data['equity'], 2)
        
        if 'net_income' in extracted_data and 'equity' in extracted_data and extracted_data['equity'] > 0:
            extracted_data['roe'] = round((extracted_data['net_income'] / extracted_data['equity']) * 100, 2)
        
        return extracted_data
        
    except Exception as e:
        print(f"Excel veri çıkarma hatası: {str(e)}")
        return {}

def convert_to_number(value):
    """
    Metinsel değeri sayıya dönüştürür.
    """
    if isinstance(value, (int, float)):
        return value
    
    if isinstance(value, str):
        # Binlik ayırıcı ve ondalık noktasını temizle
        cleaned_value = re.sub(r'[^\d,.]', '', value)
        
        # Türkçe formatta virgül ondalık ayırıcı ise nokta ile değiştir
        if ',' in cleaned_value and '.' not in cleaned_value:
            cleaned_value = cleaned_value.replace(',', '.')
        # Binlik ayırıcı olarak nokta, ondalık ayırıcı olarak virgül kullanılıyorsa
        elif ',' in cleaned_value and '.' in cleaned_value:
            cleaned_value = cleaned_value.replace('.', '').replace(',', '.')
        
        try:
            return float(cleaned_value)
        except ValueError:
            return 0
    
    return 0

def analyze_financial_data(financial):
    """
    Finansal verileri analiz eder ve çeşitli finansal oranları hesaplar.
    """
    analysis_results = {}
    
    try:
        # Temel Oranlar
        if financial.net_income and financial.revenue and financial.revenue > 0:
            analysis_results['net_profit_margin'] = round((financial.net_income / financial.revenue) * 100, 2)
        
        if financial.ebitda and financial.revenue and financial.revenue > 0:
            analysis_results['ebitda_margin'] = round((financial.ebitda / financial.revenue) * 100, 2)
        
        # Trend Analizi için önceki dönem verisini getir
        previous_period = None
        current_period = financial.period
        current_year = financial.year
        
        if current_period == 'Q1':
            # Önceki yıl Q4
            previous_period = CompanyFinancial.objects.filter(
                stock=financial.stock,
                year=current_year-1,
                period='Q4'
            ).first()
        elif current_period == 'Q2':
            # Aynı yıl Q1
            previous_period = CompanyFinancial.objects.filter(
                stock=financial.stock,
                year=current_year,
                period='Q1'
            ).first()
        elif current_period == 'Q3':
            # Aynı yıl Q2
            previous_period = CompanyFinancial.objects.filter(
                stock=financial.stock,
                year=current_year,
                period='Q2'
            ).first()
        elif current_period == 'Q4':
            # Aynı yıl Q3
            previous_period = CompanyFinancial.objects.filter(
                stock=financial.stock,
                year=current_year,
                period='Q3'
            ).first()
        elif current_period == 'ANNUAL':
            # Önceki yıl ANNUAL
            previous_period = CompanyFinancial.objects.filter(
                stock=financial.stock,
                year=current_year-1,
                period='ANNUAL'
            ).first()
        
        # Büyüme oranları
        if previous_period:
            if financial.revenue and previous_period.revenue and previous_period.revenue > 0:
                analysis_results['revenue_growth'] = round(((financial.revenue - previous_period.revenue) / previous_period.revenue) * 100, 2)
            
            if financial.net_income and previous_period.net_income and previous_period.net_income > 0:
                analysis_results['net_income_growth'] = round(((financial.net_income - previous_period.net_income) / previous_period.net_income) * 100, 2)
            
            if financial.ebitda and previous_period.ebitda and previous_period.ebitda > 0:
                analysis_results['ebitda_growth'] = round(((financial.ebitda - previous_period.ebitda) / previous_period.ebitda) * 100, 2)
        
        # Değerleme ölçütleri açıklamaları
        if financial.pe_ratio:
            if financial.pe_ratio < 10:
                analysis_results['pe_ratio_comment'] = "Düşük F/K oranı (potansiyel olarak değerli)"
            elif financial.pe_ratio > 20:
                analysis_results['pe_ratio_comment'] = "Yüksek F/K oranı (potansiyel olarak pahalı)"
            else:
                analysis_results['pe_ratio_comment'] = "Orta düzey F/K oranı"
        
        if financial.debt_to_equity:
            if financial.debt_to_equity < 0.5:
                analysis_results['debt_to_equity_comment'] = "Düşük borç/özsermaye oranı (güçlü finansal yapı)"
            elif financial.debt_to_equity > 1.5:
                analysis_results['debt_to_equity_comment'] = "Yüksek borç/özsermaye oranı (riskli finansal yapı)"
            else:
                analysis_results['debt_to_equity_comment'] = "Orta düzey borç/özsermaye oranı"
        
        # Analiz sonuçlarını JSON olarak sakla
        financial.extra_data = json.dumps(analysis_results)
        financial.save()
        
        return analysis_results
        
    except Exception as e:
        print(f"Finansal analiz hatası: {str(e)}")
        return {}

@login_required
@user_passes_test(is_staff_user)
def company_financial_detail(request, financial_id):
    """
    Şirket finansal verisi detay sayfası ve analiz sonuçları
    """
    # Finansal veriyi getir
    financial = get_object_or_404(CompanyFinancial, id=financial_id)
    
    # JSON formatındaki extra_data alanını Python sözlüğüne dönüştür
    extra_data = {}
    if financial.extra_data:
        try:
            extra_data = json.loads(financial.extra_data)
        except json.JSONDecodeError:
            messages.warning(request, "Finansal analiz verisi okunamadı.")
    
    context = {
        'financial': financial,
        'extra_data': extra_data
    }
    
    return render(request, 'Tahmin/company_financial_detail.html', context)

@login_required
@user_passes_test(is_staff_user)
def financial_list(request):
    """
    Şirket finansal verilerinin listesini gösteren view
    """
    # Filtreleme parametrelerini al
    stock_id = request.GET.get('stock', '')
    year = request.GET.get('year', '')
    period = request.GET.get('period', '')
    
    # Temel sorgu
    financials = CompanyFinancial.objects.all().order_by('-year', '-period', 'stock__symbol')
    
    # Filtreleme
    if stock_id:
        financials = financials.filter(stock_id=stock_id)
    if year:
        financials = financials.filter(year=year)
    if period:
        financials = financials.filter(period=period)
    
    # Sayfalama
    paginator = Paginator(financials, 20)  # Sayfa başına 20 kayıt
    page = request.GET.get('page')
    
    try:
        financials = paginator.page(page)
    except PageNotAnInteger:
        # Sayfa bir tamsayı değilse, ilk sayfayı göster
        financials = paginator.page(1)
    except EmptyPage:
        # Sayfa sayısı çok yüksekse, son sayfayı göster
        financials = paginator.page(paginator.num_pages)
    
    # Filtreler için listeleri hazırla
    stocks = Stock.objects.filter(is_active=True).order_by('symbol')
    current_year = datetime.now().year
    years = list(range(current_year, current_year-5, -1))
    
    context = {
        'financials': financials,
        'stocks': stocks,
        'years': years,
        'selected_stock': stock_id,
        'selected_year': year,
        'selected_period': period,
    }
    
    return render(request, 'Tahmin/financial_list.html', context)
