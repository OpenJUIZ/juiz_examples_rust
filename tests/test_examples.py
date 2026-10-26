"""README のサンプルを実際に動かして結果を確かめるテスト。

`cargo install juiz_app` で juiz を入れ、`cargo build` でサンプルをビルドしてから、
リポジトリのルートで実行する:

    python3 tests/test_examples.py

各サンプルごとに `juiz -f <conf> -d` を起動し、README と同じ呼び出しを行って
出力に期待する値が含まれるかを確かめたあと、Ctrl+C(SIGINT)で止める。
"""

import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"

# (設定ファイル, [(juiz のサブコマンドと引数, 出力に含まれるべき文字列)], サーバーの出力に含まれるべき文字列)
CASES = [
    ("increment_process.conf", [
        (["process", "call", f"{BASE}/process/increment0::increment_process", '{"arg1": 3}', "-p"], "Value(4)"),
    ], None),
    ("decrement_process.conf", [
        (["process", "call", f"{BASE}/process/decrement0::decrement_process", '{"arg1": 3}', "-p"], "Value(2)"),
    ], None),
    ("talker_listener.conf", [], "listener: Hello World"),
    ("example_container.conf", [
        (["container-process", "call",
          f"{BASE}/container_process/increment0::example_container_increment:container0",
          '{"arg1": 5}', "-p"], "Value(5)"),
        (["container-process", "call",
          f"{BASE}/container_process/increment0::example_container_increment:container0",
          '{"arg1": 5}', "-p"], "Value(10)"),
        (["container-process", "call",
          f"{BASE}/container_process/get0::example_container_get:container0", "{}", "-p"], "Value(10)"),
    ], None),
    ("example_component.conf", [
        (["process", "call", f"{BASE}/process/proc0::example_component_increment", '{"arg1": 1}', "-p"], "Value(2)"),
        (["container-process", "call",
          f"{BASE}/container_process/add0::example_component_container_add:container0", '{"arg1": 5}', "-p"],
         "Value(105)"),
        (["container-process", "call",
          f"{BASE}/container_process/get0::example_component_container_get:container0", "{}", "-p"],
         "Value(105)"),
    ], None),
    # 同じ名前の talker0 / listener0 を robot1 と robot2 に置く。Topic もネームスペースごとに分かれる
    ("namespace.conf", [
        (["process", "call", f"{BASE}/process/robot1/talker0::talker", '{"message": "Hi"}', "-p"], "Value(\"Hi\")"),
    ], ["listener: Hello from robot1", "listener: Hello from robot2"]),
    # Container を含まない Composite。inc_twice = increment(increment(arg1))、plus_one = decrement(inc_twice(x))
    ("composite.conf", [
        (["process", "call", f"{BASE}/process/inc_twice0::inc_twice", '{"arg1": 3}', "-p"], "Value(5)"),
        (["process", "call", f"{BASE}/process/plus_one0::plus_one", '{"x": 3}', "-p"], "Value(4)"),
        (["process", "list", "--long"], "└─ arg1: inc_twice"),
    ], None),
    # センサ → P 制御 → モータ の CompositeContainerProcess を EC で回し、位置が目標 (1.0) に着くのを確かめる
    ("control_loop.conf", [
        (["container-process", "list", "--long"], "measured: dummy_sensor_read [sensor: dummy_sensor]"),
        (["container", "list", "--long"], "motor -> core://core/container/motor0::dummy_motor"),
    ], "position=1.000"),
]


def wait_for_port(port: int, timeout: float, server: subprocess.Popen) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"juiz が終了しました (終了コード {server.returncode})")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"juiz が {timeout} 秒以内にポート {port} で待ち受けを始めませんでした")


def wait_for_port_free(port: int, timeout: float) -> None:
    """前の juiz が使っていたポートを再び待ち受けられるようになるまで待つ。"""
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def wait_for_output(path: str, expected: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with open(path, encoding="utf-8", errors="replace") as f:
            if expected in f.read():
                return True
        time.sleep(0.5)
    return False


def run_case(juiz: str, conf: str, calls: list, expected_output: str | list[str] | None) -> bool:
    print(f"--- {conf}", flush=True)
    wait_for_port_free(PORT, 30)
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    with tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False) as log:
        log_path = log.name
        server = subprocess.Popen([juiz, "-f", conf, "-d"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, **kwargs)
    ok = True
    try:
        wait_for_port(PORT, 60, server)
        for args, expected in calls:
            result = subprocess.run([juiz, *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
            print(f"juiz {' '.join(args)}\n  {result.stdout.strip()}", flush=True)
            if result.returncode != 0 or expected not in result.stdout:
                print(f"NG: {expected!r} が出力に含まれていません\n{result.stderr}", file=sys.stderr)
                ok = False
                break
        if isinstance(expected_output, str):
            expected_output = [expected_output]
        for expected in expected_output or []:
            if ok and not wait_for_output(log_path, expected, 15):
                print(f"NG: juiz の出力に {expected!r} が含まれていません", file=sys.stderr)
                ok = False

        server.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            print("NG: Ctrl+C で juiz が止まりませんでした", file=sys.stderr)
            ok = False
    except Exception as e:
        print(f"NG: {e}", file=sys.stderr)
        ok = False
    finally:
        if server.poll() is None:
            server.kill()
            server.wait()
        if not ok:
            with open(log_path, encoding="utf-8", errors="replace") as f:
                print(f"juiz の出力:\n{f.read()}", file=sys.stderr)
        os.unlink(log_path)
    return ok


def start_server(juiz: str, args: list, log) -> subprocess.Popen:
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([juiz, *args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, **kwargs)


def stop_server(server: subprocess.Popen) -> bool:
    server.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGINT)
    try:
        server.wait(timeout=15)
        return True
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait()
        print("NG: Ctrl+C で juiz が止まりませんでした", file=sys.stderr)
        return False


def run_two_namespaces(juiz: str) -> bool:
    """README の「同じ設定ファイルを 2 つ起動する」の手順。

    increment_process.conf を --namespace robot1 と robot2 で起動し、2 つ目は 1 つ目のサブシステムになる。
    """
    print("--- increment_process.conf --namespace robot1 / robot2", flush=True)
    wait_for_port_free(PORT, 30)
    wait_for_port_free(PORT + 1, 30)
    r1 = f"{BASE}/process/robot1/increment0::increment_process"
    r2 = f"http://127.0.0.1:{PORT + 1}/process/robot2/increment0::increment_process"
    servers = []
    logs = []
    ok = True
    try:
        for ns in ["robot1", "robot2"]:
            log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
            logs.append(log.name)
            servers.append(start_server(juiz, ["-f", "increment_process.conf", "--namespace", ns, "-d"], log))
            log.close()
            if ns == "robot1":
                wait_for_port(PORT, 60, servers[0])
            else:
                wait_for_port(PORT + 1, 60, servers[1])
        # 2 つ目の登録の手続き中に問い合わせると互いの応答待ちで止まることがある (juiz#159) ので少し待つ
        time.sleep(3)
        calls = [
            (["process", "list", "--namespace", "robot2"], r2),
            (["process", "call", r1, '{"arg1": 1}', "-p"], "Value(2)"),
            (["process", "call", r2, '{"arg1": 10}', "-p"], "Value(11)"),
        ]
        for args, expected in calls:
            result = subprocess.run([juiz, *args], cwd=ROOT, capture_output=True, text=True, timeout=60)
            print(f"juiz {' '.join(args)}\n  {result.stdout.strip()}", flush=True)
            if result.returncode != 0 or expected not in result.stdout:
                print(f"NG: {expected!r} が出力に含まれていません\n{result.stderr}", file=sys.stderr)
                ok = False
                break
    except Exception as e:
        print(f"NG: {e}", file=sys.stderr)
        ok = False
    finally:
        for server in reversed(servers):
            if server.poll() is None and not stop_server(server):
                ok = False
        for path in logs:
            if not ok:
                with open(path, encoding="utf-8", errors="replace") as f:
                    print(f"juiz の出力:\n{f.read()}", file=sys.stderr)
            os.unlink(path)
    return ok


def main() -> int:
    juiz = shutil.which("juiz")
    if juiz is None:
        print("juiz コマンドが見つかりません (cargo install juiz_app を実行してください)", file=sys.stderr)
        return 1
    failed = [conf for conf, calls, expected in CASES if not run_case(juiz, conf, calls, expected)]
    if not run_two_namespaces(juiz):
        failed.append("increment_process.conf --namespace")
    if failed:
        print(f"失敗したサンプル: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
