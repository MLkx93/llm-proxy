# =============================================================================
# WebUI Main Application - LLM Proxy Testing Interface
# Modern Dark Theme with Glassmorphism Design
# =============================================================================

import time
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from config.settings import settings

app = FastAPI(title='LLM Proxy Testing Interface')

# Provider configurations
PROVIDERS = {
    'openrouter': {
        'id': 'openrouter',
        'name': 'OpenRouter',
        'description': 'Multi-provider gateway (OpenAI, Anthropic, Google, Meta)',
        'icon': '🌐',
        'base_url': 'https://openrouter.ai/api/v1',
        'models': {
            'free': [
                {'id': 'google/gemini-flash', 'name': 'Gemini Flash', 'provider': 'Google', 'cost': 'Free'},
                {'id': 'meta-llama/llama-3-8b-instruct', 'name': 'Llama 3 8B', 'provider': 'Meta', 'cost': 'Free'},
            ],
            'paid': [
                {'id': 'openai/gpt-4o', 'name': 'GPT-4o', 'provider': 'OpenAI', 'cost': '$5/million tokens'},
                {'id': 'openai/gpt-4-turbo', 'name': 'GPT-4 Turbo', 'provider': 'OpenAI', 'cost': '$10/million tokens'},
                {'id': 'openai/gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'provider': 'OpenAI', 'cost': '$0.50/million tokens'},
                {'id': 'google/gemini-pro', 'name': 'Gemini Pro', 'provider': 'Google', 'cost': '$3/million tokens'},
                {'id': 'meta-llama/llama-3-70b-instruct', 'name': 'Llama 3 70B', 'provider': 'Meta', 'cost': '$8/million tokens'},
                {'id': 'anthropic/claude-3-haiku', 'name': 'Claude 3 Haiku', 'provider': 'Anthropic', 'cost': '$0.25/million tokens'},
                {'id': 'anthropic/claude-3-sonnet', 'name': 'Claude 3 Sonnet', 'provider': 'Anthropic', 'cost': '$3/million tokens'},
                {'id': 'anthropic/claude-3-opus', 'name': 'Claude 3 Opus', 'provider': 'Anthropic', 'cost': '$15/million tokens'},
            ]
        }
    },
    'openai': {
        'id': 'openai',
        'name': 'OpenAI Direct',
        'description': 'Direct access to OpenAI models',
        'icon': '🟢',
        'base_url': 'https://api.openai.com/v1',
        'models': {
            'free': [],
            'paid': [
                {'id': 'gpt-4o', 'name': 'GPT-4o', 'provider': 'OpenAI', 'cost': '$5/million tokens'},
                {'id': 'gpt-4-turbo', 'name': 'GPT-4 Turbo', 'provider': 'OpenAI', 'cost': '$10/million tokens'},
                {'id': 'gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'provider': 'OpenAI', 'cost': '$0.50/million tokens'},
            ]
        }
    },
    'anthropic': {
        'id': 'anthropic',
        'name': 'Anthropic Direct',
        'description': 'Direct access to Anthropic Claude models',
        'icon': '🟣',
        'base_url': 'https://api.anthropic.com/v1',
        'models': {
            'free': [],
            'paid': [
                {'id': 'claude-3-haiku-20240307', 'name': 'Claude 3 Haiku', 'provider': 'Anthropic', 'cost': '$0.25/million tokens'},
                {'id': 'claude-3-sonnet-20240229', 'name': 'Claude 3 Sonnet', 'provider': 'Anthropic', 'cost': '$3/million tokens'},
                {'id': 'claude-3-opus-20240229', 'name': 'Claude 3 Opus', 'provider': 'Anthropic', 'cost': '$15/million tokens'},
            ]
        }
    },
    'litellm': {
        'id': 'litellm',
        'name': 'LiteLLM Proxy',
        'description': 'LiteLLM proxy server (self-hosted)',
        'icon': '🔀',
        'base_url': '',
        'models': {
            'free': [],
            'paid': [
                {'id': 'gpt-4o', 'name': 'GPT-4o (via LiteLLM)', 'provider': 'OpenAI', 'cost': 'Varies'},
                {'id': 'claude-3-sonnet', 'name': 'Claude 3 Sonnet (via LiteLLM)', 'provider': 'Anthropic', 'cost': 'Varies'},
            ]
        }
    }
}

# Runtime provider state (in-memory, persists until server restart)
_provider_state = {
    'active_provider': 'openrouter' if settings.use_openrouter else ('litellm' if settings.use_litellm else 'openrouter'),
    'api_keys': {
        'openrouter': settings.OPENROUTER_API_KEY,
        'openai': settings.OPENAI_API_KEY,
        'anthropic': settings.ANTHROPIC_API_KEY,
        'litellm': settings.LITELLM_API_KEY,
    },
    'litellm_base_url': settings.LITELLM_API_BASE,
}

# Model configurations (backward compat)
MODELS = PROVIDERS['openrouter']['models']

# Static files path
STATIC_PATH = Path(__file__).parent / 'static'
STATIC_PATH.mkdir(exist_ok=True)
app.mount('/static', StaticFiles(directory=str(STATIC_PATH)), name='static')


# =============================================================================
# Provider Configuration API Endpoints
# =============================================================================

@app.get('/api/providers')
async def get_providers():
    '''Get available providers and current configuration'''
    active = _provider_state['active_provider']
    result = []
    for pid, pconfig in PROVIDERS.items():
        has_key = bool(_provider_state['api_keys'].get(pid))
        result.append({
            'id': pid,
            'name': pconfig['name'],
            'description': pconfig['description'],
            'icon': pconfig['icon'],
            'active': pid == active,
            'configured': has_key or pid == 'litellm',
            'model_count': len(pconfig['models']['free']) + len(pconfig['models']['paid']),
        })
    return {'providers': result, 'active_provider': active}


@app.post('/api/providers/switch')
async def switch_provider(request: Request):
    '''Switch the active provider'''
    body = await request.json()
    provider_id = body.get('provider_id')
    if provider_id not in PROVIDERS:
        return JSONResponse(status_code=400, content={'error': f'Unknown provider: {provider_id}'})
    _provider_state['active_provider'] = provider_id
    return {
        'success': True,
        'active_provider': provider_id,
        'provider_name': PROVIDERS[provider_id]['name'],
        'message': f'Switched to {PROVIDERS[provider_id]["name"]}'
    }


@app.get('/api/providers/{provider_id}/models')
async def get_provider_models(provider_id: str):
    '''Get models for a specific provider'''
    if provider_id not in PROVIDERS:
        return JSONResponse(status_code=404, content={'error': f'Unknown provider: {provider_id}'})
    models = PROVIDERS[provider_id]['models']
    return {
        'provider_id': provider_id,
        'provider_name': PROVIDERS[provider_id]['name'],
        'free_models': models['free'],
        'paid_models': models['paid']
    }


@app.post('/api/providers/api-key')
async def set_provider_api_key(request: Request):
    '''Set or update an API key for a provider'''
    body = await request.json()
    provider_id = body.get('provider_id')
    api_key = body.get('api_key', '')
    if provider_id not in PROVIDERS:
        return JSONResponse(status_code=400, content={'error': f'Unknown provider: {provider_id}'})
    _provider_state['api_keys'][provider_id] = api_key
    return {
        'success': True,
        'provider_id': provider_id,
        'configured': bool(api_key),
        'message': f'API key {"updated" if api_key else "cleared"} for {PROVIDERS[provider_id]["name"]}'
    }


@app.get('/', response_class=HTMLResponse)
async def home():
    '''Main interface page with unified design system'''
    html = '''
<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>LLM Proxy - Model Testing Interface</title>
<link rel='stylesheet' href='/static/styles.css'>
<style>
/* Provider Selector Styles */
.provider-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-lg);
    margin-bottom: var(--space-lg);
}
.provider-bar-label {
    font-size: 0.875rem;
    color: var(--text-muted);
    font-weight: 500;
    white-space: nowrap;
}
.provider-select {
    flex: 1;
    padding: 10px 14px;
    border: 2px solid var(--border);
    border-radius: var(--radius-lg);
    font-size: 1rem;
    background: var(--background-light);
    color: var(--text);
    cursor: pointer;
    transition: all var(--transition);
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' fill='%2394a3b8' viewBox='0 0 16 16'%3E%3Cpath d='M8 11L3 6h10z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 12px center;
    padding-right: 36px;
}
.provider-select:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}
.provider-select:hover {
    border-color: var(--primary-light);
}
.provider-status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 6px;
}
.provider-status-dot.active { background: var(--success); box-shadow: 0 0 8px var(--success); }
.provider-status-dot.configured { background: var(--warning); }
.provider-status-dot.unconfigured { background: var(--text-dim); }
.provider-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: var(--text-muted);
    white-space: nowrap;
}
.provider-switch-btn {
    padding: 8px 16px;
    border: 2px solid var(--accent);
    border-radius: var(--radius-lg);
    background: transparent;
    color: var(--accent);
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all var(--transition);
    white-space: nowrap;
}
.provider-switch-btn:hover {
    background: var(--accent);
    color: white;
    box-shadow: 0 4px 15px rgba(6, 182, 212, 0.4);
}
.provider-switch-btn.active-provider {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
    color: white;
    border-color: transparent;
    cursor: default;
    box-shadow: 0 4px 15px rgba(6, 182, 212, 0.3);
}
.provider-toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 16px 24px;
    background: var(--surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    border-left: 4px solid var(--success);
    z-index: 1000;
    animation: slideIn var(--transition);
    display: none;
}
.provider-toast.show { display: block; }
.provider-toast .toast-text { font-weight: 600; font-size: 0.95rem; }
.provider-toast .toast-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
</style>
</head>
<body>
<div class='header'>
<h1>🤖 LLM Proxy Model Testing</h1>
<p>Securely test and compare AI models</p>
<div class='nav-links'>
<a href='/' class='nav-link active'>🔬 Model Testing</a>
<a href='/dashboard' class='nav-link'>📊 Dashboard</a>
<a href='/state' class='nav-link'>📋 State Report</a>
</div>
</div>

<div class='container'>

<!-- Provider Selection Bar -->
<div class='provider-bar'>
<span class='provider-bar-label'>🔌 Provider:</span>
<select id='provider_select' class='provider-select' onchange='onProviderSelect()'>
</select>
<div class='provider-info' id='provider_info'>
<span class='provider-status-dot active' id='provider_dot'></span>
<span id='provider_desc'>Loading...</span>
</div>
<button class='provider-switch-btn' id='switch_provider_btn' onclick='switchProvider()'>Switch</button>
</div>

<!-- Model Selection Card -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>🎯 Select a Model</h2>
</div>

<div class='tabs'>
<button class='tab active' onclick='showTab("free")'>🆓 Free Models</button>
<button class='tab' onclick='showTab("paid")'>💰 Paid Models</button>
</div>

<div id='free-models' class='tab-content active'>
<div class='model-grid' id='free-model-grid'>
<div style='color: var(--text-muted); text-align: center; padding: 24px;'>Loading models...</div>
</div>
</div>

<div id='paid-models' class='tab-content'>
<div class='model-grid' id='paid-model-grid'>
<div style='color: var(--text-muted); text-align: center; padding: 24px;'>Loading models...</div>
</div>
</div>
</div>

<!-- Configuration Card -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>⚙️ Test Configuration</h2>
</div>

<div class='form-group'>
<label class='form-label'>🔑 Proxy API Key</label>
<input type='text' id='api_key' class='form-input' value='dev-local-key-1234' placeholder='Enter your proxy API key'>
</div>

<div class='form-group'>
<label class='form-label'>🎯 Selected Model</label>
<input type='text' id='model_id' class='form-input' readonly placeholder='Click a model above to select it'>
</div>

<div class='form-group'>
<label class='form-label'>💬 Your Message</label>
<textarea id='message' class='form-textarea' placeholder='Enter your test message here...'>Hello! Can you tell me a short joke?</textarea>
</div>

<button class='btn' onclick='testModel()' id='submit_btn'>🚀 Test Model</button>
</div>

<!-- Response Card -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>📊 Response</h2>
</div>
<div id='response' class='response-box'>Response will appear here...</div>
</div>
</div>

<!-- Provider Switch Toast -->
<div class='provider-toast' id='provider_toast'>
<div class='toast-text' id='toast_text'>Provider switched!</div>
<div class='toast-sub' id='toast_sub'></div>
</div>

<script>
let selectedModel = null;
let currentProvider = null;
let pendingProvider = null;

// ---- Provider Management ----

async function loadProviders() {
    try {
        const res = await fetch('/api/providers');
        const data = await res.json();
        currentProvider = data.active_provider;

        const select = document.getElementById('provider_select');
        select.innerHTML = '';
        data.providers.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.icon + ' ' + p.name + (p.active ? ' ✓' : '') + (!p.configured ? ' (not configured)' : '');
            opt.selected = p.active;
            select.appendChild(opt);
        });

        updateProviderInfo(data.providers.find(p => p.id === currentProvider));
        await loadProviderModels(currentProvider);
    } catch (err) {
        console.error('Failed to load providers:', err);
    }
}

function updateProviderInfo(provider) {
    if (!provider) return;
    const dot = document.getElementById('provider_dot');
    const desc = document.getElementById('provider_desc');
    const btn = document.getElementById('switch_provider_btn');

    dot.className = 'provider-status-dot ' + (provider.active ? 'active' : (provider.configured ? 'configured' : 'unconfigured'));
    desc.textContent = provider.description;
    pendingProvider = document.getElementById('provider_select').value;

    if (provider.active) {
        btn.textContent = '✓ Active';
        btn.classList.add('active-provider');
    } else {
        btn.textContent = 'Switch';
        btn.classList.remove('active-provider');
    }
}

function onProviderSelect() {
    const select = document.getElementById('provider_select');
    const btn = document.getElementById('switch_provider_btn');
    pendingProvider = select.value;

    if (pendingProvider === currentProvider) {
        btn.textContent = '✓ Active';
        btn.classList.add('active-provider');
    } else {
        btn.textContent = 'Switch →';
        btn.classList.remove('active-provider');
    }

    // Update description
    const selected = select.options[select.selectedIndex];
    const desc = document.getElementById('provider_desc');
    const dot = document.getElementById('provider_dot');
    // Find if configured
    const hasKey = !selected.textContent.includes('not configured');
    dot.className = 'provider-status-dot ' + (pendingProvider === currentProvider ? 'active' : (hasKey ? 'configured' : 'unconfigured'));
}

async function switchProvider() {
    const select = document.getElementById('provider_select');
    const newProvider = select.value;

    if (newProvider === currentProvider) return;

    try {
        const res = await fetch('/api/providers/switch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({provider_id: newProvider})
        });
        const data = await res.json();

        if (data.success) {
            currentProvider = newProvider;
            await loadProviders();
            showToast('Provider switched!', data.message);
        } else {
            showToast('Error', data.error || 'Failed to switch provider', true);
        }
    } catch (err) {
        showToast('Error', err.message, true);
    }
}

async function loadProviderModels(providerId) {
    try {
        const res = await fetch('/api/providers/' + providerId + '/models');
        const data = await res.json();

        const freeGrid = document.getElementById('free-model-grid');
        const paidGrid = document.getElementById('paid-model-grid');

        // Free models
        if (data.free_models.length === 0) {
            freeGrid.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 24px; grid-column: 1 / -1;">No free models available for this provider</div>';
        } else {
            freeGrid.innerHTML = '';
            data.free_models.forEach(model => {
                freeGrid.innerHTML += `
                    <button class='model-btn free' onclick='selectModel("${model.id}", this)'>
                        <div class='model-name'>${model.name}</div>
                        <div class='model-info'>${model.provider}</div>
                        <span class='model-cost'>Free</span>
                    </button>`;
            });
        }

        // Paid models
        if (data.paid_models.length === 0) {
            paidGrid.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 24px; grid-column: 1 / -1;">No paid models available for this provider</div>';
        } else {
            paidGrid.innerHTML = '';
            data.paid_models.forEach(model => {
                paidGrid.innerHTML += `
                    <button class='model-btn' onclick='selectModel("${model.id}", this)'>
                        <div class='model-name'>${model.name}</div>
                        <div class='model-info'>${model.provider}</div>
                        <span class='model-cost'>${model.cost}</span>
                    </button>`;
            });
        }

        // Clear selected model when switching providers
        selectedModel = null;
        document.getElementById('model_id').value = '';
        document.querySelectorAll('.model-btn').forEach(b => b.classList.remove('selected'));

    } catch (err) {
        console.error('Failed to load models:', err);
    }
}

function showToast(title, message, isError) {
    const toast = document.getElementById('provider_toast');
    const text = document.getElementById('toast_text');
    const sub = document.getElementById('toast_sub');
    text.textContent = title;
    sub.textContent = message;
    toast.style.borderLeftColor = isError ? 'var(--error)' : 'var(--success)';
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
}

// ---- Tab & Model Selection ----

function showTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById(tab + '-models').classList.add('active');
}

function selectModel(modelId, btn) {
    document.querySelectorAll('.model-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedModel = modelId;
    document.getElementById('model_id').value = modelId;
}

// ---- Test Model ----

async function testModel() {
    const modelId = document.getElementById('model_id').value;
    const message = document.getElementById('message').value;
    const apiKey = document.getElementById('api_key').value;
    const responseDiv = document.getElementById('response');
    const submitBtn = document.getElementById('submit_btn');

    if (!modelId) {
        responseDiv.innerHTML = '<div class="status-badge error">⚠️ Please select a model first!</div>';
        return;
    }

    if (!message.trim()) {
        responseDiv.innerHTML = '<div class="status-badge error">⚠️ Please enter a message!</div>';
        return;
    }

    responseDiv.innerHTML = '<div class="loading"></div>';
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Testing...';

    const startTime = Date.now();

    try {
        const response = await fetch('/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`,
                'X-Provider': currentProvider || 'openrouter'
            },
            body: JSON.stringify({
                model: modelId,
                messages: [{ role: 'user', content: message }],
                max_tokens: 500,
                temperature: 0.7
            })
        });

        const endTime = Date.now();
        const duration = (endTime - startTime) / 1000;

        const data = await response.json();

        if (response.ok) {
            const content = data.choices?.[0]?.message?.content || 'No response content';
            const model = data.model || modelId;
            const usage = data.usage || {};

            responseDiv.innerHTML = `
                <div class="status-badge success">✅ Success! (${duration.toFixed(2)}s)</div>
                <div class="metric-card" style="margin: 16px 0; text-align: left;">
                    <strong>Provider:</strong> ${currentProvider}<br>
                    <strong>Model:</strong> ${model}<br>
                    <strong>Prompt tokens:</strong> ${usage.prompt_tokens || 'N/A'}<br>
                    <strong>Completion tokens:</strong> ${usage.completion_tokens || 'N/A'}<br>
                    <strong>Total tokens:</strong> ${usage.total_tokens || 'N/A'}
                </div>
                <strong>Response:</strong>
                <div class="response-box">${content}</div>
            `;
        } else {
            const error = data.error?.message || data.error?.code || JSON.stringify(data);
            responseDiv.innerHTML = `
                <div class="status-badge error">❌ Error: ${data.error?.code || 'Unknown Error'}</div>
                <div class="response-box">${error}</div>
            `;
        }
    } catch (error) {
        responseDiv.innerHTML = `
            <div class="status-badge error">❌ Network Error</div>
            <div class="response-box">${error.message}</div>
        `;
    }

    submitBtn.disabled = false;
    submitBtn.textContent = '🚀 Test Model';
}

// ---- Initialize ----
loadProviders();
</script>
</body>
</html>
'''
    return html


@app.post('/v1/chat/completions')
async def proxy_chat(request: Request):
    '''Proxy the request to the main LLM proxy, using the selected provider'''
    body = await request.json()
    api_key = request.headers.get('authorization', '').replace('Bearer ', '')
    provider_id = request.headers.get('x-provider', _provider_state['active_provider'])

    # Determine the upstream URL and headers based on the active provider
    provider_key = _provider_state['api_keys'].get(provider_id, '')

    if provider_id == 'openrouter' and provider_key:
        # Use OpenRouter directly
        upstream_url = f"{settings.OPENROUTER_BASE_URL}/chat/completions"
        upstream_headers = {
            'Authorization': f'Bearer {provider_key}',
            'Content-Type': 'application/json',
        }
    elif provider_id == 'openai' and provider_key:
        # Use OpenAI directly
        upstream_url = 'https://api.openai.com/v1/chat/completions'
        upstream_headers = {
            'Authorization': f'Bearer {provider_key}',
            'Content-Type': 'application/json',
        }
    elif provider_id == 'litellm' and _provider_state['litellm_base_url']:
        # Use LiteLLM proxy
        base = _provider_state['litellm_base_url'].rstrip('/')
        upstream_url = f"{base}/v1/chat/completions"
        upstream_headers = {
            'Content-Type': 'application/json',
            'x-api-key': provider_key,
        }
    else:
        # Fallback: forward to main proxy on port 8080
        upstream_url = 'http://localhost:8080/v1/chat/completions'
        upstream_headers = {'Authorization': f'Bearer {api_key}'}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                upstream_url,
                json=body,
                headers=upstream_headers,
            )
            return response.json()
    except Exception as e:
        return {'error': {'code': 'PROXY_ERROR', 'message': str(e)}}


# =============================================================================
# Dashboard API Endpoints
# =============================================================================

@app.get('/dashboard/api/health')
async def dashboard_health():
    '''Get system health status for dashboard'''
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health_resp = await client.get('http://localhost:8080/health')
            ready_resp = await client.get('http://localhost:8080/ready')

            return {
                'proxy_status': 'online' if health_resp.status_code == 200 else 'offline',
                'nexus_status': 'configured' if ready_resp.status_code == 200 else 'not_configured',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            }
    except Exception:
        return {
            'proxy_status': 'offline',
            'nexus_status': 'unknown',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
        }


@app.get('/dashboard/api/metrics')
async def dashboard_metrics():
    '''Get anonymized usage metrics from audit logs'''
    import json
    from pathlib import Path

    metrics = {
        'total_requests': 0,
        'allowed_requests': 0,
        'blocked_requests': 0,
        'error_requests': 0,
        'block_reasons': {},
        'recent_activity': []
    }

    # Read audit logs
    log_path = Path('logs/audit.jsonl')
    if log_path.exists():
        try:
            lines = log_path.read_text().strip().split('\n')
            recent_lines = lines[-100:] if len(lines) > 100 else lines

            for line in recent_lines:
                try:
                    entry = json.loads(line)
                    metrics['total_requests'] += 1
                    action = entry.get('action', 'UNKNOWN')

                    if action == 'ALLOWED':
                        metrics['allowed_requests'] += 1
                    elif action == 'BLOCKED':
                        metrics['blocked_requests'] += 1
                        block_code = entry.get('block_code', 'UNKNOWN')
                        metrics['block_reasons'][block_code] = metrics['block_reasons'].get(block_code, 0) + 1
                    elif action == 'ERROR':
                        metrics['error_requests'] += 1

                    if len(metrics['recent_activity']) < 10:
                        metrics['recent_activity'].append({
                            'timestamp': entry.get('timestamp', ''),
                            'action': action,
                            'block_code': entry.get('block_code'),
                            'model': entry.get('model', 'unknown')
                        })
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass

    return metrics


@app.get('/dashboard/api/features')
async def dashboard_features():
    '''Get current features and capabilities'''
    return {
        'security_features': [
            {
                'name': 'PII Detection',
                'description': 'Detects and blocks personal information like emails, phone numbers, and credit card numbers',
                'status': 'active',
                'category': 'input',
                'tool': 'Microsoft Presidio + spaCy NER'
            },
            {
                'name': 'Credential Detection',
                'description': 'Identifies API keys, passwords, and secrets in prompts to prevent data leakage',
                'status': 'active',
                'category': 'input',
                'tool': 'Custom Regex Patterns'
            },
            {
                'name': 'Prompt Injection Protection',
                'description': 'Blocks attempts to manipulate the AI with malicious instructions',
                'status': 'active',
                'category': 'input',
                'tool': 'Pattern Matching'
            },
            {
                'name': 'Smart Redaction',
                'description': 'Blocks latest message with PII, redacts older messages to preserve conversation flow',
                'status': 'active',
                'category': 'input',
                'tool': 'Context-Aware Strategy'
            },
            {
                'name': 'Nexus Dependency Validation',
                'description': 'Verifies code dependencies against approved packages in Nexus repository',
                'status': 'active',
                'category': 'output',
                'tool': 'Sonatype Nexus REST API'
            },
            {
                'name': 'Vulnerability Scanning',
                'description': 'Scans packages against OSV and NVD/CVE databases for known vulnerabilities',
                'status': 'configurable',
                'category': 'output',
                'tool': 'OSV + NVD APIs'
            },
            {
                'name': 'Version Validation',
                'description': 'Checks specific package versions against security advisories with semver matching',
                'status': 'configurable',
                'category': 'output',
                'tool': 'SQLite Advisory DB'
            },
            {
                'name': 'Dependency Tree Analysis',
                'description': 'Resolves transitive dependencies and detects version conflicts across ecosystems',
                'status': 'configurable',
                'category': 'output',
                'tool': 'pip/npm/maven resolvers'
            },
            {
                'name': 'Sandbox Execution',
                'description': 'Runs code in isolated Docker containers with behavior monitoring and risk scoring',
                'status': 'configurable',
                'category': 'output',
                'tool': 'Docker + 18 detection rules'
            },
            {
                'name': 'Risk Scoring Engine',
                'description': 'Weighted multi-factor risk assessment combining sandbox, violations, and behavior analysis',
                'status': 'configurable',
                'category': 'output',
                'tool': '5-factor weighted scoring'
            },
            {
                'name': 'Rate Limiting',
                'description': 'Prevents abuse with token bucket rate limiting per application',
                'status': 'active',
                'category': 'resilience',
                'tool': 'In-memory Token Bucket'
            },
            {
                'name': 'Circuit Breaker',
                'description': 'Automatically handles Nexus and vulnerability service failures gracefully',
                'status': 'active',
                'category': 'resilience',
                'tool': '3-failure threshold, 30s recovery'
            }
        ],
        'supported_languages': ['Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Ruby', 'Shell/Bash'],
        'supported_providers': ['OpenAI', 'Anthropic', 'Google', 'Meta', 'LiteLLM', 'OpenRouter'],
        'codebase_stats': {
            'source_files': 22,
            'total_loc': 4800,
            'test_files': 14,
            'test_loc': 1200,
            'security_phases': 5,
            'detection_rules': 18,
            'rule_categories': 9
        }
    }


@app.get('/dashboard/api/updates')
async def dashboard_updates():
    '''Get recent updates and changelog'''
    return {
        'version': '1.0.0',
        'last_updated': 'April 2026',
        'updates': [
            {
                'version': '1.0.0',
                'date': 'April 2026',
                'type': 'major',
                'changes': [
                    'Initial production-ready release',
                    '5-phase output security pipeline',
                    'Vulnerability scanning (OSV + NVD)',
                    'Version-specific validation with semver matching',
                    'Dependency tree analysis with conflict detection',
                    'Docker sandbox with 18 detection rules',
                    'Weighted risk scoring engine',
                    'Smart redaction strategy for Anthropic endpoint',
                    '14 test files with comprehensive coverage'
                ]
            },
            {
                'version': '0.9.0',
                'date': 'March 2026',
                'type': 'feature',
                'changes': [
                    'Added Anthropic Gateway support',
                    'OpenRouter integration',
                    'Enhanced audit logging'
                ]
            },
            {
                'version': '0.8.0',
                'date': 'March 2026',
                'type': 'feature',
                'changes': [
                    'Output Security Engine with Nexus validation',
                    'Circuit breaker implementation',
                    'Dependency extraction for 7 languages'
                ]
            },
            {
                'version': '0.7.0',
                'date': 'March 2026',
                'type': 'feature',
                'changes': [
                    'Input Policy Engine',
                    'PII detection with Presidio',
                    'Credential and injection detection'
                ]
            }
        ]
    }


@app.get('/dashboard/api/issues')
async def dashboard_issues():
    '''Get known issues and gaps from state report'''
    return {
        'critical': [
            {
                'id': 1,
                'title': 'validate_package_version() signature mismatch',
                'file': 'engine.py:271 vs version_validator.py:103',
                'impact': 'Version validation phase will crash at runtime'
            },
            {
                'id': 2,
                'title': 'No Pydantic validation on /v1/messages',
                'file': 'main.py:455',
                'impact': 'Server crash on malformed input'
            },
            {
                'id': 3,
                'title': 'analyze_package_health() return type mismatch',
                'file': 'engine.py:314 vs dependency_resolver.py:518',
                'impact': 'Dependency scan phase will crash at runtime'
            }
        ],
        'high': [
            {
                'id': 4,
                'title': 'main.py is 598 lines — monolithic',
                'file': 'main.py',
                'impact': 'Hard to maintain, test, and extend'
            },
            {
                'id': 5,
                'title': 'Streaming not supported',
                'file': 'main.py:92-94',
                'impact': 'Major limitation for real-world usage'
            },
            {
                'id': 6,
                'title': 'In-memory rate limiter',
                'file': 'rate_limiter.py',
                'impact': 'Cannot scale horizontally'
            },
            {
                'id': 7,
                'title': 'Inconsistent auth between endpoints',
                'file': 'main.py:75 vs main.py:433-445',
                'impact': 'Security inconsistency'
            },
            {
                'id': 8,
                'title': 'requirements.txt incomplete',
                'file': 'requirements.txt',
                'impact': 'Installation failures'
            }
        ],
        'medium': [
            {'id': 9, 'title': 'Model name mapping hardcoded'},
            {'id': 10, 'title': 'No JS/TS/Ruby stdlib filtering'},
            {'id': 11, 'title': 'Vulnerability cache is in-memory only'},
            {'id': 12, 'title': 'Sandbox uses sync subprocess.run'},
            {'id': 13, 'title': 'No request body size limit'},
            {'id': 14, 'title': 'No CORS configuration'},
            {'id': 15, 'title': '_openai_to_anthropic ignores multiple choices'}
        ],
        'low': [
            {'id': 16, 'title': '/ready doesn\'t check Nexus reachability'},
            {'id': 17, 'title': 'No OpenTelemetry tracing'},
            {'id': 18, 'title': 'No graceful shutdown handler'},
            {'id': 19, 'title': 'Audit log is file-based only'},
            {'id': 20, 'title': 'No RBAC/user management'}
        ],
        'summary': {
            'critical': 3,
            'high': 5,
            'medium': 7,
            'low': 5,
            'total': 20
        }
    }


@app.get('/dashboard', response_class=HTMLResponse)
async def dashboard():
    '''Main dashboard page with unified design system'''
    html = '''
<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>LLM Proxy - Project Status Dashboard</title>
<link rel='stylesheet' href='/static/styles.css'>
<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
<style>
.issue-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; margin-right: 6px; }
.issue-badge.critical { background: rgba(239,68,68,0.2); color: #fca5a5; border: 1px solid rgba(239,68,68,0.3); }
.issue-badge.high { background: rgba(245,158,11,0.2); color: #fcd34d; border: 1px solid rgba(245,158,11,0.3); }
.issue-badge.medium { background: rgba(251,146,60,0.2); color: #fdba74; border: 1px solid rgba(251,146,60,0.3); }
.issue-badge.low { background: rgba(59,130,246,0.2); color: #93c5fd; border: 1px solid rgba(59,130,246,0.3); }
.issue-item { padding: 10px 14px; border-left: 3px solid; margin-bottom: 8px; border-radius: 0 8px 8px 0; background: rgba(255,255,255,0.03); }
.issue-item.critical { border-left-color: #ef4444; }
.issue-item.high { border-left-color: #f59e0b; }
.issue-item.medium { border-left-color: #fb923c; }
.issue-item.low { border-left-color: #3b82f6; }
.issue-title { font-weight: 600; font-size: 0.9rem; margin-bottom: 2px; }
.issue-file { font-size: 0.75rem; color: var(--text-muted); font-family: monospace; }
.pipeline-phase { display: flex; align-items: center; padding: 12px 16px; border-radius: 8px; margin-bottom: 6px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); }
.pipeline-phase .phase-num { width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; margin-right: 12px; flex-shrink: 0; }
.pipeline-phase .phase-info { flex: 1; }
.pipeline-phase .phase-name { font-weight: 600; font-size: 0.95rem; }
.pipeline-phase .phase-desc { font-size: 0.8rem; color: var(--text-muted); }
.pipeline-phase .phase-status { font-size: 0.75rem; padding: 2px 10px; border-radius: 12px; }
.phase-active { background: rgba(16,185,129,0.2); color: #6ee7b7; }
.phase-configurable { background: rgba(245,158,11,0.2); color: #fcd34d; }
.phase-0 .phase-num { background: rgba(16,185,129,0.2); color: #6ee7b7; }
.phase-1 .phase-num { background: rgba(245,158,11,0.2); color: #fcd34d; }
.phase-2 .phase-num { background: rgba(245,158,11,0.2); color: #fcd34d; }
.phase-3 .phase-num { background: rgba(245,158,11,0.2); color: #fcd34d; }
.phase-4 .phase-num { background: rgba(245,158,11,0.2); color: #fcd34d; }
.stats-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.stat-pill { display: flex; align-items: center; gap: 6px; padding: 6px 14px; border-radius: 20px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); font-size: 0.85rem; }
.stat-pill .stat-num { font-weight: 700; }
</style>
</head>
<body>
<div class='header'>
<h1>🛡️ LLM Security Proxy</h1>
<p>Project Status & Security Overview Dashboard</p>
<div class='nav-links'>
<a href='/' class='nav-link'>🔬 Model Testing</a>
<a href='/dashboard' class='nav-link active'>📊 Dashboard</a>
<a href='/state' class='nav-link'>📋 State Report</a>
</div>
</div>

<div class='container'>
<!-- System Status -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>📡 System Status</h2>
</div>
<div class='status-grid'>
<div class='status-card' id='proxy-status'>
<div class='status-icon'>🌐</div>
<div class='status-label'>Proxy Server</div>
<div class='status-value'>Loading...</div>
</div>
<div class='status-card' id='nexus-status'>
<div class='status-icon'>📦</div>
<div class='status-label'>Nexus Repository</div>
<div class='status-value'>Loading...</div>
</div>
<div class='status-card'>
<div class='status-icon'>📁</div>
<div class='status-label'>Source Files</div>
<div class='status-value'>22</div>
</div>
<div class='status-card'>
<div class='status-icon'>🔒</div>
<div class='status-label'>Security Features</div>
<div class='status-value'>12</div>
</div>
</div>
</div>

<!-- Codebase Stats -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>📈 Codebase Overview</h2>
</div>
<div class='stats-row'>
<div class='stat-pill'><span>📄</span> <span class='stat-num'>~4,800</span> LOC (source)</div>
<div class='stat-pill'><span>🧪</span> <span class='stat-num'>~1,200</span> LOC (tests)</div>
<div class='stat-pill'><span>🔬</span> <span class='stat-num'>14</span> Test files</div>
<div class='stat-pill'><span>🛡️</span> <span class='stat-num'>5</span> Security phases</div>
<div class='stat-pill'><span>🌐</span> <span class='stat-num'>7</span> Languages supported</div>
<div class='stat-pill'><span>📋</span> <span class='stat-num'>18</span> Detection rules</div>
<div class='stat-pill'><span>🔌</span> <span class='stat-num'>2</span> API endpoints</div>
</div>
</div>

<!-- Output Security Pipeline -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>🔒 Output Security Pipeline</h2>
</div>
<p style='margin-bottom: 16px; color: var(--text-muted); font-size: 0.9rem;'>5-phase defense-in-depth pipeline. All phases fail-closed (block on error).</p>

<div class='pipeline-phase phase-0'>
<div class='phase-num'>0</div>
<div class='phase-info'>
<div class='phase-name'>Nexus Validation</div>
<div class='phase-desc'>Verify package exists in approved enterprise repository</div>
</div>
<span class='phase-status phase-active'>Active</span>
</div>
<div class='pipeline-phase phase-1'>
<div class='phase-num'>1</div>
<div class='phase-info'>
<div class='phase-name'>Vulnerability Scan</div>
<div class='phase-desc'>OSV + NVD/CVE scanning with CVSS scoring and caching</div>
</div>
<span class='phase-status phase-configurable'>Configurable</span>
</div>
<div class='pipeline-phase phase-2'>
<div class='phase-num'>2</div>
<div class='phase-info'>
<div class='phase-name'>Version Validation</div>
<div class='phase-desc'>Semver matching against SQLite advisory database</div>
</div>
<span class='phase-status phase-configurable'>Configurable</span>
</div>
<div class='pipeline-phase phase-3'>
<div class='phase-num'>3</div>
<div class='phase-info'>
<div class='phase-name'>Dependency Tree</div>
<div class='phase-desc'>Transitive dependency resolution + version conflict detection</div>
</div>
<span class='phase-status phase-configurable'>Configurable</span>
</div>
<div class='pipeline-phase phase-4'>
<div class='phase-num'>4</div>
<div class='phase-info'>
<div class='phase-name'>Sandbox + Risk Score</div>
<div class='phase-desc'>Docker execution, 18 detection rules, weighted risk assessment</div>
</div>
<span class='phase-status phase-configurable'>Configurable</span>
</div>
</div>

<!-- Security Journey -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>🔄 Request Security Journey</h2>
</div>
<p style='margin-bottom: 20px; color: var(--text-muted);'>How your request is protected through our security pipeline</p>
<div class='journey-container'>
<div class='journey-flow'>
<div class='journey-step input'>
<div class='journey-step-icon'>📨</div>
<div class='journey-step-title'>Request</div>
</div>
<div class='journey-arrow'>→</div>
<div class='journey-step input'>
<div class='journey-step-icon'>🔑</div>
<div class='journey-step-title'>Auth</div>
</div>
<div class='journey-arrow'>→</div>
<div class='journey-step input'>
<div class='journey-step-icon'>⚡</div>
<div class='journey-step-title'>Rate Limit</div>
</div>
<div class='journey-arrow'>→</div>
<div class='journey-step input'>
<div class='journey-step-icon'>🔍</div>
<div class='journey-step-title'>Input Scan</div>
</div>
<div class='journey-arrow'>→</div>
<div class='journey-step process'>
<div class='journey-step-icon'>🤖</div>
<div class='journey-step-title'>AI</div>
</div>
<div class='journey-arrow'>→</div>
<div class='journey-step output'>
<div class='journey-step-icon'>🔒</div>
<div class='journey-step-title'>Output</div>
</div>
<div class='journey-arrow'>→</div>
<div class='journey-step output'>
<div class='journey-step-icon'>✅</div>
<div class='journey-step-title'>Response</div>
</div>
</div>
</div>
</div>

<!-- Features Matrix -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>✨ Security Features</h2>
</div>
<div class='features-grid'>
<div class='feature-item input'>
<div class='feature-icon'>🛡️</div>
<div class='feature-info'>
<h4>PII Detection</h4>
<p>Blocks personal information — emails, phones, credit cards, SSNs, passports</p>
<span class='feature-badge'>Active · Presidio + spaCy</span>
</div>
</div>
<div class='feature-item input'>
<div class='feature-icon'>🔐</div>
<div class='feature-info'>
<h4>Credential Detection</h4>
<p>Prevents API keys and secrets from leaving your organization</p>
<span class='feature-badge'>Active · Regex Patterns</span>
</div>
</div>
<div class='feature-item input'>
<div class='feature-icon'>⚠️</div>
<div class='feature-info'>
<h4>Prompt Injection</h4>
<p>Blocks attempts to manipulate the AI with malicious instructions</p>
<span class='feature-badge'>Active · Pattern Matching</span>
</div>
</div>
<div class='feature-item input'>
<div class='feature-icon'>✏️</div>
<div class='feature-info'>
<h4>Smart Redaction</h4>
<p>Blocks latest message with PII, redacts older messages to preserve flow</p>
<span class='feature-badge'>Active · Context-Aware</span>
</div>
</div>
<div class='feature-item output'>
<div class='feature-icon'>📦</div>
<div class='feature-info'>
<h4>Nexus Validation</h4>
<p>Verifies code packages against approved Nexus repository</p>
<span class='feature-badge'>Active · Circuit Breaker</span>
</div>
</div>
<div class='feature-item output'>
<div class='feature-icon'>🦠</div>
<div class='feature-info'>
<h4>Vulnerability Scan</h4>
<p>OSV + NVD/CVE scanning with CVSS scoring and 1hr cache</p>
<span class='feature-badge'>Configurable · OSV + NVD</span>
</div>
</div>
<div class='feature-item output'>
<div class='feature-icon'>🏷️</div>
<div class='feature-info'>
<h4>Version Validation</h4>
<p>Checks specific versions against advisories with semver matching</p>
<span class='feature-badge'>Configurable · SQLite DB</span>
</div>
</div>
<div class='feature-item output'>
<div class='feature-icon'>🌳</div>
<div class='feature-info'>
<h4>Dependency Tree</h4>
<p>Transitive dependency resolution, conflict detection, upgrade recommendations</p>
<span class='feature-badge'>Configurable · pip/npm/maven</span>
</div>
</div>
<div class='feature-item output'>
<div class='feature-icon'>🐳</div>
<div class='feature-info'>
<h4>Sandbox Execution</h4>
<p>Docker isolation, 18 detection rules, behavior monitoring</p>
<span class='feature-badge'>Configurable · Docker</span>
</div>
</div>
<div class='feature-item output'>
<div class='feature-icon'>📊</div>
<div class='feature-info'>
<h4>Risk Scoring</h4>
<p>5-factor weighted assessment: sandbox, violations, status, behavior, complexity</p>
<span class='feature-badge'>Configurable · A-F Grade</span>
</div>
</div>
<div class='feature-item resilience'>
<div class='feature-icon'>🚀</div>
<div class='feature-info'>
<h4>Rate Limiting</h4>
<p>Prevents abuse with token bucket algorithm per application</p>
<span class='feature-badge'>Active · In-Memory</span>
</div>
</div>
<div class='feature-item resilience'>
<div class='feature-icon'>🔄</div>
<div class='feature-info'>
<h4>Circuit Breaker</h4>
<p>3-failure threshold, 30s recovery, fail-closed policy</p>
<span class='feature-badge'>Active · Nexus + Vuln</span>
</div>
</div>
</div>
</div>

<!-- Known Issues -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>🐛 Known Issues</h2>
</div>
<div class='stats-row' id='issue-stats'>
<div class='stat-pill'><span class='issue-badge critical'>🔴</span> <span class='stat-num' id='critical-count'>3</span> Critical</div>
<div class='stat-pill'><span class='issue-badge high'>🟡</span> <span class='stat-num' id='high-count'>5</span> High</div>
<div class='stat-pill'><span class='issue-badge medium'>🟠</span> <span class='stat-num' id='medium-count'>7</span> Medium</div>
<div class='stat-pill'><span class='issue-badge low'>🔵</span> <span class='stat-num' id='low-count'>5</span> Low</div>
</div>
<div id='issues-list'></div>
</div>

<!-- Usage Metrics -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>📊 Usage Metrics</h2>
</div>
<div class='metrics-grid'>
<div class='metric-card'>
<div class='metric-value' id='total-requests'>0</div>
<div class='metric-label'>Total Requests</div>
</div>
<div class='metric-card'>
<div class='metric-value' id='allowed-requests'>0</div>
<div class='metric-label'>Allowed</div>
</div>
<div class='metric-card'>
<div class='metric-value' id='blocked-requests'>0</div>
<div class='metric-label'>Blocked</div>
</div>
<div class='metric-card'>
<div class='metric-value' id='block-rate'>0%</div>
<div class='metric-label'>Block Rate</div>
</div>
</div>
<div class='chart-container'>
<canvas id='metricsChart' width='400' height='200'></canvas>
</div>
</div>

<!-- Supported Technologies -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>🛠️ Supported Technologies</h2>
</div>
<div class='features-grid'>
<div class='feature-item'>
<div class='feature-icon'>🐍</div>
<div class='feature-info'>
<h4>Languages Supported</h4>
<p>Python, JavaScript, TypeScript, Java, Go, Ruby, Shell/Bash</p>
</div>
</div>
<div class='feature-item'>
<div class='feature-icon'>☁️</div>
<div class='feature-info'>
<h4>LLM Providers</h4>
<p>OpenAI, Anthropic, Google, Meta, LiteLLM, OpenRouter</p>
</div>
</div>
<div class='feature-item'>
<div class='feature-icon'>🔧</div>
<div class='feature-info'>
<h4>Security Tools</h4>
<p>Microsoft Presidio, Sonatype Nexus, Docker Sandbox, OSV, NVD/CVE</p>
</div>
</div>
</div>
</div>

<!-- Recent Updates -->
<div class='card'>
<div class='card-header'>
<h2 class='card-title'>📝 Recent Updates</h2>
</div>
<div class='timeline'>
<div class='timeline-item'>
<div class='timeline-header'>
<span class='timeline-version'>v1.0.0</span>
<span class='timeline-date'>April 2026</span>
</div>
<ul class='timeline-changes'>
<li>5-phase output security pipeline</li>
<li>Vulnerability scanning (OSV + NVD)</li>
<li>Version validation with semver matching</li>
<li>Dependency tree analysis + conflict detection</li>
<li>Docker sandbox with 18 detection rules</li>
<li>Weighted risk scoring engine (A-F grading)</li>
<li>Smart redaction for Anthropic endpoint</li>
</ul>
</div>
<div class='timeline-item'>
<div class='timeline-header'>
<span class='timeline-version'>v0.9.0</span>
<span class='timeline-date'>March 2026</span>
</div>
<ul class='timeline-changes'>
<li>Anthropic Gateway support</li>
<li>OpenRouter integration</li>
<li>Enhanced audit logging</li>
</ul>
</div>
<div class='timeline-item'>
<div class='timeline-header'>
<span class='timeline-version'>v0.8.0</span>
<span class='timeline-date'>March 2026</span>
</div>
<ul class='timeline-changes'>
<li>Output Security Engine with Nexus validation</li>
<li>Circuit breaker implementation</li>
<li>Dependency extraction for 7 languages</li>
</ul>
</div>
</div>
</div>
</div>

<script>
async function loadDashboardData() {
    try {
        // Load health
        const healthRes = await fetch('/dashboard/api/health');
        const health = await healthRes.json();

        const proxyCard = document.getElementById('proxy-status');
        const nexusCard = document.getElementById('nexus-status');

        if (health.proxy_status === 'online') {
            proxyCard.classList.add('online');
            proxyCard.querySelector('.status-value').textContent = 'Online ✅';
        } else {
            proxyCard.classList.add('offline');
            proxyCard.querySelector('.status-value').textContent = 'Offline ❌';
        }

        if (health.nexus_status === 'configured') {
            nexusCard.classList.add('online');
            nexusCard.querySelector('.status-value').textContent = 'Configured ✅';
        } else {
            nexusCard.classList.add('warning');
            nexusCard.querySelector('.status-value').textContent = 'Not Configured ⚠️';
        }

        // Load metrics
        const metricsRes = await fetch('/dashboard/api/metrics');
        const metrics = await metricsRes.json();

        document.getElementById('total-requests').textContent = metrics.total_requests;
        document.getElementById('allowed-requests').textContent = metrics.allowed_requests;
        document.getElementById('blocked-requests').textContent = metrics.blocked_requests;

        const blockRate = metrics.total_requests > 0
            ? ((metrics.blocked_requests / metrics.total_requests) * 100).toFixed(1) + '%'
            : '0%';
        document.getElementById('block-rate').textContent = blockRate;

        const ctx = document.getElementById('metricsChart').getContext('2d');
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Allowed', 'Blocked', 'Errors'],
                datasets: [{
                    data: [metrics.allowed_requests, metrics.blocked_requests, metrics.error_requests],
                    backgroundColor: ['#10b981', '#ef4444', '#f59e0b']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    title: { display: true, text: 'Request Outcomes' }
                }
            }
        });

        // Load issues
        const issuesRes = await fetch('/dashboard/api/issues');
        const issues = await issuesRes.json();

        document.getElementById('critical-count').textContent = issues.summary.critical;
        document.getElementById('high-count').textContent = issues.summary.high;
        document.getElementById('medium-count').textContent = issues.summary.medium;
        document.getElementById('low-count').textContent = issues.summary.low;

        const issuesList = document.getElementById('issues-list');
        let issuesHtml = '';

        // Critical issues
        issues.critical.forEach(issue => {
            issuesHtml += `<div class="issue-item critical">
                <span class="issue-badge critical">🔴 Critical #${issue.id}</span>
                <div class="issue-title">${issue.title}</div>
                <div class="issue-file">${issue.file}</div>
            </div>`;
        });

        // High issues
        issues.high.forEach(issue => {
            issuesHtml += `<div class="issue-item high">
                <span class="issue-badge high">🟡 High #${issue.id}</span>
                <div class="issue-title">${issue.title}</div>
                <div class="issue-file">${issue.file || ''}</div>
            </div>`;
        });

        // Medium issues
        issues.medium.forEach(issue => {
            issuesHtml += `<div class="issue-item medium">
                <span class="issue-badge medium">🟠 Medium #${issue.id}</span>
                <div class="issue-title">${issue.title}</div>
            </div>`;
        });

        // Low issues
        issues.low.forEach(issue => {
            issuesHtml += `<div class="issue-item low">
                <span class="issue-badge low">🔵 Low #${issue.id}</span>
                <div class="issue-title">${issue.title}</div>
            </div>`;
        });

        issuesList.innerHTML = issuesHtml;

    } catch (error) {
        console.error('Error loading dashboard data:', error);
    }
}

loadDashboardData();
</script>
</body>
</html>
'''
    return html


@app.get('/state', response_class=HTMLResponse)
async def state_report():
    '''State report page linking to the full markdown report'''
    html = '''
<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>LLM Proxy - State Report</title>
<link rel='stylesheet' href='/static/styles.css'>
<style>
.report-card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 24px; margin-bottom: 20px; }
.report-card h3 { margin-top: 0; color: var(--accent); }
.report-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.85rem; }
.report-table th { text-align: left; padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted); font-weight: 600; }
.report-table td { padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.report-table tr:hover { background: rgba(255,255,255,0.03); }
.severity-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.severity-dot.critical { background: #ef4444; }
.severity-dot.high { background: #f59e0b; }
.severity-dot.medium { background: #fb923c; }
.severity-dot.low { background: #3b82f6; }
.phase-flow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 16px 0; }
.phase-box { padding: 8px 16px; border-radius: 8px; font-size: 0.85rem; font-weight: 600; }
.phase-box.active { background: rgba(16,185,129,0.2); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.3); }
.phase-box.configurable { background: rgba(245,158,11,0.2); color: #fcd34d; border: 1px solid rgba(245,158,11,0.3); }
.phase-arrow { color: var(--text-muted); font-size: 1.2rem; }
.roadmap-phase { margin-bottom: 20px; }
.roadmap-phase h4 { margin-bottom: 8px; }
.roadmap-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 0.85rem; }
.roadmap-item .effort { color: var(--text-muted); margin-left: auto; font-style: italic; }
</style>
</head>
<body>
<div class='header'>
<h1>📋 State Report</h1>
<p>Comprehensive project assessment — April 2026</p>
<div class='nav-links'>
<a href='/' class='nav-link'>🔬 Model Testing</a>
<a href='/dashboard' class='nav-link'>📊 Dashboard</a>
<a href='/state' class='nav-link active'>📋 State Report</a>
</div>
</div>

<div class='container'>
<!-- Executive Summary -->
<div class='report-card'>
<h3>📌 Executive Summary</h3>
<p>The LLM Security Proxy is a <strong>centralized control layer</strong> enforcing security policies on all LLM interactions. Currently at <strong>v1.0.0 MVP</strong> with a functional 5-phase security pipeline.</p>
<div class='stats-row' style='margin-top: 16px;'>
<div class='stat-pill'>📄 ~4,800 LOC</div>
<div class='stat-pill'>🧪 14 test files</div>
<div class='stat-pill'>🛡️ 5 security phases</div>
<div class='stat-pill'>🌐 7 languages</div>
<div class='stat-pill'>🔌 2 API endpoints</div>
<div class='stat-pill'>📋 18 detection rules</div>
</div>
</div>

<!-- Security Pipeline -->
<div class='report-card'>
<h3>🔒 Output Security Pipeline</h3>
<p style='margin-bottom: 12px; color: var(--text-muted);'>All phases fail-closed (block on error)</p>
<div class='phase-flow'>
<div class='phase-box active'>Phase 0: Nexus</div>
<span class='phase-arrow'>→</span>
<div class='phase-box configurable'>Phase 1: Vuln Scan</div>
<span class='phase-arrow'>→</span>
<div class='phase-box configurable'>Phase 2: Version</div>
<span class='phase-arrow'>→</span>
<div class='phase-box configurable'>Phase 3: Dep Tree</div>
<span class='phase-arrow'>→</span>
<div class='phase-box configurable'>Phase 4: Sandbox</div>
<span class='phase-arrow'>→</span>
<div class='phase-box active'>✅ Allow</div>
</div>
</div>

<!-- Known Issues -->
<div class='report-card'>
<h3>🐛 Known Issues (20 total)</h3>
<table class='report-table'>
<thead>
<tr><th>#</th><th>Severity</th><th>Issue</th><th>Impact</th></tr>
</thead>
<tbody>
<tr><td>1</td><td><span class='severity-dot critical'></span>Critical</td><td>validate_package_version() signature mismatch</td><td>Version validation crashes at runtime</td></tr>
<tr><td>2</td><td><span class='severity-dot critical'></span>Critical</td><td>No Pydantic validation on /v1/messages</td><td>Server crash on malformed input</td></tr>
<tr><td>3</td><td><span class='severity-dot critical'></span>Critical</td><td>analyze_package_health() return type mismatch</td><td>Dependency scan crashes at runtime</td></tr>
<tr><td>4</td><td><span class='severity-dot high'></span>High</td><td>main.py is 598 lines — monolithic</td><td>Hard to maintain and extend</td></tr>
<tr><td>5</td><td><span class='severity-dot high'></span>High</td><td>Streaming not supported</td><td>Major real-world limitation</td></tr>
<tr><td>6</td><td><span class='severity-dot high'></span>High</td><td>In-memory rate limiter</td><td>Cannot scale horizontally</td></tr>
<tr><td>7</td><td><span class='severity-dot high'></span>High</td><td>Inconsistent auth between endpoints</td><td>Security inconsistency</td></tr>
<tr><td>8</td><td><span class='severity-dot high'></span>High</td><td>requirements.txt incomplete</td><td>Installation failures</td></tr>
<tr><td>9-15</td><td><span class='severity-dot medium'></span>Medium</td><td>7 issues (hardcoded models, missing stdlib filters, sync subprocess, etc.)</td><td>Various</td></tr>
<tr><td>16-20</td><td><span class='severity-dot low'></span>Low</td><td>5 issues (no tracing, no graceful shutdown, file-only audit, etc.)</td><td>Various</td></tr>
</tbody>
</table>
</div>

<!-- Component Inventory -->
<div class='report-card'>
<h3>📦 Component Inventory</h3>
<table class='report-table'>
<thead>
<tr><th>Layer</th><th>Module</th><th>Lines</th><th>Status</th></tr>
</thead>
<tbody>
<tr><td>Proxy</td><td>main.py</td><td>598</td><td>⚠️ Too large</td></tr>
<tr><td>Input</td><td>engine.py</td><td>267</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>engine.py (orchestrator)</td><td>577</td><td>🔴 Bug</td></tr>
<tr><td>Output</td><td>code_parser.py</td><td>172</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>nexus.py</td><td>155</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>vulnerability_scanner.py</td><td>390</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>version_validator.py</td><td>286</td><td>⚠️ Mismatch</td></tr>
<tr><td>Output</td><td>version_parser.py</td><td>320</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>security_advisory.py</td><td>335</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>dependency_tree.py</td><td>358</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>dependency_resolver.py</td><td>562</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>sandbox.py</td><td>431</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>detection_rules.py</td><td>459</td><td>✅ Good</td></tr>
<tr><td>Output</td><td>risk_scorer.py</td><td>487</td><td>✅ Good</td></tr>
</tbody>
</table>
</div>

<!-- Improvement Roadmap -->
<div class='report-card'>
<h3>🗺️ Improvement Roadmap</h3>

<div class='roadmap-phase'>
<h4><span class='severity-dot critical'></span> Phase 1: Critical Fixes (1-2 days)</h4>
<div class='roadmap-item'>Fix validate_package_version() signature mismatch <span class='effort'>1h</span></div>
<div class='roadmap-item'>Fix analyze_package_health() return type mismatch <span class='effort'>1h</span></div>
<div class='roadmap-item'>Add Pydantic model for /v1/messages endpoint <span class='effort'>2h</span></div>
<div class='roadmap-item'>Complete requirements.txt with all dependencies <span class='effort'>30m</span></div>
</div>

<div class='roadmap-phase'>
<h4><span class='severity-dot high'></span> Phase 2: Hardening (3-5 days)</h4>
<div class='roadmap-item'>Refactor main.py into route handlers + service layer <span class='effort'>2-3d</span></div>
<div class='roadmap-item'>Add streaming support with incremental output scanning <span class='effort'>2-3d</span></div>
<div class='roadmap-item'>Unify auth strategy between endpoints <span class='effort'>4h</span></div>
<div class='roadmap-item'>Add Redis-backed rate limiting <span class='effort'>1d</span></div>
<div class='roadmap-item'>Add request body size limits + CORS <span class='effort'>2h</span></div>
</div>

<div class='roadmap-phase'>
<h4><span class='severity-dot medium'></span> Phase 3: Operational Excellence (5-7 days)</h4>
<div class='roadmap-item'>Make model mapping configurable (YAML) <span class='effort'>4h</span></div>
<div class='roadmap-item'>Add JS/TS/Ruby stdlib filtering <span class='effort'>2h</span></div>
<div class='roadmap-item'>Add shared cache for vulnerability scanning <span class='effort'>1d</span></div>
<div class='roadmap-item'>Convert sandbox subprocess to async <span class='effort'>4h</span></div>
<div class='roadmap-item'>Add OpenTelemetry tracing + graceful shutdown <span class='effort'>2-3d</span></div>
</div>
</div>

<!-- Full Report Link -->
<div class='report-card' style='text-align: center;'>
<p style='font-size: 1.1rem;'>📄 The full detailed report is available at:</p>
<p style='font-family: monospace; color: var(--accent); font-size: 1.1rem;'><code>STATE_REPORT.md</code></p>
<p style='color: var(--text-muted); margin-top: 8px;'>Contains: Architecture diagrams, deep-dive per module, code quality metrics, design patterns, security posture assessment</p>
</div>
</div>
</body>
</html>
'''
    return html


if __name__ == '__main__':
    import uvicorn
    print('🚀 Starting LLM Proxy Web UI on http://localhost:8000')
    print('📝 Make sure the main proxy is running on port 8080')
    uvicorn.run(app, host='0.0.0.0', port=8000)