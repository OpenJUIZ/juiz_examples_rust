# juiz_examples_rust

ロボット・IoT 向けミドルウェア [juiz](https://github.com/sugarsweetrobotics/juiz) の Rust 版サンプル集です。
juiz 本体は crates.io で公開されている版 ([juiz_sdk](https://crates.io/crates/juiz_sdk) / [juiz_app](https://crates.io/crates/juiz_app) 0.0.23) を使うので、juiz のソースを手元に置かずにビルドして試せます。

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

Swagger UI は http://127.0.0.1:8000/docs/ で開けます。API の定義 (OpenAPI) は http://127.0.0.1:8000/api-docs/openapi.json で取得できます。

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

### ネームスペース: 同じ構成を並べて動かす

ネームスペースを使うと、同じ名前の Process を 1 つの System に並べて置けます。ID はクラスの後ろ・名前の前にネームスペースが入った `http://127.0.0.1:8000/process/robot1/talker0::talker` の形になります。

#### 1 つの設定ファイルで 2 台分を置く: namespace.conf

`talker0` と `listener0` を `robot1` と `robot2` の 2 つのネームスペースに置き、Topic `chatter` でつなぎます。Topic 名もネームスペースの中で解決される (`robot1/chatter` と `robot2/chatter`) ので、それぞれの `listener0` には同じネームスペースの `talker0` の出力だけが届きます。

```sh
juiz -f namespace.conf -d
# talker: Hello from robot1
# listener: Hello from robot1
# talker: Hello from robot2
# listener: Hello from robot2
# ...
```

別のターミナルから、ネームスペースの列つきで一覧を出したり、ネームスペース付きの ID で呼び出したりできます。

```sh
juiz process list --long
# NAMESPACE  NAME       TYPE      ID
# /robot1    talker0    talker    http://127.0.0.1:8000/process/robot1/talker0::talker
# ...
juiz process call "http://127.0.0.1:8000/process/robot1/talker0::talker" '{"message": "Hi"}' -p
# => CapsulePtr((value:Value("Hi"), option: []))
```

設定ファイルでは各要素に `namespace` を書きます (`/` で始めるとルートからの絶対指定)。トップレベルに `namespace` を書くと、全体の既定のネームスペースになります。

#### 同じ設定ファイルを 2 つ起動する: --namespace

`--namespace` を付けると、設定ファイルの既定のネームスペースを置き換えて起動できます。2 つのターミナルで次のように起動すると、2 つ目は 1 つ目のサブシステムになり (8001 番ポートで待ち受け)、1 つの System として扱えます。

```sh
juiz -f increment_process.conf --namespace robot1 -d
```

```sh
juiz -f increment_process.conf --namespace robot2 -d
```

```sh
juiz process list --namespace robot2
# => ["http://127.0.0.1:8001/process/robot2/increment0::increment_process"]
juiz process call "http://127.0.0.1:8000/process/robot1/increment0::increment_process" '{"arg1": 1}' -p
# => CapsulePtr((value:Value(2), option: []))
juiz process call "http://127.0.0.1:8001/process/robot2/increment0::increment_process" '{"arg1": 10}' -p
# => CapsulePtr((value:Value(11), option: []))
```

### Composition: 複数の Process を 1 つにまとめる

Composition を使うと、既にある Process / ContainerProcess を、関数を書き換えずに式の木として組み合わせ、1 つの Process の型 (Composite) にできます。設定ファイルの `composites:` に定義を書きます。子の Process のインスタンスは作らず、接続 (connections) も使いません。

#### Container を含まない例: composite.conf

```text
inc_twice(arg1) = increment_process(increment_process(arg1))
plus_one(x)     = decrement_process(inc_twice(x))
```

```yaml
composites:
  - type_name: inc_twice
    body:
      process: increment_process
      args:
        arg1: { process: increment_process }   # 書かなかった内側の arg1 は、元の名前のまま公開される
  - type_name: plus_one
    body:
      process: decrement_process
      args:
        arg1:
          process: inc_twice                     # 先に定義した Composite も子に使える
          args:
            arg1: { expose: x }                  # 公開する引数の名前を x に変える
processes:
  - { type_name: inc_twice, name: inc_twice0, trace: true }
  - { type_name: plus_one, name: plus_one0 }
```

```sh
RUST_LOG=info juiz -f composite.conf -d
```

```sh
juiz process call "http://127.0.0.1:8000/process/inc_twice0::inc_twice" '{"arg1": 3}' -p
# => CapsulePtr((value:Value(5), option: []))
juiz process call "http://127.0.0.1:8000/process/plus_one0::plus_one" '{"x": 3}' -p
# => CapsulePtr((value:Value(4), option: []))
juiz process list --long
# NAMESPACE  NAME        TYPE       ID
# /          plus_one0   plus_one   http://127.0.0.1:8000/process/plus_one0::plus_one
#     decrement_process
#     └─ arg1: inc_twice
#        └─ arg1 = $x
# ...
```

`trace: true` を付けた `inc_twice0` は、呼ばれるたびに各段の戻り値をログに出します (`RUST_LOG=info` のとき)。

```text
INFO ... Composite(inc_twice) body.arg1 (increment_process) -> 4
INFO ... Composite(inc_twice) body (increment_process) -> 5
```

#### 制御ループの例: control_loop.conf

「センサを読む → 制御則 → モータに出す」を 1 つの CompositeContainerProcess にまとめ、実行コンテキスト (main_loop_ec、20Hz) に bind します。3 段が毎周期この順番で 1 回ずつ実行されるので、接続で組むときのように段の間の順番やタイミングを気にする必要がありません。

部品は `component/example_control` にあります。本物のハードウェアの代わりに、ダミーのセンサ (`dummy_sensor`) とモータ (`dummy_motor`) を使います。2 つは同じライブラリの中の模擬的な世界 (ロボットの位置) を共有していて、モータを動かすとセンサで読める位置が変わります。

```text
follow_target(cc{sensor, motor}, target)
  = dummy_motor_drive(cc.motor,
        velocity = p_control(measured = dummy_sensor_read(cc.sensor), target, gain = 2.0))
```

ContainerProcess を含む Composite は、使う Container を「スロット」(`containers:` の `sensor`、`motor`) として宣言します。インスタンスを作るときは、`composite_containers:` で CompositeContainer を作り、スロットに既存の Container をつなぎます。

```yaml
composites:
  - type_name: follow_target
    containers: { sensor: dummy_sensor, motor: dummy_motor }   # スロット名 → Container の型
    body:
      process: dummy_motor_drive
      container: motor
      args:
        velocity:
          process: p_control
          args:
            measured: { process: dummy_sensor_read, container: sensor }
            gain: { const: 2.0 }                 # 定数で固定し、公開しない
containers:
  - { type_name: dummy_sensor, name: sensor0 }
  - { type_name: dummy_motor, name: motor0, dt: 0.05 }
composite_containers:
  - name: robot0
    slots: { sensor: sensor0, motor: motor0 }    # スロット → 既存の Container
    processes:
      - { type_name: follow_target, name: follow0 }
ecs:
  - name: ec0
    type_name: main_loop_ec
    rate: 20.0
    bind:
      # ContainerProcess は Container の名前 (container_name) も書く
      - { name: follow0, type_name: follow_target, container_name: robot0 }
    auto_start: true
```

```sh
juiz -f control_loop.conf -d
# dummy_motor: velocity=2.000 position=0.100
# dummy_motor: velocity=1.800 position=0.190
# ...
# dummy_motor: velocity=0.001 position=1.000
```

位置が目標 (`target` の既定値 1.0) に近づいていきます。中身は `--long` で確かめられます。

```sh
juiz container-process list --long
# NAMESPACE  NAME     TYPE                  ID
# /          follow0  follow_target:robot0  http://127.0.0.1:8000/container_process/follow0::follow_target:robot0
#     dummy_motor_drive [motor: dummy_motor]
#     └─ velocity: p_control
#        ├─ gain = 2.0
#        ├─ measured: dummy_sensor_read [sensor: dummy_sensor]
#        └─ target = $target
juiz container list --long
# /          robot0   composite_container  http://127.0.0.1:8000/container/robot0::composite_container
#     motor -> core://core/container/motor0::dummy_motor
#     sensor -> core://core/container/sensor0::dummy_sensor
# ...
```

EC に ContainerProcess を bind するときは、`container_name` (CompositeContainer の名前) も書きます。

### データ型: 言語をまたいで同じ型を使う

Process の引数と戻り値に型を付けられます。型は IDL (JIDL) で書き、`juiz idl` (と Rust では build.rs の `juiz_idl`) で各言語の型を作ります。
このリポジトリの [types/geometry.jidl](types/geometry.jidl) は、Rust・[Python](https://github.com/OpenJUIZ/juiz_examples_python)・[C++](https://github.com/OpenJUIZ/juiz_examples_cpp)・[Haskell](https://github.com/OpenJUIZ/juiz_examples_haskell) の 4 つのサンプルリポジトリで同じ中身にしてあり、どの言語で作っても型の指紋 (`@sha256:…`) が同じになります。指紋が同じ型どうしは、言語が違ってもそのままつながります。

```text
namespace examples.geometry;

record Point2D { double x = 0.0; double y = 0.0; }
record Pose2D  { Point2D position = {"x": 0.0, "y": 0.0}; double theta = 0.0; string frame_id = "map"; }
record Twist2D { double linear = 0.0; double angular = 0.0; }
```

> データ型は juiz 0.0.23 から使えます。juiz コマンドと、Python の Process が使う pyjuiz は 0.0.23 以降を入れてください。
>
> ```sh
> cargo install juiz_app --version 0.0.23 --locked
> pip install pyjuiz==0.0.23
> ```

Rust の Process [process/pose_move](process/pose_move/src/lib.rs) は、`build.rs` で types/geometry.jidl から作った型をそのまま引数と戻り値に使います。

```rust
// build.rs
fn main() {
    juiz_idl::build::compile(&["../../types/geometry.jidl"]).unwrap();
}
```

```rust
include!(concat!(env!("OUT_DIR"), "/juiz_idl.rs"));
use examples::geometry::{Point2D, Pose2D, Twist2D};

#[juiz_process(arguments = { default = "{\"pose\": {}, \"twist\": {}, \"dt\": 1.0}" })]
fn pose_move(pose: Pose2D, twist: Twist2D, dt: f64) -> JuizResult<Pose2D> { … }
```

#### Rust と Python をつなぐ: typed_pose.conf

Python の Process ([python/](python/)) が出した `Twist2D` を Rust の `pose_move` が受け取り、`pose_move` が出した `Pose2D` を Python の Process が受け取ります。Python の Process には pyjuiz が要ります (`pip install pyjuiz`)。

```text
twist0 (Python, Twist2D) --Pull--> move0 (Rust, pose_move) --Push--> print0 (Python, Pose2D を表示)
```

先に Python の型を `gen/` に作ってから起動します (設定ファイルの `option.pythonpath` で `gen/` を読みます)。

```sh
juiz idl -g python -o gen types/geometry.jidl
juiz -f typed_pose.conf -d
```

別のターミナルから `move0` を実行 (execute) すると、`twist0` から速度を取ってきて動き、結果を `print0` に送ります。

```sh
curl -X PATCH "http://127.0.0.1:8000/api/process/execute?identifier=core://core/process/move0::pose_move" -H "Content-Type: application/json" -d '{}'
# => {"frame_id":"map","position":{"x":0.5,"y":0.0},"theta":0.0}
```

```text
pose_move: (0.00, 0.00, 0.00) -> (0.50, 0.00, 0.00)
pose_print_python receives Pose2D(x=0.50, y=0.00, theta=0.00, frame_id=map)
```

型付きの引数も、CLI や curl からは今までどおり辞書で渡せます。書かなかったフィールドは既定値になります。

```sh
juiz process call "http://127.0.0.1:8000/process/move0::pose_move" '{"pose": {"position": {"x": 1.0, "y": 2.0}}, "twist": {"linear": 1.0}, "dt": 2.0}' -p
# => CapsulePtr((value:Value({"frame_id":"map","position":{"x":3.0,"y":2.0},"theta":0.0}), option: []))
```

読み込んだ型は `juiz type` で見られます。Rust と Python の型の指紋が同じなので、1 つの型として登録されています。

```sh
juiz type list
# => ["examples.geometry.Point2D@sha256:5649ab39…","examples.geometry.Pose2D@sha256:123b8c15…","examples.geometry.Twist2D@sha256:115b9e0f…"]
juiz type show examples.geometry.Twist2D
# // examples.geometry.Twist2D@sha256:115b9e0f…
# // used by: pose_move, twist_python
# namespace examples.geometry;
# ...
```

#### 型が合わないとつながらない: typed_mismatch.conf

`twist0` の `Twist2D` を `move0` の引数 `pose` (`Pose2D`) につなごうとする設定ファイルです。juiz は接続を作らず、エラーで終わります。

```sh
juiz -f typed_mismatch.conf -d
# Error:setup_objects() failed in setup in system.rs
# ...
#     2: Type examples.geometry.Twist2D@sha256:115b9e0f… cannot be read as examples.geometry.Pose2D@sha256:123b8c15… at 'Pose2D': record name examples.geometry.Twist2D does not match examples.geometry.Pose2D (add an alias to read it)
```

### OpenCV: juiz_opencv (任意)

カメラ画像の取得・表示・保存を行うサンプルです。OpenCV (と libclang) のインストールが必要なので、`cargo build` の対象からは外しています。

```sh
cargo build -p juiz_opencv
juiz -f opencv.conf -d
```

`opencv_capture_oneshot.conf` はカメラから 1 枚撮って保存する例です。

`opencv_capture_oneshot_composite.conf` は、その 3 段 (カメラから読む → 色変換 → ファイルに書く) を接続ではなく 1 つの CompositeContainerProcess `capture_save` にまとめた版です。カメラ (`video_capture`) とファイル (`filesystem`) の 2 つの Container をスロットで受け取り、呼び出すたびに 1 枚撮って保存します。

```sh
juiz -f opencv_capture_oneshot_composite.conf -d
juiz container-process call "http://127.0.0.1:8000/container_process/capture_save0::capture_save:cam_fs0" '{"path": "capture.png"}' -p
```

どこかの段で失敗すると、式の木の中の位置 (`body.img.img` など) 付きのエラーが返ります。

## 構成

| ディレクトリ | 内容 |
| --- | --- |
| `process/` | Process (入力と出力を持つ冪等な関数) のサンプル |
| `container/` | Container (状態を持つ) と ContainerProcess のサンプル |
| `component/` | 複数の要素を 1 つのライブラリにまとめた Component のサンプル |
| `types/` | 4 つのサンプルリポジトリで共通に使う型 (JIDL) |
| `python/` | データ型のサンプルで Rust の Process とつなぐ Python の Process |
| `*.conf` | 各サンプルを動かすための juiz の設定ファイル |
| `tests/test_examples.py` | 上のサンプルを起動して呼び出し、結果を確かめるテスト (`cargo build` のあと `python3 tests/test_examples.py`。データ型のサンプルのために pyjuiz が要る)。CI でも実行する |

## 自分で書くときは

新しいクレートを作って `crate-type = ["cdylib"]` にし、`juiz_sdk` を依存に加えます。

```toml
[lib]
crate-type = ["cdylib"]

[dependencies]
juiz_sdk = "0.0.23"
```

```rust
use juiz_sdk::prelude::*;

#[juiz_process]
fn my_process(arg1: i64) -> JuizResult<JuizResponse> {
    Ok(jvalue!(arg1 * 2).into())
}
```

ワークスペースに追加する場合はルートの `Cargo.toml` の `members` に足してください。

## ライセンス

このリポジトリのサンプルは、次のどちらかのライセンスを選んで利用できます(デュアルライセンス)。

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) または <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT License ([LICENSE-MIT](LICENSE-MIT) または <https://opensource.org/licenses/MIT>)

Licensed under either of Apache License, Version 2.0 or MIT license at your option.

### コントリビューション

明示的に別の意思表示をしない限り、このリポジトリに提出されたコントリビューションは、Apache-2.0 ライセンスの定義に従い、追加の条件なしに上記と同じデュアルライセンスで提供されるものとします。

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in the work by you, as defined in the Apache-2.0 license, shall be dual licensed as above, without any additional terms or conditions.
