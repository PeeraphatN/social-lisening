# Facebook counter coverage recovery — 18 ต.ค. 2026

## อัปเดตล่าสุด

หลังยืนยันว่า collector เลือกโพสต์เป้าหมายผ่าน requested/resolved identity chain ได้แล้ว ผ่อนเงื่อนไข body counter: ไม่บังคับให้ header/permalink ใน DOM ต้องยืนยัน route ซ้ำ ใช้ post-level story engagement row ที่มี story-reaction summary และมี candidate เดียวแทน ยังคงไม่ scan body ทั้งหน้า และยังปฏิเสธแถวซ้ำ/กำกวม

P02/P05 ที่เคยถูกนับว่า Reaction ขัดกันจริง ๆ ไม่ขัดกัน: P02 แสดง Reaction 1.1 พัน, Comment 374, Share 353; P05 แสดง Reaction 395, Comment 77, Share 79 ตัวเลข 353/79 เป็น Share ไม่ใช่ Reaction และ Like/Love subtype counts ไม่ใช่ยอด Reaction รวม

## ผลที่ได้

Replay HTML ที่บันทึกไว้จาก final run เดิม (`counter-scope-final-20261018T202456Z`) ด้วย parser ใหม่แบบ offline ไม่ได้เปิด Facebook ซ้ำ:

| Sample | Reaction | Comment | Share |
| --- | ---: | ---: | ---: |
| P01 | 170 | 72 | 76 |
| P02 | 1.1 พัน (ประมาณ) | 374 | 353 |
| P03 | 24 | 4 | 0 |
| P04 | 275 | 1 | 414 |
| P05 | 395 | 77 | 79 |
| P06 | 61 | 3 | 102 |
| P07 | 3.9 หมื่น (ประมาณ) | 542 | 1.5 พัน (ประมาณ) |
| P08 | 71 | 2 | 40 |
| P09 | 53 | 30 | 3 |
| P10 | 7 | 0 | 6 |

Coverage จาก saved snapshot รอบนี้ได้ 30/30: Reaction 10/10, Comment 10/10, Share 10/10; Reaction 2 ค่าและ Share 1 ค่าเป็น approximate จาก compact notation ค่า 0 ของ P03 Share และ P10 Comment ยังคงมีหลักฐาน ไม่ได้อนุมานจาก label ที่หายไป

## ที่เจอ

- Counter row ของ Facebook ไม่ได้ติด label กับทุกตัวเสมอ บาง layout render ตัวเลข Comment แล้ว Share เป็น bare counts ในแถวเดียว จึงอ่านตามลำดับภายในแถวเท่านั้น
- Reaction ต้องใช้ยอดรวมที่ตามหลัง `ความรู้สึกทั้งหมด`/`All reactions`; ห้ามใช้ Like/Love subtype หรือ action button `ถูกใจ` เป็นยอด Reaction
- Header permalink อาจเป็น canonical alias/มี `rdid`; require ให้ซ้ำ route identity ทำให้ข้อมูลใน post row ที่เลือกไว้ถูกทิ้งทั้งที่ URL identity chain ผ่าน

## แก้แล้ว

- ใช้ story-level reaction summary เป็น anchor ของ engagement row แล้วอ่านเฉพาะ labels/counters ใน row เดียวกัน
- Bare Comment/Share รับตามลำดับใน row; action labels, comment/reply, menu และ nested article ไม่ถูกนำมารวม
- ถ้า identity chain ไม่สอดคล้องหรือมีหลาย story rows ให้ fail closed; identity-scoped structured fallback และ null-vs-zero rules ยังอยู่
- เพิ่ม browser-seam regressions สำหรับ P02/P05 row ordering, Reaction total เทียบกับ Like/Love breakdown, P04 label order, alias route, reply exclusion และ duplicate/conflicting rows
- Offline suite ผ่าน 107/107 tests

## ยังไม่สรุป

30/30 เป็น coverage ของ offline replay เท่านั้น ไม่ใช่ live validation รอบใหม่หรือ accuracy claim รอบใหม่ ตัวเลขที่ parse ได้ตรงกับ saved rendered row แต่ยังต้องตรวจ reference/accuracy แยกจาก coverage; compact notation ไม่ถูกนับเป็น exact

## งานต่อ

- รัน final anonymous P01–P10 ใหม่หลัง freeze source hashes เว้นอย่างน้อย 20 วินาทีต่อ URL และหยุดตาม stop conditions เดิม
- สร้าง/ตรวจ browser reference manifest จาก saved evidence ที่ metric association ถูกต้อง แล้ว re-score
- อัปเดต #6/#8 ด้วย coverage และ accuracy แยกกัน; ยังไม่ปิด #2 จนตรวจ release criteria ของ #2 ครบ

สรุป replay machine-readable อยู่ใน ignored `experiments/facebook_posts/runs/counter-scope-final-20261018T202456Z-coverage-replay.json`; raw HTML/body/screenshot ไม่ได้เพิ่มเข้า Git.