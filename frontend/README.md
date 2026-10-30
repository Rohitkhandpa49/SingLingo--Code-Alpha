# Frontend

Next.js App Router and TypeScript application. It includes responsive landing, account, dashboard, translator, history, profile, settings, and about screens. Registration, login, profile lookup, logout, and translation-history management call the FastAPI backend. Gesture recognition, speech processing, and avatar animation remain disconnected until later phases.

## Development

From this directory:

```powershell
npm.cmd install
npm.cmd run dev
```

The interface is available at `http://localhost:3000`. To run validation:

```powershell
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

The project uses Vitest and Testing Library for unit/component tests. Camera permission is requested only after the user starts hand tracking. MediaPipe Tasks Vision processes video frames locally and draws detected hand landmarks; fixed-length normalized landmark sequences are sent over an authenticated WebSocket. Raw video frames are never sent. Recognition remains unknown until a validated backend TorchScript model is configured.

Tailwind CSS 4 and its PostCSS plugin provide the styling pipeline; Lucide React supplies interface icons. Framer Motion is used for restrained landing-page transitions; `prefers-reduced-motion` and the in-session reduced-motion preference suppress non-essential motion. Three.js and React Three Fiber are included for the later avatar phase; the current avatar area is a clearly labeled static placeholder.
