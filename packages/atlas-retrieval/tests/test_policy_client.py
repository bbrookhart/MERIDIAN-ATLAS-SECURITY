import httpx
from atlas_retrieval.policy_client import authorize_post, authorize_pre


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_authorize_pre_returns_visible_roles():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b'"mode": "pre"' in body or b'"mode":"pre"' in body
        return httpx.Response(200, json={"visible_roles": ["broker", "shared"]})

    async with _client(handler) as client:
        roles = await authorize_pre(client, "http://atlas-control", "broker")
    assert roles == ["broker", "shared"]


async def test_authorize_post_returns_per_chunk_decisions():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "decisions": [
                    {
                        "chunk_id": 1,
                        "allowed_roles": ["broker"],
                        "allow": True,
                        "rule": "role_in_allowed_roles",
                    },
                    {
                        "chunk_id": 2,
                        "allowed_roles": ["hr"],
                        "allow": False,
                        "rule": "role_not_permitted",
                    },
                ]
            },
        )

    async with _client(handler) as client:
        decisions = await authorize_post(
            client,
            "http://atlas-control",
            "broker",
            [
                {"chunk_id": 1, "allowed_roles": ["broker"]},
                {"chunk_id": 2, "allowed_roles": ["hr"]},
            ],
        )
    assert decisions[0].allow is True
    assert decisions[1].allow is False
    assert decisions[1].chunk_id == 2
