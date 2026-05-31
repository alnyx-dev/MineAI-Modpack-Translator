"""Application entry point.

Initializes logging as early as possible so every module that imports
mineai.logger.get_logger() gets a fully configured logger attached to
the rotating file handler and the console handler.
"""

from mineai.logger import setup_logging, get_logger, current_log_path


def main() -> None:
  setup_logging()
  log = get_logger(__name__)
  log.info("MineAI Modpack Translator starting")
  log.info("Session log: %s", current_log_path())

  # Import the GUI lazily so any import-time errors are captured by the
  # logger we just configured.
  from mineai.gui.app import run

  try:
      run()
  except Exception:
      log.exception("Unhandled exception in GUI main loop")
      raise
  finally:
      log.info("MineAI Modpack Translator shutting down")


if __name__ == "__main__":
  main()
