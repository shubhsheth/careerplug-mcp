import fastmcp

mcp = fastmcp.FastMCP("careerplug")


@mcp.tool
def list_jobs() -> list:
    """List all open jobs."""
    return []


@mcp.tool
def list_applicants() -> list:
    """List all applicants."""
    return []


if __name__ == "__main__":
    mcp.run()
