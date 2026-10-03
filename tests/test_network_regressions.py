"""Exercise malformed streams, worker cleanup and repeatable server hosting."""

import copy
import json
import socket
import threading
import time
from unittest.mock import patch

import pytest

from ttx.net import client, server
from ttx.net.protocol import JsonLineReader, ProtocolError, valid_snapshot
from ttx.net.transport import SnapshotWriter
from ttx.terminal import CardTerminal, TerminalRenderer


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            pytest.fail("Timed out waiting for worker state.")
        time.sleep(0.005)


def test_utf8_frames_survive_every_possible_packet_boundary():
    payload = (json.dumps({"label": "測試", "move": 1}, ensure_ascii=False) + "\n").encode()
    for boundary in range(len(payload) + 1):
        reader = JsonLineReader(128)
        frames = list(reader.feed(payload[:boundary])) + list(reader.feed(payload[boundary:]))
        assert frames == [{"label": "測試", "move": 1}]


@pytest.mark.parametrize("payload", [b"[]\n", b"null\n", b"1\n", b'{"x":NaN}\n', b'{bad}\n', b'{"x":\xff}\n'])
def test_invalid_json_frames_are_rejected(payload):
    with pytest.raises(ProtocolError):
        list(JsonLineReader(128).feed(payload))


def test_message_limit_applies_to_each_frame_and_unterminated_data():
    reader = JsonLineReader(8)
    assert list(reader.feed(b'{}\n' * 20)) == [{}] * 20
    with pytest.raises(ProtocolError):
        list(reader.feed(b'x' * 9))
    with pytest.raises(ProtocolError):
        list(JsonLineReader(8).feed(b'123456789\n'))


@pytest.mark.parametrize("message", [
    [], None, {"pause": "yes"}, {"build": True, "x": None},
    {"gather": True, "dx": "1"}, {"attack": True, "enemy_id": []},
    {"attack": True, "damage": -10}, {"input_seq": 1, "move": True},
    {"input_seq": 1, "move": float("nan")}, {"battle": {"start": True}},
])
def test_invalid_commands_do_not_mutate_world(message):
    with patch.dict(server.players, {"p": {"x": 5, "y": 21}}, clear=True):
        before = copy.deepcopy(server.players)
        server.process_message("p", message)
        assert server.players == before


def test_state_snapshot_is_detached_from_live_world():
    with patch.dict(server.players, {"p": {"x": 5, "y": 21, "inventory": {"wood": 1}}}, clear=True):
        state = server.build_state("p")
        server.players["p"]["inventory"]["wood"] += 1
        assert state["players"]["p"]["inventory"] == {"wood": 1}


@pytest.fixture
def host():
    handle = server.start_server(80, 30, verbose=False, host="127.0.0.1", port=0)
    try:
        yield handle
    finally:
        handle.stop()
    assert not server.connections
    assert not server.snapshot_writers
    assert not handle.runtime.handlers
    assert not handle.thread.is_alive()


def test_bind_failure_is_reported_to_caller_without_leaking_workers():
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        with pytest.raises(OSError):
            server.start_server(80, 30, verbose=False, host="127.0.0.1", port=occupied.getsockname()[1])
    assert server.server_socket is None
    assert server.server_runtime is None
    assert not any(thread.name.startswith("ttx-") for thread in threading.enumerate())


def test_second_host_does_not_reset_the_running_world(host):
    seed = server.map_seed
    with pytest.raises(RuntimeError, match="already running"):
        server.start_server(80, 30, verbose=False, host="127.0.0.1", port=0)
    assert server.map_seed == seed
    assert host.thread.is_alive()


def test_live_world_cannot_be_reset_without_stopping_its_workers(host):
    seed = server.map_seed
    with pytest.raises(RuntimeError, match="running"):
        server.reset_game_state(80, 30, seed=999)
    assert server.map_seed == seed
    assert host.thread.is_alive()


def test_reset_and_host_start_cannot_overwrite_each_others_world():
    entered = threading.Event()
    release = threading.Event()
    attempted = threading.Event()
    ready = threading.Event()
    result = {}
    original_init = server.InfiniteGameMap.__init__

    def slow_init(game_map, *args, **kwargs):
        if threading.current_thread().name == "reset-test":
            entered.set()
            assert release.wait(2)
        original_init(game_map, *args, **kwargs)

    def host_start():
        attempted.set()
        result["handle"] = server.start_server(80, 30, verbose=False, host="127.0.0.1", port=0)
        result["seed"] = server.map_seed
        ready.set()

    reset = threading.Thread(target=server.reset_game_state, args=(80, 30, 999), name="reset-test")
    starter = threading.Thread(target=host_start)
    try:
        with patch.object(server.InfiniteGameMap, "__init__", slow_init):
            reset.start()
            assert entered.wait(1)
            starter.start()
            assert attempted.wait(1)
            # A broken implementation can finish host startup while reset is
            # still generating, then replace that active world's seed with 999.
            ready.wait(0.2)
            release.set()
            reset.join(timeout=2)
            starter.join(timeout=2)
        assert not reset.is_alive() and not starter.is_alive()
        assert server.map_seed == result["seed"]
    finally:
        release.set()
        if reset.ident is not None:
            reset.join(timeout=2)
        if starter.ident is not None:
            starter.join(timeout=2)
        if "handle" in result:
            result["handle"].stop()


def test_host_is_ready_on_return_and_stop_joins_connected_workers(host):
    with socket.create_connection(("127.0.0.1", host.port), timeout=2) as peer:
        with peer.makefile("rb") as stream:
            state = json.loads(stream.readline())
            own_id = state["client_id"]
            assert own_id in state["players"]
            wait_until(lambda: bool(host.runtime.handlers))
            workers = list(host.runtime.handlers) + [writer.thread for writer in server.snapshot_writers.values()]
            host.stop()
            assert all(not worker.is_alive() for worker in workers)
            assert not server.players


def test_old_handle_cannot_stop_a_new_host():
    old = server.start_server(80, 30, verbose=False, host="127.0.0.1", port=0)
    old.stop()
    current = server.start_server(80, 30, verbose=False, host="127.0.0.1", port=0)
    try:
        old.stop()
        assert current.thread.is_alive()
        assert not server.server_stop_event.is_set()
    finally:
        current.stop()


def test_same_port_can_be_rehosted_after_stopping_connected_clients():
    first = server.start_server(80, 30, verbose=False, host="127.0.0.1", port=0)
    peer = socket.create_connection(("127.0.0.1", first.port), timeout=2)
    second = None
    try:
        with peer.makefile("rb") as stream:
            json.loads(stream.readline())
        port = first.port
        first.stop()
        second = server.start_server(80, 30, verbose=False, host="127.0.0.1", port=port)
        assert second.thread.is_alive()
    finally:
        peer.close()
        first.stop()
        if second is not None:
            second.stop()


def test_more_than_ten_connections_get_distinct_walkable_spawns(host):
    peers = []
    try:
        positions = []
        for _ in range(12):
            peer = socket.create_connection(("127.0.0.1", host.port), timeout=2)
            peers.append(peer)
            with peer.makefile("rb") as stream:
                state = json.loads(stream.readline())
                player = state["players"][state["client_id"]]
                positions.append((player["x"], player["y"]))
                assert server.world_map.is_walkable(player["x"], player["y"])
        assert len(set(positions)) == 12
    finally:
        for peer in peers:
            peer.close()


def test_invalid_numeric_command_does_not_disconnect_a_healthy_peer(host):
    with socket.create_connection(("127.0.0.1", host.port), timeout=2) as peer:
        with peer.makefile("rb") as stream:
            initial = json.loads(stream.readline())
            own_id = initial["client_id"]
            peer.sendall(b'{"gather":true,"dx":null}\n{"pause":true}\n')
            for _ in range(40):
                snapshot = json.loads(stream.readline())
                if snapshot["players"][own_id].get("paused"):
                    break
            assert snapshot["players"][own_id].get("paused")


def test_unterminated_large_input_releases_the_player(host):
    with socket.create_connection(("127.0.0.1", host.port), timeout=2) as peer:
        with peer.makefile("rb") as stream:
            own_id = json.loads(stream.readline())["client_id"]
            peer.sendall(b'x' * (64 * 1024 + 1))
            wait_until(lambda: own_id not in server.players)


def test_snapshot_writer_coalesces_backlog_without_blocking_publish():
    class SlowPeer:
        def __init__(self):
            self.writes = []
            self.started = threading.Event()
            self.release = threading.Event()

        def sendall(self, payload):
            self.writes.append(payload)
            self.started.set()
            assert self.release.wait(2)

        def shutdown(self, _how):
            self.release.set()

    peer = SlowPeer()
    writer = SnapshotWriter(peer)
    writer.start()
    try:
        writer.publish(b"first")
        assert peer.started.wait(1)
        writer.publish(b"second")
        writer.publish(b"latest")
        peer.release.set()
        wait_until(lambda: len(peer.writes) == 2)
        assert peer.writes == [b"first", b"latest"]
    finally:
        peer.release.set()
        writer.close()
        writer.thread.join(timeout=2)
    assert not writer.thread.is_alive()


def test_listener_rejects_invalid_snapshot_without_poisoning_current_state():
    local, peer = socket.socketpair()
    stopped = threading.Event()
    previous = {"unchanged": True}
    with patch.object(client, "game_state", previous):
        listener = threading.Thread(target=client.network_listener, args=(local, stopped))
        listener.start()
        try:
            peer.sendall(b'{"players":[]}\n')
            assert stopped.wait(2)
            assert client.game_state is previous
        finally:
            stopped.set()
            peer.close()
            local.close()
            listener.join(timeout=2)
    assert not listener.is_alive()


@pytest.mark.parametrize("field,value", [
    ("facing", None), ("move", "right"), ("jump_buffer", {}),
    ("coyote_ticks", -1), ("input_seq", "1"),
])
def test_invalid_prediction_fields_are_rejected_before_rendering(field, value):
    with patch.dict(server.players, {"p": {"x": 5, "y": 21}}, clear=True):
        snapshot = server.build_state("p")
    assert valid_snapshot(snapshot)
    snapshot["players"]["p"][field] = value
    assert not valid_snapshot(snapshot)


def test_disconnected_battle_exits_instead_of_waiting_for_input_forever():
    screen = type("Screen", (), {"timeout": lambda *args: None})()
    stopped = threading.Event()
    stopped.set()
    terminal = CardTerminal(TerminalRenderer(screen), stop_event=stopped)
    with pytest.raises(ConnectionError):
        terminal.get_key()


def test_card_rewards_are_added_once_even_for_duplicate_reward_ids():
    game = client.Game.__new__(client.Game)
    game.card_deck_ids = ["strike"]
    packet = {"client_id": "p", "players": {"p": {"cards": ["first_aid"]}}}
    game._sync_card_rewards(packet)
    game._sync_card_rewards(packet)
    packet["players"]["p"]["cards"].append("first_aid")
    game._sync_card_rewards(packet)
    assert game.card_deck_ids == ["strike", "first_aid", "first_aid"]


def test_removed_local_player_does_not_select_someone_elses_actor():
    game = client.Game.__new__(client.Game)
    packet = {"client_id": "gone", "players": {"other": {"x": 5, "y": 21}}}
    with patch.object(client, "game_state", packet):
        assert game._my_player() is None
        assert game._server_player() is None
