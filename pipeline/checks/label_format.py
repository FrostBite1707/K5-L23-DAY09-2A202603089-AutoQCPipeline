"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    """Kiểm tra định dạng và hình học các box trong mọi file nhãn."""
    settings = cfg["label_format"]
    overflow_tol = settings["overflow_tol"]
    min_box_px = settings["min_box_px"]
    max_box_frac = settings["max_box_frac"]
    dup_box_iou = settings["dup_box_iou"]
    issues = []

    for label_file in ds.label_files():
        stem = label_file.stem
        previous_boxes = []
        for line_no, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, width, height = parse_yolo_line(text)
            except ValueError as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    f"định dạng nhãn không hợp lệ: {exc}", line_no))
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"id lớp ngoài phạm vi: {class_id}", line_no))
                continue

            if width <= 0 or height <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    "chiều rộng và chiều cao box phải lớn hơn 0", line_no))
                continue

            # Mức tràn lớn nhất qua bốn cạnh; 0 nghĩa là box nằm hoàn toàn trong ảnh.
            overflow = max(0.0, -(cx - width / 2), -(cy - height / 2),
                           cx + width / 2 - 1.0, cy + height / 2 - 1.0)
            if overflow > overflow_tol:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box vượt biên ảnh {overflow:.6g}", line_no,
                                    extra={"overflow": overflow}))

            box = (cx, cy, width, height)
            if any(prev_class == class_id and iou_xywh(box, prev_box) > dup_box_iou
                   for prev_class, prev_box in previous_boxes):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                    "box trùng với box cùng lớp ở dòng trước", line_no))
            previous_boxes.append((class_id, box))

            size = ds.image_size(stem)
            if size is not None:
                image_width, image_height = size
                if min(width * image_width, height * image_height) < min_box_px:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        "cạnh ngắn của box nhỏ hơn ngưỡng pixel", line_no))

            if width * height > max_box_frac:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    "diện tích box vượt tỷ lệ tối đa", line_no))

    return issues
