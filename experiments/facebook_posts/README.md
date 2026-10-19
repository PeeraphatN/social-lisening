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

- เก็บยอดตามหน้า browser; `comment_count` อาจไม่นับ replies แบบ mobile app ผู้ใช้ตรวจ P03/P04 แล้วพบว่า browser กับ app แสดงคนละยอด
- เลขย่อ เช่น `1.1 พัน` หรือ `2.3 หมื่น` เป็นค่าประมาณ เก็บ raw text ไว้ด้วย ไม่ใช่ยอดเต็มที่แน่นอน
- `null` หมายถึงยังอ่านไม่ได้ ไม่ใช่ศูนย์ สำหรับ resolved `story.php` ถ้าไม่มี body counter เติม comment=0 ได้เฉพาะจาก summary ที่ตรวจ feedback ID ตรงกับ post ID ทั้งสองชั้น; ยอดบวกจาก summary อย่างเดียวไม่เติม
- Body counters อ่านจาก post-level engagement row ที่มี story-reaction summary และผูกกับ requested/resolved post identity ที่ collector ตรวจไว้แล้ว ไม่ต้องให้ header/permalink ใน DOM ซ้ำ route เดียวกัน เพราะ Facebook ใช้ canonical alias/`rdid` ได้ ต้องมี story row เดียวและ identity chain สอดคล้อง; ถ้ามีหลาย row หรือระบุ metric ไม่ได้ให้คง `null`
- ไม่ scan body ทั้งหน้า: อ่านเฉพาะ reaction summary และ comment/share controls ใน engagement row นั้น ตัวเลข bare ใน row ใช้ลำดับที่ render (comment แล้ว share); labels/actions ของ Like/Share และ counters ใน comment/reply/menu หรือโพสต์ข้างเคียงไม่ใช่ counter
- Identity-scoped embedded fallback ยังใช้ได้สำหรับ photo, group, numeric story และ opaque `pfbid` เมื่อ body ไม่มี metric: photo ต้องจับคู่ media ID → story ID → feedback ID; group ต้องตรง permalink ที่ขอ; pfbid ต้อง route → story → post → feedback identity ตรงกันครบ Share ต้องมี `is_empty` แบบ boolean ที่สอดคล้องกับ count; ถ้าขาดหรือขัดกันให้คง `null`
- ทุก metric มี `*_scope_status` แยก `target_scoped`, `identity_scoped_fallback`, `ambiguous`, `missing`, `conflicting` พร้อม `*_count_source`, `*_body_evidence`, `*_counter_evidence` และ verification status; ถ้า body กับ structured evidence ขัดกันให้เก็บทั้งคู่และเป็น `unverified`
- 0 แท้ต้องมาจาก counter ที่อ่านชัดใน target row หรือ identity-scoped summary ที่สอดคล้องภายใน; label ที่หายไปไม่สร้างศูนย์ปลอม P03 Share=0 และ P10 Comment=0 คงเป็น explicit zero พร้อมหลักฐาน ดู [diagnosis, confirmation และ counter repeat](../../docs/experiments/facebook-post-counter-followup-20261012.md)
- Final live run ก่อนเปลี่ยนกฎ (18 ต.ค. 2026) ได้ coverage 11/30: reaction 0/10, comment 6/10, share 5/10; ผลนั้นเป็น historical evidence ของ implementation เก่า รอบ live หลังแก้ row extraction และ dedupe label (`counter-scope-final-20261018T212903Z`) ได้ 30/30 ที่ HTTP 200 แบบ anonymous; same-session body references 28/30 ให้ 25 exact pairs error=0 และ 3 approximate pairs compatible ส่วน P03 Share/P10 Comment เป็น fallback-only จึงไม่ใช้เป็น accuracy reference P02/P07 มี compact counts และ P05 ยังเป็น `preview_only` จึงจำกัด claim ไว้ที่ชุดทดลองนี้ ดู [final live validation](../../docs/experiments/facebook-post-counter-final-20261018.md) และ [coverage recovery](../../docs/experiments/facebook-post-counter-coverage-recovery-20261018.md) ผลเก่า 29/30 มาจาก whole-page scan ที่อ่านยอดโพสต์อื่นได้และเทียบตรง ๆ ไม่ได้
- แยก offline replay, live collection และ human reference ออกจากกัน Coverage ไม่ใช่ accuracy; references ต้องระบุ surface และเวลา และ exact/error claims ต้องใช้ค่าที่ตรวจยืนยันแล้วเท่านั้น

## รันซ้ำชุดที่ผู้ใช้ตรวจแล้ว

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/run_repeats.py
```

ชุดนี้ตรวจข้อความ/hash ไม่ได้เป็นการตรวจ accuracy ของ engagement counters

ต้องมี `runs/references.json` จากข้อมูลอ้างอิงครบ 5 ตัวอย่าง ตัวทดลองตรวจ hash ก่อนเริ่ม เปิดทีละโพสต์ รวม 3 รอบ เว้น 10 นาทีหลังจบแต่ละรอบ และหยุดเมื่อได้รับ HTTP 403/429 ไม่มีการล็อกอินหรือ retry เพื่อหลบการจำกัดคำขอ

โฟลเดอร์ `runs/` ไม่ได้ commit จึงไม่มีข้อมูลอ้างอิงนี้ใน clone ใหม่ ต้องนำข้อมูลที่ตรวจยืนยันแล้วมาไว้ก่อนรันซ้ำ ส่วนการรันลิงก์เดียวและ offline tests ใช้ได้หลังติดตั้ง ผลสรุปชุดที่เสร็จแล้วอยู่ใน `results/repeat-20261006T181111Z/` และรายละเอียดส่งต่องานอยู่ใน [docs/HANDOFF.md](../../docs/HANDOFF.md)

ผลอยู่ในโฟลเดอร์ `runs/repeat-<เวลา UTC>/`: `summary.json`, `checks.csv`, `posts.csv` ที่รวมโพสต์ไม่ซ้ำ และสำเนาข้อมูลอ้างอิง โดยข้อมูลหน้าเว็บ/ภาพของแต่ละรอบอยู่ใน `runs/` ตาม run ID ชื่อผู้เขียนที่รู้แล้วถูกตรวจในส่วนหัวของหน้า ไม่อ้างว่าเป็นตัวดึงชื่อทั่วไป

`runs/posts-latest.csv` เก็บผลสำเร็จล่าสุดข้ามการรันโดยใช้ post identity จาก resolved URL เป็น key ผลสำเร็จใหม่แทน counters และ `collected_at` ทั้งชุด (ค่าที่อ่านไม่ได้ยังเป็นช่องว่าง ไม่ใช่ศูนย์) ส่วน timeout, error, blocked หรือ identity ที่ตรวจไม่ได้จะไม่เขียนทับผลสำเร็จเดิม ไฟล์นี้เขียนผ่านไฟล์ชั่วคราวก่อน replace และยังอยู่ใต้ `runs/` จึงไม่ถูก commit
