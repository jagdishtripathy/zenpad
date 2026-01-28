"""
Zenpack Base Class

All Zenpacks must inherit from this base class and implement
the activate() and deactivate() methods.
"""


class Zenpack:
    """
    Base class for all Zenpacks.
    
    A Zenpack is a lightweight extension that adds functionality to Zenpad.
    Each Zenpack must implement activate() and optionally deactivate().
    
    Example:
        class WordCountZenpack(Zenpack):
            def activate(self, api):
                self.api = api
                api.register_hook("on_text_changed", self.update_count)
            
            def update_count(self):
                text = self.api.get_current_text()
                self.api.show_status(f"Words: {len(text.split())}")
            
            def deactivate(self):
                self.api.show_status("")
    """
    
    # Zenpack metadata (set by manager from manifest.json)
    id = None
    name = None
    version = None
    description = None
    author = None
    
    def activate(self, api):
        """
        Called when the Zenpack is loaded and enabled.
        
        Args:
            api: ZenpackAPI instance providing sandboxed access to Zenpad.
        
        Override this method to initialize your Zenpack, register hooks,
        and set up any required state.
        """
        raise NotImplementedError("Zenpacks must implement activate()")
    
    def deactivate(self):
        """
        Called when the Zenpack is disabled or Zenpad is closing.
        
        Override this method to clean up resources, unregister callbacks,
        and reset any UI changes made by the Zenpack.
        """
        pass  # Optional - not all Zenpacks need cleanup
