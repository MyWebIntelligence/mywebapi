#!/usr/bin/env python3
"""
Test de détection de langue avec langdetect
"""

import sys
sys.path.insert(0, '/app')

from app.utils.text_utils import detect_language

# Textes de test dans différentes langues
test_texts = {
    'fr': "Bonjour, ceci est un texte en français pour tester la détection de langue. La France est un pays européen.",
    'en': "Hello, this is a text in English to test language detection. England is a European country.",
    'es': "Hola, este es un texto en español para probar la detección de idiomas. España es un país europeo.",
    'de': "Hallo, dies ist ein Text auf Deutsch zum Testen der Spracherkennung. Deutschland ist ein europäisches Land.",
    'it': "Ciao, questo è un testo in italiano per testare il rilevamento della lingua. L'Italia è un paese europeo.",
    'pt': "Olá, este é um texto em português para testar a detecção de idioma. Portugal é um país europeu.",
    'nl': "Hallo, dit is een tekst in het Nederlands om taaldetectie te testen. Nederland is een Europees land.",
    'ru': "Привет, это текст на русском языке для проверки определения языка. Россия - европейская страна.",
    'zh': "你好，这是一段中文文本，用于测试语言检测。中国是一个亚洲国家。",
    'ja': "こんにちは、これは言語検出をテストするための日本語のテキストです。日本はアジアの国です。",
    'ar': "مرحبا، هذا نص باللغة العربية لاختبار اكتشاف اللغة. السعودية هي دولة في الشرق الأوسط.",
    'ko': "안녕하세요, 이것은 언어 감지를 테스트하기 위한 한국어 텍스트입니다. 한국은 아시아 국가입니다.",
}

print("=" * 70)
print("Test de détection de langue - langdetect")
print("=" * 70)
print()

success = 0
total = len(test_texts)

for expected_lang, text in test_texts.items():
    detected = detect_language(text)
    status = "✅" if detected == expected_lang else "❌"

    if detected == expected_lang:
        success += 1

    print(f"{status} {expected_lang:5} → Détecté: {detected:5} | {text[:60]}...")

print()
print("=" * 70)
print(f"Résultat: {success}/{total} détections correctes ({success*100//total}%)")
print("=" * 70)
