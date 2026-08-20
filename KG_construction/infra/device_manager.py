from __future__ import annotations

import os
import platform
from functools import lru_cache
from typing import Any, Callable, TypeVar

import torch

T = TypeVar("T")


def _normalize_device_name(device: str | None, prefer_gpu: bool = True) -> str:
    raw = (device or os.getenv("KG_FORCE_DEVICE") or ("cuda" if prefer_gpu else "cpu")).strip().lower()
    if raw.startswith("cuda"):
        return "cuda"
    return "cpu"


def _build_cpu_fallback_info(info: dict[str, Any], reason: str) -> dict[str, Any]:
    info["selected_device"] = "cpu"
    info["device"] = "cpu"
    info["fallback_applied"] = True
    info["fallback_reason"] = reason
    info["probe_success"] = True
    info["probe_summary"] = f"GPU 不可用，已稳定回退到 CPU。原因: {reason}"
    return info


@lru_cache(maxsize=4)
def _probe_requested_device(requested_device: str) -> dict[str, Any]:
    info: dict[str, Any] = {
        "requested_device": requested_device,
        "selected_device": "cpu",
        "device": "cpu",
        "fallback_applied": False,
        "fallback_reason": "",
        "probe_success": False,
        "probe_summary": "",
        "torch_version": torch.__version__,
        "torch_cuda_build": getattr(torch.version, "cuda", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "force_device_env": os.getenv("KG_FORCE_DEVICE", ""),
    }

    if requested_device == "cpu":
        info["probe_success"] = True
        info["probe_summary"] = "按请求使用 CPU。"
        return info

    if info["torch_cuda_build"] is None:
        return _build_cpu_fallback_info(info, "当前 torch 为 CPU build，未编译 CUDA 支持。")

    if not info["cuda_available"] or info["cuda_device_count"] <= 0:
        return _build_cpu_fallback_info(info, "torch.cuda.is_available() 为 False，或未检测到可用 CUDA 设备。")

    try:
        tensor = torch.zeros(1, device="cuda")
        tensor.add_(1)
        torch.cuda.synchronize()
        info["selected_device"] = "cuda"
        info["device"] = "cuda"
        info["probe_success"] = True
        info["probe_summary"] = "CUDA 运行时探测成功。"
        info["gpu_name"] = torch.cuda.get_device_name(0)
        return info
    except Exception as exc:
        return _build_cpu_fallback_info(
            info,
            f"CUDA 运行时探测失败: {exc.__class__.__name__}: {exc}",
        )


def resolve_torch_device(prefer_gpu: bool = True, force_device: str | None = None) -> str:
    requested_device = _normalize_device_name(force_device, prefer_gpu=prefer_gpu)
    return _probe_requested_device(requested_device)["selected_device"]


def get_embedding_batch_size(device: str | None = None) -> int:
    resolved = device or resolve_torch_device()
    resolved = _normalize_device_name(resolved, prefer_gpu=True)
    return 32 if resolved == "cuda" else 8


def get_device_info(prefer_gpu: bool = True, force_device: str | None = None) -> dict[str, Any]:
    requested_device = _normalize_device_name(force_device, prefer_gpu=prefer_gpu)
    return dict(_probe_requested_device(requested_device))


def load_with_device_fallback(
    loader: Callable[[str], T],
    *,
    component: str,
    prefer_gpu: bool = True,
    force_device: str | None = None,
) -> tuple[T, dict[str, Any]]:
    runtime_info = get_device_info(prefer_gpu=prefer_gpu, force_device=force_device)
    initial_device = runtime_info["selected_device"]
    attempts: list[dict[str, Any]] = []

    try:
        resource = loader(initial_device)
        attempts.append({"device": initial_device, "success": True})
        runtime_info["component"] = component
        runtime_info["attempts"] = attempts
        return resource, runtime_info
    except Exception as exc:
        attempts.append(
            {
                "device": initial_device,
                "success": False,
                "error": f"{exc.__class__.__name__}: {exc}",
            }
        )
        if initial_device == "cpu":
            runtime_info["component"] = component
            runtime_info["attempts"] = attempts
            raise

        resource = loader("cpu")
        attempts.append({"device": "cpu", "success": True})
        previous_reason = runtime_info.get("fallback_reason", "").strip()
        fallback_reason = f"{component} 初始化在 {initial_device} 失败: {exc.__class__.__name__}: {exc}"
        if previous_reason:
            fallback_reason = f"{previous_reason} {fallback_reason}"
        runtime_info["selected_device"] = "cpu"
        runtime_info["device"] = "cpu"
        runtime_info["fallback_applied"] = True
        runtime_info["fallback_reason"] = fallback_reason
        runtime_info["probe_summary"] = f"模型加载已回退 CPU。原因: {fallback_reason}"
        runtime_info["component"] = component
        runtime_info["attempts"] = attempts
        return resource, runtime_info
