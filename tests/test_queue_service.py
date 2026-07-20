from __future__ import annotations

from app.models.download_job import DownloadJob, DownloadStatus
from app.services.queue_service import QueueService


def _job(**kw) -> DownloadJob:
    base = dict(
        url="https://example.com/x",
        title="Titre",
        mode="video",
        quality="1080p",
        output_format="mp4",
        destination="C:/Downloads",
        filename_template="%(title)s.%(ext)s",
    )
    base.update(kw)
    return DownloadJob(**base)


def test_download_job_roundtrip_preserves_status_enum():
    job = _job()
    job.status = DownloadStatus.RUNNING
    restored = DownloadJob.from_dict(job.to_dict())
    assert restored.status is DownloadStatus.RUNNING
    assert restored.status.value == "running"
    assert restored.url == job.url
    assert restored.id == job.id


def test_from_dict_ignores_unknown_keys():
    data = _job().to_dict()
    data["totally_unknown"] = 123
    restored = DownloadJob.from_dict(data)
    assert restored.title == "Titre"


def test_queue_service_save_and_load(tmp_path, monkeypatch):
    path = tmp_path / "queue.json"
    monkeypatch.setattr("app.services.queue_service.queue_path", lambda: path)
    service = QueueService()
    jobs = [_job(title="A"), _job(title="B")]
    service.save(jobs)
    loaded = service.load()
    assert [entry["title"] for entry in loaded] == ["A", "B"]
    service.clear()
    assert service.load() == []
