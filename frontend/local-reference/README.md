# Original live chat UI (source-only local reference)

The original `components/ChatInterface/index.tsx` and evidence/SSE components are retained.
They are not part of the exported site's import graph and are not a public live mode.
Use the API through `/docs` or curl unless you specifically need to develop the original UI.

For that optional action only, in a local checkout with your own provider configuration:

1. Preserve the contents of `app/page.tsx` outside the checkout before editing it.
2. Temporarily replace its contents with the snippet below. Do not commit that change.
3. Start the local FastAPI backend as in `docs/LOCAL_DEVELOPMENT.md`.
4. Run `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev` from `frontend`.
5. Restore the saved static page and remove that variable before static build/test/release.

```tsx
import { ChatInterface } from '@/components/ChatInterface';
export default function LocalChat() { return <ChatInterface />; }
```

The local config requires explicit loopback addressing and development mode; it has no hosted
fallback. Production exports reject backend settings, and the browser audit rejects escaped
chat endpoint code. Do not add browser key entry. Provider/embedding requests here may incur
charges and are separate from the public demo's $0 eligible static hosting.
