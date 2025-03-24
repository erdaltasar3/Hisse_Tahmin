from django.shortcuts import render

# Create your views here.


from django.http import HttpResponse

def home(request):
    return HttpResponse("Hisse Tahmin Projesine Hoş Geldiniz!")

from django.shortcuts import render

def home(request):
    return render(request, 'Tahmin/home.html')

def register(request):
    return render(request, 'Tahmin/register.html')
