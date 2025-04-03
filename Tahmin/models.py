from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

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
    moving_average_50 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="50 Günlük Ortalama")
    moving_average_200 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="200 Günlük Ortalama")
    rsi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="RSI")
    macd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="MACD")
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

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.stock.symbol} - {self.filename}"
