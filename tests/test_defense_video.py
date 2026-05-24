from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_video_builder():
    script = Path("scripts/build_defense_video.py")
    spec = importlib.util.spec_from_file_location("build_defense_video", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_defense_video_timeline_is_exactly_one_minute():
    module = _load_video_builder()

    assert sum(segment.duration for segment in module.SEGMENTS) == 60


def test_defense_video_uses_versioned_demo_screenshots():
    module = _load_video_builder()

    filenames = [segment.filename for segment in module.SEGMENTS]
    assert len(filenames) == len(set(filenames))
    for filename in filenames:
        assert (module.SCREENSHOT_DIR / filename).exists()
