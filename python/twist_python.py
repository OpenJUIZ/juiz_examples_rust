# 速度 (examples.geometry.Twist2D) を出す Python の Process。
# 型は types/geometry.jidl から `juiz idl -g python -o gen types/geometry.jidl` で作ったもの (gen/)
from juiz import juiz_process
from examples.geometry import Twist2D


@juiz_process
def twist_python(linear: float = 0.5, angular: float = 0.0) -> Twist2D:
    """速度 (前向き linear [m/s]、回転 angular [rad/s]) を出力する"""
    return Twist2D(linear=linear, angular=angular)
