"""
Desktop pet module -- the cat escalation overlay.

This package is intentionally self-contained: nothing outside it
(intervention_manager.py, main.py) needs to know how the cat is drawn
or animated, only the small CatController surface in cat_controller.py.
See cat_controller.CatController for the entry point.
"""

from desktop_pet.cat_controller import CatController

__all__ = ["CatController"]
