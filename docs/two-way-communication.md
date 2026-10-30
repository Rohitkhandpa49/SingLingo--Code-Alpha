# Two-way communication

SignLingo currently has two bounded communication paths:

1. **ISL landmarks to spoken text:** browser-local hand tracking sends validated landmark sequences to the authenticated gesture WebSocket. A configured classifier produces a model label; the Phase 8 interpreter accepts only compatible, verified vocabulary or exact phrase mappings. The browser TTS provider speaks only successful interpreted text.
2. **Hindi/English speech or text to a sign sequence:** microphone audio is temporarily transcribed by the authenticated optional local Whisper endpoint, or the user types text. The Phase 10 lookup maps exact normalized text to verified vocabulary entries and explicit phrase sequences. Unsupported spans are returned. The 3D player remains unavailable unless every sign has a registered local GLB and named animation clip.

These are not full ISL translation, a general English/Hindi translation system, or a live multi-user conversation service. Sentence grammar, facial/body grammar interpretation, verified vocabulary data, trained model quality, and bundled avatar assets are not available. The application does not fabricate a translation or play a substitute gesture. Real-time camera frames stay in the browser; audio is held temporarily and not persisted. Translation history is saved only when a user explicitly requests it.

See [speech recognition](speech-recognition.md), [text-to-speech](text-to-speech.md), [the ISL language engine](isl-language-engine.md), [speech-to-sign](speech-to-sign.md), and [avatar asset registration](avatar-assets.md) for each path's contracts and limitations.
