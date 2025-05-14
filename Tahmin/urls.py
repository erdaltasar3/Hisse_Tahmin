from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Hisse Yönetimi URLs
    path('stocks/', views.stock_management, name='stock_management'),
    path('stocks/add/', views.add_stock, name='add_stock'),
    path('stocks/edit/<int:stock_id>/', views.edit_stock, name='edit_stock'),
    path('stocks/delete/<int:stock_id>/', views.delete_stock, name='delete_stock'),
    path('stocks/toggle-status/<int:stock_id>/', views.toggle_stock_status, name='toggle_stock_status'),
    path('stocks/<int:stock_id>/add-price/', views.add_stock_price, name='add_stock_price'),
    path('api/add-stock-price/', views.add_stock_price_api, name='add_stock_price_api'),
    path('api/upload-stock-data/', views.upload_stock_data, name='upload_stock_data'),
    path('api/process-stock-data/', views.process_stock_data, name='process_stock_data'),
    path('api/delete-all-stock-prices/', views.delete_all_stock_prices, name='delete_all_stock_prices'),

    # Hisse dosya yönetimi
    path('stocks/<int:stock_id>/files/', views.stock_files, name='stock_files'),
    path('stocks/<int:stock_id>/upload-file/', views.upload_stock_file, name='upload_stock_file'),
    path('api/update-file-note/<int:file_id>/', views.update_file_note, name='update_file_note'),
    path('api/delete-file/<int:file_id>/', views.delete_file, name='delete_file'),
    path('api/process-file/<int:file_id>/', views.process_stock_data, name='process_file'),
    path('api/file-report/<int:file_id>/', views.file_report, name='file_report'),
    path('api/process-all-files/', views.process_all_files, name='process_all_files'),

    # Kullanıcı profili
    path('profile/', views.profile_view, name='profile'),

    path('stocks/<int:stock_id>/', views.stock_detail, name='stock_detail'),
    path('stocks/<int:stock_id>/calculate-analysis/', views.calculate_analysis, name='calculate_analysis'),
    path('stocks/<int:stock_id>/view-analysis/', views.view_stock_analysis, name='view_stock_analysis'),
    
    # Tahmin sayfası
    path('stocks/<int:stock_id>/prediction/', views.start_prediction, name='start_prediction'),
    path('stocks/<int:stock_id>/run-prediction/', views.run_prediction, name='run_prediction'),
    path('stocks/<int:stock_id>/prediction-status/', views.get_prediction_status, name='prediction_status'),
    
    # Tahmin veri kaynakları sayfası
    path('prediction-data-sources/', views.prediction_data_sources, name='prediction_data_sources'),
    
    # Makroekonomik veriler
    path('macroeconomic-data/', views.macroeconomic_data, name='macroeconomic_data'),
    path('macroeconomic-data/add/', views.add_macroeconomic_data, name='add_macroeconomic_data'),
    path('macroeconomic-data/edit/<int:data_id>/', views.edit_macroeconomic_data, name='edit_macroeconomic_data'),
    path('macroeconomic-data/delete/<int:data_id>/', views.delete_macroeconomic_data, name='delete_macroeconomic_data'),
    path('macroeconomic-data/import/', views.import_macroeconomic_data, name='import_macroeconomic_data'),
    
    # Enflasyon verileri
    path('inflation-data/', views.inflation_data, name='inflation_data'),
    path('inflation-data/delete/<int:data_id>/', views.delete_inflation_data, name='delete_inflation_data'),
]

