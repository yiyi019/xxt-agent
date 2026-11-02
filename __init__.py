# -*- coding: utf-8 -*-
"""
Xuexitong Agent Core Package.
Lightweight, headless, and agent-optimized course automation system.
"""
from .core.agent import XuexitongAgent
from .core.config import AgentConfig
from .core.solver import DeepSeekSolver
from .core.font_decoder import FontDecoder

__version__ = "1.0.0"
__all__ = ["XuexitongAgent", "AgentConfig", "DeepSeekSolver", "FontDecoder"]
