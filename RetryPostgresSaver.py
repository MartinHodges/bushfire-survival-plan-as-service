import os
import time
import logging
import psycopg
from langgraph.checkpoint.postgres import PostgresSaver


logger = logging.getLogger(__name__)

class RetryPostgresSaver:
    def __init__(self, max_retries=3, retry_delay=5):
      """Create PostgreSQL checkpointer for LangGraph state persistence with retry logic"""
      
      # Database connection string
      db_host = os.getenv('POSTGRES_HOST', 'kates-storage.home.b30')
      db_port = os.getenv('POSTGRES_PORT', '5432')
      db_name = os.getenv('POSTGRES_DB', 'bushfire_plans')
      db_user = os.getenv('POSTGRES_USER', 'bushfire_user')
      db_password = os.getenv('POSTGRES_PASSWORD', '')
      
      self.connection_string = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?options=-csearch_path%3Dbushfire_plans"
      self.max_retries = max_retries
      self.retry_delay = retry_delay
      self._saver = None
      self._connect()
    
    def _connect(self):
        for attempt in range(self.max_retries):
            try:
                connection = psycopg.connect(self.connection_string, autocommit=True)
                self._saver = PostgresSaver(connection)
                try:
                    self._saver.setup()
                except Exception as setup_error:
                    # Check if this is a warning-level error (non-fatal)
                    error_msg = str(setup_error).lower()

                    warning_indicators = [
                        "already exists",
                        "duplicate", 
                        "relation already exists",
                        "column already exists"
                    ]
                    
                    if any(indicator in error_msg for indicator in warning_indicators):
                        logger.warning(f"Schema setup warning (ignoring): {setup_error}")
                    else:
                        # This is a real error, re-raise it
                        logger.error(f"Schema setup failed: {setup_error}")
                        raise setup_error
                logger.info(f"PostgreSQL connected on attempt {attempt + 1}")
                return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error("All PostgreSQL connection attempts failed - service degraded")
                    raise ConnectionError("PostgreSQL unavailable - cannot persist session state")
    
    def __getattr__(self, name):
        try:
            return getattr(self._saver, name)
        except Exception as e:
            logger.warning(f"Operation failed, retrying connection: {e}")
            self._connect()
            return getattr(self._saver, name)
