//! Transformations のサンプル: 台車 → 雲台 → カメラ の部品 (OpenJUIZ/juiz#374)。
//!
//! 位置姿勢 (ContainerPose) は juiz が Container ごとに持ち、利用者の状態とは別にある。
//! 部品のつながり (Transform) と基点 (Anchor) は transformations.conf に書く:
//!
//! ```text
//! map (Periodic) → odom (Static) → base0 (mobile_base) → pantilt0 (pantilt) → camera0 (camera)
//! ```
//!
//! - `mobile_base_move` はオドメトリを積分して、odom から見た自分の位置姿勢を `set_pose` で書く。
//! - `pantilt_set_pan` はパン角を書く (台車から見た自分の向きだけを変える)。
//! - `camera_pose` は基準から見た自分の位置姿勢を `pose` で読む。カメラは Transform で雲台につながっているだけ。
//!   読むだけなので readonly (`&ContainerImpl`) にしている。
//! - `pose_print` は Pose 通知 (conf の pose_listeners:) で呼ばれる Process。

use juiz_sdk::geometry::{Pose, PoseStamped, Quaternion, Vector3};
use juiz_sdk::prelude::*;

/// 台車。オドメトリ (odom から見た x, y, 向き theta) を自分で積分して持つ
pub struct MobileBase {
    pub x: f64,
    pub y: f64,
    pub theta: f64,
}

#[juiz_component_container]
fn mobile_base() -> JuizResult<Box<MobileBase>> {
    Ok(Box::new(MobileBase { x: 0.0, y: 0.0, theta: 0.0 }))
}

/// 速度 vx [m/s]・角速度 omega [rad/s] で dt [s] 動かし、基準 reference (odom) から見た位置姿勢を書く
#[juiz_component_container_process(container_type = "mobile_base" arguments = {
    default = { vx = 0.0 omega = 0.0 dt = 1.0 reference = "odom" }
})]
fn mobile_base_move(
    c: &mut ContainerImpl<MobileBase>,
    vx: f64,
    omega: f64,
    dt: f64,
    reference: String,
) -> JuizResult<Capsule> {
    c.x += vx * c.theta.cos() * dt;
    c.y += vx * c.theta.sin() * dt;
    c.theta += omega * dt;
    let pose = Pose::new(Vector3::new(c.x, c.y, 0.0), Quaternion::from_rpy(0.0, 0.0, c.theta));
    // odom → base0 の Transform が書き換わり、Pose 通知が出る
    Ok(c.set_pose(&reference, pose)?.into())
}

/// 雲台。パン角を持つ
pub struct Pantilt {
    pub pan: f64,
}

#[juiz_component_container]
fn pantilt() -> JuizResult<Box<Pantilt>> {
    Ok(Box::new(Pantilt { pan: 0.0 }))
}

/// パン角 pan [rad] にする。取り付け位置はそのままで、基準 reference (台車) から見た向きだけを変える
#[juiz_component_container_process(container_type = "pantilt" arguments = {
    default = { pan = 0.0 reference = "base0" }
})]
fn pantilt_set_pan(c: &mut ContainerImpl<Pantilt>, pan: f64, reference: String) -> JuizResult<Capsule> {
    c.pan = pan;
    let mount = c.pose(&reference)?.pose.position;
    Ok(c.set_pose(&reference, Pose::new(mount, Quaternion::from_rpy(0.0, 0.0, pan)))?.into())
}

/// カメラ。利用者の状態は持たない
pub struct Camera {}

#[juiz_component_container]
fn camera() -> JuizResult<Box<Camera>> {
    Ok(Box::new(Camera {}))
}

/// 基準 reference から見た自分の位置姿勢 (juiz_std.geometry.PoseStamped)。
///
/// 読むだけなので readonly にする (OpenJUIZ/juiz#377)。Container を `&ContainerImpl` で受け取ると
/// マクロが readonly の ContainerProcess にし、juiz は Container を読み出しロックで呼ぶ。
/// 同じ Container の readonly 同士は並行に走る。中では `set_pose` を呼べない
#[juiz_component_container_process(container_type = "camera" arguments = {
    default = { reference = "map" }
})]
fn camera_pose(c: &ContainerImpl<Camera>, reference: String) -> JuizResult<Capsule> {
    Ok(c.pose(&reference)?.into())
}

/// Pose 通知の受け手。受け取った位置姿勢 (juiz_std.geometry.PoseStamped) を表示する
#[juiz_component_process(arguments = { default = { pose = {} } })]
fn pose_print(pose: Value) -> JuizResult<JuizResponse> {
    let p = PoseStamped::try_from(&pose)?;
    let (_, _, yaw) = p.pose.orientation.to_rpy();
    let text = format!(
        "pose_print: x={:.2} y={:.2} yaw={:.1}deg (from {})",
        p.pose.position.x,
        p.pose.position.y,
        yaw.to_degrees(),
        p.header.frame_id
    );
    println!("{text}");
    Ok(jvalue!(text).into())
}

juiz_component_manifest!(
    component_name = "mobile_robot"
    containers = {
        mobile_base = [mobile_base_move]
        pantilt = [pantilt_set_pan]
        camera = [camera_pose]
    }
    processes = [pose_print]
);
