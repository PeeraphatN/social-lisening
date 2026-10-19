# Facebook post target-scope regression — 20 ต.ค. 2026

## ผลที่ได้

Replay `counter-scope-final-20261018T212903Z-p01..p10` จาก saved HTML ชุดเดียวกัน โดยปิด page scripts/service workers และ fulfill/abort ทุก request ไม่มีการเรียก Facebook live:

| Source | Reaction | Comment | Share | Coverage | ต่างจาก saved counts |
| --- | ---: | ---: | ---: | ---: | ---: |
| `fd6a9eb^` | 10/10 | 10/10 | 10/10 | 30/30 | 0 |
| `fd6a9eb` | 2/10 | 8/10 | 7/10 | 17/30 | 13 |
| หลังแก้ | 10/10 | 10/10 | 10/10 | 30/30 | 0 |

P05 กลับมา Reaction=395, Comment=77, Share=79 และ `body_scope_status=target_scoped` ทำให้ rendered-message fallback กลับมาเป็น `candidate_text_unverified`/`rendered_dom_story_message` ไม่ได้ยืนยันว่าข้อความครบหรือผ่าน human verification

Replay saved HTML อีกชุด `scope-live-20261019T184904Z-p05` ยืนยันผลเดียวกัน: `fd6a9eb` ได้ Reaction=null, scope=`conflicting`, status=`preview_only`; หลังแก้ได้ 395/77/79, `target_scoped`, `candidate_text_unverified` รายงานอยู่ใน `runs/target-scope-regression-live-artifact-p05.json` เป็น offline replay ของ artifact เดิม

P02 Reaction=1100, P07 Reaction=39000/Share=1500 ยังคงเป็น approximate จาก compact notation; P03 Share=0 และ P10 Comment=0 ยังคงมาจาก identity-scoped embedded fallback

## สาเหตุและแก้แล้ว

- `fd6a9eb` ป้องกัน unrelated toolbar ด้วยเงื่อนไขที่บังคับ article/message และ DOM identity ซ้ำกับ URL ทำให้ row จริงถูกทิ้ง: P02 ไม่มี article ครอบ row หรือ `story_message`; P03/P04/P06/P08/P10 มีลิงก์ในข้อความ; P05/P09 มี numeric/slug group aliases
- คืนการรับ unique standalone story row เมื่อ requested/resolved identity ผ่าน และไม่มี populated article อื่นให้ row ยืม scope ส่วน row ใน article ยังต้องมี message เดียว ลิงก์ในเนื้อหาไม่ใช่ header identity และไม่ตัดสิทธิ์ story row
- DOM group header ยอมรับ numeric/slug alias เฉพาะ post ID เดียวกัน ไม่ผ่อน requested/resolved identity check; post ID ต่างกัน, numeric group IDs ขัดกัน, malformed headers และหลาย messages ยังถูก reject
- Toolbar ใน comment/menu/message/attachment ไม่ใช่ post-level evidence แต่ dialog และ complementary เป็น wrapper ของโพสต์จริงได้ นับหลาย toolbar ใน article เดียวเป็น ambiguous แทนการให้แถวหลังเขียนทับแถวแรก

## หลักฐานการทดสอบ

1. ก่อนแก้ production code: saved replay ยืนยัน 17/30 เทียบ parent 30/30; browser regression tests ล้มใน standalone P02/P05, linked-message และ group-alias cases
2. การใช้ blocked selector ทั้งชุดตัด dialog/complementary จริงออกและ replay เหลือ 13/30 จึงจำกัด selector ตาม ancestor จาก saved DOM และเพิ่ม wrapper regressions
3. ตรวจเพิ่มพบสอง toolbar ใน article เดียวถูกยุบเป็น row เดียว; regression test ล้มก่อนเพิ่มการนับ toolbar และผ่านหลังแก้
4. ผลสุดท้าย: offline suite ผ่าน 137 tests; replay 30/30, counts ตรง saved inspection ทั้ง 30 ค่า รวม standalone P02/P05 และ unrelated/detached row rejection

## รันซ้ำ

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe -m unittest discover -s experiments/facebook_posts -p 'test_*.py'
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/replay_target_scope.py --revision fd6a9eb --output experiments/facebook_posts/runs/target-scope-regression-fd6a9eb.json
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/replay_target_scope.py --revision 'fd6a9eb^' --output experiments/facebook_posts/runs/target-scope-regression-fd6a9eb-parent.json
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/replay_target_scope.py --output experiments/facebook_posts/runs/target-scope-regression-fixed.json
```

คำสั่ง `--revision fd6a9eb` ต้อง exit 1 เพื่อแสดง regression; parent และหลังแก้ exit 0 รายงานเก็บ source/HTML SHA-256, counts, scope/evidence, containers และ text status ใน ignored `runs/` ต้องมี raw saved HTML/inspection เดิมบนเครื่อง ไม่ commit raw evidence

ผลนี้ตรวจ regression บน snapshot เดิม ไม่ใช่ accuracy reference อิสระหรือผล live ใหม่

## ตรวจ seam เพิ่มตามข้อ 4

พบว่า summary ยังใช้ ancestor `innerText` ซึ่งรวม comment/menu/nested post ได้ และ loop ข้าม article ไปยืม summary จากโพสต์ข้างเคียงได้ เพิ่ม browser tests ให้ล้มก่อนแก้ แล้วจำกัดทั้ง summary และ controls ให้ใช้ ownership เดียวกัน: ตัด blocked subtrees, ไม่รับ controls ที่ครอบ comment/nested post และหยุดที่ขอบ article/dialog ก่อนถึง body

แก้เฉพาะ collector เดิม ไม่เปลี่ยน target identity API หรือเพิ่ม extraction path ผล suite ผ่าน 140 tests รวม standalone P02/P05, unrelated/duplicate/conflicting rows, comment/reply/menu และ neighboring posts; saved replay ก่อน/หลังส่วนเพิ่มยังได้ 30/30 และตรง saved counts ทั้งหมด รายงานอยู่ใน ignored `runs/target-scope-seam-before.json` และ `runs/target-scope-seam-after.json` ไม่มี Facebook live request

## Numeric target กับ opaque header — live พบเพิ่ม

Live `live-confirmation-20261019T192323Z` บน `e9aa831` ได้ 25/30: HTTP 200 ครบ 10 URL ไม่มี challenge, source hashes คงเดิม และช่วงห่าง request อย่างน้อย 22.9 วินาที P01–P05 text hash ตรง baseline แต่ P06 หายสาม counters และ P10 หาย Reaction/Share รอบนี้จึงไม่ผ่าน live confirmation

Snapshot เก่า P06/P10 ไม่มี header links ที่ extractor เก็บได้ ส่วน snapshot ใหม่มี opaque `pfbid` header ซึ่งไม่ตรงชนิด numeric target: P06 ถูกมองว่า malformed เพราะ query `story_fbid` ไม่ใช่ตัวเลข; P10 เป็น route identity คนละชนิด การเทียบโค้ดก่อน/หลังยืนยันว่าข้อจำกัดจาก `fd6a9eb` ยังเหลืออยู่ ไม่ใช่ parser หา counter ไม่เจอ

แก้เฉพาะการยืนยัน DOM header: รับ alias เมื่อ embedded `Story` ผูก `permalink_url`, numeric `post_id`, feedback ID และ owning-profile ID สอดคล้องกับ target เดียวกัน เก็บ `header_alias_evidence` ไว้ตรวจย้อนกลับ ไม่มีการผ่อน `target_identity()`/`identities_match()` หรือ requested/resolved URL contract และไม่ถือว่า numeric กับ `pfbid` เท่ากันโดยอัตโนมัติ

- Browser regression tests ใช้ IDs สมมติหลายชุด ไม่ผูกกับ P06/P10; ไม่มีหลักฐาน, ผิดโพสต์แม้เจ้าของเดียวกัน, feedback/owner ผิด, alias ขัดกันไม่ว่าลำดับใด, header อื่นที่ไม่มี proof และ identity query ซ้ำ/ขัดกันยังถูก reject
- ก่อนแก้ tests ใหม่ล้ม 4 subcases; หลังแก้ full suite ผ่าน 143 tests และ `git diff --check` ผ่าน
- Offline replay ทั้ง snapshot เก่าและ live capture ใหม่ได้ 30/30; P06=61/3/102, P10=7/0/6 โดยคง P08 Reaction=70 ตาม capture ใหม่ ไม่บังคับให้กลับเป็น 71 ของรอบเก่า
- หลักฐานอยู่ใน ignored `runs/alias-fix-historical-replay.json` และ `runs/live-confirmation-20261019T192323Z-alias-fix-replay.json` ไม่แก้ทับ live artifacts เดิมและไม่ยิง Facebook เพิ่ม ผล 30/30 หลังแก้เป็น offline regression check เท่านั้น ยังไม่ใช่ live confirmation รอบใหม่
