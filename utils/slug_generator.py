# utils/slug_generator.py
"""
Slug generation utility for categories
"""

import re
import unicodedata


def generate_slug(text: str) -> str:
    """
    Generate a URL-friendly slug from text
    
    Args:
        text: Input text (e.g., "Coffee Shop")
    
    Returns:
        str: Slug (e.g., "coffee-shop")
    """
    if not text:
        return ""
    
    # Normalize Unicode characters
    text = unicodedata.normalize('NFKD', str(text))
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove accents/diacritics
    text = ''.join(c for c in text if not unicodedata.combining(c))
    
    # Replace spaces and special characters with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    
    # Remove leading/trailing hyphens
    text = text.strip('-')
    
    # Remove duplicate hyphens
    text = re.sub(r'-+', '-', text)
    
    return text


def generate_unique_slug(base_text: str, existing_slugs: list) -> str:
    """
    Generate a unique slug by adding a number suffix if needed
    
    Args:
        base_text: Base text for slug
        existing_slugs: List of existing slugs
    
    Returns:
        str: Unique slug
    """
    base_slug = generate_slug(base_text)
    
    if not base_slug:
        base_slug = "category"
    
    if base_slug not in existing_slugs:
        return base_slug
    
    # Add number suffix
    counter = 1
    while True:
        candidate = f"{base_slug}-{counter}"
        if candidate not in existing_slugs:
            return candidate
        counter += 1