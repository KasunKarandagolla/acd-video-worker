"""
Fallback Discovery Module — Alternative YouTube discovery when yt-dlp search fails.

Provides a legitimate fallback using existing configured resources:
- Tavily API (web search restricted to youtube.com) when TAVILY_API_KEY is available
- Hermes web search tool (when available in session)
- Both return YouTube URLs normalized to SourceCandidate model
"""

import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import requests
except ImportError:
    requests = None

from .discovery import SourceCandidate


class FallbackDiscoveryError(Exception):
    """Raised when fallback discovery fails."""
    pass


@dataclass
class FallbackResult:
    """Result from fallback discovery attempt."""
    method: str
    success: bool
    candidates: list[SourceCandidate]
    error: Optional[str] = None
    raw_response: Optional[dict] = None


class TavilyDiscovery:
    """
    Tavily API-based YouTube discovery.
    
    Uses Tavily web search restricted to site:youtube.com to find videos.
    Requires TAVILY_API_KEY environment variable.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY")
        self.base_url = "https://api.tavily.com/search"
        self.enabled = bool(self.api_key and requests is not None)
    
    def is_available(self) -> bool:
        return self.enabled
    
    def search(
        self,
        query: str,
        story_slot: str,
        max_results: int = 5,
        target_emotion: str = ""
    ) -> FallbackResult:
        """Search YouTube via Tavily API."""
        if not self.enabled:
            return FallbackResult(
                method="tavily",
                success=False,
                candidates=[],
                error="Tavily not available (no API key or requests library)"
            )
        
        # Restrict to YouTube
        youtube_query = f"site:youtube.com {query}"
        
        payload = {
            "api_key": self.api_key,
            "query": youtube_query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max_results,
            "include_domains": ["youtube.com", "youtu.be"]
        }
        
        try:
            response = requests.post(self.base_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            candidates = self._parse_results(data, query, story_slot, target_emotion)
            
            return FallbackResult(
                method="tavily",
                success=True,
                candidates=candidates,
                raw_response=data
            )
            
        except Exception as e:
            return FallbackResult(
                method="tavily",
                success=False,
                candidates=[],
                error=str(e)
            )
    
    def _parse_results(
        self,
        data: dict,
        query: str,
        story_slot: str,
        target_emotion: str
    ) -> list[SourceCandidate]:
        """Parse Tavily results into SourceCandidate objects."""
        candidates = []
        results = data.get("results", [])
        
        for idx, result in enumerate(results):
            url = result.get("url", "")
            video_id = self._extract_video_id(url)
            if not video_id:
                continue
            
            title = result.get("title", f"Unknown video {idx}")
            content = result.get("content", "")
            
            # Extract channel from content or URL
            channel = self._extract_channel(content, url)
            
            # Estimate duration (not available from Tavily, use default)
            duration = 180
            
            candidate = SourceCandidate(
                candidate_id=f"{story_slot}_tavily_{uuid.uuid4().hex[:8]}",
                url=url,
                video_id=video_id,
                title=title,
                channel=channel,
                duration=duration,
                upload_date="",
                thumbnail=result.get("thumbnail", ""),
                query=query,
                story_slot=story_slot,
                ranking_score=0.0,
                verification_status="unverified",
                discovery_method="tavily_search",
                metadata_confidence="low",
                deep_analysis_candidate="maybe"
            )
            candidates.append(candidate)
        
        return candidates
    
    @staticmethod
    def _extract_video_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def _extract_channel(content: str, url: str) -> str:
        """Extract channel name from content or URL."""
        # Try to find channel in content
        channel_match = re.search(r"(?:channel|c/@)([a-zA-Z0-9_-]+)", content)
        if channel_match:
            return channel_match.group(1)
        
        # Fallback: extract from URL
        if "/c/" in url:
            return url.split("/c/")[-1].split("/")[0]
        if "/@" in url:
            return url.split("/@")[-1].split("/")[0]
        
        return "Unknown"


class HermesWebSearchDiscovery:
    """
    Hermes web search tool-based discovery.
    
    Uses the Hermes `web` toolset (search, fetch) to find YouTube videos.
    Only available when running inside a Hermes session with web tool access.
    """
    
    def __init__(self):
        self.enabled = True  # Always available in principle, but needs Hermes session
    
    def is_available(self) -> bool:
        # This would need to be checked at runtime in a Hermes session
        # For now, we assume it's available when called from Hermes
        return True
    
    def search(
        self,
        query: str,
        story_slot: str,
        max_results: int = 5,
        target_emotion: str = "",
        hermes_session_id: Optional[str] = None
    ) -> FallbackResult:
        """
        Search using Hermes web tool.
        
        Note: This method should be called from within a Hermes session
        where the `web` tool is available. The actual search is performed
        by the Hermes agent, not by this Python code directly.
        """
        # This is a placeholder - the actual search happens in Hermes skill
        # We provide the prompt structure that the skill should use
        return FallbackResult(
            method="hermes_web_search",
            success=False,
            candidates=[],
            error="Must be invoked via Hermes skill with web tool access"
        )


class FallbackDiscoveryEngine:
    """
    Main fallback discovery engine.
    
    Tries multiple fallback methods in order:
    1. Tavily API (if TAVILY_API_KEY configured)
    2. Hermes web search (if in Hermes session)
    
    Only activates when primary yt-dlp discovery fails or returns insufficient candidates.
    """
    
    def __init__(
        self,
        min_candidates_per_slot: int = 3,
        tavily_api_key: Optional[str] = None
    ):
        self.min_candidates = min_candidates_per_slot
        self.tavily = TavilyDiscovery(tavily_api_key)
        self.hermes_web = HermesWebSearchDiscovery()
        
        # Track which methods have been tried
        self.tried_methods: list[str] = []
    
    def should_activate(self, primary_candidates: list[SourceCandidate]) -> bool:
        """Determine if fallback should activate based on primary results."""
        return len(primary_candidates) < self.min_candidates
    
    def discover_for_slot(
        self,
        query: str,
        story_slot: str,
        target_emotion: str = "",
        primary_candidates: Optional[list[SourceCandidate]] = None,
        max_results: int = 5
    ) -> list[SourceCandidate]:
        """
        Run fallback discovery for a single story slot.
        
        Returns combined candidates from all available fallback methods,
        deduplicated against primary candidates.
        """
        if primary_candidates is None:
            primary_candidates = []
        
        if not self.should_activate(primary_candidates):
            return []
        
        all_fallback_candidates = []
        primary_video_ids = {c.video_id for c in primary_candidates if c.video_id}
        
        # Try Tavily first
        if self.tavily.is_available():
            self.tried_methods.append("tavily")
            result = self.tavily.search(query, story_slot, max_results, target_emotion)
            if result.success and result.candidates:
                # Deduplicate against primary
                for c in result.candidates:
                    if c.video_id not in primary_video_ids:
                        all_fallback_candidates.append(c)
                        primary_video_ids.add(c.video_id)
        
        # Note: Hermes web search would be invoked from within a Hermes skill
        # This engine just provides the Tavily fallback for standalone use
        
        return all_fallback_candidates
    
    def discover_all_slots(
        self,
        slot_queries: dict[str, list[str]],
        target_emotion: str = "",
        primary_results: Optional[dict[str, list[SourceCandidate]]] = None,
        max_per_query: int = 5
    ) -> dict[str, list[SourceCandidate]]:
        """
        Run fallback discovery for all story slots.
        
        Args:
            slot_queries: Dict of story_slot -> list of query strings
            target_emotion: Target emotion for ranking context
            primary_results: Existing primary candidates per slot (for deduplication)
            max_per_query: Max results per query
            
        Returns:
            Dict of story_slot -> fallback candidates
        """
        if primary_results is None:
            primary_results = {}
        
        fallback_results = {}
        
        for slot, queries in slot_queries.items():
            primary_for_slot = primary_results.get(slot, [])
            slot_fallback = []
            
            for query in queries:
                candidates = self.discover_for_slot(
                    query=query,
                    story_slot=slot,
                    target_emotion=target_emotion,
                    primary_candidates=primary_for_slot + slot_fallback,
                    max_results=max_per_query
                )
                slot_fallback.extend(candidates)
            
            # Deduplicate within slot
            seen = set()
            unique = []
            for c in slot_fallback:
                if c.video_id not in seen:
                    seen.add(c.video_id)
                    unique.append(c)
            
            if unique:
                fallback_results[slot] = unique
        
        return fallback_results


def create_fallback_discovery(
    min_candidates: int = 3,
    tavily_key: Optional[str] = None
) -> FallbackDiscoveryEngine:
    """Factory function to create fallback discovery engine."""
    return FallbackDiscoveryEngine(
        min_candidates_per_slot=min_candidates,
        tavily_api_key=tavily_key
    )


# CLI for testing
if __name__ == "__main__":
    import sys
    
    print("Testing Fallback Discovery...")
    
    # Check Tavily availability
    tavily = TavilyDiscovery()
    print(f"Tavily available: {tavily.is_available()}")
    
    if tavily.is_available():
        result = tavily.search(
            query="Messi World Cup 2022 final pressure",
            story_slot="opening_pressure",
            max_results=3,
            target_emotion="triumph"
        )
        print(f"Tavily result: success={result.success}, candidates={len(result.candidates)}")
        if result.error:
            print(f"  Error: {result.error}")
        for c in result.candidates[:3]:
            print(f"  - {c.title[:50]} | {c.video_id} | {c.channel}")
    else:
        print("Tavily not available (no TAVILY_API_KEY or requests not installed)")
        print("Set TAVILY_API_KEY environment variable to enable")
    
    # Test engine
    engine = FallbackDiscoveryEngine(min_candidates_per_slot=3)
    print(f"\nFallback engine created, min_candidates={engine.min_candidates}")
    
    # Test with mock primary results
    from .discovery import SourceCandidate
    primary = [
        SourceCandidate(
            candidate_id="primary_1",
            url="https://youtu.be/abc123",
            video_id="abc123",
            title="Primary Video",
            channel="Test",
            duration=100,
            upload_date="",
            thumbnail="",
            query="test",
            story_slot="opening_pressure",
            ranking_score=7.0,
        )
    ]
    
    should_activate = engine.should_activate(primary)
    print(f"Should activate with {len(primary)} primary candidates: {should_activate}")
    
    primary_many = [primary[0] for _ in range(5)]
    should_activate = engine.should_activate(primary_many)
    print(f"Should activate with {len(primary_many)} primary candidates: {should_activate}")