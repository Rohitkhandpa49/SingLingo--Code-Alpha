# Initial architecture

## Service boundaries

- **Frontend (`frontend/`)**: Next.js and TypeScript application. It will own accessible user workflows, camera/microphone permissions, API clients, and the 3D avatar viewer. Browser capture should send only the data needed for inference, not persist raw recordings.
- **Backend (`backend/`)**: FastAPI application with validated HTTP contracts, cookie-based JWT authentication, session revocation, SMTP-backed password recovery, profile/accessibility preference management, account deletion, translation-history operations, rate limiting, database access, and an authenticated landmark-sequence WebSocket. The optional TorchScript classifier reports unknown until a model is configured.
- **AI engine (`ai-engine/`)**: Python dependencies and planned modules for landmark processing, sequence preparation, model training and inference, speech processing, language utilities, and sign-animation mappings. It is not a claim that a model or verified sign dataset currently exists.
- **Shared (`shared/`)**: Language-neutral or generated contracts and constants shared across the services. Service-specific implementation details remain in their owning directories.
- **Infrastructure (`infrastructure/`)**: Deployment and operational configuration. The root Compose file currently starts only local MongoDB; app containers will be added when those services exist.
- **Tests (`tests/` and service-level test directories)**: Cross-service checks live at the root; frontend, backend, and AI tests live beside their respective components.

## Data and trust boundaries

The browser processes camera frames locally with MediaPipe Tasks Vision and sends only bounded, normalized hand-landmark sequences over an authenticated WebSocket. The backend validates those sequences and does not persist them; raw camera footage remains in the browser. The optional TorchScript classifier is disabled by default. MongoDB credentials and signing secrets are supplied through environment variables, never source code.

The backend creates one asynchronous PyMongo client per application lifespan. Startup pings the database, additively ensures validators for the nine application collections, and creates the required indexes; it does not drop collections or alter existing documents. Pool size, idle time, connection timeout, server-selection timeout, and optional wait-queue timeout are environment-configurable; defaults match the PyMongo driver defaults. Tune them only after observing workload concurrency and Atlas connection metrics. The MongoDB URI is held as a secret setting and is not included in its representation. In production, use MongoDB Atlas with a restricted database user and network access policy, HTTPS/WSS, a strong unique JWT secret, and an explicit CORS allowlist. The local Compose MongoDB instance is for development only.

## AI validation principles

Recognition must return an uncertain/unknown result when confidence is insufficient. Supported labels, model versions, evaluation metrics, and sign-animation mappings must be traceable to validated data/assets. Do not claim complete ISL coverage or invent evaluation results. Placeholder assets must be clearly identified as placeholders.

## Implementation status

Account/profile management, optional password recovery, account deletion, translation history, initial database indexes, browser hand tracking, the gesture WebSocket contract, verified-vocabulary interpretation, bounded speech transcription/TTS, and exact verified text-to-sign vocabulary lookup are implemented. Password-recovery email requires deployment SMTP configuration. Whisper is optional and its model weights are not bundled. General ISL grammar, a validated ISL dataset/model, verified production vocabulary, and signing-avatar assets remain unavailable.
