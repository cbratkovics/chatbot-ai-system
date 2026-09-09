# infrastructure/

Full-deployment artefacts. **The public demo uses none of this**: it runs one FastAPI worker on
Render's free tier and the frontend on Vercel, with no Redis, database, Kubernetes, or
monitoring stack (see the root README and `docs/adr/`).

| directory | what it is | status |
|---|---|---|
| `terraform/` | AWS ECS deployment: networking, cluster, services, data stores | written, never applied against a real account |
| `kubernetes/helm/` | Helm chart for the backend (`chatbot-ai-system`) | written, not exercised in CI |
| `kubernetes/manifests/` | raw Deployment and Service manifests | written, not exercised in CI |
| `monitoring/` | Prometheus configs and alert rules, Grafana dashboards, Jaeger config, SLI/SLO config, custom exporters, an observability compose file | mounted by `docker/docker-compose.prod.yml` for a local full stack; not run by the demo |
| `disaster-recovery/` | DR automation script and a critical-service recovery runbook | design sketch |

The application package also contains design sketches under
`src/chatbot_ai_system/infrastructure/` (multi-region routing, global load balancing); they are
labelled `DESIGN SKETCH - NOT WIRED` in their first line and import libraries that are not
project dependencies.
