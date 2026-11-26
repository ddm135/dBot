from cogs.role import plan_set

ORDER = [1, 2, 3, 4, 5, 6]  # lowest to highest
GROUP = {2, 3, 4, 6}


def test_set_wears_the_target_and_below_and_stores_above():
    change = plan_set(ORDER, GROUP, target=3, worn={4, 6, 1}, stored={2, 3})
    assert change.apply == (2, 3)
    assert change.store == (4, 6)  # 1 is not a group role, so it is left alone


def test_set_to_the_top_stores_nothing():
    change = plan_set(ORDER, GROUP, target=6, worn={2}, stored={3, 4, 6})
    assert change.apply == (3, 4, 6) and change.store == ()


def test_set_ignores_roles_already_worn_or_not_owned():
    change = plan_set(ORDER, GROUP, target=4, worn={2, 3, 4}, stored=set())
    assert change.apply == () and change.store == ()
