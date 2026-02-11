"""Uthana Blender Plugin UI Module.

This module provides all UI components for the Uthana plugin including:
- Property definitions (PropertyGroup)
- Operators
- Modal operators for async operations
- Panels
- UIList classes for asset browsing
"""

from . import lists, modal_operators, operators, panels, properties

# Collect all classes for registration
# Order matters: PropertyGroups first, then UILists, then Operators, then Panels
classes = (
    *properties.classes,
    *lists.classes,
    *operators.classes,
    *modal_operators.classes,
    *panels.classes,
)

# Export the UthanaProperties class for easy access
UthanaProperties = properties.UthanaProperties
