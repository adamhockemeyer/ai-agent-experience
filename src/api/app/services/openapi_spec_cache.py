# app/services/openapi_spec_cache.py
import logging
import httpx
import json
import yaml
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from opentelemetry import trace

from app.models import Agent, Tool
from app.config.azure_app_config import AzureAppConfig
from app.config.config import get_settings

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class OpenAPISpecCache:
    """
    A cache for OpenAPI specifications to avoid fetching them repeatedly.
    This implementation supports:
    - Prefetching specs at application startup
    - Caching specs with TTL
    - Automatic periodic refresh of specs
    """
    
    # Singleton instance
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'OpenAPISpecCache':
        """Get the singleton instance of the cache."""
        if cls._instance is None:
            cls._instance = OpenAPISpecCache()
        return cls._instance
    
    def __init__(self):
        """Initialize the OpenAPI spec cache."""
        # Map of spec URLs to parsed specs and their timestamp
        self._spec_cache: Dict[str, Dict[str, Any]] = {}
        
        # Timestamp tracking for each cached spec
        self._cache_timestamps: Dict[str, float] = {}
        
        # Authentication information by spec URL
        self._auth_map: Dict[str, List] = {}
        
        # Flag to track if refresh task is running
        self._refresh_task = None
        
        # Configuration
        settings = get_settings()
        self._config_client = AzureAppConfig(
            connection_string=settings.azure_app_config_connection_string,
            endpoint=settings.azure_app_config_endpoint
        )
        
        # Cache configuration
        self._enable_cache = getattr(settings, "openapi_cache_enabled", True)
        self._cache_ttl = getattr(settings, "openapi_cache_ttl_seconds", 3600)  # 1 hour default
        self._refresh_interval = getattr(settings, "openapi_cache_refresh_interval_seconds", 300)  # 5 minutes default
        
        logger.info(f"OpenAPI spec cache initialized with TTL: {self._cache_ttl}s, refresh interval: {self._refresh_interval}s")
        
    async def prefetch_all_specs(self) -> None:
        """
        Prefetch all OpenAPI specs for all agents.
        This should be called during application startup.
        """
        if not self._enable_cache:
            logger.info("OpenAPI spec caching is disabled")
            return
            
        with tracer.start_as_current_span("prefetch_all_specs"):
            try:
                # Get all agents from configuration
                logger.info("Prefetching OpenAPI specs for all agents")
                agents = await self._config_client.list(model_type=Agent, prefix="agent:")
                
                # Collect all unique OpenAPI spec URLs and their authentications
                spec_urls = set()
                auth_map = {}
                
                for agent in agents:
                    for tool in agent.tools:
                        if tool.type == "OpenAPI" and tool.specUrl:
                            spec_url = tool.specUrl
                            spec_urls.add(spec_url)
                            auth_map[spec_url] = tool.authentications
                
                # Fetch all specs in parallel
                fetch_tasks = []
                for spec_url in spec_urls:
                    fetch_tasks.append(self._fetch_and_cache_spec(spec_url, auth_map.get(spec_url)))
                
                # Wait for all fetch tasks to complete
                if fetch_tasks:
                    await asyncio.gather(*fetch_tasks)
                    
                logger.info(f"Prefetched {len(self._spec_cache)} OpenAPI specs successfully")
                
                # Start the periodic refresh task after initial prefetch
                if self._enable_cache and not self._refresh_task:
                    self._start_refresh_task()
                    
            except Exception as e:
                logger.error(f"Error prefetching OpenAPI specs: {str(e)}", exc_info=True)
    
    def _start_refresh_task(self) -> None:
        """Start the periodic refresh task in the background."""
        if self._refresh_task is None:
            self._refresh_task = asyncio.create_task(self._periodic_refresh())
            logger.info(f"Started periodic refresh task with interval {self._refresh_interval}s")
            
    async def _periodic_refresh(self) -> None:
        """Periodically refresh cached specs that have exceeded their TTL."""
        try:
            while True:
                # Wait for the refresh interval
                await asyncio.sleep(self._refresh_interval)
                
                # Find specs that need refreshing
                current_time = time.time()
                specs_to_refresh = []
                
                for spec_url, timestamp in self._cache_timestamps.items():
                    # If the spec has exceeded its TTL
                    if current_time - timestamp > self._cache_ttl / 2:
                        # Refresh before TTL expires (at half TTL) to ensure availability
                        specs_to_refresh.append((spec_url, self._auth_map.get(spec_url)))
                        
                if specs_to_refresh:
                    logger.info(f"Refreshing {len(specs_to_refresh)} OpenAPI specs")
                    
                    # Refresh specs in parallel
                    refresh_tasks = []
                    for spec_url, authentications in specs_to_refresh:
                        refresh_tasks.append(self._fetch_and_cache_spec(spec_url, authentications, is_refresh=True))
                        
                    # Wait for all refresh tasks to complete
                    await asyncio.gather(*refresh_tasks, return_exceptions=True)
                    
        except asyncio.CancelledError:
            logger.info("Periodic refresh task cancelled")
        except Exception as e:
            logger.error(f"Error in periodic refresh task: {str(e)}", exc_info=True)
            # Restart the task after a short delay
            asyncio.create_task(self._restart_refresh_task_after_delay())
            
    async def _restart_refresh_task_after_delay(self, delay: float = 60) -> None:
        """Restart the refresh task after a delay."""
        await asyncio.sleep(delay)
        self._refresh_task = None
        self._start_refresh_task()
            
    async def get_spec(self, spec_url: str, authentications: List = None) -> Optional[Dict[str, Any]]:
        """
        Get an OpenAPI spec from the cache or fetch it if not found.
        This method never throws exceptions, it will return None on any failure.
        
        Args:
            spec_url: URL of the OpenAPI spec
            authentications: Authentication configurations for the spec
            
        Returns:
            Parsed OpenAPI spec or None if fetch failed
        """
        # If cache is disabled, always fetch
        if not self._enable_cache:
            try:
                return await self._fetch_openapi_spec(spec_url, authentications)
            except Exception as e:
                logger.error(f"Error fetching OpenAPI spec: {str(e)}", exc_info=True)
                return None
                
        try:
            with tracer.start_as_current_span("get_spec") as span:
                span.set_attribute("url", spec_url)
                
                # Check if in cache first
                if spec_url in self._spec_cache:
                    logger.debug(f"Using cached OpenAPI spec for {spec_url}")
                    span.set_attribute("cache_hit", True)
                    
                    try:
                        # Check if we should refresh in the background
                        current_time = time.time()
                        last_fetch_time = self._cache_timestamps.get(spec_url, 0)
                        
                        # If the cache entry is getting stale (> 75% of TTL), trigger a background refresh
                        if current_time - last_fetch_time > (self._cache_ttl * 0.75):
                            logger.debug(f"Background refreshing stale spec: {spec_url}")
                            # Schedule a background refresh without waiting for result
                            # Use create_task with error handling
                            refresh_task = asyncio.create_task(self._fetch_and_cache_spec(spec_url, authentications, is_refresh=True))
                            
                            # Add error handling for the background task
                            refresh_task.add_done_callback(
                                lambda t: logger.error(f"Background refresh failed: {t.exception()}") if t.exception() else None
                            )
                    except Exception as e:
                        # Log but don't fail if background refresh scheduling fails
                        logger.error(f"Failed to schedule background refresh: {str(e)}")
                        
                    # Return cached spec immediately, regardless of refresh status
                    return self._spec_cache[spec_url]
                
                # Not in cache, fetch and cache it
                span.set_attribute("cache_hit", False)
                return await self._fetch_and_cache_spec(spec_url, authentications)
        except Exception as e:
            # Catch all exceptions to ensure this method never fails
            logger.error(f"Unexpected error in get_spec for {spec_url}: {str(e)}", exc_info=True)
            
            # As a last resort, try to fetch directly without caching
            try:
                return await self._fetch_openapi_spec(spec_url, authentications)
            except Exception as fetch_error:
                logger.error(f"Direct fetch also failed for {spec_url}: {str(fetch_error)}")
                return None
    
    async def _fetch_and_cache_spec(self, spec_url: str, authentications: List = None, is_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch an OpenAPI spec and cache it."""
        try:
            log_prefix = "Refreshing" if is_refresh else "Fetching"
            logger.info(f"{log_prefix} OpenAPI spec from {spec_url}")
            
            spec = await self._fetch_openapi_spec(spec_url, authentications)
            
            if spec:
                # Cache the spec and update timestamp
                self._spec_cache[spec_url] = spec
                self._cache_timestamps[spec_url] = time.time()
                self._auth_map[spec_url] = authentications
                
                action = "refreshed" if is_refresh else "cached"
                logger.info(f"Successfully {action} OpenAPI spec for {spec_url}")
                
            return spec
        except Exception as e:
            logger.error(f"Error {is_refresh and 'refreshing' or 'fetching'} OpenAPI spec from {spec_url}: {str(e)}", exc_info=True)
            return None
            
    async def clear_cache(self) -> None:
        """Clear the entire cache."""
        self._spec_cache.clear()
        self._cache_timestamps.clear()
        self._auth_map.clear()
        logger.info("Cleared OpenAPI spec cache")
    
    async def _fetch_openapi_spec(self, url: str, authentications: List = None) -> Dict[str, Any]:
        """Fetch and parse an OpenAPI specification from a URL."""
        with tracer.start_as_current_span("fetch_openapi_spec") as span:
            span.set_attribute("url", url)
            headers = {}
            
            # Add authentication headers if provided
            if authentications:
                for auth in authentications:
                    if auth.type == "Header":
                        headers[auth.headerName] = auth.headerValue
                        span.set_attribute(f"auth_header.{auth.headerName}", "[REDACTED]")
            
            # Use async HTTP client with timeout and proper error handling
            try:
                timeout = httpx.Timeout(30.0, connect=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    
                    # Try to parse as JSON first
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        # If not JSON, try as YAML
                        return yaml.safe_load(response.text)
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching OpenAPI spec: {e.response.status_code} {str(e)}")
                span.set_attribute("error", f"http_status_{e.response.status_code}")
                raise Exception(f"Failed to fetch OpenAPI spec: HTTP {e.response.status_code}")
                
            except httpx.RequestError as e:
                logger.error(f"Network error fetching OpenAPI spec: {str(e)}")
                span.set_attribute("error", "network_error")
                raise Exception(f"Network error fetching OpenAPI spec: {str(e)}")
                
            except Exception as e:
                logger.error(f"Error parsing OpenAPI spec: {str(e)}")
                span.set_attribute("error", "parse_error")
                raise Exception(f"Error parsing OpenAPI spec: {str(e)}")
                
    async def cleanup(self) -> None:
        """Clean up resources used by the cache."""
        # Cancel the refresh task if running
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
            
        # Clear the cache
        await self.clear_cache()
        logger.info("OpenAPI spec cache cleanup complete")