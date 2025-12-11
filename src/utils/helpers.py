"""
Utility functions for the Creative Intelligence Engine.
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config.config import LOGS_DIR


def setup_logging(log_level: str = "INFO"):
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handler
    logger.remove()
    
    # Add console handler with colors
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True,
    )
    
    # Add file handler for all logs
    log_file = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
    )
    
    # Add file handler for errors only
    error_log = LOGS_DIR / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
    logger.add(
        error_log,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
    )
    
    logger.info(f"Logging initialized - level: {log_level}")


def load_json(file_path: str | Path) -> Optional[dict | list]:
    """
    Load JSON from a file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON data or None if failed
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        logger.warning(f"JSON file not found: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


def save_json(data: Any, file_path: str | Path, indent: int = 2) -> bool:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        file_path: Path to save to
        indent: JSON indentation level
        
    Returns:
        True if successful, False otherwise
    """
    file_path = Path(file_path)
    
    try:
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, default=str)
        
        logger.debug(f"Saved JSON to {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving to {file_path}: {e}")
        return False


def get_file_hash(file_path: str | Path) -> Optional[str]:
    """
    Calculate MD5 hash of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MD5 hash string or None if failed
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        return None
    
    try:
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
        
    except Exception as e:
        logger.error(f"Error hashing {file_path}: {e}")
        return None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string for use as a filename.
    
    Args:
        filename: Original filename string
        
    Returns:
        Sanitized filename
    """
    # Remove/replace invalid characters
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Limit length
    if len(filename) > 200:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:195] + ('.' + ext if ext else '')
    
    return filename


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2m 30s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Original text
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def create_ad_id(competitor: str, platform: str, content_hash: str) -> str:
    """
    Create a unique ad ID.
    
    Args:
        competitor: Competitor name
        platform: Ad platform
        content_hash: Hash of ad content
        
    Returns:
        Unique ad ID
    """
    competitor_short = competitor[:10].lower().replace(' ', '_')
    platform_short = platform[:3].lower()
    return f"{competitor_short}_{platform_short}_{content_hash[:8]}"

