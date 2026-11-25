def test_a_frozen_heap_is_skipped_by_collections_and_released_when_asked():
    import gc

    from games.bundles import freeze_heap, release_memory

    keep = [{"a": [1, 2, 3]} for _ in range(100)]  # stands in for the tables
    freeze_heap()
    assert gc.get_freeze_count() >= len(keep)
    release_memory()  # one bundle's worth: the frozen objects stay frozen
    assert gc.get_freeze_count() >= len(keep)
    release_memory(everything=True)  # a whole bot dropped
    assert gc.get_freeze_count() == 0
    del keep
