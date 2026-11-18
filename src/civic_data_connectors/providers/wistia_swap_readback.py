"""Optional provider-reported asset evidence; never fetches media/CDN bytes."""

import hashlib
import re
from urllib.parse import urlsplit


def _original_file(media):
    if not isinstance(media, dict) or not isinstance(media.get("assets"), list):
        return None
    assets = [asset for asset in media["assets"]
              if isinstance(asset, dict) and asset.get("type") == "OriginalFile"]
    if len(assets) != 1:
        return None
    asset = assets[0]
    url = asset.get("url")
    size = asset.get("file_size")
    mime = asset.get("content_type")
    if (not isinstance(url, str) or not url or any(c.isspace() for c in url)
            or type(size) is not int or size <= 0 or not isinstance(mime, str) or not mime):
        return None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment):
            return None
    except ValueError:
        return None
    return {key: asset[key] for key in ("url", "file_size", "content_type", "type")}


def swap_asset_evidence(original_before, replacement_before, target_after):
    """Compare approval-bound modern Media Show snapshots with the target GET.

    This is optional metadata evidence, separate from acknowledged-job success.
    Exact URL equality is a provider-reported pointer match, not a byte hash.
    """
    evidence = {
        "state": "inconclusive",
        "public_media_url": {
            "basis": "vendor_swap_url_preservation_promise_and_target_hashed_id_readback",
            "identity_preserved": False,
            "reachability_verified": False,
        },
        "verification_limits": "Provider-reported asset metadata only; no CDN bytes, checksum, "
                               "public URL reachability or playback independently verified.",
    }
    if not all(isinstance(row, dict) for row in (original_before, replacement_before, target_after)):
        evidence["reason"] = "missing_media_snapshots"
        return evidence
    identity = original_before.get("hashed_id")
    replacement_id = replacement_before.get("hashed_id")
    if (not isinstance(identity, str) or re.fullmatch(r"[A-Za-z0-9_-]+", identity) is None
            or not isinstance(replacement_id, str) or not replacement_id or replacement_id == identity
            or target_after.get("hashed_id") != identity
            or any(row.get("type") != "Video" for row in (original_before, replacement_before, target_after))):
        evidence["reason"] = "media_identity_or_supported_type_mismatch"
        return evidence
    evidence["public_media_url"].update({"identity_preserved": True, "hashed_id": identity})
    original, replacement, target = map(_original_file, (original_before, replacement_before, target_after))
    if any(asset is None for asset in (original, replacement, target)):
        evidence["reason"] = "missing_ambiguous_or_incomplete_original_file"
    elif original["url"] == replacement["url"]:
        evidence["reason"] = "original_and_intended_asset_not_distinguishable"
    elif target != replacement:
        evidence["reason"] = "target_original_file_does_not_match_intended_asset"
    else:
        def summary(asset):
            return {"url_sha256": hashlib.sha256(asset["url"].encode("utf-8")).hexdigest(),
                    **{key: asset[key] for key in ("file_size", "content_type", "type")}}

        evidence.update({"state": "matched", "basis": "distinct_original_file_url_then_exact_intended_metadata",
                         "original_asset": summary(original), "intended_asset": summary(replacement),
                         "target_asset": summary(target)})
    return evidence
