"""
LLM Proxy Web UI - Interface for testing different models
"""
import time
import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

app = FastAPI(title="LLM Proxy Testing Interface")

# Model configurations (OpenRouter format)
MODELS = {
    # Free models (with limitations)
    "free": [
        {"id": "google/gemini-flash", "name": "Gemini Flash", "provider": "Google", "cost": "Free"},
        {"id": "meta-llama/llama-3-8b-instruct", "name": "Llama 3 8B", "provider": "Meta", "cost": "Free"},
    ],
    # Paid models
    "paid": [
        {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI", "cost": "$5/million tokens"},
        {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI", "cost": "$10/million tokens"},
        {"id": "openai/gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "OpenAI", "cost": "$0.50/million tokens"},
        {"id": "google/gemini-pro", "name": "Gemini Pro", "provider": "Google", "cost": "$3/million tokens"},
        {"id": "meta-llama/llama-3-70b-instruct", "name": "Llama 3 70B", "provider": "Meta", "cost": "$8/million tokens"},
    ]
}

# Static files path
STATIC_PATH = Path(__file__).parent / "static"
STATIC_PATH.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home():
    """Main interface page"""
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LLM Proxy - Model Testing Interface</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { 
                color: white; 
                text-align: center; 
                margin-bottom: 30px;
                font-size: 2.5em;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .card {
                background: white;
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .section-title {
                font-size: 1.3em;
                color: #333;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 2px solid #667eea;
            }
            .model-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 15px;
                margin-bottom: 20px;
            }
            .model-btn {
                padding: 12px 20px;
                border: 2px solid #667eea;
                background: white;
                border-radius: 10px;
                cursor: pointer;
                transition: all 0.3s ease;
                text-align: left;
            }
            .model-btn:hover {
                background: #667eea;
                color: white;
            }
            .model-btn.selected {
                background: #667eea;
                color: white;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }
            .model-btn.free {
                border-color: #10b981;
            }
            .model-btn.free.selected {
                background: #10b981;
            }
            .model-name { font-weight: 600; font-size: 0.95em; }
            .model-info { font-size: 0.8em; opacity: 0.8; margin-top: 5px; }
            .input-group { margin-bottom: 15px; }
            label {
                display: block;
                margin-bottom: 5px;
                color: #555;
                font-weight: 500;
            }
            input, textarea, select {
                width: 100%;
                padding: 12px;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                font-size: 14px;
                transition: border-color 0.3s;
            }
            input:focus, textarea:focus, select:focus {
                outline: none;
                border-color: #667eea;
            }
            textarea { min-height: 120px; resize: vertical; }
            .api-key-section {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .submit-btn {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 1.1em;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .submit-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
            }
            .submit-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            #response {
                background: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                margin-top: 20px;
                min-height: 200px;
                white-space: pre-wrap;
                word-wrap: break-word;
                font-family: monospace;
                font-size: 13px;
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
            }
            .loading::after {
                content: '⏳ Testing model...';
                animation: pulse 1s infinite;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .status {
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 15px;
            }
            .status.success { background: #d4edda; color: #155724; }
            .status.error { background: #f8d7da; color: #721c24; }
            .tabs {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
            }
            .tab {
                padding: 10px 20px;
                border: none;
                background: #e0e0e0;
                border-radius: 5px;
                cursor: pointer;
            }
            .tab.active {
                background: #667eea;
                color: white;
            }
            .tab-content { display: none; }
            .tab-content.active { display: block; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 LLM Proxy Model Testing</h1>
            
            <div class="card">
                <div class="tabs">
                    <button class="tab active" onclick="showTab('free')">🆓 Free Models</button>
                    <button class="tab" onclick="showTab('paid')">💰 Paid Models</button>
                </div>
                
                <div id="free-models" class="tab-content active">
                    <h3 class="section-title">🆓 Available Free Models</h3>
                    <div class="model-grid">
    """
    
    # Add free models
    for model in MODELS["free"]:
        html += f"""
                        <button class="model-btn free" onclick="selectModel('{model['id']}', this)">
                            <div class="model-name">{model['name']}</div>
                            <div class="model-info">{model['provider']} • {model['cost']}</div>
                        </button>
        """
    
    html += """
                    </div>
                </div>
                
                <div id="paid-models" class="tab-content">
                    <h3 class="section-title">💰 Available Paid Models</h3>
                    <div class="model-grid">
    """
    
    # Add paid models
    for model in MODELS["paid"]:
        html += f"""
                        <button class="model-btn" onclick="selectModel('{model['id']}', this)">
                            <div class="model-name">{model['name']}</div>
                            <div class="model-info">{model['provider']} • {model['cost']}</div>
                        </button>
        """
    
    html += """
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h3 class="section-title">📝 Test Configuration</h3>
                
                <div class="api-key-section">
                    <div class="input-group">
                        <label for="api_key">🔑 Proxy API Key</label>
                        <input type="text" id="api_key" value="dev-local-key-1234" placeholder="Enter your proxy API key">
                    </div>
                </div>
                
                <div class="input-group">
                    <label for="model_id">🎯 Selected Model (OpenRouter ID)</label>
                    <input type="text" id="model_id" readonly placeholder="Click a model above to select it">
                </div>
                
                <div class="input-group">
                    <label for="message">💬 Your Message</label>
                    <textarea id="message" placeholder="Enter your test message here...">Hello! Can you tell me a short joke?</textarea>
                </div>
                
                <button class="submit-btn" onclick="testModel()" id="submit_btn">🚀 Test Model</button>
            </div>
            
            <div class="card">
                <h3 class="section-title">📊 Response</h3>
                <div id="response">Response will appear here...</div>
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
                // Remove previous selection
                document.querySelectorAll('.model-btn').forEach(b => b.classList.remove('selected'));
                // Select new
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
                    responseDiv.innerHTML = '<div class="status error">⚠️ Please select a model first!</div>';
                    return;
                }
                
                if (!message.trim()) {
                    responseDiv.innerHTML = '<div class="status error">⚠️ Please enter a message!</div>';
                    return;
                }
                
                // Show loading
                responseDiv.innerHTML = '<div class="loading"></div>';
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
                            <div class="status success">✅ Success! (${duration.toFixed(2)}s)</div>
                            <div style="margin: 10px 0; padding: 10px; background: #e9ecef; border-radius: 5px;">
                                <strong>Model:</strong> ${model}<br>
                                <strong>Prompt tokens:</strong> ${usage.prompt_tokens || 'N/A'}<br>
                                <strong>Completion tokens:</strong> ${usage.completion_tokens || 'N/A'}<br>
                                <strong>Total tokens:</strong> ${usage.total_tokens || 'N/A'}
                            </div>
                            <strong>Response:</strong>
                            <div style="margin-top: 10px; padding: 15px; background: white; border-radius: 5px; border-left: 4px solid #667eea;">
                                ${content}
                            </div>
                        `;
                    } else {
                        const error = data.error?.message || data.error?.code || JSON.stringify(data);
                        responseDiv.innerHTML = `
                            <div class="status error">❌ Error: ${data.error?.code || 'Unknown Error'}</div>
                            <div style="margin-top: 10px; padding: 15px; background: #fff; border-radius: 5px; white-space: pre-wrap;">
                                ${error}
                            </div>
                        `;
                    }
                } catch (error) {
                    responseDiv.innerHTML = `
                        <div class="status error">❌ Network Error</div>
                        <div style="margin-top: 10px;">
                            ${error.message}
                        </div>
                    `;
                }
                
                submitBtn.disabled = false;
                submitBtn.textContent = '🚀 Test Model';
            }
        </script>
    </body>
    </html>
    """
    return html


@app.post("/v1/chat/completions")
async def proxy_chat(request: Request):
    """Proxy the request to the main LLM proxy"""
    body = await request.json()
    api_key = request.headers.get("authorization", "").replace("Bearer ", "")
    
    # Forward to main proxy
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8080/v1/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"}
            )
            return response.json()
    except Exception as e:
        return {"error": {"code": "PROXY_ERROR", "message": str(e)}}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting LLM Proxy Web UI on http://localhost:8000")
    print("📝 Make sure the main proxy is running on port 8080")
    uvicorn.run(app, host="0.0.0.0", port=8000)