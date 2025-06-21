import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type
from ..generator import NMEAGenerator

_generators: Dict[str, Type[NMEAGenerator]] = {}

def register_generator(name: str):
    """
    Decorator for registering NMEA generator classes.

    Args:
        name (str): The name to register the generator under.

    Returns:
        Callable: The class decorator.
    """
    def decorator(cls: Type[NMEAGenerator]):
        _generators[name] = cls
        return cls
    return decorator

def get_generator(name: str) -> Type[NMEAGenerator]:
    """
    Retrieve a registered generator class by name.

    Args:
        name (str): The generator type name.

    Returns:
        Type[NMEAGenerator]: The generator class.

    Raises:
        ValueError: If the generator type is not registered.
    """
    if name not in _generators:
        raise ValueError(f"Unknown generator type: {name}")
    return _generators[name]

def load_generators():
    """
    Automatically import and register all generator modules in this package.

    This function scans the current package directory for modules
    and imports them, so that their registration decorators are executed.
    """
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        importlib.import_module(f".{module_name}", package=__name__)

load_generators()
