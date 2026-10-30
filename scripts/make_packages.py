"""packages/ の下のアプリを .juizapp にする。

    cargo build
    python3 scripts/make_packages.py [-o dist]

packages/<名前>/ には juizapp.yaml と conf だけを置き、プラグインは cargo build の結果 (target/debug) を
plugins/<この機械のターゲット>/ に写して使う。写した結果を build/packages/<名前>/ に作り、
`juiz pack --target <ターゲット>` で <出力先>/<名前>-<版>-<ターゲット>.juizapp を作る。

Rust のプラグインは、同じ juiz_sdk の版と同じ rustc でビルドした juiz でしか読み込めない
(juiz run が起動前に確かめる)。
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# パッケージ名 → plugins/<ターゲット>/ に写すプラグイン (Cargo のパッケージ名)
PACKAGES = {
    "talker_listener": ["talker", "listener"],
}


def host_target() -> str:
    """この機械のターゲット名 (Rust の target triple)。"""
    machine = platform.machine().lower()
    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(machine)
    system = {"Linux": "unknown-linux-gnu", "Darwin": "apple-darwin", "Windows": "pc-windows-msvc"}.get(
        platform.system())
    if arch is None or system is None:
        raise SystemExit(f"この機械 ({platform.system()} {machine}) のターゲット名が分かりません")
    return f"{arch}-{system}"


def library_name(name: str) -> str:
    if sys.platform == "win32":
        return f"{name}.dll"
    if sys.platform == "darwin":
        return f"lib{name}.dylib"
    return f"lib{name}.so"


def stage(name: str, plugins: list[str], target: str, build_dir: str) -> str:
    """build/packages/<name>/ に packages/<name>/ とプラグインを写し、そのパスを返す。"""
    dest = os.path.join(ROOT, "build", "packages", name)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "packages", name), dest)
    plugin_dir = os.path.join(dest, "plugins", target)
    os.makedirs(plugin_dir)
    for plugin in plugins:
        source = os.path.join(build_dir, library_name(plugin))
        if not os.path.exists(source):
            raise SystemExit(f"{source} がありません (先に cargo build を実行してください)")
        shutil.copy2(source, plugin_dir)
    for license_file in ["LICENSE-MIT", "LICENSE-APACHE"]:
        shutil.copy2(os.path.join(ROOT, license_file), os.path.join(dest, license_file))
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", default="dist", help="出力先のディレクトリ (既定は dist)")
    parser.add_argument("--build-dir", default="target/debug", help="プラグインのあるディレクトリ (既定は target/debug)")
    parser.add_argument("names", nargs="*", help="作るパッケージの名前 (省けば全部)")
    args = parser.parse_args()
    juiz = shutil.which("juiz")
    if juiz is None:
        print("juiz コマンドが見つかりません", file=sys.stderr)
        return 1
    target = host_target()
    out = os.path.join(ROOT, args.out)
    os.makedirs(out, exist_ok=True)
    for name in args.names or PACKAGES:
        if name not in PACKAGES:
            print(f"知らないパッケージです: {name} ({', '.join(PACKAGES)})", file=sys.stderr)
            return 1
        staged = stage(name, PACKAGES[name], target, os.path.join(ROOT, args.build_dir))
        result = subprocess.run([juiz, "pack", staged, "--target", target, "-o", out], cwd=ROOT)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
