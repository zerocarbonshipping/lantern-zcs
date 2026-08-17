# SPDX-FileCopyrightText: 2026 Fonden Mærsk Mc-Kinney Møller Center for Zero Carbon Shipping
# SPDX-License-Identifier: Apache-2.0

import logging


def setup_logging(log_file_path=None):
    """
    Set up logging to output messages to both the console and a log file.
    Parameters:
        log_file_path: The path to the log file.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if logger.hasHandlers():
        logger.handlers.clear()
    if log_file_path is not None:
        file_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh = logging.FileHandler(log_file_path, mode='w')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_fmt)
        logger.addHandler(fh)
    console_fmt = logging.Formatter('%(message)s')
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_fmt)
    logger.addHandler(ch)

    # Silence noisy third-party loggers
    for name in ("choreographer", "kaleido"):
        logging.getLogger(name).setLevel(logging.WARNING)
