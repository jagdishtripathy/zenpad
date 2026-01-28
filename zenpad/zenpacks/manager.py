"""
Zenpack Manager - Discovery, Loading, and Lifecycle Management

This module provides the ZenpackManager class which handles:
- Discovering installed Zenpacks
- Loading and unloading Zenpacks
- Managing enabled/disabled state
- Emitting hooks to all active Zenpacks
"""

import os
import sys
import json
import importlib.util
from .api import ZenpackAPI


class ZenpackManager:
    """
    Manages the lifecycle of all Zenpacks.
    
    The ZenpackManager is responsible for:
    - Discovering Zenpacks in ~/.config/zenpad/zenpacks/
    - Loading enabled Zenpacks on startup
    - Providing hook emission to all active Zenpacks
    - Enabling/disabling Zenpacks at runtime
    """
    
    def __init__(self, window):
        """
        Initialize the Zenpack Manager.
        
        Args:
            window: ZenpadWindow instance
        """
        self._window = window
        self._zenpacks = {}  # id -> {"instance": Zenpack, "api": ZenpackAPI, "manifest": dict}
        self._zenpacks_dir = os.path.expanduser("~/.config/zenpad/zenpacks")
        self._enabled_file = os.path.join(self._zenpacks_dir, "enabled.json")
        
        # Ensure zenpacks directory exists
        os.makedirs(self._zenpacks_dir, exist_ok=True)
    
    # ═══════════════════════════════════════════════════════════════
    # DISCOVERY
    # ═══════════════════════════════════════════════════════════════
    
    def discover_zenpacks(self) -> list:
        """
        Discover all installed Zenpacks.
        
        Returns:
            list: List of manifest dictionaries for all valid Zenpacks
        """
        zenpacks = []
        
        if not os.path.exists(self._zenpacks_dir):
            return zenpacks
        
        for item in os.listdir(self._zenpacks_dir):
            zenpack_path = os.path.join(self._zenpacks_dir, item)
            manifest_path = os.path.join(zenpack_path, "manifest.json")
            
            if os.path.isdir(zenpack_path) and os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                        manifest['_path'] = zenpack_path
                        zenpacks.append(manifest)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"[Zenpacks] Invalid manifest in '{item}': {e}")
        
        return zenpacks
    
    def get_enabled_ids(self) -> list:
        """
        Get list of enabled Zenpack IDs.
        
        Returns:
            list: List of enabled Zenpack IDs
        """
        if os.path.exists(self._enabled_file):
            try:
                with open(self._enabled_file, 'r') as f:
                    data = json.load(f)
                    return data.get("enabled", [])
            except (json.JSONDecodeError, IOError):
                pass
        return []
    
    def _save_enabled_ids(self, enabled_ids: list):
        """Save the list of enabled Zenpack IDs."""
        with open(self._enabled_file, 'w') as f:
            json.dump({"enabled": enabled_ids}, f, indent=2)
    
    # ═══════════════════════════════════════════════════════════════
    # LOADING
    # ═══════════════════════════════════════════════════════════════
    
    def load_enabled_zenpacks(self):
        """
        Load all enabled Zenpacks.
        
        This should be called once during Zenpad startup.
        """
        enabled_ids = self.get_enabled_ids()
        available = self.discover_zenpacks()
        
        for manifest in available:
            zenpack_id = manifest.get("id")
            if zenpack_id in enabled_ids:
                self.load_zenpack(zenpack_id, manifest)
    
    def load_zenpack(self, zenpack_id: str, manifest: dict = None) -> bool:
        """
        Load and activate a specific Zenpack.
        
        Args:
            zenpack_id: ID of the Zenpack to load
            manifest: Optional manifest dict (will discover if not provided)
        
        Returns:
            bool: True if loaded successfully
        """
        # Already loaded?
        if zenpack_id in self._zenpacks:
            print(f"[Zenpacks] '{zenpack_id}' is already loaded")
            return True
        
        # Find manifest if not provided
        if manifest is None:
            for m in self.discover_zenpacks():
                if m.get("id") == zenpack_id:
                    manifest = m
                    break
        
        if manifest is None:
            print(f"[Zenpacks] '{zenpack_id}' not found")
            return False
        
        zenpack_path = manifest.get('_path')
        if not zenpack_path:
            zenpack_path = os.path.join(self._zenpacks_dir, zenpack_id)
        
        entry_point = manifest.get("entry_point", "zenpack.py")
        class_name = manifest.get("class_name", "Zenpack")
        permissions = manifest.get("permissions", [])
        
        entry_file = os.path.join(zenpack_path, entry_point)
        
        if not os.path.exists(entry_file):
            print(f"[Zenpacks] Entry point not found: {entry_file}")
            return False
        
        try:
            # Dynamically load the module
            spec = importlib.util.spec_from_file_location(
                f"zenpack_{zenpack_id}", entry_file
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Get the Zenpack class
            zenpack_class = getattr(module, class_name)
            
            # Create instance
            instance = zenpack_class()
            instance.id = zenpack_id
            instance.name = manifest.get("name", zenpack_id)
            instance.version = manifest.get("version", "0.0.0")
            instance.description = manifest.get("description", "")
            instance.author = manifest.get("author", "Unknown")
            
            # Create API
            api = ZenpackAPI(self._window, zenpack_id, permissions)
            
            # Activate the Zenpack
            instance.activate(api)
            
            # Store reference
            self._zenpacks[zenpack_id] = {
                "instance": instance,
                "api": api,
                "manifest": manifest
            }
            
            print(f"[Zenpacks] Loaded '{zenpack_id}' v{instance.version}")
            return True
            
        except Exception as e:
            print(f"[Zenpacks] Failed to load '{zenpack_id}': {e}")
            return False
    
    def unload_zenpack(self, zenpack_id: str) -> bool:
        """
        Unload and deactivate a Zenpack.
        
        Args:
            zenpack_id: ID of the Zenpack to unload
        
        Returns:
            bool: True if unloaded successfully
        """
        if zenpack_id not in self._zenpacks:
            return False
        
        try:
            zp = self._zenpacks[zenpack_id]
            zp["instance"].deactivate()
            del self._zenpacks[zenpack_id]
            print(f"[Zenpacks] Unloaded '{zenpack_id}'")
            return True
        except Exception as e:
            print(f"[Zenpacks] Error unloading '{zenpack_id}': {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # ENABLE / DISABLE
    # ═══════════════════════════════════════════════════════════════
    
    def enable_zenpack(self, zenpack_id: str) -> bool:
        """
        Enable a Zenpack (load it and add to enabled list).
        """
        enabled = self.get_enabled_ids()
        if zenpack_id not in enabled:
            enabled.append(zenpack_id)
            self._save_enabled_ids(enabled)
        
        return self.load_zenpack(zenpack_id)
    
    def disable_zenpack(self, zenpack_id: str) -> bool:
        """
        Disable a Zenpack (unload it and remove from enabled list).
        """
        enabled = self.get_enabled_ids()
        if zenpack_id in enabled:
            enabled.remove(zenpack_id)
            self._save_enabled_ids(enabled)
        
        return self.unload_zenpack(zenpack_id)
    
    def is_enabled(self, zenpack_id: str) -> bool:
        """Check if a Zenpack is enabled."""
        return zenpack_id in self.get_enabled_ids()
    
    def is_loaded(self, zenpack_id: str) -> bool:
        """Check if a Zenpack is currently loaded."""
        return zenpack_id in self._zenpacks
    
    # ═══════════════════════════════════════════════════════════════
    # HOOKS
    # ═══════════════════════════════════════════════════════════════
    
    def emit_hook(self, hook_name: str, *args):
        """
        Emit a hook to all loaded Zenpacks.
        
        Args:
            hook_name: Name of the hook (e.g., "on_file_save")
            *args: Arguments to pass to hook callbacks
        """
        for zenpack_id, zp in self._zenpacks.items():
            try:
                zp["api"]._call_hooks(hook_name, *args)
            except Exception as e:
                print(f"[Zenpacks] Hook error in '{zenpack_id}': {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_loaded_zenpacks(self) -> list:
        """
        Get list of currently loaded Zenpacks.
        
        Returns:
            list: List of (id, name, version) tuples
        """
        result = []
        for zp_id, zp in self._zenpacks.items():
            instance = zp["instance"]
            result.append((zp_id, instance.name, instance.version))
        return result
    
    def shutdown(self):
        """
        Unload all Zenpacks. Called when Zenpad closes.
        """
        self.emit_hook("on_shutdown")
        
        for zenpack_id in list(self._zenpacks.keys()):
            self.unload_zenpack(zenpack_id)
