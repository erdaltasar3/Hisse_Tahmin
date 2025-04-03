import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Hisse_Tahmin.settings')
django.setup()

from Tahmin.models import Stock, StockPrice, StockFile, UserProfile

def transfer_data():
    # Stock verilerini aktar
    for stock in Stock.objects.using('default').all():
        stock.save(using='default')
        print(f"Stock aktarıldı: {stock.name}")

    # StockPrice verilerini aktar
    for price in StockPrice.objects.using('default').all():
        price.save(using='default')
        print(f"StockPrice aktarıldı: {price.stock.name} - {price.date}")

    # StockFile verilerini aktar
    for file in StockFile.objects.using('default').all():
        file.save(using='default')
        print(f"StockFile aktarıldı: {file.file.name}")

    # UserProfile verilerini aktar
    for profile in UserProfile.objects.using('default').all():
        profile.save(using='default')
        print(f"UserProfile aktarıldı: {profile.user.username}")

if __name__ == '__main__':
    transfer_data() 