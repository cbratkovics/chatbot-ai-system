# Three-minute static project walkthrough

The reviewed release is a static overview and historical evidence site, not hosted generation.
Do not promise that a live backend or a replay is running. Build and serve `frontend/out/`, or
use the public URL only after the owner has verified deployment.

1. On the overview, explain the implemented FastAPI gateway: provider chain, SSE event contract,
   optional cache, request guardrails. Follow a source link to inspect the implementation.
2. Open Recorded evaluations. Point to the original timestamp, dirty commit, localhost target,
   187 requests and historical cost estimates. No new model or embedding request happens here.
3. Discuss the correctness limitation: 56.6% precision, 23 false positives among 68 adversarial
   pairs. Show the false-positive negation example and offline threshold-sweep caveat.
4. Show failover (10 trials, simulated primary outage, real fallback during the historical run)
   and SSE contracts (20 streams). Neither is an availability guarantee. Timings are historical
   localhost observations, not today's hosted latency.
5. Open ADR 0008 and the optional local setup. Offline test doubles and measured provider results
   are distinct. Generating new local answers may cost the developer money; it is not needed
   to view or publish the public evidence.

There is no public composer, fake online state, hidden live mode or synthetic replay. No Render
warm-up is needed. The owner still needs to inspect and retire existing paid resources separately.
