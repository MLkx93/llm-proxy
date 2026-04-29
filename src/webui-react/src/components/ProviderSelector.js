 import React, { useState, useEffect, useCallback } from 'react';
import { getProviders, switchProvider, getProviderModels } from '../services/api';
import './ProviderSelector.css';

function ProviderSelector({ onProviderChange, onModelSelect }) {
  const [providers, setProviders] = useState([]);
  const [activeProvider, setActiveProvider] = useState('openrouter');
  const [models, setModels] = useState({ free: [], paid: [] });
  const [switching, setSwitching] = useState(false);
  const [toast, setToast] = useState(null);

  const loadModels = useCallback(async (providerId) => {
    try {
      const res = await getProviderModels(providerId);
      setModels({
        free: res.data.free_models,
        paid: res.data.paid_models,
      });
      if (onProviderChange) {
        onProviderChange(providerId, res.data);
      }
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  }, [onProviderChange]);

  const loadProviders = useCallback(async () => {
    try {
      const res = await getProviders();
      setProviders(res.data.providers);
      setActiveProvider(res.data.active_provider);
    } catch (err) {
      console.error('Failed to load providers:', err);
    }
  }, []);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  useEffect(() => {
    if (activeProvider) {
      loadModels(activeProvider);
    }
  }, [activeProvider, loadModels]);

  const handleSwitch = async (providerId) => {
    try {
      setSwitching(true);
      const res = await switchProvider(providerId);
      setActiveProvider(providerId);
      setToast({ message: `✅ ${res.data.message}`, type: 'success' });
      setTimeout(() => setToast(null), 3000);
      loadModels(providerId);
      if (onProviderChange) {
        onProviderChange(providerId, null);
      }
    } catch (err) {
      setToast({ message: `❌ Failed to switch provider: ${err.response?.data?.detail || err.message}`, type: 'error' });
      setTimeout(() => setToast(null), 3000);
    } finally {
      setSwitching(false);
    }
  };

  const getStatusDot = (provider) => {
    if (provider.active) return 'status-dot active';
    if (provider.configured) return 'status-dot configured';
    return 'status-dot unconfigured';
  };

  const getStatusLabel = (provider) => {
    if (provider.active) return 'Active';
    if (provider.configured) return 'Configured';
    return 'Not Configured';
  };

  return (
    <div className="provider-selector">
      {toast && (
        <div className={`toast ${toast.type}`}>
          {toast.message}
        </div>
      )}

      <div className="provider-bar">
        <div className="provider-info">
          <span className="provider-label">Provider:</span>
          <select
            className="provider-select"
            value={activeProvider}
            onChange={(e) => handleSwitch(e.target.value)}
            disabled={switching}
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.icon} {p.name}
              </option>
            ))}
          </select>
          {providers.map((p) => (
            p.id === activeProvider && (
              <span key={p.id} className="provider-description">
                <span className={getStatusDot(p)}></span>
                {p.description}
                <span className="provider-status-label">{getStatusLabel(p)}</span>
              </span>
            )
          ))}
        </div>
        <div className="provider-models-count">
          {providers.find(p => p.id === activeProvider)?.model_count || 0} models
        </div>
      </div>

      <div className="models-section">
        {models.free.length > 0 && (
          <div className="model-group">
            <h4 className="model-group-title">🆓 Free Models</h4>
            <div className="model-grid">
              {models.free.map((model) => (
                <div
                  key={model.id}
                  className="model-card free"
                  onClick={() => onModelSelect && onModelSelect(model)}
                >
                  <div className="model-name">{model.name}</div>
                  <div className="model-meta">
                    <span className="model-provider">{model.provider}</span>
                    <span className="model-cost free">{model.cost}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {models.paid.length > 0 && (
          <div className="model-group">
            <h4 className="model-group-title">💰 Paid Models</h4>
            <div className="model-grid">
              {models.paid.map((model) => (
                <div
                  key={model.id}
                  className="model-card paid"
                  onClick={() => onModelSelect && onModelSelect(model)}
                >
                  <div className="model-name">{model.name}</div>
                  <div className="model-meta">
                    <span className="model-provider">{model.provider}</span>
                    <span className="model-cost paid">{model.cost}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ProviderSelector;