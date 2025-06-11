from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect

class Stock(models.Model):
    name = models.CharField(max_length=100, verbose_name="Hisse Adı")
    symbol = models.CharField(max_length=10, unique=True, verbose_name="Hisse Sembolü")
    description = models.TextField(null=True, blank=True, verbose_name="Açıklama")
    sector = models.CharField(max_length=100, null=True, blank=True, verbose_name="Sektör")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")

    def __str__(self):
        return f"{self.symbol} - {self.name}"

    class Meta:
        verbose_name = "Hisse"
        verbose_name_plural = "Hisseler"
        ordering = ['symbol']

class StockPrice(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='prices', verbose_name="Hisse")
    date = models.DateField(verbose_name="Tarih")
    opening_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Açılış Fiyatı")
    closing_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Kapanış Fiyatı")
    highest_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="En Yüksek Fiyat")
    lowest_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="En Düşük Fiyat")
    volume = models.BigIntegerField(verbose_name="İşlem Hacmi")
    daily_change = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Günlük Değişim (%)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncelleme Tarihi")

    def __str__(self):
        return f"{self.stock.symbol} - {self.date}"

    class Meta:
        verbose_name = "Hisse Fiyatı"
        verbose_name_plural = "Hisse Fiyatları"
        ordering = ['-date']
        unique_together = ['stock', 'date']  # Aynı hisse için aynı tarihte birden fazla kayıt olmamalı

class StockAnalysis(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='analyses', verbose_name="Hisse")
    date = models.DateField(verbose_name="Analiz Tarihi")

    # Hareketli Ortalamalar (Günlük)
    ma_5 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="5 Günlük Ortalama")
    ma_10 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="10 Günlük Ortalama")
    ma_20 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="20 Günlük Ortalama")
    ma_50 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="50 Günlük Ortalama")
    ma_100 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="100 Günlük Ortalama")
    ma_200 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="200 Günlük Ortalama")

    # Hareketli Ortalamalar (Haftalık, Aylık, Yıllık)
    weekly_ma = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Haftalık Ortalama")
    monthly_ma = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Aylık Ortalama")
    yearly_ma = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Yıllık Ortalama")

    # EMA (Üssel Hareketli Ortalama)
    ema_12 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="EMA 12")
    ema_26 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="EMA 26")

    # WMA (Ağırlıklı Hareketli Ortalama)
    wma_20 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="WMA 20")

    # Fibonacci Seviyeleri
    fib_0_236 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fibonacci 0.236")
    fib_0_382 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fibonacci 0.382")
    fib_0_5 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fibonacci 0.5")
    fib_0_618 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fibonacci 0.618")
    fib_0_786 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fibonacci 0.786")
    fib_1_0 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fibonacci 1.0")

    # İndikatörler
    rsi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="RSI")
    macd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="MACD")
    macd_signal = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="MACD Sinyal")
    macd_hist = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="MACD Histogram")
    stochastic_k = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Stokastik %K")
    stochastic_d = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Stokastik %D")
    cci = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="CCI")
    bollinger_upper = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Bollinger Üst")
    bollinger_middle = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Bollinger Orta")
    bollinger_lower = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Bollinger Alt")
    atr = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="ATR")
    momentum = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Momentum")
    williams_r = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Williams %R")
    obv = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="OBV")
    mfi = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="MFI")

    # Destek/Direnç
    support_level = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Destek Seviyesi")
    resistance_level = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Direnç Seviyesi")

    # Pivot Noktaları
    pivot = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Pivot")
    s1 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="S1")
    s2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="S2")
    s3 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="S3")
    r1 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="R1")
    r2 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="R2")
    r3 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="R3")

    # Diğer
    volatility = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Volatilite")
    beta = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Beta")
    sharpe_ratio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Sharpe Oranı")
    sortino_ratio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Sortino Oranı")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncelleme Tarihi")

    def __str__(self):
        return f"{self.stock.symbol} - {self.date} Analizi"

    class Meta:
        verbose_name = "Hisse Analizi"
        verbose_name_plural = "Hisse Analizleri"
        ordering = ['-date']
        unique_together = ['stock', 'date']

class StockFile(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='files')
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255)
    note = models.TextField(blank=True, null=True)
    is_processed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # İşleme sonuçları için yeni alanlar
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_details = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.stock.symbol} - {self.filename}"

# Tahmin modeli için gerekli makroekonomik veriler
class MacroeconomicData(models.Model):
    date = models.DateField(verbose_name="Tarih")
    
    # Enflasyon verileri
    tufe = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="TÜFE Aylık (%)")
    tufe_yillik = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="TÜFE Yıllık (%)")
    ufe = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="ÜFE Aylık (%)")
    ufe_yillik = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="ÜFE Yıllık (%)")
    
    # Faiz verileri
    policy_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="TCMB Politika Faizi (%)")
    bond_yield_2y = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="2 Yıllık Tahvil Faizi (%)")
    bond_yield_10y = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="10 Yıllık Tahvil Faizi (%)")
    
    # Döviz kurları
    usd_try = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, verbose_name="USD/TRY")
    eur_try = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, verbose_name="EUR/TRY")
    
    # Ekonomik büyüme verileri
    gdp_growth = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="GSYH Büyüme (%)")
    
    # İşsizlik oranı
    unemployment_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="İşsizlik Oranı (%)")
    
    # Piyasa verileri
    bist100_close = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="BIST 100 Kapanış")
    bist100_change = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="BIST 100 Değişim (%)")
    market_volume = models.BigIntegerField(null=True, blank=True, verbose_name="Piyasa İşlem Hacmi (TL)")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncelleme Tarihi")
    
    def __str__(self):
        return f"Makroekonomik Veri - {self.date}"
    
    class Meta:
        verbose_name = "Makroekonomik Veri"
        verbose_name_plural = "Makroekonomik Veriler"
        ordering = ['-date']
        get_latest_by = "date"

# Sektör bilgileri
class Sector(models.Model):
    name = models.CharField(max_length=100, verbose_name="Sektör Adı")
    code = models.CharField(max_length=20, unique=True, verbose_name="Sektör Kodu")
    description = models.TextField(null=True, blank=True, verbose_name="Açıklama")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Sektör"
        verbose_name_plural = "Sektörler"
        ordering = ['name']

# OCR ile işlenen enflasyon verileri
class InflationData(models.Model):
    MONTH_CHOICES = [
        ('Ocak', 'Ocak'),
        ('Şubat', 'Şubat'),
        ('Mart', 'Mart'),
        ('Nisan', 'Nisan'),
        ('Mayıs', 'Mayıs'),
        ('Haziran', 'Haziran'),
        ('Temmuz', 'Temmuz'),
        ('Ağustos', 'Ağustos'),
        ('Eylül', 'Eylül'),
        ('Ekim', 'Ekim'),
        ('Kasım', 'Kasım'),
        ('Aralık', 'Aralık'),
    ]
    
    month = models.CharField(max_length=10, choices=MONTH_CHOICES, verbose_name="Ay")
    year = models.IntegerField(verbose_name="Yıl")
    tufe_monthly = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="TÜFE Aylık (%)")
    tufe_yearly = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="TÜFE Yıllık (%)")
    ufe_monthly = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="ÜFE Aylık (%)")
    ufe_yearly = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="ÜFE Yıllık (%)")
    source = models.CharField(max_length=50, default="TÜİK", verbose_name="Veri Kaynağı")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"{self.year} {self.month} - Enflasyon Verileri"
    
    class Meta:
        verbose_name = "Enflasyon Verisi"
        verbose_name_plural = "Enflasyon Verileri"
        ordering = ['-year', 'month']
        unique_together = ['month', 'year']

# Faiz oranları verileri
class InterestRate(models.Model):
    date = models.DateField(verbose_name="Tarih")
    policy_rate = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="TCMB Politika Faizi (%)")
    bond_yield_2y = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="2 Yıllık Tahvil Faizi (%)")
    bond_yield_10y = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="10 Yıllık Tahvil Faizi (%)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"Faiz Oranları - {self.date}"
    
    class Meta:
        verbose_name = "Faiz Oranı"
        verbose_name_plural = "Faiz Oranları"
        ordering = ['-date']
        get_latest_by = "date"

# Sektör endeksleri
class SectorIndex(models.Model):
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='indices', verbose_name="Sektör")
    date = models.DateField(verbose_name="Tarih")
    value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Endeks Değeri")
    change = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Günlük Değişim (%)")
    volume = models.BigIntegerField(verbose_name="İşlem Hacmi")
    
    def __str__(self):
        return f"{self.sector.name} - {self.date}"
    
    class Meta:
        verbose_name = "Sektör Endeksi"
        verbose_name_plural = "Sektör Endeksleri"
        ordering = ['-date']
        unique_together = ['sector', 'date']

# Şirket finansal verileri
class CompanyFinancial(models.Model):
    PERIOD_CHOICES = [
        ('Q1', '1. Çeyrek'),
        ('Q2', '2. Çeyrek'),
        ('Q3', '3. Çeyrek'),
        ('Q4', '4. Çeyrek'),
        ('ANNUAL', 'Yıllık'),
    ]
    
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='financials', verbose_name="Hisse")
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, verbose_name="Dönem")
    year = models.IntegerField(verbose_name="Yıl")
    
    # Temel finansal veriler
    revenue = models.BigIntegerField(null=True, blank=True, verbose_name="Satış Geliri (TL)")
    ebitda = models.BigIntegerField(null=True, blank=True, verbose_name="FAVÖK (TL)")
    net_income = models.BigIntegerField(null=True, blank=True, verbose_name="Net Kar (TL)")
    
    # Bilanço verileri
    total_assets = models.BigIntegerField(null=True, blank=True, verbose_name="Toplam Varlıklar (TL)")
    total_liabilities = models.BigIntegerField(null=True, blank=True, verbose_name="Toplam Yükümlülükler (TL)")
    equity = models.BigIntegerField(null=True, blank=True, verbose_name="Özkaynaklar (TL)")
    
    # Oranlar
    debt_to_equity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Borç/Özsermaye")
    roe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="ROE (%)")
    
    # Hisse başı veriler
    eps = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Hisse Başı Kazanç (TL)")
    
    # Temettü verileri
    dividend = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Temettü (TL)")
    dividend_yield = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Temettü Verimi (%)")
    
    # Piyasa çarpanları
    pe_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="F/K Oranı")
    pb_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="PD/DD")
    ev_ebitda = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="FD/FAVÖK")
    
    # Analiz sonuçları (JSON formatında)
    extra_data = models.TextField(null=True, blank=True, verbose_name="Analiz Sonuçları (JSON)")
    
    # Dosya yolları
    pdf_path = models.CharField(max_length=255, null=True, blank=True, verbose_name="PDF Dosyası Yolu")
    excel_path = models.CharField(max_length=255, null=True, blank=True, verbose_name="Excel Dosyası Yolu")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncelleme Tarihi")
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.year} {self.period}"
    
    class Meta:
        verbose_name = "Şirket Finansalı"
        verbose_name_plural = "Şirket Finansalları"
        ordering = ['-year', '-period']
        unique_together = ['stock', 'period', 'year']

# Sosyal Medya ve Haber Duygu Analizi
class SentimentData(models.Model):
    SENTIMENT_CHOICES = [
        ('VERY_POSITIVE', 'Çok Olumlu'),
        ('POSITIVE', 'Olumlu'),
        ('NEUTRAL', 'Nötr'),
        ('NEGATIVE', 'Olumsuz'),
        ('VERY_NEGATIVE', 'Çok Olumsuz'),
    ]
    
    SOURCE_CHOICES = [
        ('TWITTER', 'Twitter'),
        ('NEWS', 'Haber'),
        ('FORUM', 'Forum'),
        ('ANALYST', 'Analist'),
        ('OTHER', 'Diğer'),
    ]
    
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='sentiments', verbose_name="Hisse")
    date = models.DateField(verbose_name="Tarih")
    
    # Duygu verileri
    sentiment_score = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Duygu Skoru (-1 ila 1)")
    sentiment_label = models.CharField(max_length=15, choices=SENTIMENT_CHOICES, verbose_name="Duygu Etiketi")
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, verbose_name="Kaynak")
    
    # Metin içeriği (isteğe bağlı)
    content_sample = models.TextField(null=True, blank=True, verbose_name="İçerik Örneği")
    
    # Hacim verileri
    mention_count = models.IntegerField(default=0, verbose_name="Bahsedilme Sayısı")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt Tarihi")
    
    def __str__(self):
        return f"{self.stock.symbol} - {self.date} - {self.get_sentiment_label_display()}"
    
    class Meta:
        verbose_name = "Duygu Analizi"
        verbose_name_plural = "Duygu Analizleri"
        ordering = ['-date']

# Döviz Kurları
class ExchangeRate(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'Amerikan Doları'),
        ('EUR', 'Euro'),
    ]
    
    date = models.DateField(verbose_name="Tarih")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, verbose_name="Para Birimi")
    
    # Kur verileri
    open_price = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Açılış")
    high_price = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="En Yüksek")
    low_price = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="En Düşük")
    close_price = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Kapanış")
    volume = models.CharField(max_length=20, null=True, blank=True, verbose_name="Hacim")
    change_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Değişim (%)")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"{self.currency}/TRY - {self.date}"
    
    class Meta:
        verbose_name = "Döviz Kuru"
        verbose_name_plural = "Döviz Kurları"
        ordering = ['-date', 'currency']
        unique_together = ['date', 'currency']

# Sektörel Endeks Verileri
class SectoralIndexData(models.Model):
    date = models.DateField(verbose_name="Tarih")
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='index_data', verbose_name="Sektör")
    
    # Endeks verileri
    open_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Açılış Değeri")
    high_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="En Yüksek Değer")
    low_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="En Düşük Değer")
    close_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Kapanış Değeri")
    volume = models.BigIntegerField(null=True, blank=True, verbose_name="İşlem Hacmi")
    change_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Değişim (%)")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"{self.sector.name} Endeksi - {self.date}"
    
    class Meta:
        verbose_name = "Sektör Endeks Verisi"
        verbose_name_plural = "Sektör Endeks Verileri"
        ordering = ['-date', 'sector']
        unique_together = ['date', 'sector']

# Sektörel Regülasyon Değişiklikleri
class SectoralRegulation(models.Model):
    IMPACT_CHOICES = [
        ('VERY_POSITIVE', 'Çok Olumlu'),
        ('POSITIVE', 'Olumlu'),
        ('NEUTRAL', 'Nötr'),
        ('NEGATIVE', 'Olumsuz'),
        ('VERY_NEGATIVE', 'Çok Olumsuz'),
    ]
    
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='regulations', verbose_name="Sektör")
    title = models.CharField(max_length=200, verbose_name="Başlık")
    description = models.TextField(verbose_name="Açıklama")
    announcement_date = models.DateField(verbose_name="Duyuru Tarihi")
    effective_date = models.DateField(verbose_name="Yürürlük Tarihi")
    impact = models.CharField(max_length=15, choices=IMPACT_CHOICES, verbose_name="Etki")
    source = models.CharField(max_length=200, verbose_name="Kaynak")
    source_url = models.URLField(null=True, blank=True, verbose_name="Kaynak URL")
    notes = models.TextField(null=True, blank=True, verbose_name="Notlar")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Eklenme Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"{self.sector.name} - {self.title} ({self.announcement_date})"
    
    class Meta:
        verbose_name = "Sektörel Regülasyon"
        verbose_name_plural = "Sektörel Regülasyonlar"
        ordering = ['-announcement_date', 'sector']

# Sektörel Büyüme Verileri
class SectoralGrowth(models.Model):
    PERIOD_CHOICES = [
        ('Q1', '1. Çeyrek'),
        ('Q2', '2. Çeyrek'),
        ('Q3', '3. Çeyrek'),
        ('Q4', '4. Çeyrek'),
        ('ANNUAL', 'Yıllık'),
    ]
    
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='growth_data', verbose_name="Sektör")
    year = models.IntegerField(verbose_name="Yıl")
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, verbose_name="Dönem")
    growth_rate = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Büyüme Oranı (%)")
    volume = models.BigIntegerField(null=True, blank=True, verbose_name="Hacim (TL)")
    employment_change = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="İstihdam Değişimi (%)")
    export_growth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="İhracat Büyümesi (%)")
    investment_growth = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Yatırım Büyümesi (%)")
    source = models.CharField(max_length=200, verbose_name="Veri Kaynağı")
    notes = models.TextField(null=True, blank=True, verbose_name="Notlar")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Eklenme Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"{self.sector.name} - {self.year} {self.period} Büyüme"
    
    class Meta:
        verbose_name = "Sektörel Büyüme Verisi"
        verbose_name_plural = "Sektörel Büyüme Verileri"
        ordering = ['-year', '-period', 'sector']
        unique_together = ['sector', 'year', 'period']

# Sektörel Mevsimsellik Etkileri
class SeasonalEffect(models.Model):
    SEASON_CHOICES = [
        ('WINTER', 'Kış'),
        ('SPRING', 'İlkbahar'),
        ('SUMMER', 'Yaz'),
        ('AUTUMN', 'Sonbahar'),
        ('QUARTER_1', '1. Çeyrek'),
        ('QUARTER_2', '2. Çeyrek'),
        ('QUARTER_3', '3. Çeyrek'),
        ('QUARTER_4', '4. Çeyrek'),
        ('RAMADAN', 'Ramazan'),
        ('EID', 'Bayram'),
        ('NEW_YEAR', 'Yılbaşı'),
        ('SUMMER_HOLIDAY', 'Yaz Tatili'),
        ('OTHER', 'Diğer'),
    ]
    
    EFFECT_CHOICES = [
        ('VERY_POSITIVE', 'Çok Olumlu'),
        ('POSITIVE', 'Olumlu'),
        ('NEUTRAL', 'Nötr'),
        ('NEGATIVE', 'Olumsuz'),
        ('VERY_NEGATIVE', 'Çok Olumsuz'),
    ]
    
    sector = models.ForeignKey(Sector, on_delete=models.CASCADE, related_name='seasonal_effects', verbose_name="Sektör")
    season = models.CharField(max_length=20, choices=SEASON_CHOICES, verbose_name="Mevsim/Dönem")
    effect = models.CharField(max_length=15, choices=EFFECT_CHOICES, verbose_name="Etki")
    effect_description = models.TextField(verbose_name="Etki Açıklaması")
    average_change = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Ortalama Değişim (%)")
    historical_data = models.TextField(null=True, blank=True, verbose_name="Tarihsel Veri Özeti")
    notes = models.TextField(null=True, blank=True, verbose_name="Notlar")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Eklenme Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")
    
    def __str__(self):
        return f"{self.sector.name} - {self.get_season_display()} ({self.get_effect_display()})"
    
    class Meta:
        verbose_name = "Mevsimsel Etki"
        verbose_name_plural = "Mevsimsel Etkiler"
        ordering = ['sector', 'season']
        unique_together = ['sector', 'season']
