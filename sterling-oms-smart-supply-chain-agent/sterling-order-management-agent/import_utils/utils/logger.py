import logging


# Suppress the warning message when importing tool files.
class NoToolTypeWarning(logging.Filter):
    """Filter for finding "tool type hint" warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Args:
            record: log record

        Returns:
            True if warning is not a "tool type hint" warning
        """
        filter_msg = "Missing type hint for tool property"
        return not record.getMessage().startswith(filter_msg)


def suppress_tool_type_hint_warning() -> None:
    """Public function for suppressing warnings."""
    logging.getLogger("ibm_watsonx_orchestrate.agent_builder.tools.python_tool").addFilter(
        NoToolTypeWarning()
    )


def get_logger(module_name: str) -> logging.Logger:
    """
    Setup and get a formatted logger.

    If we want to output the log, update logging.

    Args:
        module_name: file that is fetching the logger.

    Returns:
        logger with a specific format
    """
    logger = logging.getLogger(module_name)
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(levelname)s [%(name)s] - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
