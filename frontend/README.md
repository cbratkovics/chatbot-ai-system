# AI Chatbot Frontend

A modern, responsive frontend for the AI Chatbot System built with Next.js 14, TypeScript, and Tailwind CSS.

## Features

- Real-time WebSocket streaming
- Multi-model support (OpenAI GPT-4, Claude)
- Clean chat interface with message bubbles
- Syntax highlighting for code blocks
- Function calling visualization
- Voice input support
- Dark/light mode
- Fully responsive design

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Backend API running at http://localhost:8000

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.production.example .env.local

# Update .env.local with your backend URL
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to see the app.

## Environment Variables

- `NEXT_PUBLIC_API_URL`: Backend API URL (default: http://localhost:8000)
- `NEXT_PUBLIC_WS_URL`: WebSocket URL (default: ws://localhost:8000)

## Deployment

### Vercel

1. Push your code to GitHub
2. Import the repository in Vercel
3. Set environment variables:
   - `NEXT_PUBLIC_API_URL`: Your backend URL
   - `NEXT_PUBLIC_WS_URL`: Your WebSocket URL
4. Deploy

The `vercel.json` file is pre-configured to proxy API requests to your backend.

### Manual Deployment

```bash
# Build the application
npm run build

# Start production server
npm start
```

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Shadcn/ui
- **State Management**: Zustand
- **Animations**: Framer Motion
- **Markdown**: react-markdown
- **Syntax Highlighting**: react-syntax-highlighter

## Project Structure

```
frontend/
├── app/              # Next.js app directory
├── components/       # React components
│   ├── ui/          # Shadcn UI components
│   ├── ChatInterface.tsx
│   ├── ChatMessage.tsx
│   ├── ChatInput.tsx
│   └── ModelSelector.tsx
├── hooks/           # Custom React hooks
│   └── useWebSocket.ts
├── lib/             # Utilities and API client
│   ├── api.ts
│   ├── store.ts
│   └── utils.ts
└── public/          # Static assets
```
