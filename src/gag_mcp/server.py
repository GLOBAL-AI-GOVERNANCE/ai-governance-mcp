"""Deprecated alias of ``gaig_mcp.server``. Use ``gaig-mcp`` or ``python -m gaig_mcp.server``."""

if __name__ == "__main__":
    from gaig_mcp.server import main

    main()
else:
    import sys

    from gaig_mcp import server as _server

    sys.modules[__name__] = _server
