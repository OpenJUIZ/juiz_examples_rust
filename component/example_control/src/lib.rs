//! 制御ループのサンプル: センサを読む → 制御則 → モータに出す。
//!
//! 本物のロボットの代わりに、ダミーのセンサとモータを使う。2 つの Container は、
//! このライブラリの中の模擬的な世界(ロボットの位置)を共有していて、
//! モータを動かすとセンサで読める位置が変わる。
use std::sync::Mutex;

use juiz_sdk::prelude::*;

/// 模擬的な世界: ロボットの位置 [m]。dummy_motor が動かし、dummy_sensor が読む。
static POSITION: Mutex<f64> = Mutex::new(0.0);

fn position() -> f64 {
    *POSITION.lock().unwrap_or_else(|e| e.into_inner())
}

/// 位置を読むだけのダミーのセンサ。
#[repr(Rust)]
pub struct DummySensor {}

#[juiz_component_container]
fn dummy_sensor() -> JuizResult<Box<DummySensor>> {
    Ok(Box::new(DummySensor {}))
}

#[juiz_component_container_process(
    container_type = "dummy_sensor"
    description = "ロボットの位置 [m] を読む"
)]
fn dummy_sensor_read(_container: &mut ContainerImpl<DummySensor>) -> JuizResult<JuizResponse> {
    Ok(jvalue!(position()).into())
}

/// 速度指令を受けて、周期 dt [s] の間だけロボットを動かすダミーのモータ。
#[repr(Rust)]
pub struct DummyMotor {
    pub dt: f64,
}

#[juiz_component_container(
    arguments = {
        default = {
            dt = 0.05
        }
    }
)]
fn dummy_motor(dt: f64) -> JuizResult<Box<DummyMotor>> {
    Ok(Box::new(DummyMotor { dt }))
}

#[juiz_component_container_process(
    container_type = "dummy_motor"
    description = "速度指令 velocity [m/s] で dt 秒だけ動かし、動かした後の位置 [m] を返す"
    arguments = {
        default = {
            velocity = 0.0
        }
    }
)]
fn dummy_motor_drive(
    container: &mut ContainerImpl<DummyMotor>,
    velocity: f64,
) -> JuizResult<JuizResponse> {
    let mut p = POSITION.lock().unwrap_or_else(|e| e.into_inner());
    *p += velocity * container.dt;
    println!("dummy_motor: velocity={velocity:.3} position={:.3}", *p);
    Ok(jvalue!(*p).into())
}

/// P 制御: 目標 target と計測値 measured の差に gain を掛けて速度指令にする。
#[juiz_component_process(
    description = "P 制御。velocity = gain * (target - measured)"
    arguments = {
        default = {
            measured = 0.0
            target = 1.0
            gain = 1.0
        }
    }
)]
fn p_control(measured: f64, target: f64, gain: f64) -> JuizResult<JuizResponse> {
    Ok(jvalue!(gain * (target - measured)).into())
}

juiz_component_manifest!(
    component_name = "example_control"
    containers = {
        dummy_sensor = [
            dummy_sensor_read
        ]
        dummy_motor = [
            dummy_motor_drive
        ]
    }
    processes = [
        p_control
    ]
);
