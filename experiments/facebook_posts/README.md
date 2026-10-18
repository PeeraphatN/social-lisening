# ทดลองดึงโพสต์ Facebook ฟรีบนเครื่อง

ตัวทดลองหนึ่งโพสต์แบบไม่ล็อกอิน ผลต้องตรวจด้วยมือก่อนนับว่าข้อความครบ แผนและผล P01 อยู่ใน `docs/experiments/`

## รันเมื่อมี environment แล้ว

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/inspect_browser.py https://www.facebook.com/share/p/19TTvcsmZ8/ --run-id p01-browser-02
```

ผลอยู่ใน `experiments/facebook_posts/runs/` เป็น CSV, ข้อความ, JSON สำหรับตรวจ และภาพหน้าจอ รวมถึง `*-page.html` และ `*-body.txt` สำหรับ replay snapshot โดยไม่ร้องขอ Facebook ซ้ำ หลักฐานทั้งหมดเก็บ local ในโฟลเดอร์ที่ไม่ commit ตัวอ่าน DOM ยังจำกัดตามหน้าโพสต์ที่ทดสอบ ไม่รับประกันใช้ได้กับ Facebook ทุกลิงก์

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

## ความหมายและหลักฐานของ engagement counters

- เก็บยอดตามหน้า browser; ไม่รับประกันว่า `comment_count` รวม replies แบบ mobile app ผู้ใช้ตรวจ P03/P04 แล้วพบว่า browser กับ app แสดงคนละยอด
- เลขย่อ เช่น `1.1 พัน` หรือ `2.3 หมื่น` เป็นค่าประมาณ เก็บ raw text ไว้ด้วย ไม่ใช่ยอดเต็มที่แน่นอน
- `null` หมายถึงยังอ่านหรือยืนยันไม่ได้ ไม่ใช่ศูนย์ สำหรับ resolved `story.php` สามารถเติม comment=0 จาก summary ที่ตรวจ feedback ID ตรงกับ post ID ทั้งสองชั้น
- Photo/group ที่ counter เป็นไอคอน ใช้ embedded UFI summary เติมเฉพาะยอดที่ขาด พร้อม `*_count_source` และ `*_counter_evidence`: photo ต้องจับคู่ media ID → story ID → feedback ID; group ต้องตรง permalink ที่ขอ ไม่ใช้ยอดจากโพสต์อื่น
- ยอดที่อ่านจาก body text ยังสแกนทั้งหน้า ไม่ถือว่า target scope ได้รับการยืนยันทุก metric
- Opaque `pfbid` ใช้ embedded UFI summary ได้เมื่อ route → story → post → feedback identity ตรงกันครบและมี candidate เดียว ข้อมูล Share ต้องมี `is_empty` แบบ boolean ที่สอดคล้องกับ count; ถ้าขาด ขัดกัน หรือกำกวมให้คง `null`
- P03 Share=0 อ่านได้จาก identity-scoped summary แล้ว ผล live ใหม่ยืนยัน P03 Comment=4/Share=0 และ P04 Comment=1/Share=414; ค่าบวกของ P04 ตรงกับ body ดู [diagnosis, confirmation และ counter repeat](../../docs/experiments/facebook-post-counter-followup-20261012.md)
- แยก offline replay, live collection และ human reference ออกจากกัน การอ่านได้เป็น coverage ไม่ใช่หลักฐาน accuracy; reference ต้องระบุ surface และเวลาที่ตรวจ เลขที่เปลี่ยนตามเวลาหรือ scope ต่างกันไม่ใช้ตั้ง tolerance โดยอัตโนมัติ

## รันซ้ำชุดที่ผู้ใช้ตรวจแล้ว

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/run_repeats.py
```

ชุดนี้ตรวจข้อความ/hash ไม่ได้เป็นการตรวจ accuracy ของ engagement counters

ต้องมี `runs/references.json` จากข้อมูลอ้างอิงครบ 5 ตัวอย่าง ตัวทดลองตรวจ hash ก่อนเริ่ม เปิดทีละโพสต์ รวม 3 รอบ เว้น 10 นาทีหลังจบแต่ละรอบ และหยุดเมื่อได้รับ HTTP 403/429 ไม่มีการล็อกอินหรือ retry เพื่อหลบการจำกัดคำขอ

โฟลเดอร์ `runs/` ไม่ได้ commit จึงไม่มีข้อมูลอ้างอิงนี้ใน clone ใหม่ ต้องนำข้อมูลที่ตรวจยืนยันแล้วมาไว้ก่อนรันซ้ำ ส่วนการรันลิงก์เดียวและ offline tests ใช้ได้หลังติดตั้ง ผลสรุปชุดที่เสร็จแล้วอยู่ใน `results/repeat-20261006T181111Z/` และรายละเอียดส่งต่องานอยู่ใน [docs/HANDOFF.md](../../docs/HANDOFF.md)

ผลอยู่ในโฟลเดอร์ `runs/repeat-<เวลา UTC>/`: `summary.json`, `checks.csv`, `posts.csv` ที่รวมโพสต์ไม่ซ้ำ และสำเนาข้อมูลอ้างอิง โดยข้อมูลหน้าเว็บ/ภาพของแต่ละรอบอยู่ใน `runs/` ตาม run ID ชื่อผู้เขียนที่รู้แล้วถูกตรวจในส่วนหัวของหน้า ไม่อ้างว่าเป็นตัวดึงชื่อทั่วไป
