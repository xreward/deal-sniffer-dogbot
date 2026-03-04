#!/usr/bin/env python
"""
Configuration Cache Manager
Centralized config loading and caching system to eliminate duplicate file reads
"""

import yaml
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class ConfigCache:
    """Centralized configuration cache with file change detection"""
    
    def __init__(self):
        """Initialize the config cache"""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._file_hashes: Dict[str, str] = {}
        self._last_modified: Dict[str, float] = {}
        self._lock = Lock()
        
        # Config directories
        self.config_dir = Path(__file__).parent.parent / "config"
        self.common_config_dir = Path(__file__).parent.parent.parent / "common" / "config"
        
        logger.info("🗃️ Configuration cache initialized")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Get file content hash for change detection"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.warning(f"⚠️ Failed to get file hash for {file_path}: {e}")
            return ""
    
    def _has_file_changed(self, file_path: Path) -> bool:
        """Check if file has changed since last cache"""
        file_str = str(file_path)
        
        # Check if file exists
        if not file_path.exists():
            return False
        
        # Get current modification time and hash
        current_mtime = file_path.stat().st_mtime
        current_hash = self._get_file_hash(file_path)
        
        # Compare with cached values
        cached_mtime = self._last_modified.get(file_str, 0)
        cached_hash = self._file_hashes.get(file_str, "")
        
        # File changed if modification time or hash differs
        has_changed = (current_mtime != cached_mtime or current_hash != cached_hash)
        
        if has_changed:
            logger.info(f"📝 File change detected: {file_path.name}")
            # Update cache metadata
            self._last_modified[file_str] = current_mtime
            self._file_hashes[file_str] = current_hash
        
        return has_changed
    
    def get_config(self, config_name: str, force_reload: bool = False) -> Dict[str, Any]:
        """
        Get configuration with caching
        
        Args:
            config_name: Name of config file (without .yaml extension)
            force_reload: Force reload even if cached
            
        Returns:
            Configuration dictionary
        """
        with self._lock:
            # browser_profiles는 common/config에서 찾기
            if config_name == "browser_profiles":
                file_path = self.common_config_dir / f"{config_name}.yaml"
            else:
                file_path = self.config_dir / f"{config_name}.yaml"
            file_str = str(file_path)
            
            # Check if we need to reload
            need_reload = (
                force_reload or 
                file_str not in self._cache or 
                self._has_file_changed(file_path)
            )
            
            if need_reload:
                logger.info(f"📖 Loading config: {config_name}.yaml")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)
                    
                    # Cache the config
                    self._cache[file_str] = config_data
                    
                    # Update metadata
                    self._last_modified[file_str] = file_path.stat().st_mtime
                    self._file_hashes[file_str] = self._get_file_hash(file_path)
                    
                    logger.info(f"✅ Config cached: {config_name}.yaml")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to load config {config_name}.yaml: {e}")
                    # Return empty dict on error, or existing cache if available
                    if file_str in self._cache:
                        logger.warning(f"⚠️ Using cached version of {config_name}.yaml")
                        return self._cache[file_str]
                    return {}
            else:
                logger.debug(f"🗃️ Using cached config: {config_name}.yaml")
            
            return self._cache.get(file_str, {})
    
    def get_config_section(self, config_name: str, section_path: str, default: Any = None) -> Any:
        """
        Get specific section from config with dot notation
        
        Args:
            config_name: Name of config file
            section_path: Dot-separated path (e.g., 'crawler_settings.timeouts')
            default: Default value if section not found
            
        Returns:
            Configuration section or default value
        """
        config = self.get_config(config_name)
        
        # Navigate through section path
        current = config
        for key in section_path.split('.'):
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def invalidate_config(self, config_name: str):
        """Invalidate specific config cache"""
        with self._lock:
            file_path = self.config_dir / f"{config_name}.yaml"
            file_str = str(file_path)
            
            if file_str in self._cache:
                del self._cache[file_str]
                logger.info(f"🗑️ Invalidated cache for: {config_name}.yaml")
    
    def invalidate_all(self):
        """Invalidate all cached configs"""
        with self._lock:
            cache_count = len(self._cache)
            self._cache.clear()
            self._file_hashes.clear()
            self._last_modified.clear()
            logger.info(f"🗑️ Invalidated all config cache ({cache_count} files)")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            stats = {
                'cached_files': len(self._cache),
                'files': []
            }
            
            for file_path, config in self._cache.items():
                file_name = Path(file_path).name
                config_size = len(str(config))
                last_modified = self._last_modified.get(file_path, 0)
                
                stats['files'].append({
                    'name': file_name,
                    'size_bytes': config_size,
                    'last_loaded': time.ctime(last_modified) if last_modified else 'Unknown'
                })
            
            return stats
    
    def preload_configs(self, config_names: list):
        """Preload multiple configs for better performance"""
        logger.info(f"📚 Preloading {len(config_names)} configs...")
        
        for config_name in config_names:
            try:
                self.get_config(config_name)
                logger.debug(f"✅ Preloaded: {config_name}.yaml")
            except Exception as e:
                logger.warning(f"⚠️ Failed to preload {config_name}.yaml: {e}")
        
        logger.info(f"📚 Preloading completed")


# Global cache instance
_config_cache_instance = None
_cache_lock = Lock()

def get_config_cache() -> ConfigCache:
    """Get singleton instance of ConfigCache"""
    global _config_cache_instance
    if _config_cache_instance is None:
        with _cache_lock:
            if _config_cache_instance is None:
                _config_cache_instance = ConfigCache()
    return _config_cache_instance


# Convenience functions for common config access patterns
def get_crawler_config(section: Optional[str] = None, default: Any = None) -> Any:
    """Get crawler config or specific section"""
    cache = get_config_cache()
    if section:
        return cache.get_config_section('crawler_config', section, default)
    return cache.get_config('crawler_config')


def get_browser_profiles() -> Dict[str, Any]:
    """Get browser profiles config"""
    cache = get_config_cache()
    return cache.get_config('browser_profiles')


def get_config_with_cache(config_name: str, section: Optional[str] = None, default: Any = None) -> Any:
    """Generic config getter with optional section access"""
    cache = get_config_cache()
    if section:
        return cache.get_config_section(config_name, section, default)
    return cache.get_config(config_name) 