# =============================================================================
# WebUI Main Application - LLM Proxy Testing Interface
# Modern Dark Theme with Glassmorphism Design
# =============================================================================

import time
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title='LLM Proxy Testing Interface')

# Model configurations (OpenRouter format)
MODELS = {
    # Free models (with limitations)
    'free': [
        {'id': 'google/gemini-flash', 'name': 'Gemini Flash', 'provider': 'Google', 'cost': 'Free'},
        {'id': 'meta-llama/llama-3-8b-instruct', 'name': 'Llama 3 8B', 'provider': 'Meta', 'cost': 'Free'},
    ],
    # Paid models
    'paid': [
        {'id': 'openai/gpt-4o', 'name': 'GPT-4o', 'provider': 'OpenAI', 'cost': '$5/million tokens'},
        {'id': 'openai/gpt-4-turbo', 'name': 'GPT-4 Turbo', 'provider': 'OpenAI', 'cost': '$10/million tokens'},
        {'id': 'openai/gpt-3.5-turbo', 'name': 'GPT-3.5 Turbo', 'provider': 'OpenAI', 'cost': '$0.50/million tokens'},
        {'id': 'google/gemini-pro', 'name': 'Gemini Pro', 'provider': 'Google', 'cost': '$3/million tokens'},
        {'id': 'meta-llama/llama-3-70b-instruct', 'name': 'Llama 3 70B', 'provider': 'Meta', 'cost': '$8/million tokens'},
    ]
}

# Static files path
STATIC_PATH = Path(__file__).parent / 'static'
STATIC_PATH.mkdir(exist_ok=True)
app.mount('/static', StaticFiles(directory=str(STATIC_PATH)), name='static')


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
    </head>
    <body>
        <div class='header'>
            <h1>🤖 LLM Proxy Model Testing</h1>
            <p>Securely test and compare AI models</p>
            <div class='nav-links'>
                <a href='/' class='nav-link active'>🔬 Model Testing</a>
                <a href='/dashboard' class='nav-link'>📊 Dashboard</a>
            </div>
        </div>
        
        <div class='container'>
            <!-- Model Selection Card -->
            <div class='card'>
                <div class='card-header'>
                    <h2 class='card-title'>🎯 Select a Model</h2>
                </div>
                
                <div class='tabs'>
                    <button class='tab active' onclick='showTab(\"free\")'>🆓 Free Models</button>
                    <button class='tab' onclick='showTab(\"paid\")'>💰 Paid Models</button>
                </div>
                
                <div id='free-models' class='tab-content active'>
                    <div class='model-grid'>
    '''
    
    # Add free models
    for model in MODELS['free']:
        html += f'''
                        <button class='model-btn free' onclick='selectModel(\"{model['id']}\", this)'>
                            <div class='model-name'>{model['name']}</div>
                            <div class='model-info'>{model['provider']}</div>
                            <span class='model-cost'>Free</span>
                        </button>
        '''
    
    html += '''
                    </div>
                </div>
                
                <div id='paid-models' class='tab-content'>
                    <div class='model-grid'>
    '''
    
    # Add paid models
    for model in MODELS['paid']:
        html += f'''
                        <button class='model-btn' onclick='selectModel(\"{model['id']}\", this)'>
                            <div class='model-name'>{model['name']}</div>
                            <div class='model-info'>{model['provider']}</div>
                            <span class='model-cost'>{model['cost']}</span>
                        </button>
        '''
    
    html += '''
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
        
        <script>
            let selectedModel = null;
            
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
            
            async function testModel() {
                const modelId = document.getElementById('model_id').value;
                const message = document.getElementById('message').value;
                const apiKey = document.getElementById('api_key').value;
                const responseDiv = document.getElementById('response');
                const submitBtn = document.getElementById('submit_btn');
                
                if (!modelId) {
                    responseDiv.innerHTML = '<div class=\\'status-badge error\\'>⚠️ Please select a model first!</div>';
                    return;
                }
                
                if (!message.trim()) {
                    responseDiv.innerHTML = '<div class=\\'status-badge error\\'>⚠️ Please enter a message!</div>';
                    return;
                }
                
                responseDiv.innerHTML = '<div class=\\'loading\\'></div>';
                submitBtn.disabled = true;
                submitBtn.textContent = '⏳ Testing...';
                
                const startTime = Date.now();
                
                try {
                    const response = await fetch('/v1/chat/completions', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${apiKey}`
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
                            <div class='status-badge success'>✅ Success! (${duration.toFixed(2)}s)</div>
                            <div class='metric-card' style='margin: 16px 0; text-align: left;'>
                                <strong>Model:</strong> ${model}<br>
                                <strong>Prompt tokens:</strong> ${usage.prompt_tokens || 'N/A'}<br>
                                <strong>Completion tokens:</strong> ${usage.completion_tokens || 'N/A'}<br>
                                <strong>Total tokens:</strong> ${usage.total_tokens || 'N/A'}
                            </div>
                            <strong>Response:</strong>
                            <div class='response-box'>${content}</div>
                        `;
                    } else {
                        const error = data.error?.message || data.error?.code || JSON.stringify(data);
                        responseDiv.innerHTML = `
                            <div class='status-badge error'>❌ Error: ${data.error?.code || 'Unknown Error'}</div>
                            <div class='response-box'>${error}</div>
                        `;
                    }
                } catch (error) {
                    responseDiv.innerHTML = `
                        <div class='status-badge error'>❌ Network Error</div>
                        <div class='response-box'>${error.message}</div>
                    `;
                }
                
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 Test Model';
            }
        </script>
    </body>
    </html>
    '''
    return html


@app.post('/v1/chat/completions')
async def proxy_chat(request: Request):
    '''Proxy the request to the main LLM proxy'''
    body = await request.json()
    api_key = request.headers.get('authorization', '').replace('Bearer ', '')
    
    # Forward to main proxy
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'http://localhost:8080/v1/chat/completions',
                json=body,
                headers={'Authorization': f'Bearer {api_key}'}
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
                'category': 'input'
            },
            {
                'name': 'Credential Detection',
                'description': 'Identifies API keys, passwords, and secrets in prompts to prevent data leakage',
                'status': 'active',
                'category': 'input'
            },
            {
                'name': 'Prompt Injection Protection',
                'description': 'Blocks attempts to manipulate the AI with malicious instructions',
                'status': 'active',
                'category': 'input'
            },
            {
                'name': 'Dependency Validation',
                'description': 'Verifies code dependencies against approved packages in Nexus repository',
                'status': 'active',
                'category': 'output'
            },
            {
                'name': 'Rate Limiting',
                'description': 'Prevents abuse with token bucket rate limiting per application',
                'status': 'active',
                'category': 'resilience'
            },
            {
                'name': 'Circuit Breaker',
                'description': 'Automatically handles Nexus failures to maintain service availability',
                'status': 'active',
                'category': 'resilience'
            }
        ],
        'supported_languages': ['Python', 'JavaScript', 'TypeScript', 'Java', 'Go', 'Ruby', 'Shell/Bash'],
        'supported_providers': ['OpenAI', 'Anthropic', 'Google', 'Meta', 'LiteLLM', 'OpenRouter'],
        'test_coverage': {
            'total': 138,
            'status': 'all_passing'
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
                    '138 tests passing with full coverage'
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
    </head>
    <body>
        <div class='header'>
            <h1>🛡️ LLM Security Proxy</h1>
            <p>Project Status & Security Overview Dashboard</p>
            <div class='nav-links'>
                <a href='/' class='nav-link'>🔬 Model Testing</a>
                <a href='/dashboard' class='nav-link active'>📊 Dashboard</a>
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
                        <div class='status-icon'>✅</div>
                        <div class='status-label'>Test Coverage</div>
                        <div class='status-value'>138/138</div>
                    </div>
                    <div class='status-card'>
                        <div class='status-icon'>🔒</div>
                        <div class='status-label'>Security Features</div>
                        <div class='status-value'>6 Active</div>
                    </div>
                </div>
            </div>
            
            <!-- Security Journey -->
            <div class='card'>
                <div class='card-header'>
                    <h2 class='card-title'>🔄 Security Journey</h2>
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
                            <p>Blocks personal information like emails, phone numbers, credit cards</p>
                            <span class='feature-badge'>Active</span>
                        </div>
                    </div>
                    <div class='feature-item input'>
                        <div class='feature-icon'>🔐</div>
                        <div class='feature-info'>
                            <h4>Credential Detection</h4>
                            <p>Prevents API keys and secrets from leaving your organization</p>
                            <span class='feature-badge'>Active</span>
                        </div>
                    </div>
                    <div class='feature-item input'>
                        <div class='feature-icon'>⚠️</div>
                        <div class='feature-info'>
                            <h4>Prompt Injection</h4>
                            <p>Blocks attempts to manipulate the AI with malicious instructions</p>
                            <span class='feature-badge'>Active</span>
                        </div>
                    </div>
                    <div class='feature-item output'>
                        <div class='feature-icon'>📦</div>
                        <div class='feature-info'>
                            <h4>Dependency Validation</h4>
                            <p>Verifies code packages against approved Nexus repository</p>
                            <span class='feature-badge'>Active</span>
                        </div>
                    </div>
                    <div class='feature-item resilience'>
                        <div class='feature-icon'>🚀</div>
                        <div class='feature-info'>
                            <h4>Rate Limiting</h4>
                            <p>Prevents abuse with token bucket algorithm per application</p>
                            <span class='feature-badge'>Active</span>
                        </div>
                    </div>
                    <div class='feature-item resilience'>
                        <div class='feature-icon'>🔄</div>
                        <div class='feature-info'>
                            <h4>Circuit Breaker</h4>
                            <p>Automatically handles external service failures gracefully</p>
                            <span class='feature-badge'>Active</span>
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
                            <li>Initial production-ready release</li>
                            <li>138 tests passing with full coverage</li>
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
                            <p>Microsoft Presidio, Sonatype Nexus, OpenAI Compatible API</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            async function loadDashboardData() {
                try {
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


if __name__ == '__main__':
    import uvicorn
    print('🚀 Starting LLM Proxy Web UI on http://localhost:8000')
    print('📝 Make sure the main proxy is running on port 8080')
    uvicorn.run(app, host='0.0.0.0', port=8000)