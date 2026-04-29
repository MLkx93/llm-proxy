#!/usr/bin/env python3
"""Test the Web UI API endpoints."""
import sys
sys.path.insert(0, 'src')

import importlib
from fastapi.testclient import TestClient

mod = importlib.import_module('webui_api.main')
app = mod.app
client = TestClient(app)

# Test health
resp = client.get('/api/health')
print('Health:', resp.status_code, resp.json())

# Test providers
resp = client.get('/api/providers')
print('Providers:', resp.status_code, resp.json()['active_provider'])

# Test models
resp = client.get('/api/providers/openrouter/models')
data = resp.json()
print('Models:', resp.status_code, 'free:', len(data['free_models']), 'paid:', len(data['paid_models']))

# Test switch
resp = client.post('/api/providers/switch', json={'provider_id': 'openai'})
print('Switch:', resp.status_code, resp.json()['message'])

# Test dashboard
resp = client.get('/api/dashboard/health')
print('Dashboard health:', resp.status_code, resp.json())

resp = client.get('/api/dashboard/features')
print('Features:', resp.status_code, len(resp.json()))

resp = client.get('/api/dashboard/issues')
print('Issues:', resp.status_code, 'total:', resp.json()['summary']['total'])

resp = client.get('/api/dashboard/pipeline')
print('Pipeline:', resp.status_code, len(resp.json()))

resp = client.get('/api/dashboard/codebase-stats')
print('Codebase stats:', resp.status_code, resp.json())

resp = client.get('/api/dashboard/components')
print('Components:', resp.status_code, len(resp.json()))

resp = client.get('/api/dashboard/roadmap')
print('Roadmap:', resp.status_code, len(resp.json()))

print('\n✅ All API tests passed!')