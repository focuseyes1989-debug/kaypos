# utils/image_optimizer.py
import os
import uuid
from PIL import Image
from loguru import logger
from utils.paths import app_path


class ImageOptimizer:
    """Handle product image optimization and storage"""
    
    # Default settings
    THUMBNAIL_SIZE = (50, 50)
    STANDARD_SIZE = (400, 400)
    JPEG_QUALITY = 80
    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp')
    
    @staticmethod
    def optimize_image(input_path: str, output_size: tuple = None, 
                       quality: int = None, output_format: str = 'JPEG') -> str:
        """
        Optimize an image: resize and compress
        
        Args:
            input_path: Path to source image
            output_size: (width, height) tuple, defaults to STANDARD_SIZE
            quality: JPEG quality (1-100), defaults to JPEG_QUALITY
            output_format: 'JPEG' or 'PNG'
            
        Returns:
            Path to optimized image (saved in product_images directory)
        """
        if not input_path or not os.path.exists(input_path):
            return input_path
            
        if output_size is None:
            output_size = ImageOptimizer.STANDARD_SIZE
            
        if quality is None:
            quality = ImageOptimizer.JPEG_QUALITY
            
        try:
            # Open image
            img = Image.open(input_path)
            
            # Convert RGBA to RGB for JPEG
            if output_format == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Resize (maintain aspect ratio)
            img.thumbnail(output_size, Image.Resampling.LANCZOS)
            
            # Generate output path
            ext = '.jpg' if output_format == 'JPEG' else '.png'
            dest_filename = f"product_{uuid.uuid4().hex}{ext}"
            
            from utils.paths import app_path
            images_dir = app_path("database", "product_images")
            os.makedirs(images_dir, exist_ok=True)
            
            dest_path = os.path.join(images_dir, dest_filename)
            
            # Save optimized image
            if output_format == 'JPEG':
                img.save(dest_path, 'JPEG', quality=quality, optimize=True)
            else:
                img.save(dest_path, 'PNG', optimize=True)
                
            # Log file size reduction
            original_size = os.path.getsize(input_path)
            new_size = os.path.getsize(dest_path)
            reduction = ((original_size - new_size) / original_size) * 100
            logger.debug(f"Image optimized: {original_size//1024}KB → {new_size//1024}KB ({reduction:.1f}% reduction)")
            
            return dest_path
            
        except Exception as e:
            logger.error(f"Error optimizing image {input_path}: {e}")
            # Fallback: copy original
            return ImageOptimizer._copy_image(input_path)
    
    @staticmethod
    def _copy_image(source_path: str) -> str:
        """Fallback: copy original image without optimization"""
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg'):
            ext = '.png'
        dest_filename = f"product_{uuid.uuid4().hex}{ext}"
        
        from utils.paths import app_path
        images_dir = app_path("database", "product_images")
        os.makedirs(images_dir, exist_ok=True)
        
        dest_path = os.path.join(images_dir, dest_filename)
        import shutil
        shutil.copy2(source_path, dest_path)
        return dest_path
    
    @staticmethod
    def get_thumbnail_path(image_path: str, size: tuple = None) -> str:
        """
        Get or create thumbnail for an image
        
        Returns path to thumbnail image
        """
        if not image_path:
            return ""
            
        if size is None:
            size = ImageOptimizer.THUMBNAIL_SIZE
            
        # Check if thumbnail already exists
        thumb_dir = app_path("database", "product_images", "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        
        # Create thumbnail filename from original
        import hashlib
        size_key = f"{int(size[0])}x{int(size[1])}"
        hash_id = hashlib.md5(f"{image_path}|{size_key}".encode()).hexdigest()[:12]
        thumb_path = os.path.join(thumb_dir, f"thumb_{hash_id}.jpg")
        
        # Return existing thumbnail if it exists and is newer than source
        if os.path.exists(thumb_path):
            if os.path.getmtime(thumb_path) >= os.path.getmtime(image_path):
                return thumb_path
        
        # Create thumbnail
        try:
            from PIL import Image
            img = Image.open(image_path)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Convert to RGB for JPEG
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
                
            img.save(thumb_path, 'JPEG', quality=70, optimize=True)
            return thumb_path
        except Exception as e:
            logger.error(f"Failed to create thumbnail for {image_path}: {e}")
            return image_path
