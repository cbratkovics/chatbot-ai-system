// Model selector component with dropdown

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
      <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        AI Model
      </label>
      <select
        id="model-select"
        value={currentModel}
        onChange={(e) => onModelChange(e.target.value)}
        disabled={disabled}
        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
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
        <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
          <div>Context: {currentModelData.contextLength.toLocaleString()} tokens</div>
          {currentModelData.description && (
            <div className="mt-1">{currentModelData.description}</div>
          )}
          {currentModelData.capabilities && currentModelData.capabilities.length > 0 && (
            <div className="mt-1 flex gap-1 flex-wrap">
              {currentModelData.capabilities.map((cap) => (
                <span
                  key={cap}
                  className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs"
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
