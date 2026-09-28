"""
Pure-Python stand-in for the `uuid_utils` package.

Why this exists: the real package ships a compiled file (_uuid_utils.pyd)
that Windows Smart App Control blocks ("An Application Control policy has
blocked this file"). LangChain/LangGraph and LangSmith only use one thing
from it — uuid_utils.compat.uuid7 — so this folder provides that function
in plain Python. Streamlit puts the project folder first on Python's search
path, so this stand-in is found before the blocked one.
"""

from .compat import uuid7

__all__ = ["uuid7"]