import logging


def get_logger(name: str = "DomainsValidation", verbose: bool = False) -> logging.Logger:
    """
    Set up a logger.

    Args:
        name: Name of the logger, defaults to "DomainsValidation"
        verbose: Whether to enable verbose (debug) logging. Defaults to
            False.

    Returns:
        a logger instance
    """
    logging.basicConfig()
    logger = logging.getLogger(name)
    if verbose:
        logger.setLevel(level=logging.DEBUG)
    else:
        logger.setLevel(level=logging.INFO)
    # add formatter if needed
    return logger
