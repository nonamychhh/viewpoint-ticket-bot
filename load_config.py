import json
import logging

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler(f"logs/{__name__}.log", mode='a',encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

def load_config() -> dict:
    """Загружает конфигурацию из файла"""
    try:
        with open("data/config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except FileNotFoundError:
        logger.error("Файл конфигурации не найден")
        return {}
    except json.JSONDecodeError:
        logger.error("Ошибка декодирования конфигурации")
        return {}

def save_config(config):
    """Сохраняет конфигурацию в файл"""
    try:
        with open("data/config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
            logger.info("Конфигурация сохранена")
    except Exception as e:
        logger.error(f"Ошибка сохранения конфигурации: {str(e)}")