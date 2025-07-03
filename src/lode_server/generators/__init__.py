import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

from lode_server.generator import LodeGenerator

_generators: Dict[str, Type[LodeGenerator]] = {}

def register_generator(name: str):
    """
    Decorator for registering generator classes.

    Args:
        name (str): The name to register the generator under.

    Returns:
        Callable: The class decorator.
    """
    def decorator(cls: Type[LodeGenerator]):
        _generators[name] = cls
        return cls
    return decorator

def get_generator(name: str) -> Type[LodeGenerator]:
    """
    Retrieve a registered generator class by name.

    Args:
        name (str): The generator type name.

    Returns:
        Type[LodeGenerator]: The generator class.

    Raises:
        ValueError: If the generator type is not registered.
    """
    if name not in _generators:
        raise ValueError(f"Unknown generator type: {name}")
    return _generators[name]

def load_generators():
    """
    Load all built-in and external generator plugins.
    
    This function performs two main tasks:
    1. Automatically imports and registers all generator modules in the current package.
    2. Discovers and loads external generator plugins using entry points (if available).
    
    Built-in generators are loaded by scanning the package directory. External generators
    are loaded via the entry point group 'lode_server.generators'.
    
    Note:
        If `importlib.metadata` is not available (Python < 3.8), external plugins
        will be silently skipped.
    
    Side Effects:
        - Imports all generator modules in the package, executing their decorators.
        - Populates the `_generators` dictionary with external plugin instances.
    """
    # Load built-in generators
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        importlib.import_module(f".{module_name}", package=__name__)
    
    # Load external plugins via entry points
    try:
        from importlib.metadata import entry_points
        
        # Automatically determine plugin group name from package root
        root_package = __name__.split('.')[0]
        plugin_group = f"{root_package}.generators"
        
        eps = entry_points()
        if hasattr(eps, 'select'):  # Python 3.10+
            plugins = eps.select(group=plugin_group)
        else:
            plugins = eps.get(plugin_group, [])
        
        for ep in plugins:
            generator_class = ep.load()
            _generators[ep.name] = generator_class
    except ImportError:
        pass
    
load_generators()
