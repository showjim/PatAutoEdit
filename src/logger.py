'''
Logging module for PatAutoEdit
Provides unified logging to both console and GUI callback.
'''


class Logger:
    """Unified logger that outputs to both console (print) and GUI callback.
    
    Usage:
        # With GUI callback (Tkinter or Streamlit)
        logger = Logger(gui_callback=self.put_data_log)
        logger.info("Processing file...")
        logger.error("Something went wrong")
        
        # Without GUI (console only)
        logger = Logger()
        logger.info("Processing file...")
    """

    def __init__(self, gui_callback=None):
        """
        Args:
            gui_callback: Optional callable that accepts a string message.
                          e.g., Tkinter's put_data_log or Streamlit's send_log.
        """
        self.gui_callback = gui_callback

    def _log(self, prefix, msg):
        """Internal log method that sends to both console and GUI."""
        full_msg = f"{prefix}: {msg}"
        print(full_msg)
        if self.gui_callback:
            self.gui_callback(full_msg)

    def info(self, msg):
        """Log an informational message."""
        self._log("Info", msg)

    def error(self, msg):
        """Log an error message."""
        self._log("Error", msg)

    def warning(self, msg):
        """Log a warning message."""
        self._log("Warning", msg)

    def put(self, msg):
        """Log a raw message without prefix (for multiprocessing queue compatibility)."""
        print(msg)
        if self.gui_callback:
            self.gui_callback(msg)
