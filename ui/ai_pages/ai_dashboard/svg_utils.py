# ui/ai_pages/ai_dashboard/svg_utils.py
"""
SVG Utility Functions - Production Ready
"""

import os
from PyQt6.QtCore import QSize
from PyQt6.QtSvg import QSvgRenderer


class SVGUtils:
    """Utility functions for SVG handling"""
    
    @staticmethod
    def get_svg_info(svg_path: str) -> dict:
        """Get SVG file information"""
        if not os.path.exists(svg_path):
            return {'exists': False}
        
        try:
            renderer = QSvgRenderer(svg_path)
            if not renderer.isValid():
                return {'exists': True, 'valid': False}
            
            default_size = renderer.defaultSize()
            
            return {
                'exists': True,
                'valid': True,
                'width': default_size.width(),
                'height': default_size.height(),
                'aspect_ratio': default_size.width() / default_size.height() if default_size.height() > 0 else 0,
                'is_square': default_size.width() == default_size.height(),
            }
        except Exception as e:
            return {'exists': True, 'valid': False, 'error': str(e)}
    
    @staticmethod
    def get_optimal_size(svg_path: str, target_size: tuple) -> tuple:
        """Get optimal size for rendering"""
        info = SVGUtils.get_svg_info(svg_path)
        if not info.get('valid', False):
            return target_size
        
        svg_width = info['width']
        svg_height = info['height']
        
        if svg_width <= 0 or svg_height <= 0:
            return target_size
        
        # Calculate scale to fit
        scale = min(
            target_size[0] / svg_width,
            target_size[1] / svg_height
        )
        
        # Add padding for stroke
        padding = 2
        scale = min(scale, (target_size[0] - padding * 2) / svg_width)
        scale = min(scale, (target_size[1] - padding * 2) / svg_height)
        
        return (
            int(svg_width * scale),
            int(svg_height * scale)
        )