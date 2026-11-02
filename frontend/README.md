# Static project overview and recorded evaluations

See the [root README](../README.md) for the evidence and optional gateway source.

```bash
npm ci
npm run lint
npm test
npm run typecheck
npm run build       # exports out/; no backend or external fonts
npm start           # local static file server with configured headers
```

Node 24.x, npm 9+, Python 3 for the file server. No frontend environment variables or credentials.
`npm run dev` is an optional development preview; release verification serves `out/`.
Browser tests: `npx playwright install chromium`, then `npm run test:browser`.
[Hosting settings](DEPLOYMENT.md) · [Original local chat reference](local-reference/README.md)
