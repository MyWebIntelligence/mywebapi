# Configuration OpenRouter pour LLM Validation

## 🔑 Obtenir une clé API OpenRouter

### 1. Créer un compte OpenRouter

1. **Aller sur** : https://openrouter.ai/
2. **S'inscrire** avec email/mot de passe ou connexion GitHub/Google
3. **Vérifier l'email** si nécessaire

### 2. Obtenir la clé API

1. **Se connecter** sur https://openrouter.ai/
2. **Aller dans** : Account → API Keys (ou directement https://openrouter.ai/keys)
3. **Cliquer** sur "Create Key"
4. **Nommer** la clé (ex: "MyWebIntelligence API")
5. **Copier** la clé générée (commence par `sk-or-v1-...`)

⚠️ **Important** : Sauvegardez immédiatement la clé, elle ne sera plus affichée !

### 3. Ajouter des crédits (si nécessaire)

- OpenRouter fonctionne avec un système de **pay-per-use**
- **Crédits gratuits** : Généralement 5-10$ offerts à l'inscription  
- **Ajouter des crédits** : Account → Billing → Add Credits
- **Coût typique** : ~0.01-0.05$ par validation (selon le modèle)

## 🌐 Configuration de l'API

### URL de l'API OpenRouter
```
https://openrouter.ai/api/v1/chat/completions
```

### Modèles recommandés pour la validation

1. **`anthropic/claude-3.5-sonnet`** (recommandé)
   - Excellent pour la compréhension en français
   - Coût : ~0.015$ / 1K tokens
   - Précis et cohérent

2. **`anthropic/claude-3-haiku`** (économique)
   - Bon rapport qualité/prix
   - Coût : ~0.003$ / 1K tokens  
   - Plus rapide

3. **`openai/gpt-4o-mini`** (alternatif)
   - Coût : ~0.002$ / 1K tokens
   - Bon pour des validations simples

### Configuration MyWebIntelligence

Ajouter dans votre fichier `.env` :

```bash
# OpenRouter LLM Validation
OPENROUTER_ENABLED=True
OPENROUTER_API_KEY=sk-or-v1-your-actual-api-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_TIMEOUT=30
OPENROUTER_MAX_RETRIES=3
```

## 🧪 Tester la configuration

### Test rapide avec curl

```bash
# Test direct API OpenRouter
curl -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer sk-or-v1-your-key" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://mywebintelligence.io" \
  -H "X-Title: MyWebIntelligence API" \
  -d '{
    "model": "anthropic/claude-3.5-sonnet",
    "messages": [{"role": "user", "content": "Réponds juste par oui ou non : Est-ce que Paris est en France ?"}],
    "max_tokens": 10
  }'
```

### Test avec MyWebIntelligence

```bash
# 1. Authentification
TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=changeme" | jq -r .access_token)

# 2. Test crawl avec LLM validation
curl -X POST "http://localhost:8000/api/v2/lands/36/crawl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 3,
    "analyze_media": false,
    "enable_llm": true
  }'

# 3. Test readable avec LLM validation
curl -X POST "http://localhost:8000/api/v2/lands/36/readable" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 3,
    "enable_llm": true
  }'
```

## 💰 Estimation des coûts

### Coût par validation
- **Prompt typique** : ~500 tokens (description land + contenu expression)
- **Réponse** : 1-2 tokens ("oui" ou "non")
- **Coût Claude 3.5 Sonnet** : ~0.007$ par validation

### Estimation mensuelle
- **100 expressions/jour** : ~21$ / mois
- **500 expressions/jour** : ~105$ / mois  
- **1000 expressions/jour** : ~210$ / mois

### Optimisations
1. **Utiliser Claude Haiku** pour réduire les coûts de 70%
2. **Filtrer par pertinence** (`minrel >= 2.0`) avant validation
3. **Valider seulement le contenu readable** (pas le HTML brut)

## 🛠️ Dépannage

### Erreur 401 "Unauthorized"
- Vérifier que la clé API est correcte
- S'assurer que `OPENROUTER_ENABLED=True`
- Vérifier que la clé commence par `sk-or-v1-`

### Erreur 429 "Rate Limited" 
- OpenRouter limite à ~60 requêtes/minute par défaut
- Le système retry automatiquement avec backoff
- Réduire `batch_size` si nécessaire

### Erreur 402 "Insufficient Credits"
- Ajouter des crédits sur https://openrouter.ai/account
- Vérifier le solde : Account → Billing

### Timeouts
- Augmenter `OPENROUTER_TIMEOUT` si nécessaire
- Vérifier la connectivité réseau
- Certains modèles sont plus lents que d'autres

## 📊 Monitoring

### Logs à surveiller
```bash
# Logs de validation LLM
docker logs mywebclient-celery_worker-1 --tail=20 -f | grep -i "llm\|openrouter"

# Statistiques de validation
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v2/lands/36/stats"
```

### Champs de résultat
- `valid_llm` : "oui" ou "non" (résultat validation)
- `valid_model` : Modèle utilisé pour la validation
- `relevance` : Score de pertinence (peut être mis à 0 si non pertinent)

## 🔗 Liens utiles

- **Site OpenRouter** : https://openrouter.ai/
- **Documentation API** : https://openrouter.ai/docs
- **Modèles disponibles** : https://openrouter.ai/models
- **Statut service** : https://status.openrouter.ai/
- **Communauté Discord** : https://discord.gg/fVyRaUDgxW