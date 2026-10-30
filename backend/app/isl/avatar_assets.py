import re
from collections.abc import Mapping
from dataclasses import dataclass

_SIGN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
_ASSET_PATH = re.compile(r"^/assets/signs/([A-Za-z0-9][A-Za-z0-9_-]{0,99})\.glb$")
_CLIP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,99}$")


@dataclass(frozen=True, slots=True)
class AvatarAnimationAsset:
    path: str
    clip_name: str


class AvatarAssetRegistry:
    def __init__(
        self,
        assets: Mapping[str, AvatarAnimationAsset] | None = None,
    ) -> None:
        self._assets = dict(assets or {})
        for sign_id, asset in self._assets.items():
            path_match = _ASSET_PATH.fullmatch(asset.path)
            if (
                _SIGN_ID.fullmatch(sign_id) is None
                or path_match is None
                or path_match.group(1) != sign_id
                or _CLIP_NAME.fullmatch(asset.clip_name) is None
            ):
                raise ValueError("Avatar registry entries must use safe sign IDs, GLB paths, and clip names")

    def resolve(
        self,
        sign_id: str,
        vocabulary_asset: str | None,
    ) -> AvatarAnimationAsset | None:
        registered = self._assets.get(sign_id)
        if registered is None or registered.path != vocabulary_asset:
            return None
        return registered


DEFAULT_AVATAR_ASSET_REGISTRY = AvatarAssetRegistry()
