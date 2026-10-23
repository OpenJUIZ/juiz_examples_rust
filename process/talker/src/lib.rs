use juiz_sdk::prelude::*;

/// 文字列を出力します。
///
/// 引数 message の文字列 (既定は "Hello World") を出力します。
#[juiz_process(
    description = "This is talker process."
    arguments = {
        default = {
            message = "Hello World"
        }
        description = {
            message = "This message is printed and returned."
        }
    }
)]
fn talker(message: String) -> JuizResult<JuizResponse> {
    log::trace!("talker({:}) called", message);
    println!("talker: {:}", message);
    return Ok(jvalue!(message).into());
}
