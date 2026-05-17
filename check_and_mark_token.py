"""Вспомогательная функция для атомарной проверки и пометки токена"""
import asyncio
import os
import json
from datetime import datetime, timezone

# Используем тот же Lock, что и в main_base.py
_alert_lock = asyncio.Lock()

async def check_and_mark_token_atomic(tracker, token_address: str, cache_file: str) -> bool:
    """
    Атомарная проверка и пометка токена с использованием Lock.
    Возвращает True, если токен можно отправить (еще не был отправлен).
    Возвращает False, если токен уже был отправлен.
    """
    addr_lower = token_address.lower()
    
    async with _alert_lock:
        # Перечитываем файл ВНУТРИ Lock
        try:
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    alerted_map = data.get("alerted", {}) if isinstance(data, dict) else {}
                    # Синхронизируем локальный кеш
                    for a in alerted_map.keys():
                        a_lower = a.lower()
                        if a_lower not in tracker.alerted:
                            tracker.alerted.add(a_lower)
                            try:
                                ts_str = alerted_map[a]
                                tracker.last_alert_at[a_lower] = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                            except:
                                pass
        except Exception:
            pass
        
        # Проверяем, был ли токен уже отправлен
        if addr_lower in tracker.alerted:
            return False
        
        # Помечаем токен СРАЗУ
        tracker.alerted.add(addr_lower)
        tracker.last_alert_at[addr_lower] = datetime.now(timezone.utc)
        
        # Сохраняем в файл СРАЗУ
        try:
            import fcntl
            payload = {"alerted": {a: tracker.last_alert_at.get(a, datetime.now(timezone.utc)).isoformat() for a in tracker.alerted}}
            temp_file = cache_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except (AttributeError, OSError):
                    pass
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, cache_file)
        except ImportError:
            try:
                payload = {"alerted": {a: tracker.last_alert_at.get(a, datetime.now(timezone.utc)).isoformat() for a in tracker.alerted}}
                temp_file = cache_file + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                os.replace(temp_file, cache_file)
            except Exception:
                pass
        except Exception:
            pass
        
        return True

