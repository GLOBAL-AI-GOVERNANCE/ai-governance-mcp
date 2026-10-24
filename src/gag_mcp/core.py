"""Deprecated alias of ``gaig_mcp.core``. Import ``gaig_mcp.core`` instead."""

import sys

from gaig_mcp import core as _core

sys.modules[__name__] = _core
