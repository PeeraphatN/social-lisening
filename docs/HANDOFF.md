# ส่งต่องานให้ agent — 12 ตุลาคม 2026

## เริ่มอ่านตรงนี้

เป้าหมายแรกคือ **Facebook Collector**: keyword → ค้นพบ URL โพสต์สาธารณะ → เก็บข้อมูลโพสต์ → เก็บข้อความความคิดเห็น ใช้กับแบรนด์ องค์กร บุคคล หรือหัวข้อที่ผู้ใช้กำหนดเอง รายละเอียดเป้าหมาย เกณฑ์จบ และสถานะงานติดตามใน [goal #3](https://github.com/PeeraphatN/social-lisening/issues/3)

1. อ่าน goal #3 และ [issue #2: facebook-post-scraping](https://github.com/PeeraphatN/social-lisening/issues/2) รวมคอมเมนต์ล่าสุดผ่าน `gh` ก่อนเริ่มงาน ใช้ issue เป็นที่อ้างอิงหลักเมื่อเอกสารใน branch เก่ามีข้อมูลไม่ตรงกัน
2. ตรวจ `git status --short --branch` และ `git worktree list` งานโค้ดต่ออยู่บน `experiment/facebook-post-scraping-data`; ตอนตรวจ handoff worktree `C:/dev/social-lisening` อยู่ `master` และ branch ทดลองเปิดอยู่ในอีก worktree ให้ทำงานใน worktree ของ branch ทดลอง
3. อ่าน [วิธีติดตั้งและรันบน branch ทดลอง](https://github.com/PeeraphatN/social-lisening/blob/experiment/facebook-post-scraping-data/experiments/facebook_posts/README.md) แล้วรัน `python -m unittest discover -s experiments/facebook_posts -p 'test_*.py'` จาก root ของ worktree นั้น รายงานวันที่ 8 ตุลาคมบน branch ทดลองผ่าน 13/13 ส่วน baseline 9 tests ในเอกสารเดิมเป็นผลก่อนเพิ่ม metrics; master ปัจจุบัน revert โค้ดทดลองออกแล้ว ให้ตรวจผลใหม่บน branch ทดลองก่อนอ้างว่า tests ปัจจุบันผ่าน
4. ทำ #2 ต่อ: จำกัดการอ่านข้อความ/counter ให้เฉพาะโพสต์เป้าหมาย และตรวจ counter แบบตัวเลขข้างไอคอน ปัญหา P02 หน้า photo อยู่ใน [issue #1](https://github.com/PeeraphatN/social-lisening/issues/1)
5. ทำ #2 ให้ผ่านเกณฑ์ก่อน แล้วต่อ #4 → #5 → ตรวจเส้นทางรวมของ goal #3 เก็บผลตรวจและข้อจำกัดใน issue ที่เกี่ยวข้อง

## Goal และ issue ที่จัดแล้ว

| Issue | หน้าที่ | สถานะเมื่อตรวจ 12 ตุลาคม |
| --- | --- | --- |
| [#3 Facebook Collector](https://github.com/PeeraphatN/social-lisening/issues/3) | Goal แรกและเกณฑ์จบเส้นทาง keyword → post → comments | เปิด; มี sub-issues #2, #4, #5 |
| [#2 facebook-post-scraping](https://github.com/PeeraphatN/social-lisening/issues/2) | รับ URL แล้วเก็บข้อความ ยอด reaction/comment/share และเวลาเก็บ | งานทดลองที่ต้องทำต่อ; มี sub-issue #1 |
| [#1 photo-page metrics](https://github.com/PeeraphatN/social-lisening/issues/1) | แก้ comment/share ของ P02 หน้า photo | เปิด |
| [#4 facebook-post-search](https://github.com/PeeraphatN/social-lisening/issues/4) | รับ keyword แล้วค้นพบ URL โพสต์ | วางแผนแล้ว; ยังไม่มี implementation ที่ยืนยันในงานนี้ |
| [#5 facebook-comment-scraping](https://github.com/PeeraphatN/social-lisening/issues/5) | รับ URL แล้วเก็บข้อความความคิดเห็น | วางแผนแล้ว; ยังไม่ได้ทดลองเก็บข้อความความคิดเห็น |

ทั้งสาม feature เป็น sub-issues จริงบน GitHub พร้อมเกณฑ์จบ วิธีตรวจ และ dependency งานรับ URL ทดสอบแยกจาก search ได้ และ comment scraping ทดลองจาก URL ที่รู้แล้วได้โดยไม่จำเป็นต้องรอ search เสร็จ ลำดับ #2 → #4 → #5 เป็นลำดับทำงานที่ตกลงไว้ ส่วน sentiment, dashboard และแพลตฟอร์มอื่นอยู่นอก goal แรก

## Branch และงานล่าสุดใน session นี้

- งานทดลอง `experiment/facebook-post-scraping-data` รวม commit `ed16cb8` ที่เพิ่ม metrics แล้ว ก่อน sync handoff ตรวจ worktree อยู่ที่ `0aa06bc`; ใช้ `git worktree list` หาที่ทำงานแทนการเปลี่ยน branch ในโฟลเดอร์ master
- `master` มี commit `3850559` ซึ่ง revert งานทดลองออกแล้ว เมื่อจะนำงานกลับเข้า master ต้องคืนการเปลี่ยนแปลงที่เคย revert ด้วย การ merge branch ทดลองอย่างเดียวไม่คืนไฟล์เหล่านั้น ดู [บันทึกจัด branch](https://github.com/PeeraphatN/social-lisening/issues/2#issuecomment-6044944137)
- งานจัด goal/issue ใช้ `gh` และ `gh api` ผ่าน auth ของ CLI ไม่มีการติดตั้ง GitHub integration แยก
- งานจัด issue และอัปเดต handoff นี้ไม่ได้แก้ implementation หรือรัน Facebook/tests ใหม่ ผลเทคนิคด้านล่างเป็นหลักฐานจากรอบที่ระบุวันที่ไว้
- ตรวจรายการ staged/untracked ก่อน commit และรวมเฉพาะงานที่ตั้งใจเปลี่ยน การ sync handoff ใช้ commit เอกสารแยกจาก implementation และไฟล์ตั้งค่าเครื่องมือ

## ผลทดลองที่ผ่านและงานที่ยังไม่ผ่าน

งานทดลอง **ข้อความจาก URL ที่ทราบแล้ว** ผ่าน 15/15 ครั้งเมื่อ 7 ตุลาคม: ผู้ใช้ตรวจข้อความทั้ง 5 ตัวอย่าง และทดลองซ้ำ 3 รอบ เว้น 10 นาทีหลังจบแต่ละรอบ ดู [ผลทดลองและข้อจำกัด](experiments/facebook-post-repeat-results.md) ผลนี้ไม่ครอบคลุม keyword search, counter หรือข้อความความคิดเห็น

ตาม [ผลตรวจ counter วันที่ 8 ตุลาคม](https://github.com/PeeraphatN/social-lisening/issues/2#issuecomment-6044843301) ยังต้องแก้ scope ของ parser, comment/share แบบไอคอนของ P02/P05, ข้อความ P05 ลิงก์กลุ่มเดิมที่เป็น `preview_only` และการทดสอบซ้ำของ counter P03 share ยังยืนยันไม่ได้ และ comment ของ P03/P04 ยังไม่ยืนยันว่ารวม replies จึงยังไม่ใช่รุ่นพร้อมใช้

## เป้าหมายและข้อกำหนดของผู้ใช้

โปรเจกต์เปิด public และวางเป็นเครื่องมือทั่วไป ผู้ใช้กำหนดคำค้น/เป้าหมายเอง เอกสารเป้าหมายและ issue ใช้คำอธิบายทั่วไปโดยไม่ผูกกับบริษัทเฉพาะ งาน social listening และ sentiment เป็นทิศทางต่อจาก collector ตาม goal ที่แยกภายหลัง

- ใช้เครื่องมือฟรี 100% และรันบนเครื่องได้ ผู้ใช้ปฏิเสธ Apify
- อธิบายเป็นภาษาไทย สั้น ชัด และแบ่งงานเป็นขั้นเล็ก ผู้ใช้เปิด ADHD mode
- การทดลองนี้ใช้ browser แบบไม่ล็อกอิน หยุดเมื่อ HTTP 403/429 และไม่มี proxy หรือการหลบ CAPTCHA
- ตัวอย่างทั้ง 5 เป็นชุดทดสอบทางเทคนิค ไม่ใช่ชุดข้อมูล sentiment ของเป้าหมายที่ผู้ใช้เลือก

## โค้ดบน branch ทดลอง

| ไฟล์ใน `experiments/facebook_posts/` | หน้าที่ |
| --- | --- |
| `probe_post.py` | HTTP ด้วย standard library และอ่าน metadata/embedded JSON; ข้อความที่พบยังต้องตรวจยืนยัน |
| `inspect_browser.py` | Playwright Chromium แบบ headless ไม่ล็อกอิน เก็บข้อความ JSON/CSV และ screenshot; branch ทดลองเพิ่ม engagement metrics แล้ว |
| `run_repeats.py` | เทียบข้อมูลอ้างอิง 5 โพสต์ 3 รอบ เว้น 600 วินาทีหลังจบรอบ และรวมผลไม่ซ้ำ |
| `export_p01.py` | ส่งออก P01 จากไฟล์ผลเดิมบนเครื่อง ไม่ร้องขอ Facebook ใหม่ |
| `test_probe_post.py`, `test_repeats.py` | offline tests สำหรับ parser และการเทียบผล; จำนวน tests ต่างตาม branch ดู baseline ด้านบน |

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

ทางเลือก Facebook scraping: [facebook-scraping-options.md](research/facebook-scraping-options.md)

แนวคิดเริ่มต้น: [free-thai-social-listening.md](research/free-thai-social-listening.md) — ข้อเสนอใช้เพจบริษัทในช่วงแรกถูกแทนที่ด้วยความต้องการติดตามพื้นที่สาธารณะแล้ว

เมื่อต่อ keyword search ให้อ่าน #4 ก่อน เริ่มพิสูจน์ช่องทางค้นหาที่เข้าถึงได้จริง และแยกผลค้นพบลิงก์ออกจากผลดึงข้อความเสมอ เกณฑ์จบแต่ละ feature อยู่ใน issue ไม่ต้องคัดลอก checklist ทั้งหมดมาไว้ใน handoff
