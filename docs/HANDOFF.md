# ส่งต่องานให้ agent — 8 ตุลาคม 2026

## เริ่มอ่านตรงนี้

ชื่อชุดโปรแกรมคือ **Facebook Collector** ตอนนี้ยังเป็นงานทดลอง รับลิงก์โพสต์สาธารณะที่ทราบแล้ว เก็บข้อความและจำนวน reaction/comment/share ที่อ่านได้ ยังไม่พร้อมใช้งานจริง

1. ทำงานต่อบน `experiment/facebook-post-scraping-data` ซึ่ง push งานล่าสุดแล้ว
2. อ่าน [issue #2: งานที่ต้องทำก่อนปล่อยรุ่นแรก](https://github.com/PeeraphatN/social-lisening/issues/2) และ [ผลตรวจ counter กับ DOM จริง](https://github.com/PeeraphatN/social-lisening/issues/2#issuecomment-6044843301)
3. อ่าน [วิธีติดตั้งและรัน](../experiments/facebook_posts/README.md) แล้วรัน `python -m unittest discover -s experiments/facebook_posts -p 'test_*.py'` จาก root ของ repo: ล่าสุดผ่าน 13 tests
4. งานถัดไปคือจำกัดการอ่าน counter ให้เฉพาะโพสต์เป้าหมาย และรองรับ counter แบบตัวเลขข้างไอคอน โดยเพิ่ม regression test จากหน้าที่ตรวจจริง

## Branch และข้อควรระวัง

- `experiment/facebook-post-scraping-data` เก็บโค้ดทดลองล่าสุด รวม commit `ed16cb8` ที่เพิ่ม engagement metrics
- `master` เป็น default branch บน GitHub และ push commit `3850559` แล้ว ซึ่ง revert งานทดลอง `aad7cad` ออก เนื้อหาไฟล์ ณ commit นี้ตรงกับ `6e33afe`
- ลบ local branch `feat/add-facebook-post-scraping-data` ที่ซ้ำแล้ว
- เมื่อเริ่มรุ่นแรกตาม issue #2 ให้แยก `feat/facebook-collector-post` จาก master และคืนการเปลี่ยนแปลงที่เคย revert พร้อมนำงานใหม่เข้ามา การ merge branch ทดลองอย่างเดียวจะไม่คืนไฟล์ที่ master เคย revert
- ตรวจ `git status` ก่อนเริ่ม มีไฟล์ untracked จากเครื่องมือที่ยังไม่ได้จัดการ ห้ามรวมเข้า commit โดยอัตโนมัติ

## ปัญหาที่ตรวจพบล่าสุด

- P02 และ P05 ลิงก์เดิมแสดงจำนวน comment/share เป็นตัวเลขข้างไอคอน ไม่มีคำกำกับ parser ปัจจุบันจึงคืน null แม้หน้าเว็บมีตัวเลข ดู [issue #1](https://github.com/PeeraphatN/social-lisening/issues/1) และผลตรวจใน issue #2; ปัญหานี้ไม่ได้เกิดเฉพาะ photo page
- comment ของ P03/P04 ที่อ่านได้ 1 ตรงกับตัวเลขของโพสต์บนหน้าเว็บ แต่ยังไม่ยืนยันยอดรวมที่นับ replies ด้วย
- parser อ่าน body ทั้งหน้า ยังเสี่ยงหยิบตัวเลขจากความคิดเห็นหรือโพสต์อื่น
- P05 ลิงก์กลุ่มเดิมยังได้ `preview_only`; permalink เจาะจงโพสต์เคยดึงข้อความได้ ต้องรายงานว่าใช้ URL ใด ไม่เปลี่ยนเงียบ ๆ
- เก็บค่าที่อ่านไม่ได้เป็น null ไม่ถือว่าเป็น 0 และไม่ถือว่าตัวเลขที่อ่านซ้ำได้คือถูกต้องแล้ว

รุ่นแรกจะรับ public URL แล้วเก็บข้อความและผลแต่ละรอบพร้อมเวลาเก็บ การค้นหาด้วย keyword และการดึงข้อความ comment แยกทำภายหลัง ไม่ต้องรอสองงานนี้ก่อนปล่อยรุ่นแรก

## เป้าหมายและข้อกำหนดของผู้ใช้

สร้างระบบ social listening เป็นทรัพย์สินบริษัท Turnkey Communication Services / TKC เพื่อดูการพูดถึงบริษัทจากพื้นที่สาธารณะและข่าวภาษาไทย รวมถึงความเห็นเชิงบวก ลบ และเป็นกลาง บริษัทมีความคิดเห็นบนเพจของตนเองน้อย จึงต้องการแหล่งภายนอกเพจด้วย

- ใช้เครื่องมือฟรี 100% และรันบนเครื่องได้ ผู้ใช้ปฏิเสธ Apify
- อธิบายเป็นภาษาไทย สั้น ชัด และแบ่งงานเป็นขั้นเล็ก ผู้ใช้เปิด ADHD mode
- การทดลองนี้ใช้ browser แบบไม่ล็อกอิน หยุดเมื่อ HTTP 403/429 และไม่มี proxy หรือการหลบ CAPTCHA
- ตัวอย่างทั้ง 5 เป็นชุดทดสอบทางเทคนิค ไม่ใช่ชุดข้อมูลความรู้สึกต่อ TKC

## โค้ดที่มี

| ไฟล์ใน `experiments/facebook_posts/` | หน้าที่ |
| --- | --- |
| `probe_post.py` | HTTP ด้วย standard library และอ่าน metadata/embedded JSON; ข้อความที่พบยังต้องตรวจยืนยัน |
| `inspect_browser.py` | Playwright Chromium แบบ headless ไม่ล็อกอิน เก็บข้อความ จำนวน engagement ข้อมูลดิบ hash ข้อความ ระยะเวลา JSON/CSV และ screenshot |
| `run_repeats.py` | เทียบข้อมูลอ้างอิง 5 โพสต์ 3 รอบ เว้น 600 วินาทีหลังจบรอบ และรวมผลไม่ซ้ำ |
| `export_p01.py` | ส่งออก P01 จากไฟล์ผลเดิมบนเครื่อง ไม่ร้องขอ Facebook ใหม่ |
| `test_probe_post.py`, `test_repeats.py` | 13 offline tests สำหรับ parser และการเทียบผล |

## หลักฐานและการรันจาก clone ใหม่

Session ที่เสร็จแล้ว: `repeat-20261006T181111Z` มีผลตรงกัน 15/15 ครั้ง รวมข้อความล่าสุด 5 โพสต์ 8,605 อักขระ รายงานอยู่ใน `docs/experiments/` และสำเนา `summary.json`/`checks.csv` ที่ไม่มีเนื้อหาโพสต์เต็มอยู่ใน `experiments/facebook_posts/results/repeat-20261006T181111Z/`

ข้อมูลดิบ ข้อความเต็ม ภาพหน้าจอ และข้อมูลอ้างอิงที่ผู้ใช้ยืนยันอยู่บนเครื่องเดิมใน `experiments/facebook_posts/runs/` ซึ่งถูก gitignore เช่นเดียวกับ `.venv/`, `.playwright/`, `.auth/` และ `__pycache__/` ไฟล์เหล่านี้ไม่ได้มากับ clone ใหม่

จาก clone ใหม่ติดตั้งตาม README แล้วรันลิงก์เดียวและ offline tests ได้ ส่วน `run_repeats.py` ต้องมี `runs/references.json` ของทั้ง 5 ตัวอย่างพร้อม hash และการยืนยันข้อความก่อน ไฟล์สรุปผลไม่สามารถใช้แทนข้อความอ้างอิงได้ ห้ามถือว่าข้อความที่เก็บใหม่ผ่านการตรวจของผู้ใช้จากการยืนยันรอบเก่า

## ข้อจำกัดที่ต้องรักษาให้ชัดเจน

- ผลผ่านครอบคลุม 5 ลิงก์ในช่วงประมาณ 21 นาทีเท่านั้น ยังไม่ยืนยันความเสถียรระยะยาวหรือ Facebook ทุกประเภทโพสต์
- ตรวจชื่อผู้เขียนที่รู้แล้วในส่วนหัวของหน้า ยังไม่มีตัวดึงผู้เขียนทั่วไป และไม่มีเวลาตีพิมพ์แบบ absolute ที่ยืนยันแล้ว
- P05 ใช้ canonical URL `/groups/1108191221217612/posts/1455325143170883/` จาก ID ในลิงก์เดิม ตัวรันอ้าง `fetch_url` ใน reference; ยังไม่ได้ canonicalize group URL อัตโนมัติ
- P04 มีรูปและ URL ในข้อความ ยังไม่ได้ทดสอบกล่อง link preview ข่าว; ข้อความ DOM อาจย่อ URL หรือแทน emoji จึงเก็บข้อความ embedded JSON
- การค้นหาโพสต์ด้วย keyword คอมเมนต์ OCR วิดีโอ sentiment และเว็บ dashboard ยังไม่มี implementation

## อ่านเพิ่มเฉพาะเมื่อเกี่ยวข้องกับโจทย์ใหม่

แผนเดิม: [facebook-post-experiment.md](experiments/facebook-post-experiment.md)

การค้นหาบริษัทและแหล่งข้อมูล: [tkc-public-discussion.md](research/tkc-public-discussion.md)

ทางเลือก Facebook scraping: [facebook-scraping-options.md](research/facebook-scraping-options.md)

แนวคิดเริ่มต้น: [free-thai-social-listening.md](research/free-thai-social-listening.md) — ข้อเสนอใช้เพจบริษัทในช่วงแรกถูกแทนที่ด้วยความต้องการติดตามพื้นที่สาธารณะแล้ว

งานค้นหา keyword ให้แยก issue เมื่อเริ่มทำ และแยกผลค้นพบลิงก์ออกจากผลดึงข้อความเสมอ ส่วน checklist รุ่นแรกติดตามใน issue #2 ไม่ต้องคัดลอกผลทดสอบทั้งหมดมาไว้ในเอกสารนี้
