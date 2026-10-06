# ทดลองดึงโพสต์ Facebook ฟรีบนเครื่อง

ตัวทดลองหนึ่งโพสต์แบบไม่ล็อกอิน ผลต้องตรวจด้วยมือก่อนนับว่าข้อความครบ แผนและผล P01 อยู่ใน `docs/experiments/`

## รันเมื่อมี environment แล้ว

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/inspect_browser.py https://www.facebook.com/share/p/19TTvcsmZ8/ --run-id p01-browser-02
```

ผลอยู่ใน `experiments/facebook_posts/runs/` เป็น CSV, ข้อความ, JSON สำหรับตรวจ และภาพหน้าจอ ตัวอ่าน DOM ยังจำกัดตามหน้าโพสต์ที่ทดสอบ ไม่รับประกันใช้ได้กับ Facebook ทุกลิงก์

## ติดตั้งใหม่ในโฟลเดอร์โปรเจกต์

```powershell
python -m venv experiments/facebook_posts/.venv
.\experiments\facebook_posts\.venv\Scripts\python.exe -m pip install -r experiments/facebook_posts/requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'experiments\facebook_posts\.playwright'
.\experiments\facebook_posts\.venv\Scripts\python.exe -m playwright install chromium
```

## ตรวจ parser โดยไม่เชื่อมต่อ Facebook

```powershell
python -m unittest discover -s experiments/facebook_posts -p 'test_*.py'
```

`probe_post.py` ใช้ Python standard library เพื่อเปรียบเทียบผล HTTP กับ browser ส่วน `export_p01.py` ส่งออกผล P01 ที่มีอยู่แล้วโดยไม่ร้องขอหน้าเว็บซ้ำ ไม่มีการใช้งาน proxy หรือบริการ scraping เสียเงิน

## รันซ้ำชุดที่ผู้ใช้ตรวจแล้ว

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/run_repeats.py
```

ต้องมี `runs/references.json` จากข้อมูลอ้างอิงครบ 5 ตัวอย่าง ตัวทดลองตรวจ hash ก่อนเริ่ม เปิดทีละโพสต์ รวม 3 รอบ เว้น 10 นาทีหลังจบแต่ละรอบ และหยุดเมื่อได้รับ HTTP 403/429 ไม่มีการล็อกอินหรือ retry เพื่อหลบการจำกัดคำขอ

โฟลเดอร์ `runs/` ไม่ได้ commit จึงไม่มีข้อมูลอ้างอิงนี้ใน clone ใหม่ ต้องนำข้อมูลที่ตรวจยืนยันแล้วมาไว้ก่อนรันซ้ำ ส่วนการรันลิงก์เดียวและ offline tests ใช้ได้หลังติดตั้ง ผลสรุปชุดที่เสร็จแล้วอยู่ใน `results/repeat-20261006T181111Z/` และรายละเอียดส่งต่องานอยู่ใน [docs/HANDOFF.md](../../docs/HANDOFF.md)

ผลอยู่ในโฟลเดอร์ `runs/repeat-<เวลา UTC>/`: `summary.json`, `checks.csv`, `posts.csv` ที่รวมโพสต์ไม่ซ้ำ และสำเนาข้อมูลอ้างอิง โดยข้อมูลหน้าเว็บ/ภาพของแต่ละรอบอยู่ใน `runs/` ตาม run ID ชื่อผู้เขียนที่รู้แล้วถูกตรวจในส่วนหัวของหน้า ไม่อ้างว่าเป็นตัวดึงชื่อทั่วไป
