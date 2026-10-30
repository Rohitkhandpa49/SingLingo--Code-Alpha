# SignLingo

SignLingo is an AI-assisted communication application for Indian Sign Language (ISL) and spoken Hindi/English. The repository includes a responsive frontend, FastAPI APIs, browser-local hand tracking, authenticated landmark inference, static/dynamic model training workflows, a verified-only vocabulary interpretation layer, and an optional bounded speech transcription/TTS flow. No validated training dataset, trained recognition model, verified ISL vocabulary, or signing animation assets are bundled.

## Project layout

| Path | Responsibility |
| --- | --- |
| `frontend/` | Next.js App Router UI, browser interactions, and 3D avatar presentation |
| `backend/` | FastAPI REST/WebSocket APIs, authentication, persistence, and application services |
| `ai-engine/` | Landmark processing, model training/inference, speech, NLP, and avatar mapping |
| `shared/` | Contracts, types, constants, and schemas shared across services |
| `infrastructure/` | Deployment, container, monitoring, and reverse-proxy resources |
| `docs/` | Architecture, setup, and future feature documentation |
| `scripts/` | Local development and environment helper scripts |
| `tests/` | Cross-service and end-to-end tests |

More detailed setup information is in [docs/setup-guide.md](docs/setup-guide.md), and the initial component boundaries are in [docs/architecture.md](docs/architecture.md).

## Local development

### Prerequisites

- Windows 10/11 with PowerShell
- Docker Desktop with the Compose plugin, for local MongoDB
- Node.js 20.9 or later and npm
- Python 3.11 or later for the backend and AI engine

From the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` before starting services. The checked-in values are placeholders for local development; replace the JWT secret with a random value and do not reuse local credentials in production.

Start the local MongoDB development service:

```powershell
docker compose config
docker compose up -d mongodb
docker compose ps
```

The database is bound to `127.0.0.1:27017`. The named volume `mongodb_data` persists local database contents between container restarts. To stop the service without removing data:

```powershell
docker compose stop mongodb
```

To remove the container and its persisted local database volume, use `docker compose down --volumes` only when you intentionally want to erase local data.

### Current implementation status

- **Phase 1 complete:** monorepo directories, configuration templates, local MongoDB Compose service, and setup/architecture documentation.
- **Phase 2 complete:** responsive frontend routes, accessible controls, light/dark mode, and backend-connected account, profile, and history screens.
- **Phase 3 complete:** FastAPI account registration/login/logout, protected profile and history APIs, MongoDB persistence, password hashing, cookie sessions, and API tests.
- **Phase 4 complete:** profile/preferences management, password recovery configuration, account deletion, session revocation, and browser Origin safeguards.
- **Phase 5 complete:** authenticated gesture WebSocket with heartbeat, validation, limits, and backpressure.
- **Phase 6 complete:** browser-local MediaPipe hand detection, versioned landmark normalization, bounded temporal windows, and camera controls. Raw video remains in the browser.
- **Phase 7 complete (training pipeline only):** static MLP and dynamic LSTM training/evaluation, metadata validation, and backend integration. Training and quality evaluation require an appropriate dataset that is not included.
- **Phase 8 initial architecture complete:** versioned verified-only vocabulary, model compatibility checks, cautious single-sign/exact-phrase interpretation, and authenticated feedback. No vocabulary entries or general ISL grammar are bundled, so model labels remain unsupported until reviewed resources are configured.
- **Phase 9 complete (bounded speech workflow):** authenticated WAV transcription with optional local Whisper, transcript review/editing, and browser speech synthesis for verified interpreted text. No Whisper weights are bundled; speech-to-text requires explicit model setup.
- **Phase 10 limited implementation complete:** authenticated exact verified-vocabulary text mapping, unsupported-span reporting, explicit history saving, and a 3D sequence player gated by a validated local GLB/clip registry. No verified vocabulary, grammar, or animation assets are bundled; complete speech-to-sign translation is not available.
- **Not implemented:** a validated trained recognition model, verified production vocabulary, general ISL grammar, and playable signing animations.

## Hackathon demo workflow

Start MongoDB, the backend, and frontend using [the setup guide](docs/setup-guide.md). Register and sign in, then demonstrate:

1. **Account and accessibility:** open Settings, show available preferences, and switch the site theme.
2. **Sign input:** open `/translator/sign-to-speech`, start camera tracking, and show browser-local hand landmarks. Do not present landmark detection as sign recognition: no trained gesture checkpoint or verified vocabulary is bundled, so interpreted speech is unavailable.
3. **Speech-to-sign:** open `/translator/speech-to-sign`, type a short message, and prepare a sequence. Explain that only exact reviewed vocabulary entries can map; the bundled vocabulary is empty, so unsupported text is expected. Optionally demonstrate recording and transcript review only after installing the optional Whisper dependency and configuring its model.
4. **History and privacy:** save a result explicitly if one is available, then show that history is user-scoped. Camera frames remain in the browser; temporary audio is not stored.
5. **Avatar and architecture:** show the sequence review and unavailable-player state. No verified signing animations are bundled, so do not claim avatar playback. Use [the architecture guide](docs/architecture.md) to explain the browser, FastAPI, MongoDB, and model boundaries.
6. **Limitations and next steps:** state that a consented, licensed ISL dataset, reviewed vocabulary, compatible trained checkpoints, and verified animation assets are required before recognition, full translation, or avatar playback can be demonstrated.

## Planned development phases

1. Foundation and repository configuration (complete)
2. Frontend UI and accessibility (complete)
3. Backend APIs, authentication, and database operations (complete)
4. Account and profile security (complete)
5. Gesture WebSocket infrastructure (complete)
6. Browser camera and landmark pipeline (complete)
7. Static/dynamic model training and evaluation pipeline (complete; dataset required)
8. ISL language understanding (limited verified-vocabulary architecture; reviewed data required)
9. Speech recognition and text-to-speech (implemented; see [speech setup](docs/whisper-setup.md))
10. Speech-to-sign exact vocabulary mapping and verified avatar animation mapping (limited architecture; content required)

Recognition coverage and accuracy will only be reported after evaluation on a documented, appropriate ISL dataset. Translation coverage is zero until verified vocabulary is configured. Raw camera frames remain in the browser; validated landmark sequences are sent only to the authenticated inference endpoint and are not persisted. Audio capture is temporary, and its WAV is uploaded only to the authenticated transcription endpoint; the application does not persist the recording or transcript. See [the ISL language engine](docs/isl-language-engine.md), [vocabulary guide](docs/isl-vocabulary-guide.md), [speech-recognition guide](docs/speech-recognition.md), [speech-to-sign guide](docs/speech-to-sign.md), [two-way communication](docs/two-way-communication.md), and [avatar asset registry](docs/avatar-assets.md).
