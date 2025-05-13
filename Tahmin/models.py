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
