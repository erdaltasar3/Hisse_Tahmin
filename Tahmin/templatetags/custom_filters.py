from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Sözlükten bir anahtar kullanarak değer almak için template filtresi
    Örnek kullanım: {{ my_dict|get_item:key_variable }}
    """
    return dictionary.get(key) 