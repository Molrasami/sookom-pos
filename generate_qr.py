import qrcode
import os
import sys

# =====================================================
# อย่าลืมแก้ BASE_URL ให้เป็นที่อยู่ไฟล์ index.html ของคุณนะครับ
# =====================================================
BASE_URL = "https://molrasami.github.io/sookom-pos/"  # <-- แก้ตรงนี้ให้ตรงกับเครื่องคุณ

TOTAL_TABLES = 10
OUTPUT_FOLDER = "qr_codes"


def generate_qrs():
    # ดึงที่อยู่โฟลเดอร์ปัจจุบันที่ไฟล์นี้ตั้งอยู่
    current_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(current_dir, OUTPUT_FOLDER)

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"📁 สร้างโฟลเดอร์ {OUTPUT_FOLDER} เรียบร้อยแล้ว")

    print(f"--- เริ่มสร้าง QR Code จำนวน {TOTAL_TABLES} รูป ---")

    for i in range(1, TOTAL_TABLES + 1):
        table_num = i
        full_url = f"{BASE_URL}?table={table_num}"

        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
        qr.add_data(full_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        filename = os.path.join(folder_path, f"table_{table_num}.png")
        img.save(filename)
        print(f"✅ สร้าง table_{table_num}.png สำเร็จ")

    print("\n🎉 เสร็จสิ้น! กำลังเปิดโฟลเดอร์ให้ครับ...")

    # คำสั่งพิเศษสำหรับ Mac เพื่อให้เด้งเปิดโฟลเดอร์ขึ้นมาดูรูปได้เลย!
    os.system(f'open "{folder_path}"')


if __name__ == "__main__":
    generate_qrs()