import json
import os
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))


def config_path():
    return os.path.join(BASE, "config.json")


def data_path():
    return os.path.join(BASE, "data.json")


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    fd, tmp = tempfile.mkstemp(dir=BASE, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise