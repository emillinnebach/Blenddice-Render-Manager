"""Compositor tools: the File Output node builder.

Driven by output_nodes.json (see CONFIG_README.md):
  - packages (e.g. AOV / DATA / CRYPTO): which passes go into which File Output node,
    plus node color and EXR format settings
  - path and file name templates with the tokens {SCENE}, {VIEW_LAYER}, {PACKAGE}
  - optional Denoise nodes in front of selected passes
  - socket renames (e.g. Image -> rgb)

Generated nodes are tagged, so building again replaces them instead of duplicating.
"""

import fnmatch

import bpy

from . import config

# Custom property used to recognise nodes we generated, and which
# Render Layers node (by name) they belong to.
TAG_SOURCE = "blenddice_source"
TAG_PACKAGE = "blenddice_package"

# Maps a Render Layers output socket's data type to the socket type enum
# expected by the (newer) NodeCompositorFileOutputItems.new() API.
SOCKET_TYPE_MAP = {
    "VALUE": "FLOAT",
    "RGBA": "RGBA",
    "VECTOR": "VECTOR",
}

# Layout (node editor units). Collapsed Denoise nodes are small; the File
# Output nodes are widened so the path stays readable.
GAP_X = 80
DENOISE_STEP_Y = 50
DENOISE_WIDTH = 140
DENOISE_COLUMN = DENOISE_WIDTH + 70
OUTPUT_GAP_Y = 80
DEFAULT_NODE_WIDTH = 400


# ---------------------------------------------------------------------------
# Pure helpers (no node creation - easy to reason about / test)
# ---------------------------------------------------------------------------

def hex_to_rgb(hex_code):
    """Convert a '#RRGGBB' string to a (r, g, b) float tuple in [0, 1]."""
    hex_code = hex_code.lstrip("#")
    return tuple(int(hex_code[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def fill_template(template, scene_name, view_layer_name, package_name):
    return (template.replace("{SCENE}", scene_name)
                    .replace("{VIEW_LAYER}", view_layer_name)
                    .replace("{PACKAGE}", package_name))


def clean_directory(path):
    """Forward slashes only, and no trailing slash (the shot submitter adds its own
    before the frame prefix, so a trailing one would give a double slash)."""
    path = path.replace("\\", "/")
    stripped = path.rstrip("/")
    return stripped if stripped else "//"


def assign_package(socket_name, packages):
    """The package a pass belongs to. Specific patterns win over the catch-all
    '*', whatever the list order; within each group the list order decides."""
    lowered = socket_name.lower()
    catch_all = None
    for package in packages:
        for pattern in package["match"]:
            if pattern == "*":
                if catch_all is None:
                    catch_all = package
            elif fnmatch.fnmatchcase(lowered, pattern.lower()):
                return package
    return catch_all


def plan_denoise(denoise_cfg, outputs):
    """Which passes get a Denoise node. Returns {pass_name: (pass, normal, albedo)}.

    A pass with an albedo entry (e.g. Diffuse Direct -> Diffuse Color) is only
    denoised if both its Color pass and Normal are enabled, otherwise it passes
    through untouched. A pass with null (e.g. Volume Direct) is denoised from the
    image itself, plus Normal if that pass is enabled."""
    plan = {}
    if not denoise_cfg or not denoise_cfg.get("enabled", True):
        return plan

    by_name = {o.name: o for o in outputs}
    normal = by_name.get("Normal")
    for pass_name, albedo_name in denoise_cfg.get("passes", {}).items():
        if pass_name.startswith("_"):
            continue
        source = by_name.get(pass_name)
        if source is None:
            continue
        if albedo_name:
            albedo = by_name.get(albedo_name)
            if albedo is None or normal is None:
                continue
            plan[pass_name] = (source, normal, albedo)
        else:
            plan[pass_name] = (source, normal, None)
    return plan


def remove_generated(tree, rl_node):
    """Delete the nodes we generated earlier for this Render Layers node."""
    stale = [n for n in tree.nodes if n.get(TAG_SOURCE) == rl_node.name]
    for node in stale:
        tree.nodes.remove(node)
    return len(stale)


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class BLENDDICE_OT_build_output_node(bpy.types.Operator):
    """Build File Output node(s) wired to the selected Render Layers node (replaces earlier generated nodes)"""
    bl_idname = "blenddice.build_output_node"
    bl_label = "Build Output Node"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        space = context.space_data
        if getattr(space, "tree_type", None) != 'CompositorNodeTree':
            return False
        return space.node_tree is not None

    def execute(self, context):
        cfg = config.get_output_nodes()
        if cfg is None:
            self.report({'ERROR'}, "output_nodes.json is missing or invalid - see Add-on Preferences")
            return {'CANCELLED'}

        tree = context.space_data.node_tree
        rl_nodes = [n for n in tree.nodes if n.select and n.bl_idname == 'CompositorNodeRLayers']
        if not rl_nodes:
            self.report({'WARNING'}, "Select a Render Layers node first")
            return {'CANCELLED'}

        built = 0
        replaced = 0
        notes = []
        for rl_node in rl_nodes:
            result = self._build_for_node(tree, rl_node, cfg)
            if result is None:
                continue
            built += 1
            replaced += result["replaced"]
            notes.extend(result["notes"])

        if built == 0:
            self.report({'WARNING'}, "Could not resolve a scene/view layer for the selected node(s)")
            return {'CANCELLED'}

        message = f"Built output node(s) for {built} Render Layers node(s)"
        if replaced:
            message += f", replaced {replaced} earlier generated node(s)"
        if notes:
            self.report({'WARNING'}, message + " - " + "; ".join(notes))
        else:
            self.report({'INFO'}, message)
        return {'FINISHED'}

    # -- core build logic ----------------------------------------------

    def _build_for_node(self, tree, rl_node, cfg):
        scene = rl_node.scene or bpy.context.scene
        view_layer = scene.view_layers.get(rl_node.layer) if scene else None
        if scene is None or view_layer is None:
            return None

        notes = []
        replaced = remove_generated(tree, rl_node)

        packages = cfg["packages"]
        rename = cfg.get("rename_sockets", {})
        outputs = [o for o in rl_node.outputs if o.enabled]
        plan = plan_denoise(cfg.get("denoise"), outputs)

        grouped = {package["name"]: [] for package in packages}
        unassigned = []
        for output in outputs:
            package = assign_package(output.name, packages)
            if package is None:
                unassigned.append(output.name)
            else:
                grouped[package["name"]].append(output)
        if unassigned:
            notes.append("not written (no matching package): " + ", ".join(unassigned))

        # Layout: right of the Render Layers node, from its top edge downward.
        # Collapsed Denoise nodes in one narrow column, File Output nodes next to it.
        x_start = rl_node.location.x + rl_node.width + GAP_X
        y_top = rl_node.location.y
        denoise_count = sum(
            1 for package in packages for o in grouped[package["name"]] if o.name in plan
        )
        output_x = x_start + (DENOISE_COLUMN if denoise_count else 0)
        node_width = cfg.get("node_width", DEFAULT_NODE_WIDTH)

        denoise_index = 0
        output_y = y_top
        for package in packages:
            members = grouped[package["name"]]
            if not members:
                continue

            out_node = self._create_output_node(
                tree, rl_node, package, scene.name, view_layer.name, cfg, output_x, output_y, node_width, notes,
            )

            for source in members:
                socket_name = rename.get(source.name, source.name)
                dst = self._add_output_socket(out_node, socket_name, source.type)

                if source.name in plan:
                    _src, normal, albedo = plan[source.name]
                    denoise = self._create_denoise_node(
                        tree, rl_node, source, normal, albedo, x_start, y_top - denoise_index * DENOISE_STEP_Y,
                    )
                    denoise_index += 1
                    tree.links.new(denoise.outputs["Image"], dst)
                else:
                    tree.links.new(source, dst)

            height = out_node.dimensions.y if out_node.dimensions.y > 1 else 260 + 24 * len(members)
            output_y -= height + OUTPUT_GAP_Y

        return {"replaced": replaced, "notes": notes}

    # -- node construction ----------------------------------------------

    def _create_output_node(self, tree, rl_node, package, scene_name, vl_name, cfg, x, y, width, notes):
        node = tree.nodes.new("CompositorNodeOutputFile")
        node.label = f"Output {vl_name} ({package['name']})"
        node.location = (x, y)
        node.width = width
        if package.get("color"):
            node.use_custom_color = True
            node.color = hex_to_rgb(package["color"])

        node[TAG_SOURCE] = rl_node.name
        node[TAG_PACKAGE] = package["name"]

        directory = clean_directory(fill_template(cfg["directory"], scene_name, vl_name, package["name"]))
        file_name = fill_template(cfg["file_name"], scene_name, vl_name, package["name"])

        if hasattr(node, "directory"):
            # Newer (5.x) file-output-items based API.
            node.directory = directory
            node.file_name = file_name
        else:
            # Legacy base_path/file_slots based API.
            node.base_path = f"{directory}/{file_name}"

        fmt = package.get("format", {})
        keys = [k for k in fmt if not k.startswith("_")]
        keys.sort(key=lambda k: 0 if k == "file_format" else 1)   # format first, the rest depends on it
        for key in keys:
            if not hasattr(node.format, key):
                notes.append(f"{package['name']}: format.{key} not available")
                continue
            try:
                setattr(node.format, key, fmt[key])
            except Exception:
                notes.append(f"{package['name']}: format.{key} could not be set")

        if package.get("save_as_render") is not None and hasattr(node, "save_as_render"):
            node.save_as_render = bool(package["save_as_render"])

        self._clear_default_sockets(node)
        return node

    @staticmethod
    def _create_denoise_node(tree, rl_node, source, normal, albedo, x, y):
        denoise = tree.nodes.new("CompositorNodeDenoise")
        denoise.label = f"Denoise {source.name}"
        denoise.location = (x, y)
        denoise.width = DENOISE_WIDTH
        denoise.hide = True    # collapsed: keeps the tree compact
        denoise[TAG_SOURCE] = rl_node.name

        tree.links.new(source, denoise.inputs["Image"])
        if normal is not None:
            tree.links.new(normal, denoise.inputs["Normal"])
        if albedo is not None:
            tree.links.new(albedo, denoise.inputs["Albedo"])
        return denoise

    @staticmethod
    def _clear_default_sockets(node):
        if hasattr(node, "file_output_items"):
            items = node.file_output_items
            while len(items) > 0:
                items.remove(items[0])
        else:
            node.file_slots.clear()

    @staticmethod
    def _add_output_socket(node, name, socket_data_type):
        if hasattr(node, "file_output_items"):
            item_type = SOCKET_TYPE_MAP.get(socket_data_type, "RGBA")
            item = node.file_output_items.new(item_type, name)
            return node.inputs[item.name]
        return node.file_slots.new(name)


classes = (
    BLENDDICE_OT_build_output_node,
)
