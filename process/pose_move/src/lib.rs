use juiz_sdk::prelude::*;

// types/geometry.jidl から build.rs が作った型。名前空間 examples.geometry がモジュール examples::geometry になる
include!(concat!(env!("OUT_DIR"), "/juiz_idl.rs"));
use examples::geometry::{Point2D, Pose2D, Twist2D};

/// 姿勢 pose から速度 twist で dt 秒動いた姿勢を返します。
///
/// 引数と戻り値が型付き (examples.geometry の Pose2D・Twist2D) なので、
/// 型の合わない Process とは接続できません。
#[juiz_process(
    description = "Moves the pose by the twist for dt seconds."
    arguments = {
        // 型付きの引数の既定値は辞書の表し方で書く。Pose2D・Twist2D は全フィールドに既定値があるので {} でよい
        default = "{\"pose\": {}, \"twist\": {}, \"dt\": 1.0}"
    }
)]
fn pose_move(pose: Pose2D, twist: Twist2D, dt: f64) -> JuizResult<Pose2D> {
    let distance = twist.linear * dt;
    let moved = Pose2D {
        position: Point2D {
            x: pose.position.x + distance * pose.theta.cos(),
            y: pose.position.y + distance * pose.theta.sin(),
        },
        theta: pose.theta + twist.angular * dt,
        frame_id: pose.frame_id,
    };
    println!(
        "pose_move: ({:.2}, {:.2}, {:.2}) -> ({:.2}, {:.2}, {:.2})",
        pose.position.x, pose.position.y, pose.theta, moved.position.x, moved.position.y, moved.theta
    );
    Ok(moved)
}
