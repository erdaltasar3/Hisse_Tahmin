from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(template_name='Tahmin/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='Tahmin/home.html'), name='logout'),
    path('register/', views.register, name='register'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Hisse Yönetimi URLs
    path('stocks/', views.stock_management, name='stock_management'),
    path('stocks/add/', views.add_stock, name='add_stock'),
    path('stocks/edit/<int:stock_id>/', views.edit_stock, name='edit_stock'),
    path('stocks/delete/<int:stock_id>/', views.delete_stock, name='delete_stock'),
    path('stocks/toggle-status/<int:stock_id>/', views.toggle_stock_status, name='toggle_stock_status'),
]

