"""Allow running the MCP server via: python -m ovi_cards"""
try:
    from .mcp_server import main
except ImportError:
    import sys
    print("MCP server requires the 'mcp' extra: pip install ovi-cards[mcp]", file=sys.stderr)
    sys.exit(1)

main()
