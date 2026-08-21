from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import shutil
import zipfile

import matplotlib.pyplot as plt
import numpy as np
import shapely
import trimesh
from shapely.geometry import Point, Polygon, box as sbox
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

ROOT = Path('/mnt/data/dumbbell_ptz_v8_43_annotated_internal_layout')
STL = ROOT / 'stl'
MF3 = ROOT / '3mf'
PRE = ROOT / 'preview'
VAL = ROOT / 'validation'
SRC = ROOT / 'source'
for directory in (STL, MF3, PRE, VAL, SRC):
    directory.mkdir(parents=True, exist_ok=True)

HEAD_BASE = Path('/mnt/data/dumbbell_ptz_v8_36_head_joint_floor_reinforced')
COLUMN_BASE = Path('/mnt/data/dumbbell_ptz_v8_31_v826_flat_rebuild/stl/column.stl')

# -----------------------------------------------------------------------------
# Exterior: symmetric 45 degree dumbbell shoulders
# -----------------------------------------------------------------------------
WALL = 2.4
CUP_H = 82.0
END_AF = 119.0
BELT_AF = 135.0
BOTTOM_BEVEL_TOP_Z = 8.0
TOP_BEVEL_BOTTOM_Z = 74.0
TOP_AF = 119.0
FLOOR_Z = 8.0

# Lid
LID_T = 4.0
STEP_TIER_H = 1.2
TOL = 0.50
RING_OD = 44.0
RING_ID = 35.2
RING_H = 6.0
DRIVE_OPEN_D = 21.8
CABLE_SLOT_W = 10.0
CABLE_SLOT_Y0 = 8.5
CABLE_SLOT_Y1 = 24.0
CABLE_SLOT_X = (-7.5, 7.5)
SERVO_SERVICE_X = 0.0
SERVO_SERVICE_Y = 34.0
SERVO_SERVICE_W = 38.0
SERVO_SERVICE_D = 18.0
SERVO_SERVICE_R = 3.0

# -----------------------------------------------------------------------------
# Yaw ST3215 support, restored from the older 82 mm design
# -----------------------------------------------------------------------------
SV_HALF_W = 24.7 / 2.0
YAW_Y0 = -35.1
YAW_Y1 = 10.1
MOTOR_BOTTOM_Z = 42.0
MOTOR_TOP_Z = 77.0
MOTOR_SIDE_CLEARANCE = 0.70
YAW_MOUNT_HOLES = [
    (10.25, -8.30), (-10.25, -8.30),
    (10.25, -29.00), (-10.25, -29.00),
]

# -----------------------------------------------------------------------------
# UNO Q: restored inside the shell and raised toward +Y for USB access.
# The holder stays visible and retains the intentional rear openings.
# -----------------------------------------------------------------------------
UNO_CASE_LEN = 73.5822
UNO_CASE_HEIGHT = 58.3433
UNO_CASE_THICKNESS = 11.0
UNO_CENTER_X = -36.0
UNO_CENTER_Y = 20.0
UNO_BOTTOM_Z = 14.0
UNO_CENTER_Z = UNO_BOTTOM_Z + UNO_CASE_HEIGHT / 2.0
UNO_TOP_Z = UNO_BOTTOM_Z + UNO_CASE_HEIGHT
UNO_CASE_HOLES = [
    (31.75, 8.89),
    (31.75, -19.05),
    (-19.05, 24.13),
    (-20.32, -24.13),
]
# Keep only the two mounting points on the motor-facing half of the enclosure.
UNO_USED_HOLES = [UNO_CASE_HOLES[2], UNO_CASE_HOLES[3]]
UNO_UNUSED_HOLES = [UNO_CASE_HOLES[0], UNO_CASE_HOLES[1]]

# -----------------------------------------------------------------------------
# Hub and servo-board
# -----------------------------------------------------------------------------
HUB_SLOT_T = 11.0
HUB_ALLOC_DEPTH = 15.0
HUB_CENTER_X = 35.5
HUB_Y0, HUB_Y1 = -36.5, 36.5
HUB_Z0, HUB_Z1 = 13.0, 67.0

SERVO_DRV_W = 54.5
SERVO_DRV_H = 45.5
SERVO_DRV_T = 22.0
BELT_INNER_AF = BELT_AF - 2.0 * WALL
BELT_INNER_Y = BELT_AF / 2.0 - WALL
SERVO_DRV_CENTER_Y = BELT_INNER_Y - SERVO_DRV_T / 2.0
SERVO_DRV_CENTER_Z = FLOOR_Z + SERVO_DRV_H / 2.0
SERVO_DRV_HOLES = [
    (-18.6, -14.1), (-18.6, 14.1),
    (18.6, -14.1), (18.6, 14.1),
]

POWER_HOLE_D = 20.0
POWER_HOLE_X = 22.0
POWER_HOLE_Z = 64.0
USB_A_HOLE_W = 32.0
USB_A_HOLE_H = 16.0
USB_A_HOLE_X = -9.0
USB_A_HOLE_Z = 64.0
USB_A_CORNER_R = 2.0

# -----------------------------------------------------------------------------
# Four independent cup-to-lid posts: floor-to-top, close to the wall,
# independent of UNO Q and hub supports.
# -----------------------------------------------------------------------------
POST_CENTERS = [
    (-50.0, 18.0),
    (-50.0, -18.0),
    (50.0, 18.0),
    (50.0, -18.0),
]
POST_OD = 9.0
POST_PILOT_D = 4.2
POST_TOP_Z = CUP_H - 3.6
POST_RIB_WIDTH = 7.0
POST_WALL_OVERLAP = 0.8

# -----------------------------------------------------------------------------
# Exact planar geometry helpers
# -----------------------------------------------------------------------------
def rounded_rect(cx: float, cy: float, sx: float, sy: float, radius: float,
                 resolution: int = 16):
    return sbox(
        cx - sx / 2.0 + radius,
        cy - sy / 2.0 + radius,
        cx + sx / 2.0 - radius,
        cy + sy / 2.0 - radius,
    ).buffer(radius, resolution=resolution)


def _coord3(point, fixed_axis: int, fixed_value: float, axis0: int, axis1: int):
    result = [0.0, 0.0, 0.0]
    result[axis0] = point[0]
    result[axis1] = point[1]
    result[fixed_axis] = fixed_value
    return tuple(result)


def extrude_polygon(poly, fixed_axis: int, value0: float, value1: float,
                    axis0: int, axis1: int) -> trimesh.Trimesh:
    if poly.is_empty:
        raise ValueError('Cannot extrude empty polygon')
    if poly.geom_type == 'MultiPolygon':
        return trimesh.util.concatenate([
            extrude_polygon(part, fixed_axis, value0, value1, axis0, axis1)
            for part in poly.geoms
        ])

    poly = orient(poly, sign=1.0)
    triangles = list(shapely.constrained_delaunay_triangles(poly).geoms)
    vertices = []
    faces = []
    index = {}

    def vertex_id(point, level: int):
        xyz = _coord3(
            point,
            fixed_axis,
            value0 if level == 0 else value1,
            axis0,
            axis1,
        )
        key = tuple(round(value, 9) for value in xyz)
        if key not in index:
            index[key] = len(vertices)
            vertices.append(key)
        return index[key]

    for triangle in triangles:
        coords = list(triangle.exterior.coords)[:3]
        lower = [vertex_id(point, 0) for point in coords]
        upper = [vertex_id(point, 1) for point in coords]
        faces.append([lower[0], lower[2], lower[1]])
        faces.append([upper[0], upper[1], upper[2]])

    for loop in [poly.exterior] + list(poly.interiors):
        coords = list(loop.coords)
        for point0, point1 in zip(coords[:-1], coords[1:]):
            lower0 = vertex_id(point0, 0)
            lower1 = vertex_id(point1, 0)
            upper0 = vertex_id(point0, 1)
            upper1 = vertex_id(point1, 1)
            faces.append([lower0, lower1, upper1])
            faces.append([lower0, upper1, upper0])

    mesh = trimesh.Trimesh(
        vertices=np.asarray(vertices),
        faces=np.asarray(faces),
        process=True,
    )
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    return mesh


def prism_xy(poly, z0: float, z1: float) -> trimesh.Trimesh:
    return extrude_polygon(poly, 2, z0, z1, 0, 1)


def prism_xz(poly, y0: float, y1: float) -> trimesh.Trimesh:
    return extrude_polygon(poly, 1, y0, y1, 0, 2)


def prism_yz(poly, x0: float, x1: float) -> trimesh.Trimesh:
    return extrude_polygon(poly, 0, x0, x1, 1, 2)


def hex_poly(across_flats: float) -> Polygon:
    radius = across_flats / math.sqrt(3.0)
    return Polygon([
        (
            radius * math.cos(math.radians(index * 60.0)),
            radius * math.sin(math.radians(index * 60.0)),
        )
        for index in range(6)
    ])


def hex_frustum_solid(af0: float, af1: float, z0: float, z1: float):
    angles = np.radians(np.arange(6) * 60.0)
    radius0 = af0 / math.sqrt(3.0)
    radius1 = af1 / math.sqrt(3.0)
    bottom = np.column_stack((
        radius0 * np.cos(angles),
        radius0 * np.sin(angles),
        np.full(6, z0),
    ))
    top = np.column_stack((
        radius1 * np.cos(angles),
        radius1 * np.sin(angles),
        np.full(6, z1),
    ))
    vertices = np.vstack((bottom, top))
    faces = []
    for index in range(6):
        next_index = (index + 1) % 6
        faces.extend((
            [index, next_index, 6 + next_index],
            [index, 6 + next_index, 6 + index],
        ))
    for index in range(1, 5):
        faces.append([0, index + 1, index])
        faces.append([6, 6 + index, 6 + index + 1])
    mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh


def hex_frustum_shell(outer0: float, outer1: float,
                      inner0: float, inner1: float,
                      z0: float, z1: float):
    angles = np.radians(np.arange(6) * 60.0)

    def ring(af: float, z: float):
        radius = af / math.sqrt(3.0)
        return np.column_stack((
            radius * np.cos(angles),
            radius * np.sin(angles),
            np.full(6, z),
        ))

    outer_bottom = ring(outer0, z0)
    outer_top = ring(outer1, z1)
    inner_bottom = ring(inner0, z0)
    inner_top = ring(inner1, z1)
    vertices = np.vstack((outer_bottom, outer_top, inner_bottom, inner_top))
    OB, OT, IB, IT = 0, 6, 12, 18
    faces = []
    for index in range(6):
        next_index = (index + 1) % 6
        faces.extend((
            [OB + index, OB + next_index, OT + next_index],
            [OB + index, OT + next_index, OT + index],
        ))
        faces.extend((
            [IB + index, IT + next_index, IB + next_index],
            [IB + index, IT + index, IT + next_index],
        ))
        faces.extend((
            [OB + index, IB + next_index, OB + next_index],
            [OB + index, IB + index, IB + next_index],
        ))
        faces.extend((
            [OT + index, OT + next_index, IT + next_index],
            [OT + index, IT + next_index, IT + index],
        ))
    mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=True)
    mesh.fix_normals()
    return mesh


def box_mesh(x0: float, x1: float, y0: float, y1: float,
             z0: float, z1: float) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    mesh.apply_translation([
        (x0 + x1) / 2.0,
        (y0 + y1) / 2.0,
        (z0 + z1) / 2.0,
    ])
    return mesh


def cylinder_mesh(diameter: float, height: float, axis: str = 'z',
                  center=(0.0, 0.0, 0.0), sections: int = 64):
    mesh = trimesh.creation.cylinder(
        radius=diameter / 2.0,
        height=height,
        sections=sections,
    )
    if axis == 'x':
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(math.pi / 2.0, [0, 1, 0])
        )
    elif axis == 'y':
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(math.pi / 2.0, [1, 0, 0])
        )
    mesh.apply_translation(center)
    return mesh


def annulus_mesh(outer_d: float, inner_d: float, height: float,
                 axis: str = 'z', center=(0.0, 0.0, 0.0), sections: int = 64):
    transform = np.eye(4)
    if axis == 'x':
        transform = trimesh.transformations.rotation_matrix(math.pi / 2.0, [0, 1, 0])
    elif axis == 'y':
        transform = trimesh.transformations.rotation_matrix(math.pi / 2.0, [1, 0, 0])
    transform[:3, 3] = np.asarray(center, dtype=float)
    mesh = trimesh.creation.annulus(
        r_min=inner_d / 2.0,
        r_max=outer_d / 2.0,
        height=height,
        sections=sections,
        transform=transform,
    )
    mesh.fix_normals()
    return mesh


def local_radial_rib(angle_deg: float, rz_polygon: Polygon,
                     tangential_width: float) -> trimesh.Trimesh:
    # Create in local X(radial)-Z coordinates, extrude along local Y(tangent),
    # then rotate the part around global Z.
    mesh = prism_xz(rz_polygon, -tangential_width / 2.0, tangential_width / 2.0)
    mesh.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(angle_deg), [0, 0, 1]
        )
    )
    return mesh


def save_components(name: str, components: list[trimesh.Trimesh]):
    combined = trimesh.util.concatenate(components)
    combined.remove_unreferenced_vertices()
    combined.export(STL / f'{name}.stl')
    scene = trimesh.Scene()
    for index, component in enumerate(components):
        scene.add_geometry(component, geom_name=f'{name}_{index:03d}')
    scene.export(MF3 / f'{name}_components.3mf')
    return combined


def outer_af_at_z(z: float) -> float:
    if z <= BOTTOM_BEVEL_TOP_Z:
        return END_AF + (BELT_AF - END_AF) * (z / BOTTOM_BEVEL_TOP_Z)
    if z >= TOP_BEVEL_BOTTOM_Z:
        return BELT_AF + (TOP_AF - BELT_AF) * (
            (z - TOP_BEVEL_BOTTOM_Z) / (CUP_H - TOP_BEVEL_BOTTOM_Z)
        )
    return BELT_AF


def inner_inradius_at_z(z: float) -> float:
    return outer_af_at_z(z) / 2.0 - WALL


def radial_hex_boundary_at_z(
    z: float,
    angle_deg: float,
    inner: bool = True,
) -> float:
    af = outer_af_at_z(z) - (2.0 * WALL if inner else 0.0)
    local_angle = math.radians(angle_deg % 60.0)
    circumradius = af / math.sqrt(3.0)
    denominator = (
        math.cos(local_angle)
        + math.sin(local_angle) / math.sqrt(3.0)
    )
    return circumradius / denominator


def hex_envelope_margin(x: float, y: float, z: float, inner: bool = False) -> float:
    af = outer_af_at_z(z) - (2.0 * WALL if inner else 0.0)
    radius = af / math.sqrt(3.0)
    return radius - (abs(x) + abs(y) / math.sqrt(3.0))

# -----------------------------------------------------------------------------
# CUP EXTERIOR
# -----------------------------------------------------------------------------
cup_parts: list[trimesh.Trimesh] = []

# Solid lower 45 degree shoulder. Its top plane is the structural floor.
cup_parts.append(hex_frustum_solid(END_AF, BELT_AF, 0.0, FLOOR_Z))

belt_outer = hex_poly(BELT_AF)
belt_inner = hex_poly(BELT_INNER_AF)
outer_vertices = np.asarray(belt_outer.exterior.coords[:-1])
inner_vertices = np.asarray(belt_inner.exterior.coords[:-1])

# Five uninterrupted walls. +Y is generated with the requested ports only.
for index in range(6):
    next_index = (index + 1) % 6
    if index == 1:
        continue
    wall_panel = Polygon([
        tuple(outer_vertices[index]),
        tuple(outer_vertices[next_index]),
        tuple(inner_vertices[next_index]),
        tuple(inner_vertices[index]),
    ])
    cup_parts.append(prism_xy(wall_panel, FLOOR_Z, TOP_BEVEL_BOTTOM_Z))

x_half = (BELT_AF / math.sqrt(3.0)) / 2.0
port_face = sbox(-x_half, FLOOR_Z, x_half, TOP_BEVEL_BOTTOM_Z)
port_holes = [
    rounded_rect(
        USB_A_HOLE_X, USB_A_HOLE_Z,
        USB_A_HOLE_W, USB_A_HOLE_H,
        USB_A_CORNER_R,
    ),
    Point(POWER_HOLE_X, POWER_HOLE_Z).buffer(
        POWER_HOLE_D / 2.0, resolution=24
    ),
]
for hole_x, local_z in SERVO_DRV_HOLES:
    port_holes.append(
        Point(hole_x, SERVO_DRV_CENTER_Z + local_z).buffer(1.7, resolution=20)
    )
port_face_cut = port_face.difference(unary_union(port_holes))
# Decompose the perforated face into individually watertight triangular prisms.
# This avoids non-manifold triangulation around several mixed round/rectangular holes.
for triangle in shapely.constrained_delaunay_triangles(port_face_cut).geoms:
    if port_face_cut.covers(triangle.representative_point()):
        cup_parts.append(
            prism_xz(
                triangle,
                BELT_AF / 2.0 - WALL,
                BELT_AF / 2.0,
            )
        )

# Symmetric upper 45 degree shoulder.
cup_parts.append(
    hex_frustum_shell(
        BELT_AF, TOP_AF,
        BELT_INNER_AF, TOP_AF - 2.0 * WALL,
        TOP_BEVEL_BOTTOM_Z, CUP_H,
    )
)

# -----------------------------------------------------------------------------
# Independent floor-to-wall lid posts
# -----------------------------------------------------------------------------
post_centers = []
post_components = []
for center in POST_CENTERS:
    post_centers.append(center)
    angle_deg = math.degrees(math.atan2(center[1], center[0])) % 360.0
    post_radius = math.hypot(center[0], center[1])

    # Full-height annular post, independent of electronics holders.
    post = annulus_mesh(
        POST_OD,
        POST_PILOT_D,
        POST_TOP_Z - FLOOR_Z,
        center=(
            center[0], center[1],
            (POST_TOP_Z + FLOOR_Z) / 2.0,
        ),
    )
    cup_parts.append(post)
    post_components.append(post)

    # At these middle-wall locations the post remains inside the top
    # 45-degree shoulder, so the rib can follow the full tapered wall.
    post_outer_r = post_radius + POST_OD / 2.0 - 0.5
    wall_r_floor = (
        radial_hex_boundary_at_z(FLOOR_Z, angle_deg, inner=True)
        + POST_WALL_OVERLAP
    )
    wall_r_bevel = (
        radial_hex_boundary_at_z(
            TOP_BEVEL_BOTTOM_Z, angle_deg, inner=True
        )
        + POST_WALL_OVERLAP
    )
    wall_r_top = (
        radial_hex_boundary_at_z(POST_TOP_Z, angle_deg, inner=True)
        + POST_WALL_OVERLAP
    )
    rib_section = Polygon([
        (post_outer_r, FLOOR_Z),
        (wall_r_floor, FLOOR_Z),
        (wall_r_bevel, TOP_BEVEL_BOTTOM_Z),
        (wall_r_top, POST_TOP_Z),
        (post_outer_r, POST_TOP_Z),
    ]).buffer(0)
    wall_rib = local_radial_rib(
        angle_deg,
        rib_section,
        POST_RIB_WIDTH,
    )
    cup_parts.append(wall_rib)
    post_components.append(wall_rib)

# -----------------------------------------------------------------------------
# Restored yaw motor height-setting cradle
# -----------------------------------------------------------------------------
yaw_support_parts = []
rail_inner = SV_HALF_W + MOTOR_SIDE_CLEARANCE
rail_outer = rail_inner + 2.6
rear_inner = YAW_Y0 - MOTOR_SIDE_CLEARANCE
front_inner = YAW_Y1 + MOTOR_SIDE_CLEARANCE

# Two tall side rails locate the motor body and carry load to the floor.
for x0, x1 in ((-rail_outer, -rail_inner), (rail_inner, rail_outer)):
    rail = box_mesh(
        x0, x1,
        rear_inner - 1.8, front_inner + 1.8,
        FLOOR_Z, MOTOR_BOTTOM_Z + 16.0,
    )
    cup_parts.append(rail)
    yaw_support_parts.append(rail)

# Two 2 mm top ledges establish the exact motor bottom plane at Z=42 mm,
# leaving the center open for wiring and underside details.
for x0, x1 in ((-SV_HALF_W, -7.0), (7.0, SV_HALF_W)):
    ledge = box_mesh(
        x0, x1,
        YAW_Y0, YAW_Y1,
        MOTOR_BOTTOM_Z - 2.0, MOTOR_BOTTOM_Z,
    )
    cup_parts.append(ledge)
    yaw_support_parts.append(ledge)

# Restored front/rear end stops from the old 82 mm cradle.
for x0, x1 in ((-rail_outer, -7.2), (7.2, rail_outer)):
    rear_stop = box_mesh(
        x0, x1,
        rear_inner - 2.2, rear_inner,
        FLOOR_Z, MOTOR_BOTTOM_Z + 12.0,
    )
    front_stop = box_mesh(
        x0, x1,
        front_inner, front_inner + 2.2,
        FLOOR_Z, MOTOR_BOTTOM_Z + 12.0,
    )
    cup_parts.extend((rear_stop, front_stop))
    yaw_support_parts.extend((rear_stop, front_stop))

# Four original-style lower pads hold the motor mounting ears at the correct level.
for pad_x in (-9.1, 9.1):
    for pad_y in (-26.0, 4.5):
        pad = box_mesh(
            pad_x - 3.2, pad_x + 3.2,
            pad_y - 4.0, pad_y + 4.0,
            FLOOR_Z, MOTOR_BOTTOM_Z + 2.2,
        )
        cup_parts.append(pad)
        yaw_support_parts.append(pad)

# Floor cross-ribs make the pedestal a single supported structure instead of
# four isolated towers.
for y_center in (-26.0, 4.5):
    cross_rib = box_mesh(
        -rail_outer, rail_outer,
        y_center - 2.2, y_center + 2.2,
        FLOOR_Z, FLOOR_Z + 3.2,
    )
    cup_parts.append(cross_rib)
    yaw_support_parts.append(cross_rib)

# -----------------------------------------------------------------------------
# UNO Q holder: raised for USB access, open rear frame, two screws only
# -----------------------------------------------------------------------------
uno_parts = []
case_x0 = UNO_CENTER_X - UNO_CASE_THICKNESS / 2.0
case_x1 = UNO_CENTER_X + UNO_CASE_THICKNESS / 2.0
case_y0 = UNO_CENTER_Y - UNO_CASE_LEN / 2.0
case_y1 = UNO_CENTER_Y + UNO_CASE_LEN / 2.0

# Every planar UNO support is clipped to the inner hex. Only the portion that
# would pass through the faceted outline is removed.
uno_clip_polygon = hex_poly(BELT_INNER_AF - 0.4)


def add_clipped_uno_plate(
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    z0: float,
    z1: float,
):
    footprint = sbox(x0, y0, x1, y1).intersection(uno_clip_polygon)
    if footprint.is_empty:
        return None
    component = prism_xy(footprint, z0, z1)
    cup_parts.append(component)
    uno_parts.append(component)
    return component


# Rear mounting frame. The large central opening restores the intentional
# clearance for components on the rear face of the UNO Q assembly.
backplate_x0 = case_x0 - 3.0
backplate_x1 = case_x0 - 0.6
backplate_y0 = case_y0 + 2.0
backplate_y1 = case_y1 - 1.0
backplate_z0 = UNO_BOTTOM_Z
backplate_z1 = min(UNO_TOP_Z, TOP_BEVEL_BOTTOM_Z - 1.2)

uno_window_y0 = UNO_CENTER_Y - 28.0
uno_window_y1 = UNO_CENTER_Y + 28.0
uno_window_z0 = UNO_BOTTOM_Z + 4.2
uno_window_z1 = UNO_TOP_Z - 5.2

# Bottom and top bars.
add_clipped_uno_plate(
    backplate_x0, backplate_x1,
    backplate_y0, backplate_y1,
    backplate_z0, uno_window_z0,
)
add_clipped_uno_plate(
    backplate_x0, backplate_x1,
    backplate_y0, backplate_y1,
    uno_window_z1, backplate_z1,
)

# Two narrow side rails around the open window.
add_clipped_uno_plate(
    backplate_x0, backplate_x1,
    backplate_y0, uno_window_y0,
    uno_window_z0, uno_window_z1,
)
add_clipped_uno_plate(
    backplate_x0, backplate_x1,
    uno_window_y1, backplate_y1,
    uno_window_z0, uno_window_z1,
)

# The lower support is also a frame, not a solid flat board.
shelf_outer = sbox(
    backplate_x0,
    case_y0 + 1.5,
    case_x1 - 0.8,
    case_y1 - 1.5,
)
shelf_opening = sbox(
    backplate_x0 + 3.4,
    case_y0 + 8.0,
    case_x1 - 3.0,
    case_y1 - 8.0,
)
shelf_footprint = (
    shelf_outer
    .difference(shelf_opening)
    .intersection(uno_clip_polygon)
)
shelf = prism_xy(
    shelf_footprint,
    UNO_BOTTOM_Z - 2.8,
    UNO_BOTTOM_Z,
)
cup_parts.append(shelf)
uno_parts.append(shelf)

# Small end lips stop vertical sliding. Their footprints are clipped too.
for lip_y0, lip_y1 in (
    (case_y0 + 1.5, case_y0 + 4.5),
    (case_y1 - 4.5, case_y1 - 1.5),
):
    add_clipped_uno_plate(
        backplate_x0,
        case_x0 + 1.5,
        lip_y0,
        lip_y1,
        UNO_BOTTOM_Z,
        UNO_BOTTOM_Z + 5.0,
    )

# Keep only the two holes nearest the centre motor.
# Small backing tabs link each annular boss to the nearest frame rail while
# leaving the main rear opening clear.
uno_mount_centers = []
for local_y, local_z in UNO_USED_HOLES:
    mount_y = UNO_CENTER_Y + local_y
    mount_z = UNO_CENTER_Z + local_z
    center = (
        backplate_x1 - 0.2,
        mount_y,
        mount_z,
    )
    uno_mount_centers.append(center)

    backing_y0 = min(uno_window_y0, mount_y - 4.5)
    backing_y1 = mount_y + 4.5
    backing_z0 = mount_z - 4.5
    backing_z1 = mount_z + 4.5
    add_clipped_uno_plate(
        backplate_x0,
        backplate_x1,
        backing_y0,
        backing_y1,
        backing_z0,
        backing_z1,
    )

    boss = annulus_mesh(
        outer_d=8.0,
        inner_d=3.0,
        height=4.8,
        axis='x',
        center=center,
    )
    cup_parts.append(boss)
    uno_parts.append(boss)

# -----------------------------------------------------------------------------
# Hub holder remains independent of the lid posts
# -----------------------------------------------------------------------------
hub_parts = []
hub_x0 = HUB_CENTER_X - HUB_SLOT_T / 2.0
hub_x1 = HUB_CENTER_X + HUB_SLOT_T / 2.0
for component in (
    box_mesh(
        HUB_CENTER_X - HUB_ALLOC_DEPTH / 2.0,
        HUB_CENTER_X + HUB_ALLOC_DEPTH / 2.0,
        HUB_Y0, HUB_Y1,
        FLOOR_Z, HUB_Z0,
    ),
    box_mesh(hub_x0 - 1.2, hub_x0, -31.0, HUB_Y1, HUB_Z0, HUB_Z1),
    box_mesh(hub_x1, hub_x1 + 2.2, -31.0, HUB_Y1, HUB_Z0, HUB_Z1),
    box_mesh(hub_x0 - 1.2, hub_x0 + 0.8, -30.0, 32.0, HUB_Z1, HUB_Z1 + 2.5),
    box_mesh(hub_x1 - 0.8, hub_x1 + 2.2, -30.0, 32.0, HUB_Z1, HUB_Z1 + 2.5),
):
    cup_parts.append(component)
    hub_parts.append(component)

cup_mesh = save_components('cup', cup_parts)

# -----------------------------------------------------------------------------
# LID: holes follow the new independent wall posts
# -----------------------------------------------------------------------------
lid_outer = hex_poly(TOP_AF)
lid_lower = hex_poly(TOP_AF - 2.0 * WALL - TOL)


def cable_slot(x_center: float):
    radius = CABLE_SLOT_W / 2.0
    return (
        sbox(
            x_center - radius, CABLE_SLOT_Y0,
            x_center + radius, CABLE_SLOT_Y1,
        )
        .union(Point(x_center, CABLE_SLOT_Y0).buffer(radius, resolution=20))
        .union(Point(x_center, CABLE_SLOT_Y1).buffer(radius, resolution=20))
    )


service_opening = rounded_rect(
    SERVO_SERVICE_X, SERVO_SERVICE_Y,
    SERVO_SERVICE_W, SERVO_SERVICE_D,
    SERVO_SERVICE_R,
)
upper_holes = [
    Point(0.0, 0.0).buffer(DRIVE_OPEN_D / 2.0, resolution=32),
    service_opening,
]
recess_holes = [
    Point(0.0, 0.0).buffer(DRIVE_OPEN_D / 2.0, resolution=32),
    service_opening,
]
for x_center in CABLE_SLOT_X:
    upper_holes.append(cable_slot(x_center))
    recess_holes.append(cable_slot(x_center))
for hole_x, hole_y in YAW_MOUNT_HOLES:
    upper_holes.append(Point(hole_x, hole_y).buffer(1.2, resolution=16))
    recess_holes.append(Point(hole_x, hole_y).buffer(2.2, resolution=16))
for post_x, post_y in post_centers:
    upper_holes.append(Point(post_x, post_y).buffer(1.7, resolution=16))
    recess_holes.append(Point(post_x, post_y).buffer(1.7, resolution=16))

upper_cut = unary_union(upper_holes)
recess_cut = unary_union(recess_holes)
ring_section = (
    Point(0.0, 0.0).buffer(RING_OD / 2.0, resolution=32)
    .difference(Point(0.0, 0.0).buffer(RING_ID / 2.0, resolution=32))
)
lid_parts = [
    prism_xy(lid_outer.difference(upper_cut), 0.0, LID_T),
    prism_xy(lid_lower.difference(upper_cut), -STEP_TIER_H, -0.8),
    prism_xy(lid_lower.difference(recess_cut), -0.8, 0.0),
    prism_xy(ring_section, LID_T, LID_T + RING_H),
]
lid_mesh = save_components('lid', lid_parts)

# -----------------------------------------------------------------------------
# Preserve reinforced head and column
# -----------------------------------------------------------------------------
for name in ('head_front', 'head_back'):
    shutil.copy2(HEAD_BASE / 'stl' / f'{name}.stl', STL / f'{name}.stl')
for name in (
    'head_front_reinforced_components.3mf',
    'head_back_reinforced_components.3mf',
):
    shutil.copy2(HEAD_BASE / '3mf' / name, MF3 / name)
shutil.copy2(COLUMN_BASE, STL / 'column.stl')

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------
def bbox_overlap_volume(bounds_a, bounds_b) -> float:
    overlap = np.minimum(bounds_a[1], bounds_b[1]) - np.maximum(bounds_a[0], bounds_b[0])
    return float(np.prod(np.maximum(overlap, 0.0)))


def combined_bounds(meshes: list[trimesh.Trimesh]):
    vertices = np.vstack([mesh.vertices for mesh in meshes])
    return np.asarray([vertices.min(axis=0), vertices.max(axis=0)])


uno_case_bounds = np.asarray([
    [case_x0, case_y0, UNO_BOTTOM_Z],
    [case_x1, case_y1, UNO_TOP_Z],
])
servo_board_bounds = np.asarray([
    [-SERVO_DRV_W / 2.0, SERVO_DRV_CENTER_Y - SERVO_DRV_T / 2.0, FLOOR_Z],
    [SERVO_DRV_W / 2.0, SERVO_DRV_CENTER_Y + SERVO_DRV_T / 2.0, FLOOR_Z + SERVO_DRV_H],
])
yaw_motor_bounds = np.asarray([
    [-SV_HALF_W, YAW_Y0, MOTOR_BOTTOM_Z],
    [SV_HALF_W, YAW_Y1, MOTOR_TOP_Z],
])
hub_bounds = np.asarray([
    [hub_x0, HUB_Y0, HUB_Z0],
    [hub_x1, HUB_Y1, HUB_Z1],
])

# Exterior clipping checks for all newly created internal supports.
internal_support_parts = post_components + yaw_support_parts + uno_parts + hub_parts
all_support_vertices = np.vstack([part.vertices for part in internal_support_parts])
outer_margins = np.asarray([
    hex_envelope_margin(x, y, z, inner=False)
    for x, y, z in all_support_vertices
])

uno_vertices = np.vstack([part.vertices for part in uno_parts])
uno_inner_margins = np.asarray([
    hex_envelope_margin(x, y, z, inner=True)
    for x, y, z in uno_vertices
])

post_vertices = np.vstack([part.vertices for part in post_components])
post_outer_margins = np.asarray([
    hex_envelope_margin(x, y, z, inner=False)
    for x, y, z in post_vertices
])

post_circle_polys = [Point(x, y).buffer(POST_OD / 2.0, resolution=32) for x, y in post_centers]
uno_xy = sbox(case_x0, case_y0, case_x1, case_y1)
hub_xy = sbox(hub_x0, HUB_Y0, hub_x1, HUB_Y1)
post_to_uno_distances = [poly.distance(uno_xy) for poly in post_circle_polys]
post_to_hub_distances = [poly.distance(hub_xy) for poly in post_circle_polys]

lid_underside_z = CUP_H - STEP_TIER_H
motor_to_lid_gap = lid_underside_z - MOTOR_TOP_Z

validation = {
    'version': 'v8.43',
    'cup_profile': {
        'height_mm': CUP_H,
        'bottom_end_af_mm': END_AF,
        'belt_af_mm': BELT_AF,
        'top_end_af_mm': TOP_AF,
        'bottom_bevel_z_mm': [0.0, BOTTOM_BEVEL_TOP_Z],
        'top_bevel_z_mm': [TOP_BEVEL_BOTTOM_Z, CUP_H],
        'half_width_change_mm': (BELT_AF - END_AF) / 2.0,
        'vertical_run_mm': BOTTOM_BEVEL_TOP_Z,
        'side_section_angle_degrees': 45.0,
        'top_bottom_symmetric': True,
    },
    'uno_q': {
        'case_center_mm': [UNO_CENTER_X, UNO_CENTER_Y, UNO_CENTER_Z],
        'case_bounds_mm': uno_case_bounds.tolist(),
        'moved_to_negative_x_vertex': False,
        'moved_inward_to_prevent_holder_clipping': True,
        'raised_plus_y_for_usb_access': True,
        'centered_in_y_to_reduce_interference': False,
        'used_mount_holes_local_yz_mm': [list(value) for value in UNO_USED_HOLES],
        'unused_mount_holes_local_yz_mm': [list(value) for value in UNO_UNUSED_HOLES],
        'mount_screw_count': 2,
        'minimum_holder_margin_inside_inner_hex_mm': round(float(uno_inner_margins.min()), 3),
        'top_clearance_to_45deg_bevel_mm': round(TOP_BEVEL_BOTTOM_Z - UNO_TOP_Z, 3),
        'servo_board_overlap_mm3': round(
            bbox_overlap_volume(uno_case_bounds, servo_board_bounds), 3
        ),
        'yaw_motor_overlap_mm3': round(
            bbox_overlap_volume(uno_case_bounds, yaw_motor_bounds), 3
        ),
    },
    'lid_posts': {
        'count': 4,
        'specified_centers_xy_mm': [[x, y] for x, y in POST_CENTERS],
        'centers_xy_mm': [[round(x, 4), round(y, 4)] for x, y in post_centers],
        'vertical_range_mm': [FLOOR_Z, POST_TOP_Z],
        'wall_attached_with_following_tapered_ribs': True,
        'connected_to_uno_holder': False,
        'connected_to_hub_holder': False,
        'minimum_post_circle_distance_to_uno_mm': round(min(post_to_uno_distances), 3),
        'minimum_post_circle_distance_to_hub_mm': round(min(post_to_hub_distances), 3),
        'minimum_post_rib_margin_inside_outer_shell_mm': round(float(post_outer_margins.min()), 3),
        'lid_holes_relocated_to_post_centers': True,
    },
    'yaw_motor_height_support': {
        'restored_old_style_bottom_cradle': True,
        'floor_z_mm': FLOOR_Z,
        'motor_bottom_support_plane_z_mm': MOTOR_BOTTOM_Z,
        'motor_top_proxy_z_mm': MOTOR_TOP_Z,
        'lid_underside_z_mm': lid_underside_z,
        'motor_top_to_lid_underside_gap_mm': round(motor_to_lid_gap, 3),
        'side_rails_top_z_mm': MOTOR_BOTTOM_Z + 16.0,
        'mounting_ear_pad_top_z_mm': MOTOR_BOTTOM_Z + 2.2,
        'lid_yaw_screw_holes_unchanged': [list(value) for value in YAW_MOUNT_HOLES],
    },
    'interference': {
        'uno_vs_servo_board_bbox_overlap_mm3': round(
            bbox_overlap_volume(uno_case_bounds, servo_board_bounds), 3
        ),
        'uno_vs_yaw_motor_bbox_overlap_mm3': round(
            bbox_overlap_volume(uno_case_bounds, yaw_motor_bounds), 3
        ),
        'hub_vs_yaw_motor_bbox_overlap_mm3': round(
            bbox_overlap_volume(hub_bounds, yaw_motor_bounds), 3
        ),
        'all_new_support_vertices_inside_outer_hex': bool(np.all(outer_margins >= -1e-6)),
        'minimum_new_support_outer_margin_mm': round(float(outer_margins.min()), 3),
    },
    'preserved': {
        'hub_slot_mm': HUB_SLOT_T,
        'round_port_diameter_mm': POWER_HOLE_D,
        'rectangular_port_mm': [USB_A_HOLE_W, USB_A_HOLE_H],
        'lid_cable_slot_width_mm': CABLE_SLOT_W,
        'v8_36_reinforced_head': True,
        'column_from_v8_31': True,
    },
    'mesh': {
        'cup_component_count': len(cup_parts),
        'lid_component_count': len(lid_parts),
        'cup_all_components_watertight': all(part.is_watertight for part in cup_parts),
        'lid_all_components_watertight': all(part.is_watertight for part in lid_parts),
        'cup_stl_body_count': int(trimesh.load(STL / 'cup.stl', force='mesh', process=True).body_count),
        'lid_stl_body_count': int(trimesh.load(STL / 'lid.stl', force='mesh', process=True).body_count),
        'recommended_print_files': [
            '3mf/cup_components.3mf',
            '3mf/lid_components.3mf',
            '3mf/head_front_reinforced_components.3mf',
            '3mf/head_back_reinforced_components.3mf',
        ],
    },
}
(VAL / 'validation_v8_43.json').write_text(
    json.dumps(validation, indent=2, ensure_ascii=False), encoding='utf-8'
)

# -----------------------------------------------------------------------------
# Previews
# -----------------------------------------------------------------------------
# Top layout
fig = plt.figure(figsize=(10, 9))
ax = fig.add_subplot(111)
outer_xy = np.asarray(hex_poly(BELT_AF).exterior.coords)
inner_xy = np.asarray(hex_poly(BELT_INNER_AF).exterior.coords)
ax.plot(outer_xy[:, 0], outer_xy[:, 1], linewidth=2, label='outer shell')
ax.plot(inner_xy[:, 0], inner_xy[:, 1], linewidth=1, linestyle='--', label='inner shell')
ax.add_patch(plt.Rectangle(
    (case_x0, case_y0),
    case_x1 - case_x0,
    case_y1 - case_y0,
    fill=False,
    linewidth=2,
    label='UNO Q',
))
ax.add_patch(plt.Rectangle(
    (-SERVO_DRV_W / 2.0, SERVO_DRV_CENTER_Y - SERVO_DRV_T / 2.0),
    SERVO_DRV_W,
    SERVO_DRV_T,
    fill=False,
    linewidth=2,
    label='servo board',
))
ax.add_patch(plt.Rectangle(
    (-SV_HALF_W, YAW_Y0),
    SV_HALF_W * 2.0,
    YAW_Y1 - YAW_Y0,
    fill=False,
    linewidth=2,
    label='yaw motor',
))
ax.add_patch(plt.Rectangle(
    (hub_x0, HUB_Y0),
    hub_x1 - hub_x0,
    HUB_Y1 - HUB_Y0,
    fill=False,
    linewidth=2,
    label='hub slot',
))
for index, (post_x, post_y) in enumerate(post_centers, start=1):
    ax.add_patch(plt.Circle((post_x, post_y), POST_OD / 2.0, fill=False, linewidth=2))
    ax.text(post_x, post_y, f'P{index}', ha='center', va='center', fontsize=8)
for index, (_, hole_y, hole_z) in enumerate(uno_mount_centers, start=1):
    ax.plot([backplate_x1], [hole_y], marker='o')
    ax.text(backplate_x1 + 1.0, hole_y, f'U{index}', fontsize=8)
ax.set_aspect('equal')
ax.set_xlim(-82, 82)
ax.set_ylim(-72, 72)
ax.grid(True)
ax.set_xlabel('X (mm)')
ax.set_ylabel('Y (mm)')
ax.set_title('v8.43 — Annotated layout: UNO upper-left; side-wall P1–P4 posts')
ax.legend(loc='lower left', fontsize=8)
fig.tight_layout()
fig.savefig(PRE / 'v8_43_top_layout.png', dpi=180)
plt.close(fig)

# Motor support side section
fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111)
ax.add_patch(plt.Rectangle(
    (YAW_Y0, MOTOR_BOTTOM_Z),
    YAW_Y1 - YAW_Y0,
    MOTOR_TOP_Z - MOTOR_BOTTOM_Z,
    fill=False,
    linewidth=2,
    label='ST3215 body proxy',
))
ax.add_patch(plt.Rectangle(
    (YAW_Y0, MOTOR_BOTTOM_Z - 2.0),
    YAW_Y1 - YAW_Y0,
    2.0,
    fill=False,
    linewidth=2,
    label='height ledge',
))
for y_center in (-26.0, 4.5):
    ax.add_patch(plt.Rectangle(
        (y_center - 4.0, FLOOR_Z),
        8.0,
        MOTOR_BOTTOM_Z + 2.2 - FLOOR_Z,
        fill=False,
        linewidth=1.5,
    ))
ax.axhline(FLOOR_Z, linestyle='--', linewidth=1, label='structural floor')
ax.axhline(lid_underside_z, linestyle='--', linewidth=1, label='lid underside')
ax.set_xlim(-42, 18)
ax.set_ylim(0, 84)
ax.grid(True)
ax.set_xlabel('Y (mm)')
ax.set_ylabel('Z (mm)')
ax.set_title('v8.43 — restored motor height support and lid relation')
ax.legend(loc='upper left', fontsize=8)
fig.tight_layout()
fig.savefig(PRE / 'v8_43_motor_height_support.png', dpi=180)
plt.close(fig)

# 45 degree profile
fig = plt.figure(figsize=(8, 7))
ax = fig.add_subplot(111)
profile_z = [0.0, BOTTOM_BEVEL_TOP_Z, TOP_BEVEL_BOTTOM_Z, CUP_H]
profile_half = [END_AF / 2.0, BELT_AF / 2.0, BELT_AF / 2.0, TOP_AF / 2.0]
ax.plot(profile_half, profile_z, linewidth=2)
ax.plot([-value for value in profile_half], profile_z, linewidth=2)
ax.plot([-profile_half[0], profile_half[0]], [0.0, 0.0], linewidth=2)
ax.plot([-profile_half[-1], profile_half[-1]], [CUP_H, CUP_H], linewidth=2)
ax.set_aspect('equal')
ax.set_xlim(-72, 72)
ax.set_ylim(-2, 84)
ax.grid(True)
ax.set_xlabel('Across-flats half width (mm)')
ax.set_ylabel('Z (mm)')
ax.set_title('v8.43 — symmetric 45° cup shoulders')
fig.tight_layout()
fig.savefig(PRE / 'v8_43_45deg_profile.png', dpi=180)
plt.close(fig)

# 3D lower-body scene
scene = trimesh.Scene()
scene.add_geometry(cup_mesh, geom_name='cup')
lid_preview = lid_mesh.copy()
lid_preview.apply_translation([0.0, 0.0, CUP_H + 5.0])
scene.add_geometry(lid_preview, geom_name='lid')
scene.export(PRE / 'v8_43_lower_body.glb')

# Documentation and source
readme = f'''# Dumbbell PTZ v8.43

## UNO Q relocation
- UNO Q enclosure centre: X={UNO_CENTER_X:.1f}, Y={UNO_CENTER_Y:.1f} mm.
- The enclosure is moved to X=-36 mm and Y=20 mm, matching the annotated upper-left position.
- Only the two motor-facing mounting holes are retained.
- The other two printed mounting bosses are removed.
- The vertex placement removes nominal overlap with the servo-drive board and yaw motor.
- Rear and lower holder plates have intentional openings for rear-side components.
- Any printed support area crossing the inner hex is clipped at the outline.

## Independent lid posts
- P1–P2 and P3–P4 form left and right vertical pairs at the middle side walls.
- Four posts run vertically from Z={FLOOR_Z:.1f} to Z={POST_TOP_Z:.1f} mm.
- Each post is tied directly to the wall using a rib that follows the tapered shell.
- The posts do not use the UNO Q or hub holders as structural supports.
- Lid screw holes were moved to the post centres.

## Motor height support
- The older 82 mm motor cradle was restored and strengthened.
- ST3215 support plane: Z={MOTOR_BOTTOM_Z:.1f} mm.
- Motor proxy top: Z={MOTOR_TOP_Z:.1f} mm.
- Lid underside: Z={lid_underside_z:.1f} mm.
- Remaining motor-to-lid gap: {motor_to_lid_gap:.1f} mm.
- Side rails, two body ledges, four ear pads and floor cross-ribs are included.

## Preserved
- Symmetric 45-degree top and bottom cup shoulders.
- 82 mm cup and head height.
- 11 mm hub slot.
- One Ø20 mm round side port and one 32 x 16 mm rectangular side port.
- 10 mm lid cable slots.
- v8.36 reinforced front/back head joint.

## Printing
Use the 3MF component files so overlapping watertight support bodies are merged
reliably by the slicer.
'''
(ROOT / 'README.md').write_text(readme, encoding='utf-8')
shutil.copy2(Path(__file__), SRC / 'gen_stl_v8_43_complete.py')

zip_path = Path('/mnt/data/dumbbell_ptz_v8_43_annotated_internal_layout.zip')
if zip_path.exists():
    zip_path.unlink()
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in ROOT.rglob('*'):
        if path.is_file():
            archive.write(path, path.relative_to(ROOT.parent))

print(json.dumps({
    'zip': str(zip_path),
    'uno_center': [UNO_CENTER_X, UNO_CENTER_Y, UNO_CENTER_Z],
    'uno_mount_screws': 2,
    'uno_inner_margin_mm': validation['uno_q']['minimum_holder_margin_inside_inner_hex_mm'],
    'post_outer_margin_mm': validation['lid_posts']['minimum_post_rib_margin_inside_outer_shell_mm'],
    'motor_support_z_mm': MOTOR_BOTTOM_Z,
    'motor_lid_gap_mm': motor_to_lid_gap,
    'new_supports_inside_outer_hex': validation['interference']['all_new_support_vertices_inside_outer_hex'],
    'cup_all_components_watertight': validation['mesh']['cup_all_components_watertight'],
    'lid_all_components_watertight': validation['mesh']['lid_all_components_watertight'],
}, indent=2, ensure_ascii=False))
