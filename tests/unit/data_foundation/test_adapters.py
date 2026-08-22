from app.integrations.google.adapters import (
    FakeBigQueryClient,
    FakeDriveClient,
    RestBigQueryClient,
    RestDriveClient,
)


def test_fake_and_rest_adapters_share_runtime_contract() -> None:
    for client in (FakeDriveClient(), RestDriveClient()):
        assert hasattr(client, "list_children")
        assert hasattr(client, "download_file")
        assert hasattr(client, "get_file")
    for client in (FakeBigQueryClient(), RestBigQueryClient()):
        assert hasattr(client, "query_preview")
        assert hasattr(client, "get_table_physical")
        assert hasattr(client, "list_tables")


def test_fake_preview_rejects_select_star() -> None:
    client = FakeBigQueryClient()
    try:
        client.query_preview(access_token="t", sql="SELECT * FROM t")
        raised = False
    except ValueError:
        raised = True
    assert raised
