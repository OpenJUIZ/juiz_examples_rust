// サンプル共通の型 (types/geometry.jidl) から Rust の型を作り、OUT_DIR に書き出す。
// src/lib.rs が include! で読み込む。
fn main() {
    juiz_idl::build::compile(&["../../types/geometry.jidl"]).unwrap();
}
