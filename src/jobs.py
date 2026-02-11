"""Job management for async operations in Uthana plugin.

This module provides job tracking and polling for long-running operations
like video-to-motion and character upload with auto-rigging.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Optional

from .logger import logger


class JobStatus(Enum):
    """Status values for async jobs."""

    RESERVED = "RESERVED"
    READY = "READY"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, status: str) -> "JobStatus":
        """Convert string to JobStatus enum."""
        try:
            return cls(status.upper())
        except ValueError:
            return cls.UNKNOWN


@dataclass
class PendingJob:
    """Represents a pending async job."""

    job_id: str
    job_type: str  # "video_to_motion", "character_upload"
    started_at: float = field(default_factory=time.time)
    last_poll: float = 0
    poll_count: int = 0
    status: JobStatus = JobStatus.RESERVED
    result_data: Optional[Dict] = None
    error_message: Optional[str] = None
    timeout: float = 600  # 10 minutes default
    on_complete: Optional[Callable] = None
    on_progress: Optional[Callable] = None

    @property
    def is_complete(self) -> bool:
        """Check if job has reached a terminal state."""
        return self.status in (JobStatus.FINISHED, JobStatus.FAILED)

    @property
    def is_success(self) -> bool:
        """Check if job completed successfully."""
        return self.status == JobStatus.FINISHED

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since job started."""
        return time.time() - self.started_at

    @property
    def is_timed_out(self) -> bool:
        """Check if job has exceeded timeout."""
        return self.elapsed_time > self.timeout


class JobManager:
    """Manages async job polling.

    Singleton pattern to maintain state across operators.
    """

    _instance: Optional["JobManager"] = None

    def __init__(self):
        self.pending_jobs: Dict[str, PendingJob] = {}
        self.poll_interval: float = 2.0  # seconds

    @classmethod
    def instance(cls) -> "JobManager":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_job(self, job: PendingJob) -> None:
        """Add a new pending job."""
        self.pending_jobs[job.job_id] = job
        logger.info("Added job %s (type: %s) to pending jobs", job.job_id, job.job_type)

    def remove_job(self, job_id: str) -> Optional[PendingJob]:
        """Remove and return a job."""
        job = self.pending_jobs.pop(job_id, None)
        if job:
            logger.info("Removed job %s from pending jobs", job_id)
        return job

    def get_job(self, job_id: str) -> Optional[PendingJob]:
        """Get a pending job by ID."""
        return self.pending_jobs.get(job_id)

    def should_poll(self, job_id: str) -> bool:
        """Check if enough time has passed since last poll."""
        job = self.pending_jobs.get(job_id)
        if not job:
            return False
        now = time.time()
        return (now - job.last_poll) >= self.poll_interval

    def update_poll_time(self, job_id: str) -> None:
        """Update the last poll time for a job."""
        if job := self.pending_jobs.get(job_id):
            job.last_poll = time.time()
            job.poll_count += 1
            logger.debug("Updated poll time for job %s (count: %d)", job_id, job.poll_count)

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result_data: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update job status and optional result data."""
        if job := self.pending_jobs.get(job_id):
            job.status = status
            if result_data:
                job.result_data = result_data
            if error_message:
                job.error_message = error_message
            logger.info("Updated job %s status to %s", job_id, status.value)

    def get_active_jobs(self) -> list:
        """Get all jobs that are still active (not completed)."""
        return [job for job in self.pending_jobs.values() if not job.is_complete]

    def has_active_job_of_type(self, job_type: str) -> bool:
        """Check if there's an active job of the given type."""
        return any(
            job.job_type == job_type and not job.is_complete for job in self.pending_jobs.values()
        )

    def clear_completed_jobs(self) -> int:
        """Remove all completed jobs and return count removed."""
        completed = [job_id for job_id, job in self.pending_jobs.items() if job.is_complete]
        for job_id in completed:
            del self.pending_jobs[job_id]
        if completed:
            logger.info("Cleared %d completed jobs", len(completed))
        return len(completed)
