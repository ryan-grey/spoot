"""Embed-only cards must survive migration, backfill, search, and edits."""
import json
import sqlite3
from test_server import server, fx


def test_migrate_legacy_index_and_search_cards(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    monkeypatch.setattr(server, "INDEX_DB", path)
    con = sqlite3.connect(path)
    con.executescript(server.SCHEMA)
    con.execute("INSERT INTO messages(id, source, channel_id, content) VALUES (1, 'bot', '2', 'oldword')")
    con.commit()
    con.close()
    con = server._index_con()
    assert con.execute("SELECT message_content FROM messages").fetchone()[0] == "oldword"
    assert con.execute("SELECT count(*) FROM fts WHERE fts MATCH 'oldword'").fetchone()[0] == 1
    embed = {"title": "Heroic victory", "description": "Sentinel defeated",
             "fields": [{"name": "Progress", "value": "4/8 unique bosses"}],
             "author": {"name": "Saturday Raid"}, "footer": {"text": "First kill"},
             "url": "https://example.com/recap", "image": {"url": "https://example.com/card.png"},
             "thumbnail": {"url": "https://example.com/thumb.png"}}
    msg = {"id": "1", "source": "bot", "channel_id": "2", "content": "", "embeds": [embed]}
    server._upsert_message(con, msg)
    con.commit()
    result = json.loads(server.search_messages('"Saturday Raid" Heroic'))
    assert result["count"] == 1
    row = result["messages"][0]
    assert row["embeds"] == [embed]
    assert row["message_content"] == ""
    for text in ("4/8 unique bosses", "https://example.com/card.png", "First kill"):
        assert text in row["content"]
    assert json.loads(server.search_messages("oldword"))["count"] == 0
    # Reprocessing a source without embed support must not discard stored embeds.
    server._upsert_message(con, {k: v for k, v in msg.items() if k != "embeds"})
    con.commit()
    assert json.loads(server.search_messages("Sentinel"))["count"] == 1
    # Lower-ranked exports cannot clobber the card.
    server._upsert_message(con, {**msg, "source": "export", "embeds": []})
    con.commit()
    assert json.loads(server.search_messages("Sentinel"))["count"] == 1
    # An explicit embed removal must clear both the stored card and search terms.
    server._upsert_message(con, {**msg, "content": "replacement", "embeds": []})
    con.commit()
    assert json.loads(server.search_messages("Sentinel"))["count"] == 0
    assert json.loads(server.search_messages("replacement"))["messages"][0]["embeds"] == []
    con.close()
    # Opening a migrated index again is harmless.
    server._index_con().close()


def test_backfill_embed_only_posts_and_continue(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "INDEX_DB", tmp_path / "cards.db")
    api = fx.FakeDiscord()
    cid = fx.RAIDS["id"]
    api.messages[cid] = []
    for i in range(101):
        msg = api.add(cid, fx.BOT, "", "2026-08-04T01:00:00+00:00", mid=str(8000 + i))
        msg["embeds"] = [{"title": "Victory", "image": {"url": "https://example.com/card.png"}}]
    def request(method, path, body=None, params=None):
        if path == f"/channels/{cid}":
            return {**fx.RAIDS, "guild_id": fx.GUILD["id"]}
        return api(method, path, body, params)
    monkeypatch.setattr(server, "_api", request)
    first = json.loads(server.sync_channel(cid, full=True, max_pages=1))
    assert first["fetched"] == 100 and first["more"]
    assert first["empty_content"] == 0
    second = json.loads(server.sync_channel(cid, max_pages=1))
    assert second["fetched"] == 1 and not second["more"]
    assert json.loads(server.search_messages("Victory", limit=200))["count"] == 101
    assert json.loads(server.sync_channel(cid))["fetched"] == 0
    assert all(call[0] == "GET" for call in api.calls)
