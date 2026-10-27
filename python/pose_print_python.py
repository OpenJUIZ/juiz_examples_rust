# 姿勢 (examples.geometry.Pose2D) を受け取って表示する Python の Process。
# ほかの言語の Process が出した Pose2D (辞書で届く) も、Pose2D の値になってから渡される
from juiz import juiz_process
from examples.geometry import Pose2D


@juiz_process
def pose_print_python(pose: Pose2D) -> str:
    """受け取った姿勢を表示し、その文字列を返す"""
    text = f"{type(pose).__name__}(x={pose.position.x:.2f}, y={pose.position.y:.2f}, " \
           f"theta={pose.theta:.2f}, frame_id={pose.frame_id})"
    print(f"pose_print_python receives {text}")
    return text
