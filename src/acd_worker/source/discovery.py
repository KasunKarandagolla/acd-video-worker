"""
Discovery Adapter - YouTube-first candidate discovery using yt-dlp.

Provides a pluggable interface for discovering candidate source videos.
Currently implements yt-dlp search as primary method with fallback options.
"""

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import yt_dlp


@dataclass
class SourceCandidate:
    """Structured candidate from discovery."""
    candidate_id: str
    url: str
    video_id: str
    title: str
    channel: str
    duration: int
    upload_date: str
    thumbnail: str
    query: str
    story_slot: str
    ranking_score: float
    verification_status: str = "unverified"
    discovery_method: str = "yt_dlp_search"
    metadata_confidence: str = "medium"
    deep_analysis_candidate: str = "maybe"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SourceCandidate":
        return cls(**data)


class DiscoveryAdapter:
    """
    Adapter for YouTube-first discovery.
    
    Uses yt-dlp search operations (ytsearch) as the primary method.
    This works in Kaggle without browser daemons.
    """
    
    def __init__(
        self,
        max_results_per_query: int = 5,
        max_duration_seconds: int = 600,
        min_duration_seconds: int = 10,
    ):
        self.max_results = max_results_per_query
        self.max_duration = max_duration_seconds
        self.min_duration = min_duration_seconds
        self._ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
    
    def search(
        self,
        query: str,
        story_slot: str,
        max_results: Optional[int] = None
    ) -> list[SourceCandidate]:
        """
        Execute a search query and return structured candidates.
        
        Args:
            query: Search query string
            story_slot: Story slot this query targets (e.g., "opening_pressure", "goalkeeper_reaction")
            max_results: Override default max results
            
        Returns:
            List of SourceCandidate objects
        """
        max_r = max_results or self.max_results
        search_query = f"ytsearch{max_r}:{query}"
        
        candidates = []
        with yt_dlp.YoutubeDL(self._ydl_opts) as ydl:
            try:
                result = ydl.extract_info(search_query, download=False)
                entries = result.get("entries", []) if result else []
                
                for idx, entry in enumerate(entries):
                    if not entry:
                        continue
                    
                    video_id = entry.get("id", "")
                    url = f"https://youtu.be/{video_id}" if video_id else entry.get("url", "")
                    duration = entry.get("duration", 0) or 0
                    
                    # Filter by duration
                    if duration < self.min_duration or duration > self.max_duration:
                        continue
                    
                    candidate = SourceCandidate(
                        candidate_id=f"{story_slot}_{uuid.uuid4().hex[:8]}",
                        url=url,
                        video_id=video_id,
                        title=entry.get("title", "Unknown"),
                        channel=entry.get("channel", entry.get("uploader", "Unknown")),
                        duration=duration,
                        upload_date=entry.get("upload_date", ""),
                        thumbnail=entry.get("thumbnail", ""),
                        query=query,
                        story_slot=story_slot,
                        ranking_score=0.0,  # Will be set by ranker
                        verification_status="unverified",
                        discovery_method="yt_dlp_search",
                        metadata_confidence="medium",
                        deep_analysis_candidate="maybe",
                    )
                    candidates.append(candidate)
                    
            except Exception as e:
                print(f"Search error for query '{query}': {e}")
        
        return candidates
    
    def search_multiple(
        self,
        queries: list[str],
        story_slot: str,
        max_results_per_query: Optional[int] = None
    ) -> list[SourceCandidate]:
        """Execute multiple search queries and combine results."""
        all_candidates = []
        for query in queries:
            candidates = self.search(query, story_slot, max_results_per_query)
            all_candidates.extend(candidates)
        return all_candidates


class CandidateRanker:
    """
    Ranks candidates using the 7-axis football discovery rubric.
    
    Score components (0-10 total):
    - emotional_story_potential: 0-2
    - visual_scene_potential: 0-2
    - audio_commentary_potential: 0-1
    - editing_reference_value: 0-1
    - audience_signal: 0-1
    - source_quality: 0-1
    - transformability: 0-1
    - verification_confidence: 0-1
    """
    
    # Thresholds per architecture
    DEEP_ANALYSIS_THRESHOLD = 8.0
    MANUAL_INSPECT_THRESHOLD = 6.0
    TOPIC_ONLY_THRESHOLD = 4.0
    
    def rank(
        self,
        candidates: list[SourceCandidate],
        story_slot: str,
        target_emotion: str = ""
    ) -> list[SourceCandidate]:
        """Rank candidates and assign scores/flags."""
        for candidate in candidates:
            score = self._calculate_score(candidate, story_slot, target_emotion)
            candidate.ranking_score = round(score, 1)
            
            # Assign deep analysis flag
            if score >= self.DEEP_ANALYSIS_THRESHOLD:
                candidate.deep_analysis_candidate = "yes"
            elif score >= self.MANUAL_INSPECT_THRESHOLD:
                candidate.deep_analysis_candidate = "maybe"
            else:
                candidate.deep_analysis_candidate = "no"
        
        # Sort by score descending
        return sorted(candidates, key=lambda c: c.ranking_score, reverse=True)
    
    def _calculate_score(
        self,
        candidate: SourceCandidate,
        story_slot: str,
        target_emotion: str
    ) -> float:
        """Calculate 7-axis discovery score."""
        score = 0.0
        
        # 1. Emotional story potential (0-2)
        score += self._score_emotional_potential(candidate, story_slot, target_emotion)
        
        # 2. Visual scene potential (0-2)
        score += self._score_visual_potential(candidate, story_slot)
        
        # 3. Audio commentary potential (0-1)
        score += self._score_audio_potential(candidate)
        
        # 4. Editing reference value (0-1)
        score += self._score_editing_reference(candidate)
        
        # 5. Audience signal (0-1)
        score += self._score_audience_signal(candidate)
        
        # 6. Source quality (0-1)
        score += self._score_source_quality(candidate)
        
        # 7. Transformability (0-1)
        score += self._score_transformability(candidate)
        
        # 8. Verification confidence (0-1) - bonus for verified-looking metadata
        score += self._score_verification(candidate)
        
        return min(score, 10.0)
    
    def _score_emotional_potential(
        self, candidate: SourceCandidate, story_slot: str, target_emotion: str
    ) -> float:
        """Score emotional alignment with story slot."""
        title_lower = candidate.title.lower()
        slot_keywords = {
            "opening_pressure": ["pressure", "tension", "build-up", "anticipation", "nervous"],
            "stadium_atmosphere": ["crowd", "atmosphere", "stadium", "fans", "chant"],
            "player_closeup": ["close up", "close-up", "face", "eyes", "reaction", "emotion"],
            "critical_attack": ["attack", "chance", "shot", "goal", "opportunity", "break"],
            "goalkeeper_reaction": ["goalkeeper", "keeper", "save", "stop", "dive", "penalty"],
            "bench_reaction": ["bench", "substitute", "coach", "manager", "sideline", "reaction"],
            "crowd_eruption": ["celebration", "eruption", "goes wild", "fans", "party"],
            "opposition_disappointment": ["disappointed", "heartbreak", "devastated", "tears", "defeat"],
            "final_celebration": ["lifting", "trophy", "champion", "winner", "victory", "celebrate"],
            "ending_image": ["final whistle", "walk away", "empty stadium", "silence", "reflection"],
        }
        
        keywords = slot_keywords.get(story_slot, [])
        matches = sum(1 for kw in keywords if kw in title_lower)
        return min(matches * 0.3, 2.0)
    
    def _score_visual_potential(self, candidate: SourceCandidate, story_slot: str) -> float:
        """Score visual scene potential based on source type and title."""
        score = 1.0  # Base
        
        title_lower = candidate.title.lower()
        channel_lower = candidate.channel.lower()
        
        # Official/broadcast sources score higher
        if any(kw in channel_lower for kw in ["fifa", "uefa", "official", "broadcast", "premier league", "la liga", "serie a", "bundesliga"]):
            score += 0.5
        
        # Match footage keywords
        if any(kw in title_lower for kw in ["full match", "highlights", "extended", "match replay"]):
            score += 0.5
        
        # Penalize shorts-only
        if "short" in title_lower or "#shorts" in title_lower:
            score -= 0.5
            
        return max(0.0, min(score, 2.0))
    
    def _score_audio_potential(self, candidate: SourceCandidate) -> float:
        """Score audio/commentary potential."""
        title_lower = candidate.title.lower()
        
        if any(kw in title_lower for kw in ["commentary", "drury", "martinez", "tynan", "tyler", "champion", "poetic"]):
            return 1.0
        if any(kw in title_lower for kw in ["reaction", "analysis", "breakdown"]):
            return 0.5
        return 0.2
    
    def _score_editing_reference(self, candidate: SourceCandidate) -> float:
        """Score editing reference value."""
        title_lower = candidate.title.lower()
        
        if any(kw in title_lower for kw in ["cinematic", "edit", "montage", "tribute", "documentary", "film"]):
            return 1.0
        return 0.3
    
    def _score_audience_signal(self, candidate: SourceCandidate) -> float:
        """Score audience signal (views, engagement proxy)."""
        # We don't have view counts from flat extraction, use channel as proxy
        channel_lower = candidate.channel.lower()
        
        if any(kw in channel_lower for kw in ["fifa", "uefa", "official", "premier league", "espn", "sky sports", "bt sport", "bein"]):
            return 1.0
        if any(kw in channel_lower for kw in ["football", "soccer", "highlights", "goals"]):
            return 0.7
        return 0.3
    
    def _score_source_quality(self, candidate: SourceCandidate) -> float:
        """Score source quality (resolution, encoding)."""
        # Duration check - very short or very long are penalties
        if candidate.duration < 30:
            return 0.3
        if candidate.duration > 3600:
            return 0.5
        if 60 <= candidate.duration <= 1800:
            return 1.0
        return 0.7
    
    def _score_transformability(self, candidate: SourceCandidate) -> float:
        """Score transformability for fair use."""
        title_lower = candidate.title.lower()
        
        # Penalize compilations, fan edits, copyrighted music focus
        if any(kw in title_lower for kw in ["compilation", "mix", "music", "song", "lyrics", "trap", "edit", "amv"]):
            return 0.2
        
        # Good for transformative use: raw match footage, tactical analysis
        if any(kw in title_lower for kw in ["tactical", "analysis", "breakdown", "full match", "raw", "footage"]):
            return 1.0
            
        return 0.7
    
    def _score_verification(self, candidate: SourceCandidate) -> float:
        """Score verification confidence from metadata."""
        # Has upload date
        if candidate.upload_date:
            return 0.5
        return 0.2


class Deduplicator:
    """Removes duplicate videos by video_id."""
    
    def deduplicate(self, candidates: list[SourceCandidate]) -> list[SourceCandidate]:
        seen = set()
        unique = []
        for c in candidates:
            if c.video_id and c.video_id not in seen:
                seen.add(c.video_id)
                unique.append(c)
        return unique


class DiscoveryEngine:
    """
    Main discovery engine coordinating search, ranking, and deduplication.
    
    Produces ranked candidate pools per story slot.
    """
    
    def __init__(self):
        self.adapter = DiscoveryAdapter()
        self.ranker = CandidateRanker()
        self.deduplicator = Deduplicator()
    
    def discover_for_slot(
        self,
        story_slot: str,
        queries: list[str],
        target_emotion: str = "",
        max_per_query: int = 5
    ) -> list[SourceCandidate]:
        """Discover and rank candidates for a single story slot."""
        # Search
        candidates = self.adapter.search_multiple(
            queries=queries,
            story_slot=story_slot,
            max_results_per_query=max_per_query
        )
        
        # Deduplicate
        candidates = self.deduplicator.deduplicate(candidates)
        
        # Rank
        candidates = self.ranker.rank(candidates, story_slot, target_emotion)
        
        return candidates
    
    def discover_all_slots(
        self,
        slot_queries: dict[str, list[str]],
        target_emotion: str = ""
    ) -> dict[str, list[SourceCandidate]]:
        """Discover candidates for all story slots."""
        results = {}
        for slot, queries in slot_queries.items():
            results[slot] = self.discover_for_slot(slot, queries, target_emotion)
        return results


def create_story_slot_queries(
    topic: str,
    players: list[str],
    teams: list[str],
    competitions: list[str],
    target_emotion: str
) -> dict[str, list[str]]:
    """
    Generate multi-style queries for each story slot.
    
    Returns dict of story_slot -> list of query strings.
    """
    # Base components
    player_str = " ".join(players[:2]) if players else ""
    team_str = " ".join(teams[:2]) if teams else ""
    comp_str = " ".join(competitions[:1]) if competitions else ""
    topic_str = topic
    
    # Common query templates per slot (5 styles per architecture)
    slot_templates = {
        "opening_pressure": [
            f"{player_str} {team_str} {comp_str} pressure tension build up",
            f"{player_str} nervous anxious before {comp_str} final",
            f"football pressure moment {player_str} {comp_str} cinematic",
            f"official broadcast {team_str} {comp_str} tunnel walk atmosphere",
            f"{player_str} {comp_str} pression tension avant match",  # French
        ],
        "stadium_atmosphere": [
            f"{team_str} {comp_str} stadium atmosphere crowd chanting",
            f"{comp_str} final stadium full roar atmosphere",
            f"football stadium atmosphere cinematic {team_str} fans",
            f"broadcast {team_str} stadium atmosphere pre match",
            f"{team_str} estadio ambiente aficionados {comp_str}",  # Spanish
        ],
        "player_closeup": [
            f"{player_str} close up face reaction {comp_str}",
            f"{player_str} emotional face tears joy {comp_str}",
            f"cinematic football player portrait {player_str} {comp_str}",
            f"official {player_str} close up {comp_str} broadcast quality",
            f"{player_str} primer plano cara emocion {comp_str}",  # Spanish
        ],
        "critical_attack": [
            f"{player_str} {team_str} attack chance {comp_str} goal",
            f"{player_str} missed chance {comp_str} heartbreak",
            f"football attacking move {team_str} {comp_str} tactical",
            f"broadcast {team_str} dangerous attack {comp_str} build up",
            f"{player_str} ataque oportunidad gol {comp_str}",  # Spanish
        ],
        "goalkeeper_reaction": [
            f"goalkeeper save reaction {comp_str} {team_str}",
            f"penalty save goalkeeper {comp_str} dramatic",
            f"football goalkeeper dive save {comp_str} close up",
            f"official goalkeeper {comp_str} penalty shootout reaction",
            f"portero atajada reaccion {comp_str} penalti",  # Spanish
        ],
        "bench_reaction": [
            f"bench reaction {team_str} {comp_str} coach manager",
            f"substitute bench celebration {team_str} {comp_str}",
            f"football manager reaction touchline {comp_str} bench",
            f"broadcast coach bench reaction {comp_str} {team_str}",
            f"banquillo reaccion entrenador {team_str} {comp_str}",  # Spanish
        ],
        "crowd_eruption": [
            f"crowd eruption celebration {team_str} {comp_str} goal",
            f"fans go wild {player_str} goal {comp_str} stadium",
            f"football crowd celebration {team_str} {comp_str} eruption",
            f"broadcast stadium eruption {comp_str} winning goal",
            f"aficion celebracion gol {team_str} {comp_str} estadio",  # Spanish
        ],
        "opposition_disappointment": [
            f"opposition disappointed {comp_str} {team_str} defeat",
            f"heartbreak tears {team_str} opponent {comp_str} loss",
            f"football defeat reaction opposition {comp_str} devastated",
            f"broadcast losing team reaction {comp_str} final whistle",
            f"derrota desconsuelo llanto {team_str} {comp_str}",  # Spanish
        ],
        "final_celebration": [
            f"{player_str} lifting trophy {comp_str} celebration",
            f"{team_str} champions {comp_str} trophy lift party",
            f"football championship celebration {team_str} {comp_str} winners",
            f"official trophy presentation {team_str} {comp_str} champions",
            f"{player_str} levanta trofeo campeon {comp_str} celebracion",  # Spanish
        ],
        "ending_image": [
            f"final whistle {comp_str} {team_str} empty stadium silence",
            f"{player_str} walking away {comp_str} reflection",
            f"football poetic ending {comp_str} final image cinematic",
            f"broadcast post match empty stadium {comp_str} aftermath",
            f"silencio estadio final {comp_str} {team_str} reflexion",  # Spanish
        ],
    }
    
    return slot_templates


# CLI for testing
if __name__ == "__main__":
    import sys
    
    # Test discovery
    engine = DiscoveryEngine()
    
    # Example: Messi World Cup 2022
    slot_queries = create_story_slot_queries(
        topic="Messi World Cup 2022 final",
        players=["Messi"],
        teams=["Argentina", "France"],
        competitions=["World Cup 2022"],
        target_emotion="triumph"
    )
    
    print("Testing discovery for 'opening_pressure' slot...")
    candidates = engine.discover_for_slot(
        story_slot="opening_pressure",
        queries=slot_queries["opening_pressure"][:3],  # Test first 3 queries
        target_emotion="triumph"
    )
    
    print(f"Found {len(candidates)} candidates:")
    for c in candidates[:5]:
        print(f"  [{c.ranking_score:.1f}] {c.title[:60]} - {c.channel} - {c.duration}s - {c.deep_analysis_candidate}")
        print(f"       ID: {c.candidate_id} | URL: {c.url}")