"""
Sets up basic config stuff like Environment (for LLM Keys etc), Logger, Paths to invoke modules like Node, uvx etc...
"""
import os
import logging
import shutil
from typing_extensions import override
from dotenv import load_dotenv

log_level_app = os.getenv("LLM_LOG_LEVEL_APP") or logging.DEBUG
log_level_external_libs = os.getenv("LLM_LOG_LEVEL_EXTERNAL_LIBS") or logging.WARNING

load_dotenv(os.getenv("LLM_KEY_FILE"), override=True)   # if the LLM_KEY_FILE variable is not set, it keeps traversing up the directory.

def get_basic_logger(logger_name: str = "", log_format: str = "", log_level_app: int = log_level_app, log_level_external_libs: int = log_level_external_libs):
    valid_log_levels = [logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
    if log_level_app not in valid_log_levels or log_level_external_libs not in valid_log_levels:
        raise ValueError(f"Invalid Log Level")
    if not log_format:
        log_format = "%(asctime)s - %(process)d - %(name)s - %(filename)s - %(funcName)s - %(lineno)d - %(levelname)s - %(message)s"
        
    logging.basicConfig(format=log_format, level=log_level_external_libs)
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger(__name__)
    logger.setLevel(log_level_app)
    return logger


def add_to_path_if_not_exists(new_paths):
    """
    Adds a list of directories to the system's PATH variable only if they aren't already present
    """
    current_path = os.getenv("PATH")
    path_separator = os.pathsep
    for new_path in new_paths:
        if new_path not in current_path:
            current_path += path_separator + new_paths
    return current_path


def set_required_path_env():
    node_path = os.path.dirname(shutil.which("node"))
    uvx_path = os.path.dirname(shutil.which("uvx"))
    npx_path = os.path.dirname(shutil.which("npx"))
    old_path = os.getenv("PATH")
    new_path = add_to_path_if_not_exists([node_path, npx_path, uvx_path])
    # Set PATH to the new_path
    if old_path != new_path:
        os.environ["PATH"] = new_path
