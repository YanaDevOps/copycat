import logging
import os
import glob
import time
from logging.handlers import TimedRotatingFileHandler


class SizeAndTimeRotatingFileHandler(TimedRotatingFileHandler):
    def __init__(
        self,
        *args,
        max_bytes: int = 0,
        retention_days: int = 7,
        **kwargs,
    ):
        self.max_bytes = max_bytes
        self.retention_days = retention_days
        self._rollover_reason = "time"
        super().__init__(*args, **kwargs)

    def shouldRollover(self, record):
        if super().shouldRollover(record):
            self._rollover_reason = "time"
            return True
        if self.max_bytes <= 0:
            return False
        if self.stream is None:
            self.stream = self._open()
        message = f"{self.format(record)}\n"
        self.stream.seek(0, os.SEEK_END)
        should_rollover = (
            self.stream.tell() + len(message.encode("utf-8")) >= self.max_bytes
        )
        if should_rollover:
            self._rollover_reason = "size"
        return should_rollover

    def doRollover(self):
        if self._rollover_reason != "size":
            super().doRollover()
            self._delete_old_logs()
            return

        if self.stream:
            self.stream.close()
            self.stream = None

        current_time = int(time.time())
        time_tuple = time.gmtime(current_time) if self.utc else time.localtime(current_time)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time_tuple)
        destination = f"{self.baseFilename}.{timestamp}"
        counter = 1
        while os.path.exists(destination):
            destination = f"{self.baseFilename}.{timestamp}.{counter}"
            counter += 1

        if os.path.exists(self.baseFilename):
            self.rotate(self.baseFilename, destination)

        if not self.delay:
            self.stream = self._open()

        self.rolloverAt = self.computeRollover(current_time)
        while self.rolloverAt <= current_time:
            self.rolloverAt += self.interval
        self._delete_old_logs()

    def _delete_old_logs(self):
        candidates = [
            path
            for path in glob.glob(f"{self.baseFilename}.*")
            if os.path.isfile(path)
        ]
        if self.retention_days > 0:
            cutoff = time.time() - self.retention_days * 24 * 60 * 60
            for path in candidates:
                try:
                    if os.path.getmtime(path) < cutoff:
                        os.remove(path)
                except OSError:
                    logger.exception("Failed to remove old log file '%s'.", path)
            candidates = [
                path
                for path in glob.glob(f"{self.baseFilename}.*")
                if os.path.isfile(path)
            ]
        if self.backupCount <= 0:
            return
        candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        for path in candidates[self.backupCount :]:
            try:
                os.remove(path)
            except OSError:
                logger.exception("Failed to remove old log file '%s'.", path)


def _env_bool(key: str, default: bool) -> bool:
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s]: %(message)s", "%Y-%m-%d %H:%M:%S"
)
log_level = os.environ.get("COPYCAT_LOG_LEVEL") or os.environ.get("LOGLEVEL", "INFO")
log_level = log_level.upper()
log_to_file = _env_bool("COPYCAT_LOG_TO_FILE", True)
data_root = os.environ.get("COPYCAT_PATH", "/data")
default_log_file = os.path.join(data_root, ".copycat", "logs", "copycat.log")
log_file = os.environ.get("COPYCAT_LOG_FILE", default_log_file)
log_retention_days = _env_int("COPYCAT_LOG_RETENTION_DAYS", 7)
log_backup_count = _env_int("COPYCAT_LOG_BACKUP_COUNT", log_retention_days)
log_max_bytes = _env_int("COPYCAT_LOG_MAX_BYTES", 10 * 1024 * 1024)
access_log_enabled = _env_bool("COPYCAT_ACCESS_LOG", True)

# Internal
logger = logging.getLogger()
logger.handlers.clear()
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(log_level)

if log_to_file:
    try:
        if not os.path.isdir(data_root):
            raise FileNotFoundError(
                f"COPYCAT_PATH '{data_root}' is not available for file logging."
            )
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = SizeAndTimeRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=log_backup_count,
            encoding="utf-8",
            utc=True,
            max_bytes=log_max_bytes,
            retention_days=log_retention_days,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        logger.exception("Failed to initialize file logging at '%s'.", log_file)


# Uvicorn
class HealthEndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not access_log_enabled:
            return False
        return (
            record.args
            and len(record.args) >= 3
            and record.args[2] != "/health"
        )


uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(HealthEndpointFilter())
for handler in uvicorn_logger.handlers:
    handler.setFormatter(formatter)
uvicorn_logger.setLevel(log_level)
