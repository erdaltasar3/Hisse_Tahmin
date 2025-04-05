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
    path('bulk-add-stock-prices/', views.bulk_add_stock_prices, name='bulk_add_stock_prices'),
    path('api/add-stock-price/', views.add_stock_price_api, name='add_stock_price_api'),
    path('api/upload-stock-data/', views.upload_stock_data, name='upload_stock_data'),
    path('api/process-stock-data/', views.process_stock_data, name='process_stock_data'),

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
]

