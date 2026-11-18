# Báo cáo Day 09 — Nguyễn Minh Hiếu, 2A202603089

## 1. Kết luận trước

Pipeline kết luận **Hold** (mã thoát `10`). Từ **224 ảnh** đầu vào tại `data/raw`, Bước 1 (intake) loại bỏ **22/224 ảnh** vi phạm lỗi bắt buộc về tệp/kích thước/trùng lặp/rò rỉ tập test, giữ lại **202/224 ảnh** đưa vào kiểm tra chất lượng và xuất ra bản nháp tại `submission/export/clean_v1/` (**202 ảnh**, **748 bounding boxes**: `101 car`, `574 person`, `41 truck`, `32 bus`).

**Lý do chính:** Toàn bộ **36 lỗi bắt buộc (`ERROR`)** phát hiện ở vòng QC 1 trên 202 ảnh đã được giải quyết triệt để (**0/202 ảnh** còn lỗi `ERROR` ở vòng 3) nhờ máy tự động sửa 29 dòng nhãn lỗi + chuẩn hóa `data.yaml` và đẩy **6/202 ảnh** thiếu file nhãn (`MISSING_LABEL_FILE`) lên đầu hàng đợi để người gán bổ sung. Tuy nhiên, tổng hàng đợi cần người xem là **125/202 ảnh** trong khi ngân sách duyệt cố định chỉ có **80/202 ảnh**; sau khi người duyệt xong 80 ảnh ưu tiên cao nhất, vẫn còn **38/202 ảnh (18.81%)** có cảnh báo chưa được người kiểm tra, vượt ngưỡng cổng chặn `warn_ratio_hold = 10.0%` (20/202 ảnh) nên hệ thống bắt buộc giữ ở trạng thái **Hold**.

---

## 2. Lỗi và phân việc

Bảng dưới đây tổng hợp toàn bộ **20 mã lỗi và cảnh báo** xuất hiện trong `submission/reports/02_error_list_v1.txt` (bao gồm 22 lỗi cửa vào trên mẫu số **224 ảnh quét** và 189 lỗi/cảnh báo vòng 1 trên mẫu số **202 ảnh nhận**):

| Mã lỗi | Mức độ | Số ảnh / dòng (kèm mẫu số) | Ai sửa (máy/người) | Vì sao |
|---|---|---:|---|---|
| `CORRUPT_IMAGE` | `ERROR` | 2/224 ảnh (2 dòng) | **Máy** (`intake` / `remove_image`) | File ảnh hỏng cấu trúc byte (`UnidentifiedImageError`, `OSError` khi `load()`), không thể mở hay gán nhãn. |
| `BAD_SIZE` | `ERROR` | 3/224 ảnh (3 dòng) | **Máy** (`intake` / `remove_image`) | Quy tắc cứng: cạnh ngắn `< 250px` (`180px`, `226px`), kiểm tra chính xác tuyệt đối bằng kích thước ảnh. |
| `DUP_IMAGE_EXACT` | `ERROR` | 8/224 ảnh (8 dòng) | **Máy** (`intake` / `remove_image`) | Trùng khớp tuyệt đối mã băm MD5 từng byte với ảnh đứng trước trong lô dữ liệu. |
| `DUP_IMAGE_NEAR` | `ERROR` | 4/224 ảnh (4 dòng) | **Máy** (`intake` / `remove_image`) | Ảnh trùng gần đúng (`phash_dist <= 10`) do thu nhỏ/nén lại (`img_0076`, `img_0143`, `img_0186`, `img_0223`). |
| `LEAK_TEST` | `ERROR` | 5/224 ảnh (5 dòng) | **Máy** (`intake` / `remove_image`) | Trùng pHash (`<= 10`) với kho `data/test` (`test_033`, `test_039`, `test_044`, `test_085`, `test_009`), phải loại bỏ để chống rò rỉ đánh giá. |
| `BAD_CLASS_NAME` | `ERROR` | 2/4 lớp trong `data.yaml` (2 dòng) | **Máy** (`autofix`: `rename_classes`) | Sai quy ước tên lớp (`'Person'`, `'Bus'` viết hoa thay vì `'person'`, `'bus'`), máy chuẩn hóa lại theo `cfg["classes"]`. |
| `BAD_FORMAT` | `ERROR` | 3/202 ảnh (3 dòng nhãn) | **Máy** (`autofix`: `drop_line`) | Dòng nhãn thiếu cột (4 cột) hoặc chứa `nan/inf`, vi phạm cú pháp YOLO cơ bản. |
| `BAD_CLASS_ID` | `ERROR` | 6/202 ảnh (6 dòng nhãn) | **Máy** (`autofix`: `drop_line`) | ID lớp nằm ngoài tập `{0, 1, 2, 3}` (`-1`, `4`, `7`, `93`), máy xóa dòng hỏng an toàn. |
| `BOX_ZERO` | `ERROR` | 4/202 ảnh (4 dòng nhãn) | **Máy** (`autofix`: `drop_line`) | Chiều rộng hoặc chiều cao `<= 0`, box suy biến không có diện tích vật lý. |
| `DUP_BOX` | `ERROR` | 7/202 ảnh (7 dòng nhãn) | **Máy** (`autofix`: `drop_line`) | Hai dòng nhãn trong cùng ảnh có cùng lớp và `IoU > 0.9`, máy xóa bản sao ở dòng sau. |
| `BOX_OUT_OF_IMAGE` | `ERROR` | 8/202 ảnh (8 dòng nhãn) | **Máy** (`autofix`: `clip_box`) | Box tràn ra ngoài biên `[0, 1]` vượt dung sai `0.002` (mức tràn `0.023–0.060`), máy cắt (`clip`) gọn về biên ảnh. |
| `MISSING_LABEL_FILE` | `ERROR` | 6/202 ảnh (6 dòng) | **Người** (`autofix`: `needs_label` → đầu hàng đợi) | Ảnh hoàn toàn chưa có file `.txt`; máy không được phép bịa nhãn hay tạo file rỗng (sẽ biến thành ảnh nền giả). |
| `BOX_HUGE` | `WARN` | 3/202 ảnh (3 dòng nhãn) | **Người** (hàng đợi duyệt) | Box chiếm `> 95%` diện tích ảnh; có thể là lỗi vẽ trùm toàn ảnh hoặc vật thể thực sự chụp cận cảnh. |
| `BOX_TINY` | `WARN` | 6/202 ảnh v1; 7 dòng trên 5/202 ảnh v2 | **Người** (hàng đợi duyệt) | Cạnh ngắn `< 12px` (sau khi `clip_box` ở `img_0030.txt:9` phát sinh thêm 1 dòng `BOX_TINY` ở v2); cần người xác nhận có gán vật rất nhỏ không. |
| `CLASS_RARE` | `WARN` | 4 lớp trên `<dataset>` (4 dòng) | **Chỉ thống kê** (bỏ qua ở hàng đợi ảnh) | Cảnh báo cấp độ toàn tập dữ liệu về phân bố số lượng box theo lớp. |
| `EMPTY_LABEL` | `WARN` | 12/202 ảnh v1 → 15/202 ảnh v2 | **Người** (hàng đợi duyệt) | File `.txt` rỗng (tăng thêm 3 ảnh ở v2 do `drop_line` xóa dòng lỗi duy nhất trong `img_0050`, `img_0104`, `img_0194`); cần người phân biệt ảnh nền thật hay sót nhãn. |
| `POSSIBLE_WRONG_CLASS` | `WARN` | 19/202 ảnh (23 dòng v1 → 18 dòng v2) | **Người** (hàng đợi duyệt) | Model `yolo26l` dự đoán khác lớp với nhãn hiện tại (`IoU >= 0.5`); cần con người phán đoán ngữ nghĩa (vd: `truck` vs `bus`). |
| `POSSIBLE_MISSING` | `WARN` | 40/202 ảnh (48 dòng v1 → 53 dòng v2) | **Người** (hàng đợi duyệt) | Model thấy vật thể (`conf >= 0.6`, diện tích `>= 600px`) nhưng nhãn không có box nào khớp (`IoU < 0.3`); tăng lên 53 dòng ở v2 sau khi máy xóa các dòng lỗi cú pháp. |
| `POSSIBLE_FALSE_POS` | `WARN` | 28/202 ảnh (29 dòng v1 → 24 dòng v2) | **Người** (hàng đợi duyệt) | Box nhãn không khớp với bất kỳ dự đoán nào của model (`conf >= 0.1`); cần người xem là box thừa hay vật thể khó mà model bỏ sót. |
| `POSSIBLE_LOOSE_BOX` | `WARN` | 25/202 ảnh (28 dòng v1 → 28 dòng v2) | **Người** (hàng đợi duyệt) | Cùng vật, cùng lớp với dự đoán của model nhưng `0.3 <= IoU < 0.5`, cần người tinh chỉnh lại biên box. |

### Cơ chế xếp hạng `05_review_queue.csv` và độ phủ của ngân sách 80 ảnh

- **Vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy?** Hàm `review_queue.build_queue` tính điểm ưu tiên (`priority`) cho từng ảnh bằng tổng trọng số cấu hình tại `cfg["review"]["weights"]` nhân/cộng với mức độ nghiêm trọng của từng cờ:
  - Ảnh thiếu file nhãn (`MISSING_LABEL_FILE` → action `needs_label`) được gán mã `NEEDS_LABEL` với trọng số cao nhất (**`10.0`**) để bắt buộc nổi lên đầu hàng đợi (top 7 ảnh đầu tiên có `img_0020` đạt `11.524` do gộp `FIXED_DROP_LINE + POSSIBLE_MISSING + POSSIBLE_WRONG_CLASS`, tiếp theo là 6 ảnh `NEEDS_LABEL` ở mức `10.0`). Nếu 6 ảnh này không nằm trong 80 ảnh được duyệt, pipeline chắc chắn bị **Rework**.
  - Tiếp theo là các ảnh có nhiều lỗi ngữ nghĩa nặng kết hợp với việc vừa bị máy can thiệp (`POSSIBLE_WRONG_CLASS: 3`, `POSSIBLE_MISSING: 2`, `POSSIBLE_FALSE_POS: 2`, `FIXED_DROP_LINE: 2`, `POSSIBLE_LOOSE_BOX: 1.5`, `EMPTY_LABEL: 1`, `FIXED_CLIP_BOX: 1`, `BOX_HUGE: 0.5`, `BOX_TINY: 0.3`), cộng thêm điểm thưởng từ `conf` của dự đoán model hoặc độ lệch `1 - IoU`.
- **Với ngân sách 80 ảnh (`80/202` ảnh dataset, trên tổng số `125/202` ảnh trong hàng đợi), người duyệt xem được bao nhiêu lỗi ngữ nghĩa?**
  Đối chiếu trực tiếp 80 ảnh đầu trong `05_review_queue.csv` với danh sách lỗi sau sửa tự động `04_error_list_v2.csv`:
  - Xử lý **6/6 ảnh (100%)** thiếu file nhãn (`MISSING_LABEL_FILE`).
  - Duyệt được **105/138 dòng cảnh báo ngữ nghĩa (76.1%)**, tương ứng với **74/107 ảnh (69.2%)** có lỗi ngữ nghĩa. Chi tiết theo từng mã ở v2:
    - `POSSIBLE_WRONG_CLASS`: **18/18 dòng (100.0%)**
    - `POSSIBLE_MISSING`: **51/53 dòng (96.2%)**
    - `EMPTY_LABEL`: **11/15 dòng (73.3%)**
    - `POSSIBLE_FALSE_POS`: **13/24 dòng (54.2%)**
    - `POSSIBLE_LOOSE_BOX`: **12/28 dòng (42.9%)**
  - Nhờ cơ chế sắp xếp ưu tiên theo trọng số, chỉ với `80/125` ảnh hàng đợi (`64.0%` khối lượng hàng đợi), con người đã giải quyết được gần như toàn bộ các lỗi ngữ nghĩa nghiêm trọng nhất (`100%` nhầm lớp và `96.2%` thiếu box), chỉ để lại ở cuối hàng đợi các cảnh báo nhẹ hơn (`POSSIBLE_LOOSE_BOX`, `POSSIBLE_FALSE_POS`, `BOX_TINY`, `BOX_HUGE`).

### Phân rã 202 ảnh mẫu số sau khi người duyệt (4 nhóm tại cổng chặn)

Tại vòng QC 3, cổng chặn `gate.decide()` không đếm số dòng trong hàng đợi mà đếm **số ảnh còn ít nhất 1 `WARN` và chưa nằm trong danh sách 80 ảnh đã duyệt** trên mẫu số **202 ảnh** sau intake:

| Nhóm ảnh trong mẫu số 202 ảnh | Số lượng | Chi tiết trong lô `data/raw` | Tính vào tử số Hold? |
|---|---:|---|---|
| **1. Đã được người duyệt** (`06_review_log.csv`) | **80/202 ảnh** | Top 80 ảnh đầu `05_review_queue.csv` (gồm cả 6 ảnh `NEEDS_LABEL`: `img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`). Mọi `WARN` còn lại trên 80 ảnh này được coi là đã xử lý. | **Không** |
| **2. Chưa duyệt, vẫn còn `WARN`** (tử số của Hold) | **38/202 ảnh** (`18.81%`) | Nằm dưới đường cắt 80 ảnh: gồm 2 ảnh `POSSIBLE_MISSING` (`img_0210`, `img_0032`), 16 ảnh `POSSIBLE_LOOSE_BOX` (`img_0018`, `img_0038`, …), 11 ảnh `POSSIBLE_FALSE_POS` (`img_0069`, `img_0035`, …), 4 ảnh `EMPTY_LABEL` (`img_0013`, `img_0097`, `img_0129`, `img_0192`), 5 ảnh chỉ còn `BOX_TINY`/`BOX_HUGE` (`img_0161`, `img_0128`, `img_0196`, `img_0026`, `img_0051`). | **CÓ (`38/202 = 0.1881 >= 0.10` → Hold)** |
| **3. Đứng dưới đường cắt hàng đợi nhưng chỉ có `FIXED_*`, đã hết `WARN`** | **7/202 ảnh** | 3 ảnh `FIXED_DROP_LINE` (`img_0006`, `img_0109`, `img_0141`) và 4 ảnh `FIXED_CLIP_BOX` (`img_0043`, `img_0087`, `img_0108`, `img_0152`). Có mặt trong `125 - 80 = 45` ảnh cuối hàng đợi để người xem lại vết máy sửa, nhưng ở vòng 3 không còn bất kỳ `WARN` nào. | **Không** (`45 - 7 = 38` ảnh) |
| **4. Sạch từ đầu** (không vào hàng đợi) | **77/202 ảnh** | Không có lỗi bắt buộc, không bị autofix sửa và không có cảnh báo nào ở vòng 2 (`202 - 125 = 77` ảnh). | **Không** |

---

## 3. Calibration (2 ngưỡng)

Bảng đối chiếu kết quả trên tập `data/calib` (39 ảnh có đáp án tại `MANIFEST.csv`) trước và sau khi chọn ngưỡng trong `configs/pipeline.yaml`:

| Tham số | Khởi đầu | Đã chọn | Precision / Recall / F1 (trước → sau) | Lý do chọn (đánh đổi Precision – Recall) |
|---|---:|---:|---|---|
| `duplicates.phash_dist` | `2` | **`10`** | - `DUP_IMAGE_EXACT`: `1.00 / 1.00 / 1.00` → `1.00 / 1.00 / 1.00`<br>- `DUP_IMAGE_NEAR`: `1.00 / 0.50 / 0.67` (TP=3, FP=0, FN=3) → **`1.00 / 0.67 / 0.80`** (TP=4, FP=0, FN=2) | `duplicates` là lỗi bắt buộc (`ERROR`) dẫn tới hành động **tự động xóa vĩnh viễn ảnh** (`remove_image`), nên **Precision = 1.00 là điều kiện sống còn** (1 FP = xóa mất ảnh huấn luyện thật). Tăng từ `2` lên `10` giúp nâng Recall từ `0.50` lên `0.67` trên `calib` và bắt thêm 1 ảnh rò rỉ tập test (`img_0101` trùng `test_039`) + 2 cặp ảnh gần trùng thật trên `raw` (`img_0223`/`img_0077` ở `dist=6` và `img_0186`/`img_0061` ở `dist=10`) mà không gây ra bất kỳ ca xóa nhầm nào. |
| `second_opinion.conf` | `0.25` | **`0.6`** | - `WRONG_CLASS`: `0.50 / 0.83 / 0.62` → **`0.56 / 0.83 / 0.67`**<br>- `MISSING`: `0.53 / 1.00 / 0.70` → **`0.61 / 1.00 / 0.76`**<br>- `LOOSE_BOX`: `0.29 / 0.40 / 0.33` → **`0.20 / 0.20 / 0.20`**<br>- `FALSE_POS`: `0.31 / 1.00 / 0.48` → **`0.31 / 1.00 / 0.48`** | `second_opinion` sinh cảnh báo (`WARN`) đưa vào hàng đợi người duyệt (ngân sách giới hạn 80 ảnh). Ở `0.25`, model sinh quá nhiều báo động giả (FP cao ở `MISSING` và `WRONG_CLASS`), làm loãng hàng đợi và khiến sau duyệt còn tới `60/205` ảnh (`29.3%`) cảnh báo. Tăng lên `0.6` giúp tăng Precision của `WRONG_CLASS` (`0.50 → 0.56`) và `MISSING` (`0.53 → 0.61`) trong khi **giữ nguyên Recall tối đa** cho hai lỗi quan trọng nhất (`WRONG_CLASS = 0.83` tức 5/6, `MISSING = 1.00` tức 8/8). Nếu nâng tiếp lên `0.7` hoặc `0.8`, Recall của `MISSING` bị tụt xuống `0.88` và `0.75` (bỏ sót đối tượng chưa gán nhãn). |

### Chỗ calibration có thể đánh lừa (kèm bằng chứng thực nghiệm trên `data/raw`)

Nếu chỉ nhìn vào bảng sweep trên bộ `calib` (39 ảnh) và chọn theo **F1 cao nhất**, ta sẽ bị đánh lừa chọn **`duplicates.phash_dist = 16`** vì trên `calib` ngưỡng `16` đạt `Precision = 1.00`, `Recall = 0.83 (5/6)`, `F1 = 0.91` (cao hơn mức `F1 = 0.80` của ngưỡng `10`).

Tuy nhiên, khi kiểm chứng thực tế trên tập `data/raw` (**224 ảnh**):
- Ở `phash_dist = 10`, bước 1 loại tổng cộng **22/224 ảnh** (gồm `2 CORRUPT_IMAGE`, `3 BAD_SIZE`, `8 DUP_IMAGE_EXACT`, `4 DUP_IMAGE_NEAR`, `5 LEAK_TEST`). Kiểm tra trực quan từng cặp ảnh bị gắn cờ ở mức `dist = 6..10`:
  - `img_0223.jpg` (`375×309`) và `img_0077.jpg` (`500×412`, `phash_dist = 6`): đúng là cùng một ảnh được thu nhỏ 75%.
  - `img_0186.jpg` (`640×425`) và `img_0061.jpg` (`544×361`, `phash_dist = 10`): đúng là cùng bức ảnh người ngồi trên ghế gỗ trong công viên được resize ~85%.
  - `img_0101.jpg` (`450×450`) và `test/test_039.jpg` (`612×612`, `phash_dist = 6`): đúng là ảnh rò rỉ từ tập test đã bị thu nhỏ.
- Ngược lại, nếu đặt `phash_dist = 16`, số ảnh bị xóa ở Bước 1 nhảy vọt từ **22/224 lên 31/224 ảnh** (tăng thêm **9 ảnh bị xóa oan**, gồm 3 ca `DUP_IMAGE_NEAR` giả và 6 ca `LEAK_TEST` giả ở đúng khoảng cách `dist = 16`). Bằng chứng cụ thể khi mở ảnh:
  - `img_0011.jpg` (`640×427`, vận động viên nữ mặc đồ hồng đang đánh tennis trên sân xanh) bị kết luận là trùng gần đúng (`phash_dist = 16`) với `img_0008.jpg` (`640×480`, hai người mặc áo khoác trượt tuyết trên đỉnh núi tuyết trắng).
  - `img_0084.jpg` và `img_0074.jpg` (`phash_dist = 16`), `img_0177.jpg` và `img_0113.jpg` (`phash_dist = 16`), cùng 6 ảnh `img_0013`, `img_0017`, `img_0021`, `img_0033`, `img_0038`, `img_0115` đều là các cảnh hoàn toàn khác nhau nhưng ngẫu nhiên có khoảng cách Hamming 64-bit bằng 16 với một ảnh khác trong số hàng trăm ảnh.
- **Nguyên nhân sâu xa:** Bộ `calib` chỉ có `39` ảnh (tạo ra `39 × 38 / 2 = 741` cặp so sánh nội bộ), trong khi `raw` đối chiếu với chính nó và kho `test + gold_val` tạo ra hàng chục nghìn cặp so sánh (`224 × 223 / 2 + 224 × 140 ≈ 56,336` cặp). Khi không gian cặp so sánh tăng gấp ~76 lần, xác suất hai ảnh không liên quan có khoảng cách pHash `<= 16` tăng mạnh, biến `Precision = 1.00` trên `calib` thành hàng loạt False Positives gây mất dữ liệu trên `raw`.

---

## 4. Cửa chặn và điều pipeline KHÔNG bắt được

### (a) Chứng minh cửa chặn (`gate`) hoạt động đúng khi không có người duyệt

Thực thi lệnh kiểm chứng với ngân sách duyệt bằng `0`:
```bash
.venv/bin/python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb
```
Kết quả thực tế thu được:
1. **Giữ nguyên lỗi bắt buộc khi thiếu người duyệt:** Ở Bước 4 (vòng 1 & vòng 2), pipeline phát hiện **6/202 ảnh** bị lỗi `MISSING_LABEL_FILE` (`img_0031`, `img_0053`, `img_0126`, `img_0135`, `img_0170`, `img_0219`, mức độ `ERROR`). Vì máy không được phép tự bịa nhãn (`autofix` chỉ ghi `action = needs_label` và đẩy lên đầu `05_review_queue.csv`), khi `--budget 0` (người duyệt `0/202` ảnh), cả 6 ảnh này vẫn không có file `.txt` ở vòng QC 3 (`07_error_list_v3.txt` còn nguyên `6` lỗi `ERROR MISSING_LABEL_FILE`).
2. **Kết luận và mã thoát:** Hàm `gate.decide()` lập tức kích hoạt nhánh chặn ưu tiên cao nhất (`n_errors = 6 >= 1`), trả về quyết định **`Rework`** với lý do `"Rework: còn 6 lỗi bắt buộc (ERROR)."` và kết thúc tiến trình với **mã thoát `20`** (`echo $?` trả về `20`).
3. **Chặn xuất dữ liệu:** Pipeline in rõ `Bước 5/5 KHÔNG xuất: còn lỗi bắt buộc (Rework) — trả về bước 3`, thư mục `work/exp_nb` hoàn toàn **không được tạo ra**, và trường `"exported"` trong `work/rep_nb/08_summary.json` mang giá trị `null`.

### (b) Ít nhất 2 điểm mù mà pipeline KHÔNG bắt được (kèm bằng chứng)

1. **Điểm mù 1 — Ảnh trùng bị cắt cúp mạnh (heavy crop) hoặc thay đổi bố cục lớn:**
   - *Bằng chứng:* Trong `data/calib/MANIFEST.csv`, có 6 ca `DUP_IMAGE_NEAR` (`calib_034` đến `calib_039`) với mức biến đổi tăng dần từ 0 đến 4. Ở ngưỡng đã chọn `phash_dist = 10`, pipeline chỉ bắt được `4/6` ca (`Recall = 0.67`), bỏ sót 2 ca biến đổi mạnh nhất là `calib_037` (biến đổi mức 3 của `calib_015`) và `calib_038` (biến đổi mức 4 của `calib_024`). Ngay cả khi quét tới `phash_dist = 16` hoặc `20`, `calib_038` vẫn hoàn toàn thoát khỏi bộ lọc vì pHash tính biến đổi cosin rời rạc (DCT) trên toàn khung ảnh đã chuẩn hóa kích thước; khi ảnh bị cắt mất phần lớn bối cảnh nền, lưới tần số thấp thay đổi hoàn toàn.
2. **Điểm mù 2 — Nhầm lớp hoặc thiếu nhãn ở các ca mà chính model lớn (`yolo26l`) cũng dự đoán sai/bỏ sót:**
   - *Bằng chứng:* Trong `data/calib/MANIFEST.csv`, có 6 lỗi `WRONG_CLASS` được chèn cố ý, nhưng trên toàn bộ dải sweep `second_opinion.conf` từ `0.10` đến `0.80`, Recall của `POSSIBLE_WRONG_CLASS` không bao giờ vượt quá **`0.83` (5/6)** — ca `calib_009` (dòng 6, lỗi chèn `truck -> bus`) luôn bị bỏ sót (FN = 1) vì bản thân model checker `yolo26l` không phát hiện ra sự bất đồng lớp đủ ngưỡng `iou_match >= 0.5`. Ngoài ra, sau khi người thật duyệt 80 ảnh ở tập `raw` (thay bằng nhãn chuẩn của người từ `review_reference`), ở vòng QC 3 (`07_error_list_v3.txt`) `second_opinion` vẫn báo nhầm `3` dòng `POSSIBLE_WRONG_CLASS` (`img_0078`, `img_0083`, `img_0220`) và `21` dòng `POSSIBLE_FALSE_POS` trên chính các nhãn chuẩn đã được người xác nhận, chứng tỏ nơi nào `yolo26l` nhìn nhầm hoặc bỏ sót vật thể bị che khuất thì máy vừa có thể tạo cảnh báo giả, vừa mù trước lỗi thật có cùng chiều hướng với lỗi của model.
3. **Điểm mù 3 — Box lỏng vừa phải (`IoU >= 0.5`) hoặc box lỏng trên vật thể mà model có độ tự tin thấp:**
   - *Bằng chứng:* Trong `data/calib/MANIFEST.csv`, có 5 lỗi `LOOSE_BOX` được chèn cố ý (`calib_002`, `calib_006`, `calib_012`, `calib_023`, `calib_024` với `scale = 1.45..1.58`), nhưng ngay cả ở ngưỡng rất thấp `conf = 0.25`, `second_opinion` chỉ bắt được **`2/5` ca (`Recall = 0.40`)** và ở `conf = 0.60` chỉ bắt được **`1/5` ca (`Recall = 0.20`)**. Nguyên nhân là quy tắc `POSSIBLE_LOOSE_BOX` chỉ kích hoạt khi `0.3 <= IoU(pred, label) < 0.5`; các box nhãn bị nới lỏng khoảng `20%–40%` mỗi chiều hoặc lệch tâm nhẹ nhưng vẫn có `IoU >= 0.5` với box của `yolo26l` sẽ được coi là khớp hoàn toàn (`iou_match = 0.5`) và đi lọt 100% qua pipeline.

---

## 5. Train: raw vs clean (tùy chọn, chấm riêng)

**Trạng thái:** **Chưa chạy** (`--no-train`).

**Lý do:** Môi trường thực thi hiện tại là máy trạm CPU dùng để phát triển, kiểm thử đơn vị (`pytest` 79/79 passed), hiệu chỉnh ngưỡng (`make calibrate`) và vận hành pipeline kiểm nhãn tự động (`make run` / `make check-core`). Việc huấn luyện đối chứng `yolo26n` (2 biến thể `raw` vs `clean` × 2 `seed` × 20 `epochs`) là phần tùy chọn chấm riêng cần thực hiện trên GPU Google Colab.

**Phân tích kỳ vọng và giả thuyết kiểm chứng nếu chạy thực nghiệm train:**
- Khi huấn luyện trên tập dữ liệu nhỏ (~202 ảnh `clean` so với 224 ảnh `raw`) và đánh giá trên `data/test` (chỉ có **100 ảnh**), độ lệch chuẩn của `mAP50` và `mAP50-95` giữa 2 seed (`seed 0` và `seed 1`) thường dao động khoảng `±0.01–0.03`. Nếu mức chênh lệch `|mAP50(clean) - mAP50(raw)|` nhỏ hơn hoặc tương đương độ lệch chuẩn giữa các seed, ta phải kết luận trung thực là **chưa đủ bằng chứng thống kê để khẳng định bên nào tốt hơn** (chênh lệch nằm trong nhiễu ngẫu nhiên của quá trình khởi tạo và mini-batch SGD).
- **2 giả thuyết giải thích hiện tượng `raw` có thể đạt mAP trên tập test ngang hoặc thậm chí nhỉnh hơn `clean`:**
  1. *Giả thuyết 1 (Rò rỉ tập test trong `raw`):* Tập `raw` chứa **5/224 ảnh trùng với tập `data/test`** (`LEAK_TEST`: `img_0049` trùng `test_033`, `img_0101` trùng `test_039`, `img_0167` trùng `test_044`, `img_0174` trùng `test_085`, `img_0221` trùng `test_009`). Mô hình train trên `raw` được học trực tiếp các ảnh có mặt trong tập đánh giá cuối cùng nên điểm test của `raw` bị thổi phồng giả tạo, trong khi `clean` đã xóa 5 ảnh này để đảm bảo tính trung thực. *Cách kiểm chứng:* Đánh giá lại cả hai mô hình trên tập `data/test` sau khi loại bỏ 5 ảnh bị rò rỉ (`test_009`, `test_033`, `test_039`, `test_044`, `test_085`) hoặc so sánh trên `data/gold_val` (40 ảnh sạch không bị rò rỉ).
  2. *Giả thuyết 2 (Còn 122/202 ảnh trong `clean` chưa qua mắt người duyệt và dung sai của mAP50 với box lỏng):* Trong `clean_v1`, mới có `80/202` ảnh được thay bằng nhãn người chuẩn, còn `122/202` ảnh vẫn giữ nhãn máy ban đầu (trong đó còn `38/202` ảnh có cảnh báo `POSSIBLE_LOOSE_BOX`, `POSSIBLE_MISSING`, `POSSIBLE_FALSE_POS`). Hơn nữa, thước đo `mAP50` chỉ yêu cầu `IoU >= 0.50` nên ít nhạy với lỗi box lỏng nhẹ, trong khi `mAP50-95` mới phản ánh rõ lợi ích của việc gọt sát biên box. *Cách kiểm chứng:* So sánh riêng chỉ số `mAP50-95` (đòi hỏi định vị box chính xác cao) và chạy thử nghiệm tăng ngân sách duyệt lên `125` ảnh (duyệt hết hàng đợi) rồi train lại để tách biệt ảnh hưởng của nhãn máy còn sót.

---

## 6. Quyết định và ghi chú AI

### (a) Quyết định cuối cùng và điều kiện để chuyển sang Release

- **Quyết định cuối cùng:** **Hold** — **chưa phát hành** bộ dữ liệu `submission/export/clean_v1/` cho huấn luyện sản xuất chính thức. Dữ liệu đã sạch 100% lỗi bắt buộc (`n_errors = 0/202`), đã loại bỏ 22/224 ảnh hỏng/nhỏ/trùng/rò rỉ test và đã được con người duyệt xong 80/202 ảnh ưu tiên cao nhất, nhưng vẫn còn **38/202 ảnh (18.81%)** mang cảnh báo chưa được người kiểm tra (vượt ngưỡng cho phép `warn_ratio_hold = 10.0%`).
- **Cần làm gì để chuyển từ Hold thành Release?**
  - Theo công thức cổng chặn `warn_ratio = n_warn_images / n_images < 0.10`, với tổng số `n_images = 202` ảnh, số ảnh còn cảnh báo chưa qua mắt người phải giảm xuống **tối đa `20/202` ảnh (`9.90% < 10.0%`)**.
  - Hiện tại còn `38/202` ảnh có cảnh báo chưa duyệt (nằm trong số `125 - 80 = 45` ảnh cuối của `05_review_queue.csv`, từ vị trí thứ 81 đến 125). Do đó, chỉ cần **cấp thêm ngân sách cho người duyệt tối thiểu `38 - 20 = 18` ảnh nữa** (nâng tổng số ảnh người duyệt từ `80` lên **`98/202` ảnh** theo thứ tự `05_review_queue.csv`, hoặc duyệt nốt toàn bộ **45 ảnh** còn lại trong hàng đợi để đưa `warn_ratio` về `0/202 = 0.0%`), sau đó chạy lại bước tiếp tục sau duyệt (`--resume-after-review`), cổng chặn sẽ lập tức chuyển sang **Release** (mã thoát `0`).

### (b) Ghi chú sử dụng AI

1. **Prompt chính:** *"Đọc đặc tả trong docstring của 4 module `pipeline/checks/label_format.py`, `pipeline/steps/gate.py`, `pipeline/steps/autofix.py`, `pipeline/checks/second_opinion.py`; cài đặt từng module chỉ sửa trong thư mục làm việc `ds`, đọc mọi ngưỡng từ `cfg`, xử lý an toàn dòng nhãn hỏng/trống và trả về đúng cấu trúc `Issue` / dict theo unit test."*
2. **Cách kiểm tra code do AI sinh:** Chạy bộ kiểm thử tự động `pytest -q` (đạt `79 passed`), kiểm tra thêm các ca biên (một dòng nhãn vừa bị `BOX_OUT_OF_IMAGE` vừa bị `DUP_BOX`, file có dòng trống ở giữa, ảnh bị xóa ở bước trùng lặp nhưng vẫn còn issue dòng nhãn), chạy toàn bộ pipeline bằng `make calibrate` + `make run` và đối chiếu trực tiếp các cặp ảnh trên `data/raw` cùng kết quả `scripts/check_submission.py --no-train`.
3. **Một lần AI sai và cách sửa:** Khi viết script phân tích nhanh và đối chiếu thuộc tính của đối tượng `Issue` trong `duplicates.py` để kiểm tra các cặp ảnh trùng trên `data/raw`, AI đã truy cập nhầm thuộc tính `issue.detail` (giống tên cột trong `MANIFEST.csv`) dẫn tới lỗi `AttributeError: 'Issue' object has no attribute 'detail'`; đã kiểm tra lại định nghĩa `dataclass Issue` trong `pipeline/common.py` và sửa thành `issue.message` kết hợp `issue.extra`.
