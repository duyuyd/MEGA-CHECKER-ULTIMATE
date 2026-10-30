from __future__ import annotations
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = {
    "workers": 5,
    "dns_timeout_seconds": 4.0,
    "database": "mega_database_v9.db",
    "backup_directory": "backups",
    "disposable_domains_file": "data/disposable_domains.txt",
    "log_file": "logs/mega_checker.log",
    "log_level": "INFO",
}

def load_config(path: Path | None = None) -> dict:
    path = Path(path or (BASE_DIR / "config.json"))
    if not path.is_absolute():
        path = BASE_DIR / path
    data = dict(DEFAULT_CONFIG)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Không đọc được config {path}: {type(exc).__name__}") from exc
        if not isinstance(loaded, dict):
            raise ValueError("config.json phải là một JSON object.")
        data.update({k: v for k, v in loaded.items() if k in DEFAULT_CONFIG})
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        data["workers"] = max(1, min(32, int(data["workers"])))
        data["dns_timeout_seconds"] = max(1.0, min(15.0, float(data["dns_timeout_seconds"])))
    except (TypeError, ValueError) as exc:
        raise ValueError("workers hoặc dns_timeout_seconds trong config không hợp lệ.") from exc
    level = str(data["log_level"]).upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("log_level phải là DEBUG/INFO/WARNING/ERROR/CRITICAL.")
    data["log_level"] = level
    for key in ("database", "backup_directory", "disposable_domains_file", "log_file"):
        value = Path(str(data[key])).expanduser()
        data[key] = str((path.parent / value).resolve() if not value.is_absolute() else value.resolve())
    return data

def setup_logging(config: dict) -> logging.Logger:
    logger = logging.getLogger("MegaCheckerUltimate")
    if logger.handlers:
        return logger
    log_path = Path(config["log_file"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(getattr(logging, config["log_level"], logging.INFO))
    handler = RotatingFileHandler(log_path, maxBytes=1_500_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
