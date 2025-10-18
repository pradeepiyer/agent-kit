# ABOUTME: User directory path management with auto-detection for downstream projects.
# ABOUTME: Allows customization of ~/.agent-kit to ~/.custom-name via programmatic API or auto-detection.

import os
import sys
from pathlib import Path

# Module-level cache for app name
_app_name: str | None = None


def set_app_name(name: str) -> None:
    """Set the application name for user directory paths.

    This should be called before any imports that use get_user_dir().

    Args:
        name: Application name (e.g., "my-awesome-agent")

    Example:
        >>> set_app_name("my-awesome-agent")
        >>> get_user_dir()
        PosixPath('/home/user/.my-awesome-agent')
    """
    global _app_name
    _app_name = name


def get_app_name() -> str:
    """Get the application name for user directory paths.

    Priority order:
    1. Explicitly set via set_app_name()
    2. Environment variable AGENT_KIT_APP_NAME
    3. Auto-detect from __main__ module
    4. Fallback to "agent-kit"

    Returns:
        Application name string
    """
    global _app_name

    # Return cached value if explicitly set
    if _app_name is not None:
        return _app_name

    # Check environment variable
    if env_name := os.getenv("AGENT_KIT_APP_NAME"):
        _app_name = env_name
        return _app_name

    # Auto-detect from __main__
    _app_name = _detect_app_name()
    return _app_name


def _detect_app_name() -> str:
    """Auto-detect application name from __main__ module."""
    try:
        import __main__

        # Try __main__.__package__ (e.g., "my_agent" when running python -m my_agent)
        if hasattr(__main__, "__package__") and __main__.__package__:
            package_name = __main__.__package__
            # Convert underscores to hyphens for directory name
            return package_name.replace("_", "-")

        # Try __main__.__file__ directory name
        if hasattr(__main__, "__file__") and __main__.__file__:
            file_path = Path(__main__.__file__)
            # Get the parent directory name if it looks like a package
            if file_path.parent.name not in {"bin", "scripts", "site-packages"}:
                return file_path.parent.name.replace("_", "-")
    except Exception:
        pass

    # Try sys.argv[0] as last resort
    try:
        if sys.argv and sys.argv[0]:
            script_name = Path(sys.argv[0]).stem
            if script_name and script_name not in {"python", "python3", "pytest"}:
                return script_name.replace("_", "-")
    except Exception:
        pass

    # Fallback to default
    return "agent-kit"


def get_user_dir() -> Path:
    """Get the user configuration directory path.

    Returns path like ~/.{app-name} based on get_app_name().

    Returns:
        Path to user directory (not guaranteed to exist)

    Example:
        >>> get_user_dir()
        PosixPath('/home/user/.agent-kit')
    """
    return Path.home() / f".{get_app_name()}"
