import logging

from samuraizer.backend.analysis import hash_service


def test_hash_service_fallback_without_xxhash(monkeypatch, tmp_path, caplog):
    """HashService should fall back to hashlib when xxhash is unavailable."""

    default_registry = hash_service._build_default_registry()
    fallback_only_registry = hash_service.HashRegistry(
        backend for backend in default_registry.backends if backend.name != "xxhash64"
    )
    monkeypatch.setattr(hash_service, "_HASH_REGISTRY", fallback_only_registry)

    file_path = tmp_path / "sample.txt"
    file_path.write_bytes(b"samuraizer")

    with caplog.at_level(logging.WARNING):
        digest = hash_service.HashService.compute_file_hash(file_path)

    assert digest is not None
    assert len(digest) == 16  # 64-bit hex digest, matching xxhash64 output length
    assert any("xxhash package is not installed" in record.message for record in caplog.records)

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        hash_service.HashService.compute_file_hash(file_path)

    assert not any("xxhash package is not installed" in record.message for record in caplog.records)
