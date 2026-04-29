# LLM Security Proxy - React Web UI

Modern React frontend for the LLM Security Proxy, replacing the previous Jinja2 template-based UI.

## Architecture

```
React Frontend (port 3000) → API Server (port 8000) → LLM Security Proxy (port 8080) → LLM Providers
```

- **React Frontend**: SPA with provider management, model testing, and dashboard
- **API Server**: FastAPI backend providing REST API endpoints
- **LLM Security Proxy**: Core security scanning engine

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Model Testing | `/` | Chat interface with provider/model selection and security test buttons |
| Dashboard | `/dashboard` | System status, security pipeline, features, metrics, and charts |
| State Report | `/state` | Detailed project state report with issues and roadmap |

## Quick Start

### Development Mode

```bash
# Terminal 1: Start the LLM Security Proxy
python -m src.proxy.main

# Terminal 2: Start the API Server
python -m src.webui_api.main

# Terminal 3: Start the React dev server
cd src/webui-react
npm start
```

- React dev server: http://localhost:3000
- API server: http://localhost:8000
- API docs: http://localhost:8000/docs

### Production Mode

```bash
# Build the React app
cd src/webui-react
npm run build

# Start the API server (serves React build as static files)
python -m src.webui_api.main
```

- Production URL: http://localhost:8000

## Tech Stack

- **React 18** with hooks
- **React Router v6** for SPA navigation
- **Axios** for API communication
- **Chart.js + react-chartjs-2** for dashboard charts
- **CSS** with custom properties (dark theme)

## Project Structure

```
src/webui-react/
├── public/
│   └── index.html
├── src/
│   ├── App.js              # Router + layout
│   ├── App.css             # Global styles
│   ├── index.js            # Entry point
│   ├── services/
│   │   └── api.js          # Axios API client
│   └── components/
│       ├── ProviderSelector.js/css  # Provider dropdown + model grid
│       ├── ModelTester.js/css       # Chat interface + security tests
│       ├── Dashboard.js/css         # System status + metrics + charts
│       └── StateReport.js/css       # Project state report
├── .env                    # REACT_APP_API_URL
└── package.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REACT_APP_API_URL` | `http://localhost:8000` | API server base URL |

## API Endpoints

The React frontend communicates with the FastAPI backend:

- `GET /api/providers` - List providers
- `GET /api/providers/{id}/models` - Get models for provider
- `POST /api/providers/switch` - Switch active provider
- `POST /v1/chat/completions` - Send chat completion (proxied)
- `GET /api/dashboard/health` - System health
- `GET /api/dashboard/metrics` - Request metrics
- `GET /api/dashboard/features` - Security features
- `GET /api/dashboard/pipeline` - Security pipeline phases
- `GET /api/dashboard/issues` - Known issues
- `GET /api/dashboard/codebase-stats` - Codebase statistics
- `GET /api/dashboard/components` - Component inventory
- `GET /api/dashboard/roadmap` - Improvement roadmap