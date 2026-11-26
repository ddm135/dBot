import asyncio

from lease.leader import Leader, StepDownReason


class Backend:
    """An in-memory lease store: ``held`` is what the next renewal answers."""

    def __init__(self, held: bool = True, preferred_waiting: bool = False) -> None:
        self.held = held
        self.waiting = preferred_waiting
        self.calls: list[str] = []

    async def acquire_or_renew(self) -> bool:
        self.calls.append("acquire")
        return self.held

    async def release(self) -> None:
        self.calls.append("release")

    async def advertise_preferred(self) -> None:
        self.calls.append("advertise")

    async def preferred_waiting(self) -> bool:
        return self.waiting


class Time:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.now += delay
        await asyncio.sleep(0)


def make(backend: Backend, time: Time, *, preferred: bool = False) -> Leader:
    return Leader(
        backend,
        ttl=10,
        renew_interval=3,
        poll_interval=1,
        margin=2,
        request_timeout=1,
        preferred=preferred,
        clock=time,
        sleep=time.sleep,
    )


async def test_a_standby_takes_a_free_lease():
    leader = make(Backend(), Time())
    assert await leader.acquire()


async def test_a_standby_defers_while_the_preferred_instance_is_waiting():
    backend = Backend(preferred_waiting=True)
    stop = asyncio.Event()
    leader = make(backend, Time())
    task = asyncio.create_task(leader.acquire(stop))
    await asyncio.sleep(0.01)
    stop.set()
    assert await task is False
    assert "acquire" not in backend.calls


async def test_holding_ends_when_another_instance_has_the_lease():
    backend = Backend()
    time = Time()
    leader = make(backend, time)
    assert await leader.acquire()
    backend.held = False
    assert await leader.hold() is StepDownReason.LOST


async def test_a_standby_hands_over_to_the_preferred_instance():
    backend = Backend()
    leader = make(backend, Time())
    assert await leader.acquire()
    backend.waiting = True
    assert await leader.hold() is StepDownReason.HANDOVER
