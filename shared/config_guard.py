from pathlib import Path
import json
import tempfile
import shutil

def safe_write_json(path, data, ensure_ascii=False, indent=2, encoding="utf-8") -> bool:
    """原子的に JSON を保存（途中で落ちても壊れにくい）"""
    path = Path(path)  # ← ★どこから来てもPath化
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    with tmp.open("w", encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)

    # Windowsでも安全に置き換え
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            if backup.exists():
                backup.unlink()
        except Exception:
            pass
        shutil.move(str(path), str(backup))
    shutil.move(str(tmp), str(path))
    return True


def safe_read_json(path, default=None, encoding="utf-8"):
    """JSON を安全に読む（無ければ default）"""
    path = Path(path)  # ← ★Path化
    if not path.exists():
        return default
    try:
        with path.open("r", encoding=encoding) as f:
            return json.load(f)
    except Exception:
        return default
