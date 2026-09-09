import type { Metadata } from 'next';
import { EvalsView } from '@/components/evals/EvalsView';

export const metadata: Metadata = {
  title: 'System evals · AI Chat System',
  description:
    'Precision and recall of the semantic cache, provider failover pass rate, streaming contract checks, and latency by path, from the last committed benchmark run.',
};

export default function EvalsPage() {
  return <EvalsView />;
}
