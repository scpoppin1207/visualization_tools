import numpy as np


def quaternion_to_matrix(q):
    """Convert quaternion (w,x,y,z) to 4x4 transformation matrix."""
    w, x, y, z = q[0], q[1], q[2], q[3]

    norm = np.sqrt(w * w + x * x + y * y + z * z)
    if norm > 0:
        w, x, y, z = w / norm, x / norm, y / norm, z / norm

    rot_matrix = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y), 0],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x), 0],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y), 0],
        [0, 0, 0, 1],
    ])

    return rot_matrix


def create_ellipsoid_mesh(n_theta=12, n_phi=6):
    """Create vertices, normals, and faces for a unit ellipsoid mesh."""
    vertices = []
    normals = []
    faces = []

    vertices.append([0, 0, 1])
    normals.append([0, 0, 1])

    for i in range(1, n_phi):
        phi = np.pi * i / n_phi
        for j in range(n_theta):
            theta = 2 * np.pi * j / n_theta
            x = np.sin(phi) * np.cos(theta)
            y = np.sin(phi) * np.sin(theta)
            z = np.cos(phi)
            vertices.append([x, y, z])
            normals.append([x, y, z])

    vertices.append([0, 0, -1])
    normals.append([0, 0, -1])

    for j in range(n_theta):
        next_j = (j + 1) % n_theta
        faces.append([0, j + 1, next_j + 1])

    for i in range(n_phi - 2):
        for j in range(n_theta):
            next_j = (j + 1) % n_theta
            v0 = 1 + i * n_theta + j
            v1 = 1 + i * n_theta + next_j
            v2 = 1 + (i + 1) * n_theta + next_j
            v3 = 1 + (i + 1) * n_theta + j
            faces.append([v0, v1, v2])
            faces.append([v0, v2, v3])

    bottom_vertex = len(vertices) - 1
    for j in range(n_theta):
        next_j = (j + 1) % n_theta
        v0 = 1 + (n_phi - 2) * n_theta + j
        v1 = 1 + (n_phi - 2) * n_theta + next_j
        faces.append([bottom_vertex, v1, v0])

    return (
        np.array(vertices, dtype=np.float32),
        np.array(normals, dtype=np.float32),
        np.array(faces, dtype=np.uint32),
    )


def create_ply_string(vertices, normals, faces):
    """Create a PLY format string for the mesh with normals."""
    ply_header = f"""ply
        format ascii 1.0
        element vertex {len(vertices)}
        property float x
        property float y
        property float z
        property float nx
        property float ny
        property float nz
        element face {len(faces)}
        property list uchar int vertex_indices
        end_header
    """

    vertex_lines = []
    for i in range(len(vertices)):
        v = vertices[i]
        n = normals[i]
        vertex_lines.append(
            f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f} {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}"
        )

    face_lines = [f"3 {f[0]} {f[1]} {f[2]}" for f in faces]
    return ply_header + "\n".join(vertex_lines) + "\n" + "\n".join(face_lines)
