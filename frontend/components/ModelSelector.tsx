'use client';

import { Check, ChevronDown, Sparkles, Eye, Function } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { Model } from '@/lib/api';

interface ModelSelectorProps {
  models: Model[];
  selectedModel: string;
  onSelectModel: (modelId: string) => void;
}

export function ModelSelector({
  models,
  selectedModel,
  onSelectModel,
}: ModelSelectorProps) {
  const currentModel = models.find((m) => m.id === selectedModel);

  const getProviderColor = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'openai':
        return 'text-green-600 dark:text-green-400';
      case 'anthropic':
        return 'text-orange-600 dark:text-orange-400';
      default:
        return 'text-blue-600 dark:text-blue-400';
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="gap-2">
          <Sparkles className="h-4 w-4" />
          <span className="font-medium">
            {currentModel?.name || 'Select Model'}
          </span>
          <ChevronDown className="h-4 w-4 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[300px]">
        {models.map((model) => (
          <DropdownMenuItem
            key={model.id}
            onClick={() => onSelectModel(model.id)}
            className="flex items-center justify-between p-3"
          >
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{model.name}</span>
                {selectedModel === model.id && (
                  <Check className="h-4 w-4 text-primary" />
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className={cn('font-medium', getProviderColor(model.provider))}>
                  {model.provider}
                </span>
                <span>•</span>
                <span>{model.max_tokens.toLocaleString()} tokens</span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                {model.supports_vision && (
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Eye className="h-3 w-3" />
                    <span>Vision</span>
                  </div>
                )}
                {model.supports_functions && (
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Function className="h-3 w-3" />
                    <span>Functions</span>
                  </div>
                )}
              </div>
            </div>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}