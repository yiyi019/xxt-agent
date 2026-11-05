# -*- coding: utf-8 -*-
"""
Xuexitong Agent Core Package.
Lightweight, headless, and agent-optimized course automation system.

The package exports are imported lazily so that lightweight helpers
(configuration, models, tool schema) can be used without Selenium installed.
"""

__version__ = "1.0.0"
__all__ = ["XXTAgent", "XXTConfig", "DeepSeekSolver", "FontDecoder"]

_LAZY = {
    "XXTAgent": "xxt_agent.agent",
    "XXTConfig": "xxt_agent.config",
    "DeepSeekSolver": "xxt_agent.ai_solver",
    "FontDecoder": "xxt_agent.font_decoder",
}


def __getattr__(name):
    if name in _LAZY:
        import importlib

        value = getattr(importlib.import_module(_LAZY[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'xxt_agent' has no attribute {name!r}")
