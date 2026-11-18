"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    settings = cfg["second_opinion"]
    min_conf = settings["conf"]
    min_area_px = settings["min_area_px"]
    fp_conf = settings["fp_conf"]
    iou_missing = settings["iou_missing"]
    iou_match = settings["iou_match"]
    iou_loose = settings["iou_loose"]
    issues = []

    for image_path in ds.image_files():
        stem = image_path.stem
        if stem not in preds:
            continue
        label_lines = ds.read_label_lines(stem)
        if label_lines is None:
            continue

        # Keep valid labels paired with their original file line numbers.
        labels = []
        for line_no, text in label_lines:
            try:
                labels.append((line_no, parse_yolo_line(text)))
            except ValueError:
                continue

        image_size = ds.image_size(stem)
        width_px, height_px = image_size if image_size is not None else (0, 0)
        all_preds = []
        primary_preds = []
        for row in preds[stem]:
            if len(row) != 6:
                continue
            try:
                class_id = int(row[0])
                conf = float(row[1])
                box = tuple(float(value) for value in row[2:])
            except (TypeError, ValueError, OverflowError):
                continue
            if not all(value == value and abs(value) != float("inf") for value in (conf, *box)):
                continue
            prediction = (class_id, conf, box)
            if conf >= fp_conf:
                all_preds.append(prediction)
            area_px = box[2] * width_px * box[3] * height_px
            if conf >= min_conf and image_size is not None and area_px >= min_area_px:
                primary_preds.append(prediction)

        # Each primary model detection can produce at most one warning.
        for pred_class, conf, box in primary_preds:
            candidates = [(label_class, label_box, iou_xywh(box, label_box))
                          for _, (label_class, *label_coords) in labels
                          for label_box in [tuple(label_coords)]
                          if iou_xywh(box, label_box) >= iou_missing]
            if not candidates:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    "model thấy vật chưa có box nhãn tương ứng", extra={"conf": conf}))
                continue

            same_class = [iou for label_class, _, iou in candidates if label_class == pred_class]
            if same_class:
                best_iou = max(same_class)
                if best_iou < iou_loose:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        "box nhãn cùng lớp có thể lỏng hoặc lệch", extra={"iou": best_iou, "conf": conf}))
                continue

            other_class_ious = [iou for label_class, _, iou in candidates if label_class != pred_class]
            if other_class_ious and max(other_class_ious) >= iou_match:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                    "model và nhãn có thể bất đồng về lớp", extra={"iou": max(other_class_ious), "conf": conf}))

        # False-positive checks use fp_conf and intentionally do not filter by area.
        for line_no, (label_class, *label_coords) in labels:
            label_box = tuple(label_coords)
            best_iou = max((iou_xywh(label_box, box) for _, _, box in all_preds), default=0.0)
            if best_iou < iou_missing:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "box nhãn không khớp dự đoán nào của model", line_no,
                                    extra={"iou": best_iou}))

    return issues
