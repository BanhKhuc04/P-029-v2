"""Project-scoped preflight. Never downloads weights or runs a detector on page load."""
from __future__ import annotations

import hashlib
import importlib
import sys
from functools import lru_cache
from pathlib import Path

from pointsnap.core.rules import rules_catalog_dict
from pointsnap.web.findings import GROUPS


@lru_cache(maxsize=16)
def _critic_check(path, size, modified):
    try:
        import torch
        model = torch.jit.load(path, map_location="cpu").eval()
        with torch.inference_mode():
            logit, delta = model(torch.zeros(1, 256, 4), torch.zeros(1, 20))
        return bool(logit.numel() == 1 and tuple(delta.shape) == (1, 7)
                    and torch.isfinite(logit).all() and torch.isfinite(delta).all())
    except Exception:
        return False


@lru_cache(maxsize=16)
def _weight_hash(path, size, modified, prefix):
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().startswith(prefix)


def model_status(config):
    result = []
    camera_on = config.camera.enabled != "false" and any(
        getattr(config.rules, r) for r in ("cam_mismatch", "cam_class", "cam_missing", "cam_sparse"))
    for key, required, packages in (
        ("critic", config.rules.critic_box, ("torch",)),
        ("camera", camera_on, ("torch", "torchvision") + (("transformers",) if config.camera.model != "maskrcnn" else ())),
    ):
        entry = {"id": key, "required": bool(required), "ready": not required,
                 "name": "Box Critic" if key == "critic" else f"Camera · {config.camera.model}",
                 "reason": "Không dùng trong cấu hình hiện tại", "install_command": f'"{sys.executable}" -m pip install ' + ' '.join(packages)}
        if key == "critic":
            entry.update(config_key="critic.model", path=config.critic.model)
        else:
            entry["mode"] = config.camera.enabled
        if not required:
            result.append(entry)
            continue
        try:
            for package in packages:
                importlib.import_module(package)
        except Exception:
            entry.update(ready=False, reason="Thiếu hoặc lỗi runtime: " + ", ".join(packages))
            result.append(entry)
            continue
        if key == "critic":
            path = Path(config.critic.model).expanduser() if config.critic.model else None
            valid = bool(path and path.is_file())
            if valid:
                stat = path.stat()
                valid = _critic_check(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
            entry.update(ready=valid, reason="Model hợp lệ" if valid else "Cần cấu hình critic.model trỏ tới trọng số TorchScript hợp lệ",
                         config_key="critic.model", path=str(path) if path else "")
        else:
            from pointsnap.vision import detector2d as d
            valid = True
            if config.camera.model in ("maskrcnn", "hybrid"):
                import torch
                from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights
                url = MaskRCNN_ResNet50_FPN_V2_Weights.COCO_V1.url
                name = url.rsplit("/", 1)[-1]
                weight = Path(torch.hub.get_dir()) / "checkpoints" / name
                if weight.is_file():
                    st = weight.stat()
                    valid = _weight_hash(str(weight), st.st_size, st.st_mtime_ns, name.rsplit("-", 1)[-1].split(".")[0])
                else:
                    valid = False
            if config.camera.model in ("gdino-sam2", "hybrid"):
                from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection, Sam2Model
                try:
                    for repo, rev, cls in ((d.GDINO_ID, d.GDINO_REVISION, AutoModelForZeroShotObjectDetection),
                                            (d.SAM2_ID, d.SAM2_REVISION, Sam2Model)):
                        AutoProcessor.from_pretrained(repo, revision=rev, local_files_only=True)
                        # Resolve all shards without downloading or allocating the model.
                        from transformers.utils.hub import cached_file
                        valid = valid and bool(cached_file(repo, "model.safetensors", revision=rev, local_files_only=True))
                except Exception:
                    valid = False
            if config.camera.enabled == "auto":
                import torch
                if not torch.cuda.is_available():
                    valid = False
                    entry["reason"] = "Camera auto cần GPU CUDA; chọn camera.enabled: true để chạy CPU hoặc tắt các luật camera"
            entry.update(ready=valid, reason=entry["reason"] if "CUDA" in entry["reason"] else (
                "Runtime và trọng số có sẵn" if valid else "Thiếu/hỏng trọng số camera; tải model theo hướng dẫn rồi kiểm tra lại"))
            entry["weights_command"] = f'"{sys.executable}" -m pointsnap.models prepare-camera --model {config.camera.model}'
        result.append(entry)
    return {"items": result, "all_ready": all(m["ready"] for m in result), "python": sys.executable}


def project_catalog(config=None):
    data = rules_catalog_dict()
    models = model_status(config) if config else None
    status = {m["id"]: m for m in models["items"]} if models else {}
    rules, seen = [], set()
    for rule in data["rules"]:
        if rule["error_type"] not in GROUPS or rule["default_severity"] == "info" or rule["switch_key"] in seen:
            continue
        seen.add(rule["switch_key"])
        enabled = bool(getattr(config.rules, rule["switch_key"], False)) if config else None
        dependency = "critic" if rule["id"].startswith("critic.") else "camera" if rule["id"].startswith("cam.") else None
        ready = not dependency or not config or status[dependency]["ready"]
        if dependency == "camera" and config and config.camera.enabled == "false":
            ready = False
        rule.update(enabled=enabled, runnable=bool(enabled and ready), dependency=dependency,
                    unavailable_reason=status.get(dependency, {}).get("reason", "") if not ready else "")
        rules.append(rule)
    data.update(rules=rules, groups=GROUPS, models=models)
    return data
