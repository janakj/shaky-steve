import logging

def init_logging(verbose):
    if verbose == 0:
        level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    if verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level)
