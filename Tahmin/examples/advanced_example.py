import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import logging
import argparse

# Ana proje klasörünü Python yolu ekle
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Tahmin modüllerini içe aktar
from Tahmin.prediction import (
    ModelOrchestrator,
    LSTMModel,
    XGBoostModel,
    HybridModel,
    ModelOptimizer,
    ModelExplainer,
    ModelTracker,
    ReportExporter
)

# Günlük yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("advanced_example.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AdvancedExample")

def load_sample_data(file_path='sample_data.csv'):
    """Örnek veri yükleme"""
    try:
        # Örnek veri dosyasını kontrol et
        if not os.path.exists(file_path):
            # Örnek veri oluştur
            logger.info(f"Örnek veri dosyası bulunamadı: {file_path}, yeni veri oluşturuluyor")
            
            # Tarih aralığı oluştur - son 3 yıl
            dates = pd.date_range(end=datetime.now(), periods=1000, freq='D')
            
            # Fiyat serisi oluştur - rassal yürüyüş
            np.random.seed(42)  # Tekrarlanabilirlik için
            price = 100.0  # Başlangıç fiyatı
            prices = [price]
            
            # Fiyat değişimlerini oluştur
            daily_returns = np.random.normal(0.0005, 0.02, len(dates)-1)  # Ortalama ve standart sapma
            
            for r in daily_returns:
                price *= (1 + r)
                prices.append(price)
            
            # Hacim serisi oluştur
            volume = np.random.normal(1000000, 300000, len(dates))
            volume = np.abs(volume)  # Negatif hacimleri kaldır
            
            # Yüksek ve düşük fiyatlar
            high = [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices]
            low = [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices]
            
            # Açılış fiyatları - önceki kapanışın biraz değişmiş hali
            open_prices = [prices[0]] + [prices[i-1] * (1 + np.random.normal(0, 0.005)) for i in range(1, len(prices))]
            
            # DataFrame oluştur
            df = pd.DataFrame({
                'date': dates,
                'opening_price': open_prices,
                'high': high,
                'low': low,
                'closing_price': prices,
                'volume': volume,
                'symbol': 'EXAMPLE'
            })
            
            # Teknik gösterge örneği - 14 günlük Göreceli Güç Endeksi (RSI)
            delta = df['closing_price'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 20 günlük hareketli ortalama
            df['sma_20'] = df['closing_price'].rolling(window=20).mean()
            
            # 50 günlük hareketli ortalama
            df['sma_50'] = df['closing_price'].rolling(window=50).mean()
            
            # Bollinger Bandları
            df['sma_20'] = df['closing_price'].rolling(window=20).mean()
            df['bollinger_upper'] = df['sma_20'] + 2 * df['closing_price'].rolling(window=20).std()
            df['bollinger_lower'] = df['sma_20'] - 2 * df['closing_price'].rolling(window=20).std()
            
            # MACD (Moving Average Convergence Divergence)
            df['ema_12'] = df['closing_price'].ewm(span=12, adjust=False).mean()
            df['ema_26'] = df['closing_price'].ewm(span=26, adjust=False).mean()
            df['macd'] = df['ema_12'] - df['ema_26']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            
            # Na değerleri temizle
            df.dropna(inplace=True)
            
            # CSV olarak kaydet
            df.to_csv(file_path, index=False)
            logger.info(f"Örnek veri oluşturuldu ve kaydedildi: {file_path}")
        
        # Veriyi yükle
        df = pd.read_csv(file_path)
        
        # Tarih sütununu dönüştür
        df['date'] = pd.to_datetime(df['date'])
        
        return df
        
    except Exception as e:
        logger.error(f"Veri yükleme hatası: {str(e)}")
        raise

def main():
    """Ana fonksiyon - gelişmiş örnek uygulamayı çalıştır"""
    parser = argparse.ArgumentParser(description='Gelişmiş Hisse Senedi Tahmin Örneği')
    parser.add_argument('--model-type', type=str, default='hybrid', choices=['lstm', 'xgboost', 'hybrid'],
                        help='Kullanılacak model tipi (varsayılan: hybrid)')
    parser.add_argument('--optimize', action='store_true', help='Hiperparametre optimizasyonu yap')
    parser.add_argument('--explain', action='store_true', help='Model açıklaması oluştur')
    parser.add_argument('--report-type', type=str, default='detailed', 
                        choices=['basic', 'detailed', 'technical', 'fundamental', 'complete'],
                        help='Rapor tipi (varsayılan: detailed)')
    parser.add_argument('--export-formats', type=str, nargs='+', default=['pdf', 'excel'],
                        help='Dışa aktarma formatları (varsayılan: pdf excel)')
    parser.add_argument('--time-horizon', type=int, default=12, help='Ay cinsinden tahmin zaman ufku (varsayılan: 12)')
    parser.add_argument('--data-file', type=str, default='sample_data.csv', help='Veri dosyası (varsayılan: sample_data.csv)')
    parser.add_argument('--output-dir', type=str, default='advanced_output', help='Çıktı dizini (varsayılan: advanced_output)')
    
    args = parser.parse_args()
    
    try:
        # Veri yükleme
        logger.info(f"Veri yükleniyor: {args.data_file}")
        data = load_sample_data(args.data_file)
        logger.info(f"Veri yüklendi: {len(data)} satır")
        
        # Örnek hisse bilgileri
        stock_info = {
            'symbol': 'EXAMPLE',
            'name': 'Örnek Hisse Senedi',
            'sector': 'Teknoloji',
            'market': 'BİST',
            'currency': 'TRY'
        }
        
        # Model orchestrator oluştur
        orchestrator = ModelOrchestrator(base_dir=args.output_dir)
        
        # Veriyi eğitim ve test kümelerine ayır
        train_data, test_data = orchestrator.train_test_split(data, test_size=0.2, time_based=True)
        logger.info(f"Veri bölündü: Eğitim={len(train_data)} satır, Test={len(test_data)} satır")
        
        # Model oluştur veya yükle
        model_name = f"{args.model_type}_model_{args.time_horizon}m"
        model_path = os.path.join(args.output_dir, "models", f"{model_name}.h5")
        
        if os.path.exists(model_path):
            # Mevcut modeli yükle
            logger.info(f"Mevcut model yükleniyor: {model_name}")
            model = orchestrator.load_model(model_name, args.model_type)
        else:
            # Yeni model oluştur
            logger.info(f"Yeni model oluşturuluyor: {args.model_type}")
            model = orchestrator.create_model(
                model_type=args.model_type,
                model_name=model_name,
                time_horizon=args.time_horizon
            )
            
            # Modeli eğit
            logger.info("Model eğitimi başlıyor")
            model, history, metrics = orchestrator.train_model(
                model=model,
                data=train_data,
                target_column='closing_price',
                optimize=args.optimize,
                stock_symbol=stock_info['symbol'],
                n_trials=10 if args.optimize else 0  # Az deneme sayısı, örnek için
            )
            
            logger.info(f"Model eğitimi tamamlandı: {metrics}")
        
        # Model açıklaması oluştur
        if args.explain:
            logger.info("Model açıklaması oluşturuluyor")
            explanations = orchestrator.generate_model_explanation(
                model=model,
                data=test_data,
                n_samples=50  # Örnek için az sayı
            )
            logger.info(f"Model açıklaması oluşturuldu: {explanations['report_files']}")
        
        # Tahmin yap
        logger.info("Tahmin yapılıyor")
        prediction_result = orchestrator.predict_stock(
            model=model,
            stock_data=test_data,
            stock_info=stock_info
        )
        
        logger.info(f"Tahmin sonucu: Son Fiyat={prediction_result['last_price']:.2f}, "
                   f"Tahmin={prediction_result['final_prediction']:.2f}, "
                   f"Değişim={prediction_result['percent_change']:.2f}%")
        
        # Rapor oluştur
        logger.info(f"Rapor oluşturuluyor: {args.report_type}")
        report_result, export_paths = orchestrator.generate_report(
            model=model,
            stock_data=test_data,
            stock_info=stock_info,
            prediction_result=prediction_result,
            report_type=args.report_type,
            export_formats=args.export_formats
        )
        
        logger.info(f"Rapor oluşturuldu: {report_result['report_path']}")
        
        if export_paths:
            logger.info("Dışa aktarılan dosyalar:")
            for fmt, path in export_paths.items():
                logger.info(f"  - {fmt}: {path}")
        
        # Performans raporu oluştur
        logger.info("Performans raporu oluşturuluyor")
        perf_report = orchestrator.analyze_model_performance(
            model_name=model_name,
            stock_symbol=stock_info['symbol']
        )
        
        if perf_report.get('success', False):
            logger.info(f"Performans raporu oluşturuldu: {perf_report['report_files']}")
        else:
            logger.info(f"Performans raporu oluşturulamadı: {perf_report.get('message', 'Bilinmeyen hata')}")
        
        logger.info("İşlem tamamlandı")
        
    except Exception as e:
        logger.error(f"Uygulama hatası: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 