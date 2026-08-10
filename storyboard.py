"""
storyboard.py
Core data model, persistence, and image rendering for the Story Board Discord bot.

Each Discord channel gets its own board, saved as data/<channel_id>.json.
A board is a tree: one root node, everything else hangs off a parent.
Nodes come in two flavors:
  - "beat"    -> an actual story/plot point   (blue box)
  - "thought" -> a note / idea / question      (amber dashed box)
"""

import json
import os
import textwrap
from dataclasses import dataclass, field, asdict
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # no display needed, we just save PNGs
import matplotlib.pyplot as plt

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

NODE_COLORS = {
    "beat": {"face": "#3B6EA5", "edge": "#1F3B57", "text": "white", "style": "-"},
    "thought": {"face": "#F2A93B", "edge": "#8A5B0F", "text": "black", "style": "--"},
}


@dataclass
class Node:
    id: int
    text: str
    type: str  # "beat" or "thought"
    parent: Optional[int]
    author: str
    children: list = field(default_factory=list)


class Board:
    """A single story board, tied to one Discord channel."""

    def __init__(self, channel_id: int, title: str = "Untitled Story"):
        self.channel_id = channel_id
        self.title = title
        self.next_id = 1
        self.nodes: dict[int, Node] = {}

    # ---------- persistence ----------

    @property
    def _path(self):
        return os.path.join(DATA_DIR, f"{self.channel_id}.json")

    def save(self):
        payload = {
            "channel_id": self.channel_id,
            "title": self.title,
            "next_id": self.next_id,
            "nodes": {str(k): asdict(v) for k, v in self.nodes.items()},
        }
        with open(self._path, "w") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load(cls, channel_id: int) -> Optional["Board"]:
        path = os.path.join(DATA_DIR, f"{channel_id}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            payload = json.load(f)
        board = cls(channel_id, payload["title"])
        board.next_id = payload["next_id"]
        board.nodes = {int(k): Node(**v) for k, v in payload["nodes"].items()}
        return board

    def delete_file(self):
        if os.path.exists(self._path):
            os.remove(self._path)

    # ---------- mutation ----------

    def start(self, title: str, author: str) -> Node:
        self.title = title
        self.next_id = 1
        self.nodes = {}
        root = Node(id=self.next_id, text=title, type="beat", parent=None, author=author)
        self.nodes[root.id] = root
        self.next_id += 1
        return root

    def add(self, parent_id: int, text: str, node_type: str, author: str) -> Node:
        if parent_id not in self.nodes:
            raise ValueError(f"No node with id {parent_id}")
        node = Node(id=self.next_id, text=text, type=node_type, parent=parent_id, author=author)
        self.nodes[node.id] = node
        self.nodes[parent_id].children.append(node.id)
        self.next_id += 1
        return node

    def edit(self, node_id: int, text: str):
        if node_id not in self.nodes:
            raise ValueError(f"No node with id {node_id}")
        self.nodes[node_id].text = text

    def remove(self, node_id: int, cascade: bool = False):
        """Remove a node. By default its children are re-attached to its parent.
        If cascade=True, the whole subtree is deleted."""
        if node_id not in self.nodes:
            raise ValueError(f"No node with id {node_id}")
        node = self.nodes[node_id]
        if node.parent is None:
            raise ValueError("Can't remove the root node — use /storyboard reset instead.")

        parent = self.nodes[node.parent]
        parent.children.remove(node_id)

        if cascade:
            stack = list(node.children)
            while stack:
                cid = stack.pop()
                stack.extend(self.nodes[cid].children)
                del self.nodes[cid]
        else:
            for cid in node.children:
                self.nodes[cid].parent = node.parent
                parent.children.append(cid)

        del self.nodes[node_id]

    # ---------- rendering ----------

    def render_image(self) -> str:
        """Lay the tree out and save a PNG. Returns the file path."""
        if not self.nodes:
            raise ValueError("Board is empty.")

        root_id = next(n.id for n in self.nodes.values() if n.parent is None)

        # Recursive post-order layout: leaves get sequential x-slots,
        # internal nodes sit centered above their children.
        positions: dict[int, tuple[float, float]] = {}
        next_x = [0.0]

        def layout(node_id: int, depth: int) -> float:
            node = self.nodes[node_id]
            if not node.children:
                x = next_x[0]
                next_x[0] += 1.0
            else:
                child_xs = [layout(cid, depth + 1) for cid in node.children]
                x = sum(child_xs) / len(child_xs)
            positions[node_id] = (x, -depth)
            return x

        layout(root_id, 0)

        max_depth = max(-y for _, y in positions.values()) + 1
        max_width = max(x for x, _ in positions.values()) + 1

        fig_w = max(8, max_width * 2.2)
        fig_h = max(5, max_depth * 1.8)
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.axis("off")

        # edges first, so boxes sit on top
        for node in self.nodes.values():
            if node.parent is not None:
                x1, y1 = positions[node.parent]
                x2, y2 = positions[node.id]
                style = NODE_COLORS[node.type]["style"]
                ax.plot([x1, x2], [y1, y2], color="#999999", linewidth=1.4,
                         linestyle=style, zorder=1)

        for node in self.nodes.values():
            x, y = positions[node.id]
            colors = NODE_COLORS[node.type]
            label = f"#{node.id} {textwrap.fill(node.text, 24)}"
            ax.text(
                x, y, label,
                ha="center", va="center",
                fontsize=9, color=colors["text"],
                zorder=2,
                bbox=dict(
                    boxstyle="round,pad=0.5",
                    facecolor=colors["face"],
                    edgecolor=colors["edge"],
                    linewidth=1.6,
                    linestyle=colors["style"],
                ),
            )

        ax.set_title(self.title, fontsize=14, fontweight="bold", pad=20)
        # legend
        ax.text(0, max_depth * -0.15 - 0.6, "", alpha=0)  # spacer, keeps layout stable
        fig.text(0.01, 0.01, "■ beat   ┄ thought", fontsize=9, color="#555555")

        fig.tight_layout()
        out_path = os.path.join(DATA_DIR, f"{self.channel_id}_render.png")
        fig.savefig(out_path, dpi=170, bbox_inches="tight")
        plt.close(fig)
        return out_path

    def as_text_tree(self) -> str:
        if not self.nodes:
            return "*(empty board)*"
        root_id = next(n.id for n in self.nodes.values() if n.parent is None)
        lines = []

        def walk(node_id, depth):
            node = self.nodes[node_id]
            marker = "📌" if node.type == "beat" else "💭"
            lines.append(f"{'  ' * depth}{marker} **#{node.id}** {node.text}  _(— {node.author})_")
            for cid in node.children:
                walk(cid, depth + 1)

        walk(root_id, 0)
        return "\n".join(lines)
