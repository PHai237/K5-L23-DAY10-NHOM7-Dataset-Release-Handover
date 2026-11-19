# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 làm tròn theo seed (lỗi luật / lỗi gán nhãn / tổng) ở pha 1
  - 7007 (seed Nhóm 7): 1,0 / — / 0,8, báo 12 lỗi luật.
  - 7008 (seed kiểm tra bổ sung): 1,0 / — / 0,7, báo 11 lỗi luật.
  - Lô sạch (seed 5, 50 ảnh): 1,0 / 1,0 / 1,0, báo 0 lỗi luật.
- Dấu — là giá trị bộ chấm in cho lỗi gán nhãn khi chạy pha 1.
- Kết quả lỗi luật của seed chính được lưu riêng ở `runs/r7007/rules.json` để gộp với review ở pha 2. Lô sạch báo 0 lỗi luật trong `runs/clean/errors.json`.
- Kiểm tra box dùng dung sai làm tròn YOLO sáu chữ số thập phân. Hai box bị xem là trùng khi cùng lớp, cùng kích thước trong dung sai và tâm lệch tối đa 2 pixel theo mỗi trục.
- Số ứng viên trên lô sạch (`--no-faults`): <<...>>; hàng đợi trên seed luyện tập: <<... ảnh>>
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): <<...>>

## 2. Vì sao báo hết ứng viên làm F1 giảm?
<<Trả lời bằng số của nhóm.>>

## 3. Quyết định và lineage
<<QC v1 a/b, kết luận, vì sao R-021 phải xem lại hoặc train lại.>>

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- Khi chạy qua PowerShell với stdout dùng CP1252, script tạo lô và validator có thể ghi xong tệp rồi thoát lỗi khi in tiếng Việt. Đặt `$env:PYTHONUTF8 = '1'` trước khi chạy để Python và tiến trình con dùng UTF-8.
