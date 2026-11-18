"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line


def fix(ds, issues, cfg):
    fixes = []
    errors = [issue for issue in issues if issue.severity == ERROR]
    remove_codes = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}

    # Xóa ảnh trước để các issue khác cùng ảnh (ví dụ lỗi dòng nhãn) được bỏ qua.
    removed_stems = set()
    for issue in errors:
        if issue.code not in remove_codes or issue.image in removed_stems:
            continue
        image_path = ds.image_path(issue.image)
        label_path = ds.label_path(issue.image)
        if image_path is None and not label_path.exists():
            continue
        before = str(image_path) if image_path is not None else "(không có ảnh)"
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        label_path.unlink(missing_ok=True)
        removed_stems.add(issue.image)
        fixes.append({"image": issue.image, "line": issue.line, "action": "remove_image",
                      "before": before, "after": "đã xóa ảnh và nhãn"})

    # Gom lỗi theo file và số dòng gốc; thao tác ghi file chỉ thực hiện một lần.
    line_issues = defaultdict(list)
    for issue in errors:
        if issue.image in removed_stems:
            continue
        if issue.code == "MISSING_LABEL_FILE":
            fixes.append({"image": issue.image, "line": issue.line, "action": "needs_label",
                          "before": "(không có file)", "after": "chuyển người gán"})
        elif issue.code in drop_codes | {"BOX_OUT_OF_IMAGE"} and issue.line is not None:
            line_issues[issue.image].append(issue)

    for stem, stem_issues in line_issues.items():
        path = ds.label_path(stem)
        if not path.exists():
            continue
        original_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        by_line = defaultdict(set)
        for issue in stem_issues:
            if 1 <= issue.line <= len(original_lines):
                by_line[issue.line].add(issue.code)

        new_lines = []
        changed = False
        for line_no, original in enumerate(original_lines, 1):
            codes = by_line.get(line_no, set())
            if not codes:
                new_lines.append(original)
                continue

            # Lỗi xóa có ưu tiên: cùng dòng chỉ tạo một bản ghi drop_line.
            if codes & drop_codes:
                fixes.append({"image": stem, "line": line_no, "action": "drop_line",
                              "before": original, "after": "(đã xóa dòng)"})
                changed = True
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    class_id, cx, cy, width, height = parse_yolo_line(original)
                except ValueError:
                    # Dữ liệu đã đổi sau khi sinh issue: tránh làm hỏng file.
                    new_lines.append(original)
                    continue
                x1, y1 = max(0.0, cx - width / 2), max(0.0, cy - height / 2)
                x2, y2 = min(1.0, cx + width / 2), min(1.0, cy + height / 2)
                if x2 <= x1 or y2 <= y1:
                    fixes.append({"image": stem, "line": line_no, "action": "drop_line",
                                  "before": original, "after": "(box nằm ngoài ảnh)"})
                    changed = True
                    continue
                clipped = (class_id, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)
                after = " ".join([str(clipped[0]), *(format(value, ".10g") for value in clipped[1:])])
                new_lines.append(after)
                if after != original:
                    fixes.append({"image": stem, "line": line_no, "action": "clip_box",
                                  "before": original, "after": after})
                    changed = True
            else:
                new_lines.append(original)

        if changed:
            path.write_text("\n".join(new_lines) + ("\n" if original_lines else ""), encoding="utf-8")

    if any(issue.code == "BAD_CLASS_NAME" for issue in errors):
        path = ds.yaml_path
        if path.exists():
            before = path.read_text(encoding="utf-8", errors="replace")
            data = yaml.safe_load(before) or {}
            data["names"] = {index: name for index, name in enumerate(cfg["classes"])}
            after = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
            if after != before:
                path.write_text(after, encoding="utf-8")
                fixes.append({"image": "data.yaml", "line": None, "action": "rename_classes",
                              "before": before, "after": after})

    return fixes
