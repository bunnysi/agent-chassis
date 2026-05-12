from __future__ import annotations

from datetime import datetime, timezone

from .models import ScheduledJob, ScheduledJobRequest, ScheduledJobStatus, TriggerKind, now_iso


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchedulerRegistry:
    """Minimal scheduling layer for manual/cron/event triggers.

    v0 standardizes scheduled/manual/event work definitions and can scan due
    cron jobs. It intentionally supports a small cron subset first:
    `*`, `*/N`, or an exact integer for minute/hour fields.
    """

    def create_job(self, request: ScheduledJobRequest) -> ScheduledJob:
        status = ScheduledJobStatus.active if request.enabled else ScheduledJobStatus.paused
        return ScheduledJob(
            name=request.name,
            agent_id=request.agent_id,
            graph_id=request.graph_id,
            trigger=request.trigger,
            schedule=request.schedule,
            status=status,
            topic=request.topic,
            sources=request.sources,
            auto_approve=request.auto_approve,
            metadata=request.metadata,
        )

    def mark_triggered(self, job: ScheduledJob, run_id: str, *, triggered_at: str | None = None) -> ScheduledJob:
        job.last_run_id = run_id
        job.last_run_at = triggered_at or now_iso()
        job.run_count += 1
        job.updated_at = now_iso()
        return job

    def due_jobs(self, jobs: list[ScheduledJob], *, now: datetime | None = None) -> list[ScheduledJob]:
        current = now or _utcnow()
        return [job for job in jobs if self.is_due(job, now=current)]

    def is_due(self, job: ScheduledJob, *, now: datetime | None = None) -> bool:
        if job.status != ScheduledJobStatus.active:
            return False
        if job.trigger != TriggerKind.cron:
            return False
        if not job.schedule:
            return False
        current = now or _utcnow()
        last_run_at = _parse_dt(job.last_run_at)
        if last_run_at and last_run_at.replace(second=0, microsecond=0) >= current.replace(second=0, microsecond=0):
            return False
        return _cron_matches(job.schedule, current)

    def set_status(self, job: ScheduledJob, status: ScheduledJobStatus) -> ScheduledJob:
        job.status = status
        job.updated_at = now_iso()
        return job


def _cron_matches(expression: str, moment: datetime) -> bool:
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError("cron schedule must have 5 fields")
    minute, hour, day, month, weekday = parts
    return (
        _field_matches(minute, moment.minute, 0, 59)
        and _field_matches(hour, moment.hour, 0, 23)
        and _field_matches(day, moment.day, 1, 31)
        and _field_matches(month, moment.month, 1, 12)
        and _field_matches(weekday, (moment.weekday() + 1) % 7, 0, 6)
    )


def _field_matches(field: str, value: int, minimum: int, maximum: int) -> bool:
    if field == "*":
        return True
    if field.startswith("*/"):
        step = int(field[2:])
        return step > 0 and value % step == 0
    exact = int(field)
    if exact < minimum or exact > maximum:
        raise ValueError("cron field out of range")
    return value == exact
