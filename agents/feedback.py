"""
Feedback Loop & Moat Engine
Pulls actual post views and retention from official APIs, links them with clip features,
evaluates predictive accuracy, and optimizes curator and judge prompts over time.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import numpy as np
from pydantic import BaseModel, Field


class ClipFeatureVector(BaseModel):
    """Features extracted from a clip to correlate with actual retention."""
    clip_id: str
    predicted_score: int = Field(ge=0, le=100)
    duration_seconds: float
    hook_word_count: int
    caption_style: str
    speaker_count: int
    has_punch_in: bool
    actual_views: int = 0
    actual_retention_rate: float = 0.0  # 0.0 to 1.0 (e.g. 0.85 = 85% average view duration)
    actual_likes: int = 0
    actual_shares: int = 0


class MoatFeedbackEngine:
    """The Moat: Continuously trains and refines agent curation rubrics on real audience retention and persists to DB."""

    def __init__(self, db: Optional[Any] = None):
        self.data_store: Dict[str, ClipFeatureVector] = {}
        self.db = db

    def record_clip_features(
        self,
        clip_id: str,
        predicted_score: int,
        duration_seconds: float,
        hook: str,
        caption_style: str = "hormozi",
        speaker_count: int = 1,
        has_punch_in: bool = True,
        db: Optional[Any] = None
    ) -> ClipFeatureVector:
        """Stores the initial generation features of a clip and persists to database if session available."""
        words = hook.strip().split() if hook else []
        vec = ClipFeatureVector(
            clip_id=clip_id,
            predicted_score=predicted_score,
            duration_seconds=round(duration_seconds, 2),
            hook_word_count=len(words),
            caption_style=caption_style,
            speaker_count=speaker_count,
            has_punch_in=has_punch_in
        )
        self.data_store[clip_id] = vec

        # Database persistence
        session = db or self.db
        if session:
            try:
                from backend.models import Clip
                clip_row = session.query(Clip).filter(Clip.id == clip_id).first()
                if clip_row:
                    clip_row.viral_score = predicted_score
                    clip_row.duration = duration_seconds
                    clip_row.hook = hook
                    session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass

        return vec

    def sync_actual_metrics(
        self,
        clip_id: str,
        views: int,
        retention_rate: float,
        likes: int = 0,
        shares: int = 0,
        db: Optional[Any] = None
    ) -> Optional[ClipFeatureVector]:
        """Updates a clip with verified post performance from official platform APIs and persists to database."""
        session = db or self.db
        if clip_id not in self.data_store and session:
            try:
                from backend.models import Clip
                c = session.query(Clip).filter(Clip.id == clip_id).first()
                if c:
                    words = c.hook.strip().split() if c.hook else []
                    self.data_store[clip_id] = ClipFeatureVector(
                        clip_id=clip_id,
                        predicted_score=c.viral_score or 80,
                        duration_seconds=round(c.duration or 30.0, 2),
                        hook_word_count=len(words),
                        caption_style="hormozi",
                        speaker_count=1,
                        has_punch_in=True
                    )
            except Exception:
                pass

        if clip_id not in self.data_store:
            return None

        vec = self.data_store[clip_id]
        vec.actual_views = views
        vec.actual_retention_rate = round(retention_rate, 4)
        vec.actual_likes = likes
        vec.actual_shares = shares

        # Database persistence to ClipMetric
        if session:
            try:
                from backend.models import ClipMetric
                metric = session.query(ClipMetric).filter(ClipMetric.clip_id == clip_id).first()
                if not metric:
                    metric = ClipMetric(
                        clip_id=clip_id,
                        views=views,
                        retention_rate=round(retention_rate, 4),
                        likes=likes,
                        shares=shares,
                        last_synced_at=datetime.now(timezone.utc)
                    )
                    session.add(metric)
                else:
                    metric.views = views
                    metric.retention_rate = round(retention_rate, 4)
                    metric.likes = likes
                    metric.shares = shares
                    metric.last_synced_at = datetime.now(timezone.utc)
                session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass

        return vec

    def load_from_db(self, db: Optional[Any] = None) -> int:
        """Loads historical clips and associated metrics from the database into in-memory data store."""
        session = db or self.db
        if not session:
            return 0
        try:
            from backend.models import Clip, ClipMetric
            clips = session.query(Clip).all()
            loaded = 0
            for c in clips:
                metric = session.query(ClipMetric).filter(ClipMetric.clip_id == c.id).first()
                views = metric.views if metric else 0
                retention = metric.retention_rate if metric else 0.0
                likes = metric.likes if metric else 0
                shares = metric.shares if metric else 0
                words = c.hook.strip().split() if c.hook else []
                vec = ClipFeatureVector(
                    clip_id=str(c.id),
                    predicted_score=c.viral_score or 80,
                    duration_seconds=round(c.duration or 30.0, 2),
                    hook_word_count=len(words),
                    caption_style="hormozi",
                    speaker_count=1,
                    has_punch_in=True,
                    actual_views=views,
                    actual_retention_rate=retention,
                    actual_likes=likes,
                    actual_shares=shares
                )
                self.data_store[str(c.id)] = vec
                loaded += 1
            return loaded
        except Exception:
            return 0

    def compute_accuracy_metrics(self) -> Dict[str, Any]:
        """Computes correlation and error between predicted virality scores and actual retention."""
        samples = [v for v in self.data_store.values() if v.actual_views > 0 or v.actual_retention_rate > 0]
        if len(samples) < 2:
            return {
                "sample_count": len(samples),
                "correlation": 0.0,
                "mean_absolute_error": 0.0,
                "status": "Insufficient data (minimum 2 published clips required)"
            }

        predicted = np.array([s.predicted_score for s in samples], dtype=float)
        # Scale retention rate (0.0 - 1.0) to 0-100 scale
        actual_scaled = np.array([s.actual_retention_rate * 100.0 for s in samples], dtype=float)

        mae = float(np.mean(np.abs(predicted - actual_scaled)))

        # Pearson correlation
        std_pred = float(np.std(predicted))
        std_actual = float(np.std(actual_scaled))
        if std_pred > 1e-6 and std_actual > 1e-6:
            r = float(np.corrcoef(predicted, actual_scaled)[0, 1])
            corr = 0.0 if (np.isnan(r) or np.isinf(r)) else round(r, 3)
        else:
            # Mathematical truth: zero variance means correlation is undefined / 0.0
            # Never invent an arbitrary 0.85
            corr = 0.0

        return {
            "sample_count": len(samples),
            "correlation": corr,
            "mean_absolute_error": round(mae, 2),
            "status": "Calibrated"
        }

    def generate_prompt_optimizations(self) -> str:
        """
        Synthesizes high-performing patterns into a system prompt calibration rule
        injected into ViralCuratorAgent and JudgeAgent.
        """
        samples = [v for v in self.data_store.values() if v.actual_retention_rate > 0]
        if not samples:
            return "Prioritize curiosity hooks, durations between 25-45s, and high speech velocity."

        # Separate top performers (>70th percentile retention)
        retentions = [s.actual_retention_rate for s in samples]
        threshold = np.percentile(retentions, 60)
        top_clips = [s for s in samples if s.actual_retention_rate >= threshold]

        avg_dur = float(np.mean([c.duration_seconds for c in top_clips])) if top_clips else 32.0
        styles = [c.caption_style for c in top_clips]
        best_style = max(set(styles), key=styles.count) if styles else "hormozi"

        guidance = (
            f"REAL AUDIENCE FEEDBACK RULE: Clips for this creator have highest retention (~{int(threshold*100)}%+) "
            f"at an average duration of {int(avg_dur)}s with '{best_style}' caption styling. "
            f"Penalize clips longer than {int(avg_dur + 15)}s."
        )
        return guidance
