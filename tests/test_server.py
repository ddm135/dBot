import json
from types import SimpleNamespace

from games.api.server import Server

JYPNATION_LOGIN = (
    '{{"class":"Account","method":"loginSNS",'
    '"params":[{provider},"{id_token}",1,"{version}"]}}'
)
JYP_LOGIN = (
    '{{"class":"Account","method":"loginSNS",'
    '"params":[{provider},"{access_token}",1,"{version}",false],"ptDelta":1}}'
)


async def _check(fields):
    from games.api.auth import LoginCredentials

    sent = []

    class Spy(Server):
        async def call(self, url, payload):  # type: ignore[override]
            sent.append(json.loads(payload)["params"])
            return {"result": {"isSigned": True}}

    credentials = LoginCredentials(provider=fields["provider"], fields=fields)
    manifest = SimpleNamespace(server_url="http://x")
    await Spy(None, None).check_sns(manifest, credentials, "tok", "3.7.1")  # type: ignore[arg-type]
    return sent[0]


async def test_check_sns_takes_the_flag_only_where_the_login_does():
    assert await _check({"provider": 0, "account": JYPNATION_LOGIN}) == [0, "tok"]
    assert await _check({"provider": 3, "account": JYP_LOGIN}) == [3, "tok", False]
    assert await _check({"provider": 3}) == [3, "tok", False]  # no template: usual


class _Recorder(Server):
    def __init__(self):
        self.sent = []

    async def call(self, url, payload):  # type: ignore[override]
        self.sent.append(json.loads(payload))
        return {"result": {"user": {"objectID": 1}}, "invoke": [{"params": ["k"]}]}


async def _login(fields):
    from games.api.auth import LoginCredentials

    server = _Recorder()
    manifest = SimpleNamespace(server_url="http://x")
    credentials = LoginCredentials(provider=fields["provider"], fields=fields)
    await server.login_sns(manifest, credentials, "tok", "3.7.1")  # type: ignore[arg-type]
    return server.sent[0]


async def test_sns_login_follows_the_games_template():
    jyp_nation = await _login(
        {"provider": 0, "account": JYPNATION_LOGIN, "isSNS": True}
    )
    assert jyp_nation["params"] == [0, "tok", 1, "3.7.1"]  # no trailing false
    assert "ptDelta" not in jyp_nation

    jyp = await _login({"provider": 3, "account": JYP_LOGIN, "isSNS": True})
    assert jyp["params"] == [3, "tok", 1, "3.7.1", False] and jyp["ptDelta"] == 1


async def test_sns_login_without_a_template_sends_the_usual_request():
    sent = await _login({"provider": 3, "isSNS": True})
    assert sent["params"] == [3, "tok", 1, "3.7.1", False] and sent["ptDelta"] == 1
