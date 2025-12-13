from datetime import datetime
from typing import Any, Dict
from dateutil import parser
from loguru import logger


class DateNormalizerAgent:
    """Agent for extracting and normalizing dates from various sources"""
    
    @staticmethod
    def normalize_date(date_value: Any) -> datetime:
        """
        Normalize various date formats to datetime object
        Handles:
        - ISO format strings
        - Unix timestamps
        - Human-readable date strings
        - Twitter date formats
        """
        try:
            # If already datetime
            if isinstance(date_value, datetime):
                return date_value
            
            # If Unix timestamp
            if isinstance(date_value, (int, float)):
                return datetime.fromtimestamp(date_value)
            
            # If string, try parsing
            if isinstance(date_value, str):
                # Try ISO format first
                try:
                    return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                except:
                    pass
                
                # Try general parser
                try:
                    return parser.parse(date_value)
                except:
                    pass
            
            # Default to current time if all fails
            logger.warning(f"Could not parse date: {date_value}, using current time")
            return datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error normalizing date {date_value}: {str(e)}")
            return datetime.utcnow()
    
    @classmethod
    def normalize_item(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize dates in a data item"""
        normalized = item.copy()
        
        # Normalize published_at or created_at
        if "published_at" in item:
            normalized["normalized_date"] = cls.normalize_date(item["published_at"])
        elif "created_at" in item:
            normalized["normalized_date"] = cls.normalize_date(item["created_at"])
        else:
            normalized["normalized_date"] = datetime.utcnow()
        
        return normalized
    
    @classmethod
    def sort_by_date(cls, items: list, descending: bool = True) -> list:
        """Sort items by normalized date"""
        return sorted(
            items,
            key=lambda x: x.get("normalized_date", datetime.min),
            reverse=descending
        )