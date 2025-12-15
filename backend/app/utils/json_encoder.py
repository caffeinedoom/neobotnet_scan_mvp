"""
Enhanced JSON encoding utilities with comprehensive UUID support.
Handles nested dictionaries, lists, and complex data structures containing UUID objects.
"""
import json
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Union
from enum import Enum


def deep_uuid_serialize(obj: Any) -> Any:
    """
    Recursively serialize any data structure containing UUID objects.
    This ensures template modules and complex nested responses work seamlessly.
    """
    if isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: deep_uuid_serialize(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [deep_uuid_serialize(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(deep_uuid_serialize(item) for item in obj)
    elif isinstance(obj, set):
        return {deep_uuid_serialize(item) for item in obj}
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, Enum):
        return obj.value
    else:
        return obj


class ApplicationJSONEncoder(json.JSONEncoder):
    """
    Enhanced JSON encoder that handles UUID objects in any nested structure.
    Perfect for template modules and complex scanning responses.
    """
    def default(self, obj):
        # Handle direct UUID objects
        if isinstance(obj, uuid.UUID):
            return str(obj)
        # Handle datetime objects
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        # Handle Decimal objects
        elif isinstance(obj, Decimal):
            return float(obj)
        # Handle Enum objects
        elif isinstance(obj, Enum):
            return obj.value
        # Let the base class handle the rest
        return super().default(obj)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    UUID-safe JSON serialization that handles any nested data structure.
    Automatically processes template responses, module results, and complex dictionaries.
    """
    try:
        # First pass: deep serialize to handle nested UUIDs
        serializable_obj = deep_uuid_serialize(obj)
        
        # Second pass: standard JSON encoding with fallback
        return json.dumps(serializable_obj, cls=ApplicationJSONEncoder, **kwargs)
    except Exception as e:
        # Fallback: convert problematic objects to strings
        try:
            def fallback_serializer(obj):
                if hasattr(obj, '__dict__'):
                    return f"<{obj.__class__.__name__}>"
                return str(obj)
            
            return json.dumps(obj, default=fallback_serializer, **kwargs)
        except Exception:
            return json.dumps({"error": f"Serialization failed: {str(e)}"})


def safe_json_loads(json_str: str, **kwargs) -> Any:
    """
    Safe JSON deserialization with error handling.
    Complements safe_json_dumps for bidirectional JSON operations.
    """
    try:
        return json.loads(json_str, **kwargs)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise ValueError(f"JSON parsing failed: {str(e)}")


# Legacy compatibility
safe_json_serialize = safe_json_dumps
