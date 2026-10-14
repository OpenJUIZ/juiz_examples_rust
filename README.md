# juiz_examples_rust

ロボット・IoT 向けミドルウェア [juiz](https://github.com/sugarsweetrobotics/juiz) の Rust 版サンプル集です。
juiz 本体は crates.io で公開されている版 ([juiz_sdk](https://crates.io/crates/juiz_sdk) / [juiz_app](https://crates.io/crates/juiz_app) 0.0.12) を使うので、juiz のソースを手元に置かずにビルドして試せます。

## 必要なもの

- Rust (stable)。インストールは https://rustup.rs/ を参照してください。
- Linux または macOS

## 1. juiz コマンドをインストールする

```sh
cargo install juiz_app
```

`juiz` コマンドが `~/.cargo/bin` に入ります。

## 2. サンプルをビルドする

```sh
git clone https://github.com/sugarsweetrobotics/juiz_examples_rust.git
cd juiz_examples_rust
cargo build
```

各サンプルは共有ライブラリ (`target/debug/lib*.so`、macOS では `*.dylib`) としてビルドされ、juiz がプラグインとして読み込みます。
設定ファイル (`*.conf`) は `./target/debug` からプラグインを探すので、**リポジトリのルートで** `juiz` を実行してください。

## 3. 動かしてみる

### Process: increment_process

引数に 1 を足して返すだけの Process です。

```sh
juiz -f increment_process.conf -d
```

`-d` を付けると HTTP ブローカー (8000 番ポート) を立ち上げて待機します (Ctrl+C で終了)。
別のターミナルから呼び出せます。

```sh
juiz process list
juiz process call "http://127.0.0.1:8000/process/increment0::increment_process" '{"arg1": 3}' -p
# => CapsulePtr((value:Value(4), option: []))
```

ブラウザで http://127.0.0.1:8000/docs を開くと Swagger UI からも試せます。

`decrement_process.conf` も同じ使い方です (1 を引く Process)。

### Process の接続: talker / listener

`talker` の出力を `listener` の引数に Push 接続し、実行コンテキスト (main_loop_ec) で 1Hz で `talker` を動かします。

```sh
juiz -f talker_listener.conf -d
# talker: Hello World
# listener: Hello World
# ...
```

### Container: example_container

状態 (整数値) を持つ Container と、それを操作する ContainerProcess (`example_container_increment`、`example_container_get`) のサンプルです。

```sh
juiz -f example_container.conf -d
```

別のターミナルから呼び出すたびに値が増えていきます。

```sh
juiz container-process call "http://127.0.0.1:8000/container_process/increment0::example_container_increment:container0" '{"arg1": 5}' -p
# => CapsulePtr((value:Value(5), option: []))
```

### Component: example_component

1 つのライブラリに Process・Container・ContainerProcess をまとめて入れる Component のサンプルです。

```sh
juiz -f example_component.conf -d
juiz process call "http://127.0.0.1:8000/process/proc0::example_component_increment" '{"arg1": 1}' -p
# => CapsulePtr((value:Value(2), option: []))
juiz container-process call "http://127.0.0.1:8000/container_process/add0::example_component_container_add:container0" '{"arg1": 5}' -p
# => CapsulePtr((value:Value(105), option: []))
```

### OpenCV: juiz_opencv (任意)

カメラ画像の取得・表示・保存を行うサンプルです。OpenCV (と libclang) のインストールが必要なので、`cargo build` の対象からは外しています。

```sh
cargo build -p juiz_opencv
juiz -f opencv.conf -d
```

`opencv_capture_oneshot.conf` はカメラから 1 枚撮って保存する例です。

## 構成

| ディレクトリ | 内容 |
| --- | --- |
| `process/` | Process (入力と出力を持つ冪等な関数) のサンプル |
| `container/` | Container (状態を持つ) と ContainerProcess のサンプル |
| `component/` | 複数の要素を 1 つのライブラリにまとめた Component のサンプル |
| `*.conf` | 各サンプルを動かすための juiz の設定ファイル |

## 自分で書くときは

新しいクレートを作って `crate-type = ["cdylib"]` にし、`juiz_sdk` を依存に加えます。

```toml
[lib]
crate-type = ["cdylib"]

[dependencies]
juiz_sdk = "0.0.12"
```

```rust
use juiz_sdk::prelude::*;

#[juiz_process]
fn my_process(arg1: i64) -> JuizResult<Capsule> {
    Ok(jvalue!(arg1 * 2).into())
}
```

ワークスペースに追加する場合はルートの `Cargo.toml` の `members` に足してください。
