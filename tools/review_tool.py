#!/usr/bin/env python3
"""Interactive Detection-to-Panoptic review tool for the Day 10 lab."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, ttk
from tkinter import LEFT, RIGHT, END, HORIZONTAL, VERTICAL, NW
from tkinter import messagebox
from tkinter import Canvas, Checkbutton, Entry, Frame, Label, Listbox, Radiobutton, Scrollbar

from PIL import Image, ImageDraw, ImageTk

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pngutil


SEMANTIC_TYPES = ("class_swap", "category_swap", "bbox_drift", "missing_box", "instance_merge")
HIGHLIGHT_COLORS = {
    5065804: (255, 32, 96),
    8092282: (0, 220, 255),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_candidates(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = load_json(path)
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("candidates", [])
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def candidate_image(row: dict) -> str:
    value = row.get("image") or row.get("target") or row.get("image_id") or ""
    return str(value).strip().replace(".jpg", "").replace(".png", "")


def candidate_type(row: dict) -> str:
    return str(row.get("type") or row.get("kind") or "").strip()


def segment_statistics(width: int, height: int, pixels: bytes) -> dict[int, dict]:
    if len(pixels) != width * height * 3:
        raise ValueError("RGB mask buffer has the wrong size")
    stats: dict[int, dict] = {}
    for pixel_index in range(0, len(pixels), 3):
        segment_id = pngutil.segment_id(pixels, pixel_index)
        if segment_id == 0:
            continue
        x = (pixel_index // 3) % width
        y = (pixel_index // 3) // width
        item = stats.get(segment_id)
        if item is None:
            stats[segment_id] = {
                "area": 1,
                "min_x": x,
                "min_y": y,
                "max_x": x,
                "max_y": y,
                "sum_x": x,
                "sum_y": y,
            }
        else:
            item["area"] += 1
            item["min_x"] = min(item["min_x"], x)
            item["min_y"] = min(item["min_y"], y)
            item["max_x"] = max(item["max_x"], x)
            item["max_y"] = max(item["max_y"], y)
            item["sum_x"] += x
            item["sum_y"] += y

    for item in stats.values():
        item["bbox"] = (
            item["min_x"],
            item["min_y"],
            item["max_x"] - item["min_x"] + 1,
            item["max_y"] - item["min_y"] + 1,
        )
        item["centroid"] = (
            item["sum_x"] / item["area"],
            item["sum_y"] / item["area"],
        )
    return stats


def segment_color(segment_id: int) -> tuple[int, int, int]:
    if segment_id in HIGHLIGHT_COLORS:
        return HIGHLIGHT_COLORS[segment_id]
    return (
        (segment_id * 37) % 256,
        (segment_id * 67) % 256,
        (segment_id * 97) % 256,
    )


def draw_segment_overlay(
    image: Image.Image,
    pixels: bytes,
    width: int,
    height: int,
    stats: dict[int, dict],
    visible_ids: set[int],
    show_borders: bool,
    show_ids: bool,
) -> Image.Image:
    if image.size != (width, height) or len(pixels) != width * height * 3:
        raise ValueError("image and RGB mask dimensions do not match")

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_pixels = overlay.load()
    decoded_ids = [pngutil.segment_id(pixels, index) for index in range(0, len(pixels), 3)]

    for pixel_index, segment_id in enumerate(decoded_ids):
        if segment_id in visible_ids:
            x = pixel_index % width
            y = pixel_index // width
            overlay_pixels[x, y] = (*segment_color(segment_id), 112)

    result = Image.alpha_composite(image.convert("RGBA"), overlay)
    if show_borders:
        border_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        border_pixels = border_layer.load()
        for pixel_index, segment_id in enumerate(decoded_ids):
            if segment_id not in visible_ids:
                continue
            x = pixel_index % width
            y = pixel_index // width
            neighbors = (
                (x - 1, y),
                (x + 1, y),
                (x, y - 1),
                (x, y + 1),
            )
            for nx, ny in neighbors:
                if (
                    nx < 0
                    or ny < 0
                    or nx >= width
                    or ny >= height
                    or decoded_ids[ny * width + nx] != segment_id
                ):
                    border_pixels[x, y] = (*segment_color(segment_id), 255)
                    break
        result = Image.alpha_composite(result, border_layer)

    if show_ids:
        draw = ImageDraw.Draw(result)
        for segment_id in sorted(visible_ids):
            item = stats.get(segment_id)
            if not item:
                continue
            cx, cy = item["centroid"]
            color = segment_color(segment_id)
            label = str(segment_id)
            x = round(cx)
            y = round(cy)
            text_box = draw.textbbox((x, y), label)
            padding = 3
            draw.rectangle(
                (
                    text_box[0] - padding,
                    text_box[1] - padding,
                    text_box[2] + padding,
                    text_box[3] + padding,
                ),
                fill=(*color, 255),
            )
            draw.text((x, y), label, fill=(255, 255, 255, 255))
    return result.convert("RGB")


class ReviewTool:
    def __init__(self, root: Tk, delivery: Path, candidates_path: Path | None, review_path: Path) -> None:
        self.root = root
        self.delivery = delivery
        self.candidates_path = candidates_path
        self.review_path = review_path
        self.panoptic = load_json(delivery / "panoptic.json")
        self.categories = {int(c["id"]): c for c in self.panoptic["categories"]}
        self.panoptic_images = {str(i["id"]).zfill(12): i for i in self.panoptic["images"]}
        self.annotations = {}
        for annotation in self.panoptic["annotations"]:
            image_id = str(annotation["image_id"]).zfill(12)
            self.annotations[image_id] = annotation

        self.class_names = {}
        for line in (delivery / "classes.txt").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                class_id, name = line.split(maxsplit=1)
                self.class_names[int(class_id)] = name
        self.panoptic_name_to_category = {
            str(category["name"]): int(category["id"])
            for category in self.panoptic["categories"]
        }
        self.category_name_to_detection = {
            name: class_id for class_id, name in self.class_names.items()
        }

        manifest = load_json(delivery / "manifest.json")
        manifest_ids = set(str(image_id).zfill(12) for image_id in manifest["items"])
        file_ids = {
            p.stem for p in (delivery / "images").glob("*") if p.is_file()
        } | {
            p.stem for p in (delivery / "labels").glob("*") if p.is_file()
        } | {
            p.stem for p in (delivery / "masks").glob("*") if p.is_file()
        }
        self.image_ids = sorted(manifest_ids | file_ids)
        self.current_index = 0
        self.photo = None
        self.rendered_size = (1, 1)
        self.mask_cache: tuple[str, int, int, bytearray, dict[int, dict]] | None = None
        self.segment_vars: dict[int, BooleanVar] = {}
        self.segment_visibility_by_image: dict[str, dict[int, bool]] = {}

        self.candidates = parse_candidates(candidates_path)
        self.candidate_filter_enabled = BooleanVar(value=True)
        self.show_detection = BooleanVar(value=True)
        self.show_mask = BooleanVar(value=True)
        self.show_borders = BooleanVar(value=True)
        self.show_segment_ids = BooleanVar(value=True)
        self.show_all_classes = BooleanVar(value=False)
        self.class_filter = StringVar(value="All")
        self.candidate_type = StringVar(value=SEMANTIC_TYPES[0])
        self.verdict = StringVar(value="confirmed")
        self.zoom = StringVar(value="Fit")

        self.build_ui()
        self.refresh_list()
        self.select_current()

    def build_ui(self) -> None:
        self.root.title("Day 10 - Detection / Panoptic Review")
        self.root.geometry("1440x900")

        left = Frame(self.root, width=260)
        left.pack(side=LEFT, fill="y")

        Label(left, text="Image search").pack(anchor=NW, padx=8, pady=(8, 2))
        self.search_entry = Entry(left)
        self.search_entry.pack(fill="x", padx=8)
        self.search_entry.bind("<KeyRelease>", lambda _event: self.refresh_list())

        Label(left, text="Images").pack(anchor=NW, padx=8, pady=(8, 2))
        list_frame = Frame(left)
        list_frame.pack(fill="both", expand=True, padx=8)
        self.image_list = Listbox(list_frame, exportselection=False)
        list_scroll = Scrollbar(list_frame, orient=VERTICAL, command=self.image_list.yview)
        self.image_list.configure(yscrollcommand=list_scroll.set)
        self.image_list.pack(side=LEFT, fill="both", expand=True)
        list_scroll.pack(side=RIGHT, fill="y")
        self.image_list.bind("<<ListboxSelect>>", lambda _event: self.list_selection())

        Checkbutton(
            left,
            text="Candidates only",
            variable=self.candidate_filter_enabled,
            command=self.refresh_list,
        ).pack(anchor=NW, padx=8, pady=(8, 2))

        nav = Frame(left)
        nav.pack(fill="x", padx=8, pady=8)
        ttk.Button(nav, text="Previous", command=lambda: self.move_image(-1)).pack(side=LEFT)
        ttk.Button(nav, text="Next", command=lambda: self.move_image(1)).pack(side=RIGHT)

        center = Frame(self.root)
        center.pack(side=LEFT, fill="both", expand=True)
        controls = Frame(center)
        controls.pack(fill="x")
        Checkbutton(controls, text="Detection", variable=self.show_detection, command=self.render).pack(side=LEFT)
        Checkbutton(controls, text="Panoptic mask", variable=self.show_mask, command=self.render).pack(side=LEFT)
        Checkbutton(controls, text="Segment borders", variable=self.show_borders, command=self.render).pack(side=LEFT)
        Checkbutton(controls, text="All class filter", variable=self.show_all_classes, command=self.render).pack(side=LEFT)

        ttk.Label(controls, text="Class:").pack(side=LEFT, padx=(8, 2))
        class_names = ["All"] + [f"{cid}: {name}" for cid, name in sorted(self.class_names.items())]
        self.class_combo = ttk.Combobox(controls, textvariable=self.class_filter, values=class_names, width=24)
        self.class_combo.pack(side=LEFT)
        self.class_combo.bind("<<ComboboxSelected>>", lambda _event: self.render())

        canvas_frame = Frame(center)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = Canvas(canvas_frame, bg="#202020")
        h_scroll = Scrollbar(canvas_frame, orient=HORIZONTAL, command=self.canvas.xview)
        v_scroll = Scrollbar(canvas_frame, orient=VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(side="bottom", fill="x")
        v_scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        right = Frame(self.root, width=380)
        right.pack(side=RIGHT, fill="y")
        ttk.Button(right, text="Save review row", command=self.save_review).pack(
            side="bottom",
            fill="x",
            padx=8,
            pady=8,
        )

        review = Frame(right)
        review.pack(fill="x", padx=8, pady=(8, 4))
        Label(review, text="Review candidate").pack(anchor=NW)
        ttk.Label(review, text="Verdict").pack(anchor=NW)
        Radiobutton(review, text="confirmed", variable=self.verdict, value="confirmed").pack(anchor=NW)
        Radiobutton(review, text="rejected", variable=self.verdict, value="rejected").pack(anchor=NW)
        ttk.Label(review, text="Semantic type").pack(anchor=NW)
        ttk.Combobox(
            review,
            textvariable=self.candidate_type,
            values=SEMANTIC_TYPES,
            state="readonly",
        ).pack(fill="x")
        ttk.Label(review, text="Note (at least 20 characters)").pack(anchor=NW)
        self.note_entry = __import__("tkinter").Text(review, width=38, height=3)
        self.note_entry.pack(fill="x")

        Label(right, text="Panoptic segments (toggle each ID)").pack(anchor=NW, padx=8, pady=(4, 2))
        segment_actions = Frame(right)
        segment_actions.pack(fill="x", padx=8)
        ttk.Button(segment_actions, text="All", command=lambda: self.set_all_segments(True)).pack(side=LEFT)
        ttk.Button(segment_actions, text="None", command=lambda: self.set_all_segments(False)).pack(side=LEFT, padx=4)
        Checkbutton(
            segment_actions,
            text="Show IDs on mask",
            variable=self.show_segment_ids,
            command=self.render,
        ).pack(side=LEFT, padx=8)

        segment_list_frame = Frame(right, height=100)
        segment_list_frame.pack(fill="x", padx=8, pady=(2, 4))
        segment_list_frame.pack_propagate(False)
        self.segment_list_canvas = Canvas(segment_list_frame, highlightthickness=0)
        segment_scroll = Scrollbar(
            segment_list_frame,
            orient=VERTICAL,
            command=self.segment_list_canvas.yview,
        )
        self.segment_list_canvas.configure(yscrollcommand=segment_scroll.set)
        segment_scroll.pack(side=RIGHT, fill="y")
        self.segment_list_canvas.pack(side=LEFT, fill="both", expand=True)
        self.segment_rows = Frame(self.segment_list_canvas)
        self.segment_rows_window = self.segment_list_canvas.create_window(
            (0, 0),
            window=self.segment_rows,
            anchor=NW,
        )
        self.segment_rows.bind(
            "<Configure>",
            lambda _event: self.segment_list_canvas.configure(
                scrollregion=self.segment_list_canvas.bbox("all")
            ),
        )
        self.segment_list_canvas.bind(
            "<Configure>",
            lambda event: self.segment_list_canvas.itemconfigure(
                self.segment_rows_window,
                width=event.width,
            ),
        )

        Label(right, text="Objects and segment statistics").pack(anchor=NW, padx=8, pady=(4, 2))
        self.objects_text = __import__("tkinter").Text(right, width=48, height=7)
        self.objects_text.pack(fill="x", padx=8)

        candidate_label = Label(
            right,
            text=f"Candidates: {len(self.candidates)}",
        )
        candidate_label.pack(anchor=NW, padx=8)
        self.candidate_label = candidate_label
        if not self.candidates:
            Label(
                right,
                text="Waiting for candidates.json.\nNo candidate verdict is allowed.",
                fg="#9a3b25",
                justify="left",
            ).pack(anchor=NW, padx=8, pady=8)

    def refresh_list(self) -> None:
        query = self.search_entry.get().strip()
        candidate_ids = {candidate_image(row) for row in self.candidates}
        ids = self.image_ids
        if self.candidate_filter_enabled.get():
            ids = [image_id for image_id in ids if image_id in candidate_ids]
        if query:
            ids = [image_id for image_id in ids if query in image_id]

        self.image_list.delete(0, END)
        for image_id in ids:
            self.image_list.insert(END, image_id)
        if ids:
            self.image_list.selection_clear(0, END)
            try:
                position = ids.index(self.image_ids[self.current_index])
                self.image_list.selection_set(position)
                self.image_list.see(position)
            except (ValueError, IndexError):
                self.image_list.selection_set(0)

    def visible_ids(self) -> list[str]:
        ids = list(self.image_list.get(0, END))
        return ids

    def list_selection(self) -> None:
        selection = self.image_list.curselection()
        if not selection:
            return
        image_id = self.image_list.get(selection[0])
        if image_id in self.image_ids:
            self.current_index = self.image_ids.index(image_id)
            self.select_current()

    def move_image(self, delta: int) -> None:
        ids = self.visible_ids()
        if not ids:
            ids = self.image_ids
        if not ids:
            return
        current_id = self.current_image_id()
        if current_id in ids:
            position = ids.index(current_id)
        else:
            position = 0
        position = max(0, min(len(ids) - 1, position + delta))
        selected_id = ids[position]
        self.current_index = self.image_ids.index(selected_id)
        self.refresh_list()
        self.select_current()

    def current_image_id(self) -> str:
        if not self.image_ids:
            return ""
        return self.image_ids[self.current_index]

    def load_detection(self, image_id: str) -> list[tuple[int, float, float, float, float]]:
        label_path = self.delivery / "labels" / f"{image_id}.txt"
        if not label_path.exists():
            return []
        rows = []
        for line in label_path.read_text(encoding="utf-8").splitlines():
            fields = line.strip().split()
            if len(fields) != 5:
                continue
            try:
                cid = int(fields[0])
                cx, cy, width, height = map(float, fields[1:])
            except ValueError:
                continue
            rows.append((cid, cx, cy, width, height))
        return rows

    def in_class_filter(self, class_name: str) -> bool:
        if not self.show_all_classes.get():
            return True
        selected = self.class_filter.get()
        if selected == "All":
            return True
        selected_name = selected.split(":", 1)[1].strip()
        return class_name == selected_name

    def select_current(self) -> None:
        if not self.image_ids:
            return
        image_id = self.current_image_id()
        self.root.title(f"Day 10 Review - {image_id}")
        self.refresh_segment_controls(image_id)
        self.render()
        for candidate in self.candidates:
            if candidate_image(candidate) == image_id:
                kind = candidate_type(candidate)
                if kind in SEMANTIC_TYPES:
                    self.candidate_type.set(kind)
                elif kind == "class_or_category_swap":
                    self.candidate_type.set("class_swap")

    def get_mask_data(
        self,
        image_id: str,
    ) -> tuple[int, int, bytearray, dict[int, dict]] | None:
        if self.mask_cache and self.mask_cache[0] == image_id:
            _, width, height, pixels, stats = self.mask_cache
            return width, height, pixels, stats
        mask_path = self.delivery / "masks" / f"{image_id}.png"
        if not mask_path.exists():
            self.mask_cache = None
            return None
        width, height, pixels = pngutil.read_rgb(mask_path)
        stats = segment_statistics(width, height, pixels)
        self.mask_cache = (image_id, width, height, pixels, stats)
        return width, height, pixels, stats

    def refresh_segment_controls(self, image_id: str) -> None:
        previous = self.segment_visibility_by_image.setdefault(image_id, {})
        for segment_id, variable in self.segment_vars.items():
            previous[segment_id] = variable.get()
        for child in self.segment_rows.winfo_children():
            child.destroy()
        self.segment_vars = {}

        mask_data = self.get_mask_data(image_id)
        if mask_data is None:
            Label(self.segment_rows, text="No mask for this image").pack(anchor=NW)
            return
        _width, _height, _pixels, stats = mask_data
        annotation = self.annotations.get(image_id, {})
        segments = {
            int(segment["id"]): segment
            for segment in annotation.get("segments_info", [])
        }
        for segment_id in sorted(stats):
            segment = segments.get(segment_id, {})
            category_id = int(segment.get("category_id", -1))
            category = self.categories.get(category_id)
            name = category["name"] if category else f"unknown category {category_id}"
            variable = BooleanVar(value=previous.get(segment_id, True))
            self.segment_vars[segment_id] = variable
            color = "#%02x%02x%02x" % segment_color(segment_id)
            row = Frame(self.segment_rows)
            row.pack(fill="x", anchor=NW)
            Checkbutton(
                row,
                text=f"{segment_id}  {name}",
                variable=variable,
                anchor=NW,
                command=lambda sid=segment_id: self.segment_visibility_changed(sid),
            ).pack(side=LEFT, fill="x", expand=True)
            Label(row, text="   ", bg=color, relief="solid", borderwidth=1).pack(side=RIGHT, padx=4)

    def segment_visibility_changed(self, segment_id: int) -> None:
        image_id = self.current_image_id()
        self.segment_visibility_by_image.setdefault(image_id, {})[segment_id] = (
            self.segment_vars[segment_id].get()
        )
        self.render()

    def set_all_segments(self, visible: bool) -> None:
        image_id = self.current_image_id()
        visibility = self.segment_visibility_by_image.setdefault(image_id, {})
        for segment_id, variable in self.segment_vars.items():
            variable.set(visible)
            visibility[segment_id] = visible
        self.render()

    def visible_segment_ids(self) -> set[int]:
        return {
            segment_id
            for segment_id, variable in self.segment_vars.items()
            if variable.get()
        }

    def build_overlay(self, image_id: str) -> tuple[Image.Image, list[str]]:
        image_path = self.delivery / "images" / f"{image_id}.jpg"
        if not image_path.exists():
            image_path = self.delivery / "images" / f"{image_id}.png"
        if image_path.exists():
            image = Image.open(image_path).convert("RGB")
        else:
            pano = self.panoptic_images.get(image_id)
            size = (pano["width"], pano["height"]) if pano else (640, 480)
            image = Image.new("RGB", size, "#777777")

        width, height = image.size
        object_lines = []
        mask_data = self.get_mask_data(image_id)
        mask_stats = {}
        if mask_data:
            mask_width, mask_height, pixels, mask_stats = mask_data
            if (mask_width, mask_height) == (width, height):
                if self.show_mask.get():
                    image = draw_segment_overlay(
                        image,
                        pixels,
                        mask_width,
                        mask_height,
                        mask_stats,
                        self.visible_segment_ids(),
                        self.show_borders.get(),
                        self.show_segment_ids.get(),
                    )
            else:
                object_lines.append(
                    f"MASK SIZE MISMATCH: mask={mask_width}x{mask_height}, image={width}x{height}"
                )
        draw = ImageDraw.Draw(image, "RGBA")
        if self.show_detection.get():
            for cid, cx, cy, box_width, box_height in self.load_detection(image_id):
                name = self.class_names.get(cid, f"unknown_{cid}")
                if not self.in_class_filter(name):
                    continue
                x1 = (cx - box_width / 2) * width
                y1 = (cy - box_height / 2) * height
                x2 = (cx + box_width / 2) * width
                y2 = (cy + box_height / 2) * height
                draw.rectangle((x1, y1, x2, y2), outline=(255, 64, 64, 255), width=3)
                draw.rectangle((x1, y1 - 18, x1 + max(55, len(name) * 8), y1), fill=(180, 0, 0, 220))
                draw.text((x1 + 3, y1 - 17), name, fill=(255, 255, 255, 255))

        annotation = self.annotations.get(image_id)
        if annotation:
            for segment in annotation.get("segments_info", []):
                sid = int(segment["id"])
                cid = int(segment["category_id"])
                category = self.categories.get(cid)
                name = category["name"] if category else f"unknown_category_{cid}"
                if not self.in_class_filter(name):
                    continue
                stats = mask_stats.get(sid, {})
                actual_area = stats.get("area", 0)
                actual_bbox = stats.get("bbox", "missing")
                centroid = stats.get("centroid", "missing")
                object_lines.append(
                    f"PANOPTIC id={sid} category={cid} {name} "
                    f"area={actual_area}/{segment.get('area')} crowd={segment.get('iscrowd', 0)} "
                    f"bbox_mask={actual_bbox} bbox_json={segment.get('bbox')} centroid={centroid}"
                )

        detection_count = len(self.load_detection(image_id))
        panoptic_count = len(annotation.get("segments_info", [])) if annotation else 0
        object_lines.insert(0, f"Detection boxes: {detection_count}")
        object_lines.insert(1, f"Panoptic segments: {panoptic_count}")
        if not (self.delivery / "images" / f"{image_id}.jpg").exists():
            object_lines.insert(0, "SOURCE IMAGE MISSING")
        return image.convert("RGB"), object_lines

    def render(self) -> None:
        if not self.image_ids:
            return
        image_id = self.current_image_id()
        rendered, object_lines = self.build_overlay(image_id)
        canvas_width = max(320, self.canvas.winfo_width())
        canvas_height = max(240, self.canvas.winfo_height())
        scale = min(canvas_width / rendered.width, canvas_height / rendered.height)
        scale = min(1.0, scale)
        new_size = (max(1, int(rendered.width * scale)), max(1, int(rendered.height * scale)))
        rendered = rendered.resize(new_size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(rendered)
        self.rendered_size = new_size
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=NW, image=self.photo)
        self.canvas.configure(scrollregion=(0, 0, new_size[0], new_size[1]))

        self.objects_text.delete("1.0", END)
        candidate_rows = [
            row for row in self.candidates
            if candidate_image(row) == image_id
        ]
        if candidate_rows:
            self.objects_text.insert(END, "CANDIDATES:\n")
            for row in candidate_rows:
                self.objects_text.insert(
                    END,
                    f"- {candidate_type(row)}: {json.dumps(row, ensure_ascii=False)}\n",
                )
            self.objects_text.insert(END, "\n")
        self.objects_text.insert(END, "\n".join(object_lines))

    def save_review(self) -> None:
        if not self.candidates:
            messagebox.showwarning("Candidates unavailable", "No candidates.json loaded; no review row is allowed.")
            return
        image_id = self.current_image_id()
        matching = [
            row for row in self.candidates
            if candidate_image(row) == image_id
        ]
        if not matching:
            messagebox.showwarning("No candidate", "This image has no candidate row.")
            return
        kind = self.candidate_type.get()
        note = self.note_entry.get("1.0", END).strip()
        if len(note) < 20:
            messagebox.showwarning("Review note", "Note must describe the image and contain at least 20 characters.")
            return
        verdict = self.verdict.get()
        if verdict not in ("confirmed", "rejected"):
            messagebox.showwarning("Review verdict", "Verdict must be confirmed or rejected.")
            return

        existing = []
        if self.review_path.exists():
            with self.review_path.open("r", encoding="utf-8", newline="") as handle:
                existing = list(csv.DictReader(handle))
        duplicate = any(row.get("image") == image_id and row.get("type") == kind for row in existing)
        if duplicate:
            messagebox.showwarning("Duplicate candidate", "A review row already exists for this image and type.")
            return
        with self.review_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["image", "type", "verdict", "note"])
            if not existing:
                writer.writeheader()
            writer.writerow({"image": image_id, "type": kind, "verdict": verdict, "note": note})
        messagebox.showinfo("Saved", f"Saved {image_id},{kind},{verdict}")
        self.note_entry.delete("1.0", END)


def check_delivery(delivery: Path) -> int:
    panoptic = load_json(delivery / "panoptic.json")
    category_ids = {int(category["id"]) for category in panoptic["categories"]}
    panoptic_images = {str(image["id"]).zfill(12): image for image in panoptic["images"]}
    annotations = {
        str(annotation["image_id"]).zfill(12): annotation
        for annotation in panoptic["annotations"]
    }
    images = {p.stem for p in (delivery / "images").glob("*") if p.is_file()}
    labels = {p.stem for p in (delivery / "labels").glob("*") if p.is_file()}
    masks = {p.stem for p in (delivery / "masks").glob("*") if p.is_file()}
    manifest = load_json(delivery / "manifest.json")
    manifest_ids = {str(image_id).zfill(12) for image_id in manifest["items"]}

    print(f"delivery={delivery}")
    print(f"images={len(images)} labels={len(labels)} masks={len(masks)} panoptic={len(panoptic_images)}")
    print("missing_images=" + ", ".join(sorted(labels & masks - images)))
    print("labels_without_masks=" + ", ".join(sorted(labels - masks)))
    print("masks_without_labels=" + ", ".join(sorted(masks - labels)))
    print("manifest_ids_missing_files=" + ", ".join(sorted(manifest_ids - images)))

    invalid_categories = []
    area_mismatches = []
    size_mismatches = []
    missing_segment_ids = []
    masks_without_background = []
    mode_errors = []

    for image_id in sorted(masks):
        mask_path = delivery / "masks" / f"{image_id}.png"
        try:
            width, height, pixels = pngutil.read_rgb(mask_path)
        except Exception as exc:
            mode_errors.append((image_id, str(exc)))
            continue
        counts = {}
        for index in range(0, len(pixels), 3):
            sid = pngutil.segment_id(pixels, index)
            counts[sid] = counts.get(sid, 0) + 1
        if 0 not in counts:
            masks_without_background.append(image_id)
        panoptic_image = panoptic_images.get(image_id)
        if panoptic_image and (width, height) != (
            panoptic_image["width"],
            panoptic_image["height"],
        ):
            size_mismatches.append((image_id, (width, height)))
        annotation = annotations.get(image_id)
        known_ids = {int(segment["id"]) for segment in annotation.get("segments_info", [])} if annotation else set()
        missing_segment_ids.extend(
            (image_id, sid)
            for sid in sorted(set(counts) - known_ids - {0})
        )
        if annotation:
            for segment in annotation["segments_info"]:
                cid = int(segment["category_id"])
                if cid not in category_ids:
                    invalid_categories.append((image_id, int(segment["id"]), cid))
                sid = int(segment["id"])
                if counts.get(sid, 0) != int(segment["area"]):
                    area_mismatches.append(
                        (image_id, sid, counts.get(sid, 0), int(segment["area"]))
                    )

    print("mask_mode_errors=" + json.dumps(mode_errors, ensure_ascii=False))
    print("size_mismatches=" + json.dumps(size_mismatches))
    print("masks_without_background_id0=" + json.dumps(masks_without_background))
    print("missing_segment_ids=" + json.dumps(missing_segment_ids))
    print("invalid_category_ids=" + json.dumps(invalid_categories))
    print("area_mismatches=" + json.dumps(area_mismatches))
    return 0


def print_segment_statistics(delivery: Path, image_id: str, segment_ids: list[int]) -> int:
    mask_path = delivery / "masks" / f"{image_id}.png"
    if not mask_path.exists():
        print(f"mask not found: {mask_path}", file=sys.stderr)
        return 2
    panoptic = load_json(delivery / "panoptic.json")
    annotation = next(
        (
            item
            for item in panoptic["annotations"]
            if str(item["image_id"]).zfill(12) == image_id
        ),
        None,
    )
    if annotation is None:
        print(f"panoptic annotation not found for image {image_id}", file=sys.stderr)
        return 2
    segments = {int(item["id"]): item for item in annotation.get("segments_info", [])}
    categories = {int(item["id"]): item for item in panoptic["categories"]}
    width, height, pixels = pngutil.read_rgb(mask_path)
    stats = segment_statistics(width, height, pixels)
    output = []
    for segment_id in segment_ids:
        segment = segments.get(segment_id)
        mask_stats = stats.get(segment_id)
        if segment is None or mask_stats is None:
            output.append({"id": segment_id, "error": "segment absent from annotation or mask"})
            continue
        category_id = int(segment["category_id"])
        category = categories.get(category_id, {})
        output.append(
            {
                "id": segment_id,
                "category_id": category_id,
                "category": category.get("name", "unknown"),
                "iscrowd": int(segment.get("iscrowd", 0)),
                "area_mask_pixels": mask_stats["area"],
                "area_panoptic": int(segment["area"]),
                "bbox_mask_xywh": mask_stats["bbox"],
                "bbox_panoptic_xywh": segment["bbox"],
                "mask_centroid_xy": tuple(round(value, 2) for value in mask_stats["centroid"]),
            }
        )
    print(json.dumps({"image": image_id, "size": [width, height], "segments": output}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review Detection vs Panoptic for the Day 10 lab")
    parser.add_argument("--delivery", type=Path, default=Path("runs/r7007/delivery"))
    parser.add_argument("--candidates", type=Path, default=None)
    parser.add_argument("--review-log", type=Path, default=None)
    parser.add_argument("--check", action="store_true", help="Run a non-GUI mask and file consistency check")
    parser.add_argument("--image-id", default="000000001818", help="Image ID for --segment-stats")
    parser.add_argument(
        "--segment-stats",
        nargs="+",
        type=int,
        metavar="SEGMENT_ID",
        help="Print mask-derived area and bounding boxes for the listed segments",
    )
    args = parser.parse_args()

    delivery = args.delivery.resolve()
    if not delivery.exists():
        parser.error(f"delivery directory not found: {delivery}")
    if args.check:
        return check_delivery(delivery)
    if args.segment_stats:
        return print_segment_statistics(delivery, args.image_id.zfill(12), args.segment_stats)

    candidates_path = args.candidates.resolve() if args.candidates else None
    if candidates_path is not None and not candidates_path.exists():
        parser.error(f"candidates file not found: {candidates_path}")
    review_path = (
        args.review_log.resolve()
        if args.review_log
        else delivery.parent / "review_log.csv"
    )
    review_path.parent.mkdir(parents=True, exist_ok=True)

    root = Tk()
    ReviewTool(root, delivery, candidates_path, review_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
