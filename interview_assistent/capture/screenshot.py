from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def _is_blank_image(image_bytes: bytes, threshold: float = 0.01) -> bool:
    from PIL import Image
    import numpy as np

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pixels = np.asarray(image)
    non_black = np.any(pixels > 8, axis=2).sum()
    ratio = non_black / pixels.shape[0] / pixels.shape[1]
    return ratio < threshold


def _content_score(image_bytes: bytes) -> float:
    from PIL import Image
    import numpy as np

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pixels = np.asarray(image, dtype=np.float32)
    brightness = pixels.mean(axis=2)
    active_ratio = (brightness > 8).mean()
    variance = brightness.var() / 6500.0
    return active_ratio * 0.7 + min(variance, 1.0) * 0.3


def _list_monitors() -> list[dict]:
    try:
        import mss
    except ImportError:
        return []

    with mss.mss() as sct:
        return list(sct.monitors[1:])


def _capture_monitor_bbox(monitor: dict) -> bytes | None:
    try:
        import pyscreenshot as ImageGrab
    except ImportError:
        return None

    bbox = (
        monitor["left"],
        monitor["top"],
        monitor["left"] + monitor["width"],
        monitor["top"] + monitor["height"],
    )
    session = os.getenv("XDG_SESSION_TYPE", "").lower()
    backends = (
        ["freedesktop_dbus", "gnome_dbus", "grim", "mss"]
        if session == "wayland"
        else ["mss", "grim", "freedesktop_dbus"]
    )

    for backend in backends:
        try:
            image = ImageGrab.grab(bbox=bbox, backend=backend)
        except Exception as exc:
            logger.debug("bbox capture via %s failed: %s", backend, exc)
            continue

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data = buffer.getvalue()
        if data and not _is_blank_image(data):
            logger.info(
                "Captured monitor %s via %s",
                monitor.get("output", bbox),
                backend,
            )
            return data
    return None


def _capture_with_grim(output: str | None = None) -> bytes | None:
    if not shutil.which("grim"):
        return None
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        cmd = ["grim", str(path)]
        if output:
            cmd = ["grim", "-o", output, str(path)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=10)
        return path.read_bytes()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("grim capture failed: %s", exc)
        return None
    finally:
        path.unlink(missing_ok=True)


def _capture_with_gnome_screenshot() -> bytes | None:
    if not shutil.which("gnome-screenshot"):
        return None
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        subprocess.run(
            ["gnome-screenshot", "-f", str(path)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return path.read_bytes()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("gnome-screenshot capture failed: %s", exc)
        return None
    finally:
        path.unlink(missing_ok=True)


def _capture_with_mss(monitor_index: int = 1) -> bytes | None:
    try:
        import mss
        import mss.tools
    except ImportError:
        return None

    with mss.mss() as sct:
        if monitor_index >= len(sct.monitors):
            return None
        monitor = sct.monitors[monitor_index]
        shot = sct.grab(monitor)
        return mss.tools.to_png(shot.rgb, shot.size)


def _pick_best_monitor(monitors: list[dict]) -> tuple[dict, bytes]:
    best_monitor: dict | None = None
    best_data: bytes | None = None
    best_score = -1.0
    errors: list[str] = []

    for index, monitor in enumerate(monitors, start=1):
        try:
            data = _capture_monitor_bbox(monitor)
        except Exception as exc:
            errors.append(f"monitor {index}: {exc}")
            continue

        if not data:
            errors.append(f"monitor {index}: capture failed")
            continue
        if _is_blank_image(data):
            errors.append(f"monitor {index}: blank")
            continue

        score = _content_score(data)
        logger.info(
            "Monitor %s (%s) content score %.3f",
            index,
            monitor.get("output", "?"),
            score,
        )
        if score > best_score:
            best_score = score
            best_monitor = monitor
            best_data = data

    if best_monitor and best_data:
        return best_monitor, best_data

    raise RuntimeError(
        "No active display found. If you disconnected a second monitor, "
        "use Paste image or Upload image instead. "
        + ("; ".join(errors[-3:]) if errors else "")
    )


def capture_primary_monitor(monitor: str = "auto") -> bytes:
    """Capture a display as PNG bytes.

    monitor:
      - "auto": pick the non-blank monitor with the most on-screen content
      - "1", "2", ...: mss monitor index (1 = primary)
      - output name like "eDP-1" or "HDMI-1" when available
    """
    monitors = _list_monitors()
    if not monitors:
        legacy_captures: list[tuple[str, Callable[[], bytes | None]]] = [
            ("grim", lambda: _capture_with_grim()),
            ("gnome-screenshot", _capture_with_gnome_screenshot),
            ("mss", lambda: _capture_with_mss(1)),
        ]
        for name, capture in legacy_captures:
            data = capture()
            if data and not _is_blank_image(data):
                return data
        raise RuntimeError("No display found for screenshot capture.")

    if monitor and monitor.lower() != "auto":
        if monitor.isdigit():
            index = int(monitor)
            if index < 1 or index > len(monitors):
                raise RuntimeError(
                    f"Monitor {index} not available. Connected displays: {len(monitors)}. "
                    "Use SCREEN_MONITOR=auto or Paste/Upload instead."
                )
            data = _capture_monitor_bbox(monitors[index - 1])
            if not data or _is_blank_image(data):
                raise RuntimeError(
                    f"Monitor {index} is blank or unavailable. "
                    "Try SCREEN_MONITOR=auto, or use Paste/Upload."
                )
            return data

        for mon in monitors:
            if mon.get("output") == monitor:
                data = _capture_monitor_bbox(mon)
                if data and not _is_blank_image(data):
                    return data
                raise RuntimeError(f"Monitor {monitor} is blank. Try SCREEN_MONITOR=auto.")

    _, data = _pick_best_monitor(monitors)
    return data