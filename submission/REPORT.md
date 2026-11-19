# Báo cáo nhóm 7

## 1. Số liệu luyện tập
- F1 làm tròn theo seed (lỗi luật / lỗi gán nhãn / tổng) ở pha 1
  - 7007 (seed Nhóm 7): 1,0 / — / 0,8, báo 12 lỗi luật.
  - 7008 (seed kiểm tra bổ sung): 1,0 / — / 0,7, báo 11 lỗi luật.
  - Lô sạch (seed 5, 50 ảnh): 1,0 / 1,0 / 1,0, báo 0 lỗi luật.
- F1 sau pha 2 (đối chiếu + xem ảnh, seed 7007): **1,0 / 0,7 / 0,9**, nộp **16** lỗi (12 lỗi luật + 4 lỗi gán nhãn đã `confirmed` trong `review_log.csv`).
- Dấu — là giá trị bộ chấm in cho lỗi gán nhãn khi chạy pha 1.
- Kết quả lỗi luật của seed chính được lưu riêng ở `runs/r7007/rules.json` để gộp với review ở pha 2. Lô sạch báo 0 lỗi luật trong `runs/clean/errors.json`.
- Kiểm tra box dùng dung sai làm tròn YOLO sáu chữ số thập phân. Hai box bị xem là trùng khi cùng lớp, cùng kích thước trong dung sai và tâm lệch tối đa 2 pixel theo mỗi trục.
- Số ứng viên trên lô sạch (`--no-faults`): **0** ứng viên trên 50 ảnh (seed 5); hàng đợi trên seed luyện tập (`7007`): **5** ứng viên trên **5** ảnh (`missing_box=1`, `bbox_drift=1`, `class_or_category_swap=2`, `instance_merge=1`).
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): ghép theo tỷ lệ pixel mask panoptic nằm trong box detection kết hợp IoU (bỏ segment `iscrowd`), dùng `MATCH_IOU = 0.30`, `SWAP_IOU = 0.50`, `DRIFT_INSIDE_MAX = 0.82` (`DRIFT_IOU_MIN = 0.15`), `MISSING_MIN_FRAC = 0.008`, và kiểm `instance_merge` (`MERGE_SHARE_MIN = 0.25`, `MERGE_SINGLE_MAX = 0.80`, `MERGE_PAIR_IOU_MAX = 0.30`) trước `bbox_drift` để tránh báo đúp trên cùng segment. Đã kiểm chứng trên lô sạch `runs/clean` (50 ảnh `calib`) cho **0** ứng viên giả, đồng thời giữ hàng đợi `r7007` gọn ở 5 ảnh để xem hết bằng mắt.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
Trên seed `7007`, bộ đối chiếu sinh 5 ứng viên trên 5 ảnh, nhưng khi mở ảnh xem thực tế chỉ có **4 ca lỗi thật (`confirmed`)** và **1 ca lệch tự nhiên (`rejected`)** là ảnh `000000001818` (hai con ngựa vằn đứng chồng lên nhau làm validator ghép nhầm box con bên phải với segment con lớn). Ngoài ra, với 2 ca `class_or_category_swap` (`000000006471`, `000000013177`), nếu không mở ảnh xem thì không phân biệt được `class_swap` hay `category_swap` — đoán sai sẽ bị tính đồng thời cả 1 FP lẫn 1 FN. Khi báo bừa toàn bộ ứng viên chưa qua review mắt, số báo thừa (`FP`) tăng lên làm `precision = TP / (TP + FP)` giảm, kéo theo `F1 = 2·P·R / (P + R)` giảm theo.

## 3. Quyết định và lineage
<<QC v1 a/b, kết luận, vì sao R-021 phải xem lại hoặc train lại.>>

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Khi chạy qua PowerShell với stdout dùng CP1252, script tạo lô và validator có thể ghi xong tệp rồi thoát lỗi khi in tiếng Việt. Đặt `$env:PYTHONUTF8 = '1'` trước khi chạy để Python và tiến trình con dùng UTF-8.
