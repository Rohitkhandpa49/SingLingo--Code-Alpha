# Avatar asset registry

The avatar player uses React Three Fiber and Drei to load a registered GLB asset and play its explicitly named animation clip once per sign. The server-side allowlist is `DEFAULT_AVATAR_ASSET_REGISTRY` in `backend/app/isl/avatar_assets.py`. Entries must use a stable sign ID, the matching local path `/assets/signs/{sign_id}.glb`, and a non-empty clip name. Database `animation_asset` values are returned only when they exactly match an allowlisted entry. External URLs, traversal paths, mismatched IDs, and unregistered clips are rejected.

No model or signing animation assets are bundled or registered. Therefore, the UI intentionally shows an unavailable state and disables playback. It does not substitute a generic avatar gesture or generate motion from sign names.

To add an asset only after obtaining appropriate rights and qualified sign-language review:

1. Validate and place a self-contained `.glb` file at `frontend/public/assets/signs/{sign_id}.glb`.
2. Verify its skeleton, orientation, animation clips, timing, and accessibility with qualified ISL reviewers; document its provenance and license.
3. Add an `AvatarAnimationAsset(path="/assets/signs/{sign_id}.glb", clip_name="...")` entry to the backend registry. Use the actual clip name in the asset; do not guess it.
4. Set the matching verified vocabulary document's `animation_asset` to the exact registered path.
5. Test the actual asset in a supported WebGL browser, including load failure, playback completion, pause, stop, and sequence transitions.

The automated tests validate registry path rules and sequence-control state. They do not download or validate a GLB, verify sign correctness, or exercise WebGL playback.
