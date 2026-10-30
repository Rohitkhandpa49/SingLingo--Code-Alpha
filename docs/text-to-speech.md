# Text-to-speech

The sign-to-speech experience uses the browser's Web Speech API through a small provider abstraction. It speaks only text returned by a successful, model-compatible verified vocabulary interpretation. It does not read raw model labels, unsupported mappings, or partial results aloud. Hindi output requests the `hi-IN` voice language; English requests `en-IN`.

Speech synthesis is performed by the user's browser and operating-system voice engine. Available voices, pronunciation, language support, and playback behavior vary by device. No speech recording or generated audio is uploaded or stored. If the browser does not support speech synthesis or playback fails, the interface reports an error instead of silently claiming success.

Browser synthesis is not a guarantee of an installed Hindi or English voice. Verify available voices on each target platform. Text-to-speech does not translate between languages and does not produce ISL signs.
