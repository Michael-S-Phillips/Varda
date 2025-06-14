# varda/plugin_manager.py
import importlib
import importlib.util
import importlib.metadata
from pathlib import Path
from src.varda import VPlugin

def loadPlugins(entry_point_group="varda.plugins", plugin_dir="user_plugins"):
    plugins = []

    # --- 1. Load entry point plugins ---
    try:
        entry_points = importlib.metadata.entry_points()
        plugin_eps = entry_points.select(group=entry_point_group)
        for ep in plugin_eps:
            plugin = ep.load()
            if isinstance(plugin, VPlugin):
                plugins.append(plugin)
            else:
                print(f"[WARNING] Entry point {ep.name} is not a valid VPlugin")
    except Exception as e:
        print(f"[ERROR] Failed to load entry points: {e}")

    # --- 2. Load local plugins from plugin folder ---
    plugin_path = Path(plugin_dir)
    if plugin_path.exists() and plugin_path.is_dir():
        for file in plugin_path.glob("*.py"):
            try:
                spec = importlib.util.spec_from_file_location(file.stem, file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                for obj in mod.__dict__.values():
                    if isinstance(obj, VPlugin):
                        plugins.append(obj)
            except Exception as e:
                print(f"[ERROR] Failed to load plugin {file.name}: {e}")

    return plugins