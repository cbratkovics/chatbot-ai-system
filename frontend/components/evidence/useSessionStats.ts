'use client';

import { useMemo } from 'react';
import type { ChatMsg } from './types';
import { computeSessionStats, type SessionStats } from './sessionStats';

/** Memoised wrapper; all logic lives in the pure, unit-tested `computeSessionStats`. */
export function useSessionStats(messages: ChatMsg[]): SessionStats {
  return useMemo(() => computeSessionStats(messages), [messages]);
}
