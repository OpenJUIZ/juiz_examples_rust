#!/usr/bin/env python3
"""Transformations のサンプルの 3D モデルを作る (OpenJUIZ/juiz#385)。

    python3 scripts/make_models.py          # models/ に floor.glb・mobile_base.glb・camera.stl を書く

モデルは箱と円柱だけの単純な形で、このスクリプトが一から作る (ライセンスの心配が無い)。Python の標準ライブラリ
だけを使う。雲台のモデル models/pantilt.sdf は手書きの SDF なので、このスクリプトでは作らない。

形は juiz の約束 (メートル・x 前・y 左・z 上) で書き、ファイルに書くときに形式の約束に直す。

- .glb (床・台車): glTF は Y 上なので、juiz の (x, y, z) をファイルの (x, z, -y) にして書く。conf では
  up_axis を書かない (glTF の既定 y)。juiz が x 軸まわりに +90° 回して Z 上に戻す。
- .stl (カメラ): CAD から出したものに見立てて mm で書く。conf に scale: 0.001 と書く。
  原点はカメラの背面の中心 (取り付け面) にし、conf の origin で Container の原点に合わせる例にする。

4 つのサンプルのリポジトリ (juiz_examples_rust / python / cpp / haskell) で同じスクリプトと同じモデルを使う。
"""

import json
import math
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")

# 色 (R, G, B, A)。0〜1
GRAY = (0.75, 0.75, 0.72, 1.0)
DARK = (0.15, 0.15, 0.15, 1.0)
BLUE = (0.20, 0.40, 0.80, 1.0)
YELLOW = (0.95, 0.75, 0.10, 1.0)
RED = (0.85, 0.20, 0.20, 1.0)
GREEN = (0.20, 0.65, 0.25, 1.0)


# ---------------------------------------------------------------- 形 (三角形の集まり)
# 形は (頂点の列, 法線の列, 三角形の頂点番号の列)。座標は juiz の約束 (x 前・y 左・z 上)。

def box(center, size):
    """各軸に沿った直方体。面ごとに頂点を分けて、面の法線を付ける。"""
    cx, cy, cz = center
    hx, hy, hz = (s / 2 for s in size)
    positions, normals, indices = [], [], []
    # (法線, 面の上の 2 つの軸)。2 つの軸の外積が法線になる向きにして、反時計回りを表にする
    faces = [
        ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
        ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
        ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
        ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
        ((0, 0, -1), (0, 1, 0), (1, 0, 0)),
    ]
    half = (hx, hy, hz)
    for n, u, v in faces:
        base = len(positions)
        for su, sv in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
            positions.append(tuple(
                c + half[i] * (n[i] + su * u[i] + sv * v[i]) for i, c in enumerate((cx, cy, cz))))
            normals.append(n)
        indices += [base, base + 1, base + 2, base, base + 2, base + 3]
    return positions, normals, indices


def cylinder(center, radius, length, axis, segments=32):
    """軸 axis ("x" / "y" / "z") に沿った円柱。側面はなめらかな法線、両端は平らな蓋。"""
    # 軸 a と、それに直交する 2 つの軸 (b, c) を、b × c = a になるように選ぶ
    a, b, c = {"x": (0, 1, 2), "y": (1, 2, 0), "z": (2, 0, 1)}[axis]

    def point(along, cb, cc):
        p = [0.0, 0.0, 0.0]
        p[a], p[b], p[c] = along, cb, cc
        return tuple(center[i] + p[i] for i in range(3))

    def direction(da, db, dc):
        d = [0.0, 0.0, 0.0]
        d[a], d[b], d[c] = da, db, dc
        return tuple(d)

    positions, normals, indices = [], [], []
    h = length / 2
    # 側面
    for i in range(segments + 1):
        t = 2 * math.pi * i / segments
        cb, cc = math.cos(t), math.sin(t)
        positions += [point(-h, radius * cb, radius * cc), point(h, radius * cb, radius * cc)]
        normals += [direction(0, cb, cc)] * 2
    for i in range(segments):
        k = 2 * i
        indices += [k, k + 2, k + 3, k, k + 3, k + 1]
    # 両端の蓋
    for sign in (1, -1):
        center_index = len(positions)
        positions.append(point(sign * h, 0, 0))
        normals.append(direction(sign, 0, 0))
        for i in range(segments + 1):
            t = 2 * math.pi * i / segments
            positions.append(point(sign * h, radius * math.cos(t), radius * math.sin(t)))
            normals.append(direction(sign, 0, 0))
        for i in range(segments):
            j = center_index + 1 + i
            indices += [center_index, j, j + 1] if sign > 0 else [center_index, j + 1, j]
    return positions, normals, indices


def wedge(base_center, length, width, height):
    """+x を指す三角柱 (前の印)。底面は z = base_center.z、先は x + length/2。"""
    cx, cy, cz = base_center
    back, front = cx - length / 2, cx + length / 2
    l, r = cy + width / 2, cy - width / 2
    top = cz + height
    # 三角形ごとに頂点を分けて、面の法線を付ける (頂点の順は下でそろえる)
    triangles = [
        [(back, l, cz), (back, r, cz), (front, cy, cz)],      # 底
        [(back, r, top), (back, l, top), (front, cy, top)],   # 上
        [(back, l, cz), (back, l, top), (back, r, top)],      # 後ろ
        [(back, l, cz), (back, r, top), (back, r, cz)],
        [(back, r, cz), (back, r, top), (front, cy, top)],    # 右の斜め
        [(back, r, cz), (front, cy, top), (front, cy, cz)],
        [(front, cy, cz), (front, cy, top), (back, l, top)],  # 左の斜め
        [(front, cy, cz), (back, l, top), (back, l, cz)],
    ]
    middle = (cx, cy, cz + height / 2)
    positions, normals, indices = [], [], []
    for tri in triangles:
        n = face_normal(*tri)
        # 三角柱は凸なので、法線が中心から外を向くように頂点の順をそろえる (反時計回りが表)
        centroid = [sum(p[i] for p in tri) / 3 for i in range(3)]
        if sum(n[i] * (centroid[i] - middle[i]) for i in range(3)) < 0:
            tri = [tri[0], tri[2], tri[1]]
            n = tuple(-x for x in n)
        for p in tri:
            indices.append(len(positions))
            positions.append(p)
            normals.append(n)
    return positions, normals, indices


def face_normal(p0, p1, p2):
    u = [p1[i] - p0[i] for i in range(3)]
    v = [p2[i] - p0[i] for i in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(x * x for x in n)) or 1.0
    return tuple(x / length for x in n)


# ---------------------------------------------------------------- .glb

def to_gltf(p):
    """juiz の (x 前, y 左, z 上) を glTF の Y 上の (x, y, z) にする。juiz が x 軸まわりに +90° 回すとき (x, y, z) に戻る。"""
    x, y, z = p
    return (x, z, -y)


def write_glb(path, parts):
    """parts: [(名前, 色, (頂点, 法線, 番号))]。1 つの mesh に、部品ごとの primitive と material を入れる。"""
    binary = bytearray()
    buffer_views, accessors, materials, primitives = [], [], [], []

    def add_view(data, target):
        while len(binary) % 4:
            binary.append(0)
        buffer_views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data), "target": target})
        binary.extend(data)
        return len(buffer_views) - 1

    for name, color, (positions, normals, indices) in parts:
        positions = [to_gltf(p) for p in positions]
        normals = [to_gltf(n) for n in normals]
        pos_view = add_view(b"".join(struct.pack("<3f", *p) for p in positions), 34962)
        nor_view = add_view(b"".join(struct.pack("<3f", *n) for n in normals), 34962)
        idx_view = add_view(b"".join(struct.pack("<I", i) for i in indices), 34963)
        # POSITION の min / max は glTF で必須。float32 に丸めた値で書く
        rounded = [struct.unpack("<3f", struct.pack("<3f", *p)) for p in positions]
        accessors += [
            {"bufferView": pos_view, "componentType": 5126, "count": len(positions), "type": "VEC3",
             "min": [min(p[i] for p in rounded) for i in range(3)],
             "max": [max(p[i] for p in rounded) for i in range(3)]},
            {"bufferView": nor_view, "componentType": 5126, "count": len(normals), "type": "VEC3"},
            {"bufferView": idx_view, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ]
        materials.append({"name": name, "pbrMetallicRoughness": {
            "baseColorFactor": list(color), "metallicFactor": 0.0, "roughnessFactor": 0.8}})
        n = len(accessors)
        primitives.append({"attributes": {"POSITION": n - 3, "NORMAL": n - 2}, "indices": n - 1,
                           "material": len(materials) - 1})

    while len(binary) % 4:
        binary.append(0)
    document = {
        "asset": {"version": "2.0", "generator": "juiz_examples scripts/make_models.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"name": os.path.splitext(os.path.basename(path))[0], "mesh": 0}],
        "meshes": [{"primitives": primitives}],
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binary)}],
    }
    chunk_json = json.dumps(document, separators=(",", ":")).encode("utf-8")
    chunk_json += b" " * (-len(chunk_json) % 4)
    total = 12 + 8 + len(chunk_json) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(chunk_json), b"JSON") + chunk_json)
        f.write(struct.pack("<I4s", len(binary), b"BIN\x00") + bytes(binary))


# ---------------------------------------------------------------- .stl

def write_stl(path, parts):
    """バイナリ STL。parts: [(頂点, 法線, 番号)]。面の法線は三角形から求める。"""
    triangles = []
    for positions, _normals, indices in parts:
        for k in range(0, len(indices), 3):
            triangles.append([positions[indices[k + j]] for j in range(3)])
    header = b"juiz_examples scripts/make_models.py: camera (mm)".ljust(80, b" ")
    with open(path, "wb") as f:
        f.write(header + struct.pack("<I", len(triangles)))
        for tri in triangles:
            f.write(struct.pack("<3f", *face_normal(*tri)))
            for p in tri:
                f.write(struct.pack("<3f", *p))
            f.write(struct.pack("<H", 0))


# ---------------------------------------------------------------- モデル

def floor_parts():
    """床 (map に付ける)。8 m 四方の薄い板と、map の x 軸 (赤)・y 軸 (緑) の向きを示す線。"""
    return [
        ("floor", GRAY, box((0, 0, -0.01), (8.0, 8.0, 0.02))),
        ("x_axis", RED, box((0.5, 0, 0.001), (1.0, 0.04, 0.002))),
        ("y_axis", GREEN, box((0, 0.5, 0.001), (0.04, 1.0, 0.002))),
    ]


def mobile_base_parts():
    """台車 (base0)。原点は床の上の中心。胴体の上に前 (+x) を指す黄色の三角の印。

    雲台 (pantilt0) は conf の Transform で台車の (0.1, 0, 0.3) に付くので、胴体の上面を z = 0.3 にする。
    """
    wheels = [cylinder((x, y, 0.08), 0.08, 0.05, "y") for x in (0.17, -0.17) for y in (0.225, -0.225)]
    parts = [
        ("body", BLUE, box((0, 0, 0.19), (0.5, 0.4, 0.22))),
        ("front_mark", YELLOW, wedge((0.19, 0, 0.30), 0.10, 0.12, 0.005)),
    ]
    parts += [(f"wheel{i}", DARK, w) for i, w in enumerate(wheels)]
    return parts


def camera_parts():
    """カメラ (camera0)。単位は mm。原点は背面の中心で、+x にレンズ (前)。"""
    return [
        box((15, 0, 0), (30, 60, 30)),
        cylinder((37.5, 0, 0), 10, 15, "x"),
    ]


def main() -> int:
    os.makedirs(MODELS, exist_ok=True)
    write_glb(os.path.join(MODELS, "floor.glb"), floor_parts())
    write_glb(os.path.join(MODELS, "mobile_base.glb"), mobile_base_parts())
    write_stl(os.path.join(MODELS, "camera.stl"), camera_parts())
    for name in ("floor.glb", "mobile_base.glb", "camera.stl"):
        path = os.path.join(MODELS, name)
        print(f"wrote: {os.path.relpath(path, ROOT)} ({os.path.getsize(path)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
