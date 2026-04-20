# LLM Proxy Web UI - Testing Interface

Interface web pour tester différents modèles LLM (gratuits et payants) via votre proxy de sécurité.

## Démarrage Rapide

### 1. Démarrer le proxy principal (port 8080)

```bash
cd ~/LLM-proxy
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn src.proxy.main:app --host 0.0.0.0 --port 8080
```

### 2. Démarrer l'interface Web UI (port 8000)

```bash
cd ~/LLM-proxy
source .venv/bin/activate
uvicorn src.webui.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Ouvrir dans le navigateur

```
http://localhost:8000
```

## Fonctionnalités

### 🆓 Modèles Gratuits
- Gemini Flash Thinking (Google)
- DeepSeek Chat V3 (DeepSeek)
- Qwen 2.5 72B (Alibaba)
- Phi-4 (Microsoft)
- Llama 3.3 70B (Meta)

### 💰 Modèles Payants
- Claude 3.5 Sonnet (Anthropic)
- Claude 3.5 Haiku (Anthropic)
- Claude 3 Opus (Anthropic)
- GPT-4o (OpenAI)
- GPT-4o Mini (OpenAI)
- Gemini 2.0 Flash (Google)

### Fonctionnalités de l'Interface
- Sélection de modèle intuitive
- Affichage du temps de réponse
- Compteurs de tokens (prompt/completion/total)
- Gestion des erreurs claire
- Tests de sécurité PII intégrés

## Configuration API Key

L'interface utilise votre clé API proxy existante: `dev-local-key-1234`

Pour utiliser votre propre clé, modifiez le champ dans l'interface.

## Tests de Sécurité

L'interface transfère automatiquement les requêtes via votre proxy de sécurité qui:
- Bloque les credentials/API keys exposés
- Bloque les tentatives d'injection de prompt
- Bloque les informations personnelles (PII)
- Valide les dépendances de sortie via Nexus

## Structure des Fichiers

```
src/webui/
├── __init__.py
├── main.py      # Application FastAPI
└── README.md    # Ce fichier
```

## Personnalisation des Modèles

Pour ajouter ou modifier les modèles disponibles, modifiez le dictionnaire `MODELS` dans `main.py`:

```python
MODELS = {
    "free": [
        {"id": "provider/model-name", "name": "Display Name", "provider": "Provider", "cost": "Free"}
    ],
    "paid": [
        {"id": "provider/model-name", "name": "Display Name", "provider": "Provider", "cost": "$X/million tokens"}
    ]
}
```

## Résolution des Problemes

### Erreur de connexion au proxy
- Vérifiez que le proxy principal est démarré sur le port 8080
- Vérifiez que l'API key est correcte

### Model non disponible
- Certains modèles peuvent ne pas être disponibles avec votre clé OpenRouter
- Vérifiez les logs du proxy pour plus de détails

### Erreur CORS
- L'interface utilise des requêtes fetch locales
- Assurez-vous que les deux serveurs sont sur le même domaine

## Extension Future

Pour ajouter plus de fonctionnalités:
- Comparaison de modèles côte à côte
- Historique des conversations
- Export des résultats
- Tests automatisés de sécurité PII
- Monitoring des coûts