"""
Media control abstraction -- see media_controller.MediaController.

Nothing in desktop_pet/ imports a specific backend directly; it only
calls MediaController's is_available()/is_playing()/play()/pause()/
rewind()/forward(), per section 11 of the integration spec.
"""

from media_control.media_controller import MediaController

__all__ = ["MediaController"]
