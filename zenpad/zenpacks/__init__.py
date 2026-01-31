"""
Zenpacks - Zenpad Extension System

This package provides the extension/plugin system for Zenpad.
Zenpacks are lightweight, keyboard-first extensions that enhance Zenpad's functionality.
"""

from .base import Zenpack
from .api import ZenpackAPI
from .manager import ZenpackManager

__all__ = ['Zenpack', 'ZenpackAPI', 'ZenpackManager']
