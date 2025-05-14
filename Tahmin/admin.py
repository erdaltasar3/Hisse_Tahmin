from django.contrib import admin
# User ve UserAdmin import'larını kaldırıyoruz çünkü zaten Django tarafından kaydedilmiş durumda
from .models import (Stock, StockPrice, StockAnalysis, StockFile, 
                    MacroeconomicData, Sector, SectorIndex, 
                    CompanyFinancial, SentimentData)

# Register your models here.
# admin.site.register(User, UserAdmin) satırını kaldırıyoruz

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name', 'sector', 'is_active', 'created_at')
    list_filter = ('is_active', 'sector')
    search_fields = ('symbol', 'name')
    ordering = ('symbol',)

@admin.register(StockPrice)
class StockPriceAdmin(admin.ModelAdmin):
    list_display = ('stock', 'date', 'opening_price', 'closing_price', 'highest_price', 'lowest_price', 'volume')
    list_filter = ('date', 'stock')
    date_hierarchy = 'date'
    ordering = ('-date',)

@admin.register(StockAnalysis)
class StockAnalysisAdmin(admin.ModelAdmin):
    list_display = ('stock', 'date', 'ma_5', 'ma_20', 'ma_50', 'ma_100', 'rsi')
    list_filter = ('date', 'stock')
    date_hierarchy = 'date'
    ordering = ('-date',)

@admin.register(StockFile)
class StockFileAdmin(admin.ModelAdmin):
    list_display = ('stock', 'filename', 'is_processed', 'uploaded_at', 'uploaded_by')
    list_filter = ('is_processed', 'uploaded_at')
    search_fields = ('filename', 'note')
    ordering = ('-uploaded_at',)

@admin.register(MacroeconomicData)
class MacroeconomicDataAdmin(admin.ModelAdmin):
    list_display = ('date', 'tufe_yillik', 'usd_try', 'policy_rate', 'gdp_growth', 'bist100_close')
    list_filter = ('date',)
    date_hierarchy = 'date'
    ordering = ('-date',)
    fieldsets = (
        ('Tarih Bilgisi', {
            'fields': ('date',)
        }),
        ('Enflasyon', {
            'fields': ('tufe', 'tufe_yillik', 'ufe', 'ufe_yillik')
        }),
        ('Faiz Oranları', {
            'fields': ('policy_rate', 'bond_yield_2y', 'bond_yield_10y')
        }),
        ('Döviz Kurları', {
            'fields': ('usd_try', 'eur_try')
        }),
        ('Ekonomik Veriler', {
            'fields': ('gdp_growth', 'unemployment_rate')
        }),
        ('Piyasa Verileri', {
            'fields': ('bist100_close', 'bist100_change', 'market_volume')
        }),
    )

@admin.register(Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')
    ordering = ('name',)

@admin.register(SectorIndex)
class SectorIndexAdmin(admin.ModelAdmin):
    list_display = ('sector', 'date', 'value', 'change', 'volume')
    list_filter = ('date', 'sector')
    date_hierarchy = 'date'
    ordering = ('-date',)

@admin.register(CompanyFinancial)
class CompanyFinancialAdmin(admin.ModelAdmin):
    list_display = ('stock', 'period', 'year', 'revenue', 'net_income', 'debt_to_equity', 'pe_ratio')
    list_filter = ('period', 'year', 'stock')
    search_fields = ('stock__symbol', 'stock__name')
    ordering = ('-year', '-period')
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('stock', 'period', 'year')
        }),
        ('Gelir Tablosu', {
            'fields': ('revenue', 'ebitda', 'net_income')
        }),
        ('Bilanço', {
            'fields': ('total_assets', 'total_liabilities', 'equity')
        }),
        ('Finansal Oranlar', {
            'fields': ('debt_to_equity', 'roe', 'eps', 'dividend', 'dividend_yield')
        }),
        ('Piyasa Çarpanları', {
            'fields': ('pe_ratio', 'pb_ratio', 'ev_ebitda')
        }),
    )

@admin.register(SentimentData)
class SentimentDataAdmin(admin.ModelAdmin):
    list_display = ('stock', 'date', 'sentiment_label', 'source', 'mention_count')
    list_filter = ('date', 'sentiment_label', 'source', 'stock')
    search_fields = ('stock__symbol', 'content_sample')
    date_hierarchy = 'date'
    ordering = ('-date',)
