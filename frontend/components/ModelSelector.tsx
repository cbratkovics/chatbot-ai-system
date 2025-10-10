"use client";

import React from 'react';
import { Model } from '@/types';

interface ModelSelectorProps {
  models: Model[];
  currentModel: string;
  onModelChange: (modelId: string) => void;
  disabled?: boolean;
}

export function ModelSelector({
  models,
  currentModel,
  onModelChange,
  disabled = false,
}: ModelSelectorProps) {
  const groupedModels = React.useMemo(() => {
    const groups: Record<string, Model[]> = {};

    models.forEach((model) => {
      if (!groups[model.provider]) {
        groups[model.provider] = [];
      }
      groups[model.provider].push(model);
    });

    return groups;
  }, [models]);

  const currentModelData = models.find(m => m.id === currentModel);

  return (
    <div className="model-selector">
      <label htmlFor="model-select" className="block text-sm font-medium text-gray-300 mb-2">
        AI Model
      </label>
      <select
        id="model-select"
        value={currentModel}
        onChange={(e) => onModelChange(e.target.value)}
        disabled={disabled}
        className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 hover:bg-white/10"
        style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3E%3Cpath stroke=\'%239CA3AF\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3E%3C/svg%3E")',
          backgroundPosition: 'right 0.5rem center',
          backgroundRepeat: 'no-repeat',
          backgroundSize: '1.5em 1.5em',
          paddingRight: '2.5rem',
        }}
      >
        {Object.entries(groupedModels).map(([provider, providerModels]) => (
          <optgroup key={provider} label={provider.charAt(0).toUpperCase() + provider.slice(1)}>
            {providerModels.map((model) => (
              <option key={model.id} value={model.id} disabled={!model.available}>
                {model.name} {!model.available && '(Unavailable)'}
              </option>
            ))}
          </optgroup>
        ))}
      </select>

      {currentModelData && (
        <div className="mt-2 text-xs text-gray-400 space-y-1">
          <div className="flex items-center gap-2">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>Context: {currentModelData.contextLength.toLocaleString()} tokens</span>
          </div>
          {currentModelData.description && (
            <div className="text-gray-500">{currentModelData.description}</div>
          )}
          {currentModelData.capabilities && currentModelData.capabilities.length > 0 && (
            <div className="flex gap-1.5 flex-wrap pt-1">
              {currentModelData.capabilities.map((cap) => (
                <span
                  key={cap}
                  className="px-2 py-0.5 bg-blue-500/10 text-blue-300 border border-blue-500/20 rounded-full text-xs"
                >
                  {cap}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
