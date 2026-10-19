# ส่งต่องาน — Social Listening Scraping — 20 ตุลาคม 2026

## ภาพงานที่ตกลงกัน

Social Listening แยกอยู่สองที่เก็บ:

- **ฝั่ง scraping (repo นี้):** พัฒนา Facebook Collector เป็นเครื่องมือทั่วไป ใช้ฟรีและรันบนเครื่องได้ ไม่ผูกกับบริษัทหรือชุด keywords เฉพาะ
- **ฝั่ง demo (อีกที่เก็บ):** งาน Apify, ข้อมูล 300 posts, การคัดกรองด้วย agent, sentiment และ Dashboard ไม่รวมเป็นผลงานของ repo นี้

เป้าหมาย collector และเกณฑ์จบอยู่ใน [goal #3](https://github.com/PeeraphatN/social-lisening/issues/3) ปิด [#2](https://github.com/PeeraphatN/social-lisening/issues/2) ในฐานะ validated experiment ไม่ใช่ collector v1 งานยกระดับเป็น feature อยู่ใน [#9](https://github.com/PeeraphatN/social-lisening/issues/9) จากนั้นตามต่อ [post search #4](https://github.com/PeeraphatN/social-lisening/issues/4) → [comment scraping #5](https://github.com/PeeraphatN/social-lisening/issues/5) → ตรวจเส้นทางรวม ส่วน [load test #7](https://github.com/PeeraphatN/social-lisening/issues/7) ยังพักไว้

## Experiment → feature → master

- `master` เก็บงานพร้อมใช้ตามขอบเขตที่ประกาศ คง prototype และหลักฐานไว้บน `experiment/facebook-post-scraping-data`
- เริ่ม `feat/facebook-collector-post` จาก `master` แล้วนำเฉพาะ logic/tests/docs ที่พิสูจน์แล้วมาใช้ ไม่ merge experiment branch ทั้งชุดเข้าฐานหลัก
- ใช้ acceptance ของ #9 ตรวจ entrypoint จริงก่อน review/merge; ปิด experiment ไม่เท่ากับปล่อย feature และไม่ต้องรอ #4/#5 เพื่อปล่อยส่วนรับ URL
- ยังไม่เพิ่ม `experiment/main` และพักการปรับ global skills/workflow ข้ามโปรเจกต์ไว้
- เอกสารนี้อยู่บน experiment branch ถ้าเริ่มจาก master ให้เปิด #9 ซึ่งบันทึก flow และลิงก์ฐานทดลองไว้ด้วย

## อ่านหลักฐานก่อนทำต่อ

- [Target-scope regression และ live confirmation ล่าสุด](experiments/facebook-post-target-scope-regression-20261020.md): สาเหตุ, fixes, replay และผลบน source `f6ba59b`
- [Counter accuracy #6](https://github.com/PeeraphatN/social-lisening/issues/6) และ [scope spec #8](https://github.com/PeeraphatN/social-lisening/issues/8): ปิดผลทดลองแล้ว โดยจำกัด claim ตามหลักฐานแต่ละรอบ
- [Same-version repeat](https://github.com/PeeraphatN/social-lisening/issues/6#issuecomment-6121295648) และ [ผลตรวจต้นทาง P03](https://github.com/PeeraphatN/social-lisening/issues/6#issuecomment-6121462499)
- [รายงาน P03 และ counter repeat](experiments/facebook-post-counter-followup-20261012.md): diagnosis, identity chain, tests, hashes และตำแหน่งหลักฐาน local
- [README ทดลอง](../experiments/facebook_posts/README.md): การติดตั้ง วิธีรัน และ semantics ของ counters
- [ผล text repeat เดิม](experiments/facebook-post-repeat-results.md): เป็นผลข้อความ ไม่ใช้แทนผล counter หรือ comment scraping

Raw evidence อยู่ใน ignored `experiments/facebook_posts/runs/` ไม่มากับ clone ใหม่ อย่าบอกว่า GitHub readers เปิดไฟล์ local เหล่านี้ได้ ให้ลิงก์ public summary comments แทน

## Repeat baseline และ handoff ข้าม worktree

`experiments/facebook_posts/repeat-baseline.json` เป็น tracked hash-only baseline สำหรับ P01–P05 ใช้ได้ทันทีใน fresh worktree และไม่มี raw post text ส่วน raw inspection JSON, HTML และภาพให้ส่งเฉพาะเมื่อจำเป็น:

- ระบุ tracked baseline commit หรือ evidence bundle absolute path พร้อม SHA-256 ในงานที่ส่งให้ agent อื่น
- สร้าง bundle ด้วย `experiments/facebook_posts/handoff_evidence.py export` โดยเลือกไฟล์ที่ต้องใช้เท่านั้น และเก็บ output นอก worktree
- ฝั่งรับใช้คำสั่ง `import` พร้อม `--expected-source-commit`; ระบบตรวจ manifest, path, size และ SHA-256 ก่อนเขียนเข้า ignored `runs/`
- ห้ามส่งทั้ง `runs/` โดยอัตโนมัติ และ raw Facebook content ต้อง opt-in
- provenance ของ bundle ที่รับเข้าจะอยู่ใต้ `runs/handoff/`

## จุดที่หยุดไว้

Source `f6ba59b` ผ่าน offline suite 143/143 และ replay ทั้ง snapshot เก่า/ชุดที่เคยได้ 25/30 กลับมา 30/30 Live `live-confirmation-20261019T195024Z` ได้ 30/30 counters, HTTP 200 ครบ P01–P10, ไม่มี challenge/request failure, คิวเดียวห่าง 22.4–37.2 วินาที และ frozen hashes คงเดิม P01–P05 normalized text hash ตรง tracked baseline

P05 ใช้ rendered-DOM fallback และยังมี extraction status `candidate_text_unverified` ไม่ใช่คำรับรองว่าข้อความทุกโพสต์ครบ P02 Reaction และ P07 Reaction/Share เป็น approximate; P03 Share=0/P10 Comment=0 มี identity-scoped fallback ส่วน live รอบสุดท้าย P06/P10 ไม่มี header links ที่ extractor เก็บได้ จึงไม่ได้ exercise alias-binding branch บน live DOM; branch นี้ยืนยันด้วย browser tests และ replay ของรอบที่เคยพัง Coverage ไม่ใช่ accuracy ทั่วไป

Latest store ข้าม run, successful-null/timeout preservation และ hash-only baseline ทำได้แล้วใน experiment runner แต่ยังผูก P01–P05 และ publisher/reference ที่รู้ล่วงหน้า งาน #9 ต้องนำพฤติกรรมเหล่านี้ไปทดสอบผ่าน entrypoint ของ feature จริง ไม่เพิ่มชั้น storage ใหม่โดยไม่มีเหตุจำเป็น

ก่อนเริ่มแก้โค้ด รันจาก repo root หลังติดตั้งตาม README; ใช้ project venv ที่มี Playwright:

```powershell
.\experiments\facebook_posts\.venv\Scripts\python.exe -m unittest discover -s experiments/facebook_posts -p 'test_*.py'
.\experiments\facebook_posts\.venv\Scripts\python.exe experiments/facebook_posts/replay_target_scope.py
```

Replay ต้องมี raw snapshots ใน ignored `runs/`; fresh checkout ใช้ tracked baseline/tests ได้ แต่ replay ต้องรับ selected evidence bundle ก่อน ไม่มี live request เพิ่มในงานปิด #2

## Timesheet และเสียงผู้เขียน

รูปแบบที่ตกลงไว้เก็บใน **`daily-timesheet` skill** ไม่ต้องคัด template ซ้ำที่นี่:

- จัด activities ใต้หัวข้องานใหญ่ เช่น `Facebook Collector → facebook-post-scraping` แล้วเรียงงานย่อยภายในกลุ่ม
- แยกฝั่ง scraping จาก demo แม้ใช้ชื่อโปรเจกต์เดียวกัน
- เขียนจากมุมของเจ้าของงาน เช่น “ตรวจต้นทางแล้ว…” แทน “ผู้ใช้ยืนยัน…” รวมถึงหัวตาราง ลิงก์ และ checklist
- เวลาเริ่ม–จบงานวันนี้ยังไม่ได้ระบุ เวลารันทดลองไม่ใช่เวลาทำงานทั้งหมด และยังไม่มีหลักฐานการกรอกเข้าระบบ timesheet บริษัท

สร้าง `~/.agents/skills/daily-timesheet/SKILL.md` และอัปเดต `~/.agents/skills/project-owner-notes/SKILL.md` แล้ว เป็น shared skills ไม่ได้ติดตั้งไว้เฉพาะ default ของ pi รองรับ agents ที่ค้นพบ `.agents/skills` ถ้ายังไม่เห็น skill ให้โหลดไฟล์นี้โดยตรง

Timesheet ที่คุยกันเป็น draft ในบทสนทนา ยังไม่ได้บันทึกเข้า Hermes หรือระบบบริษัท ประวัติประชุม/เวลางานที่มาจาก Hermes ตรวจยืนยันจาก repo นี้ไม่ได้

## ข้อจำกัดระหว่างทำต่อ

- เก็บ Facebook แบบ anonymous เท่านั้น ไม่ login เปลี่ยน personal session กด interactions ใช้ proxy หรือหลบ challenge; serialize requests และหยุดเมื่อพบ block/challenge
- เก็บ live originals, replay และค่าที่ตรวจต้นทางแยกกัน ไม่เขียนทับผลเก่าเพื่อให้ coverage ดีขึ้น
- Missing ไม่ใช่ zero; counter ผิดโพสต์เป็น bug; coverage ไม่ใช่ accuracy; references ข้ามเวลาไม่ใช้แทนค่าต้นทางของ snapshot ใหม่
- Comments ตาม browser กับ app รวม replies เป็นคนละ scope ไม่บวก replies ที่โหลดมาไม่ครบเพื่อเดายอดรวม
- ไม่ commit/push หรือปิด issues อัตโนมัติ ไม่เผยแพร่ full post/comment content หรือข้อมูลลับ

## Working tree และประวัติ branch

ตรวจ `git status --short --branch` และ `git worktree list` ก่อนแก้ไฟล์ งานเก็บผลทดลองคงอยู่บน `experiment/facebook-post-scraping-data`; งาน feature ถัดไปใช้ flow ด้านบน ไม่เริ่ม implement #9 หรือ #4/#5 จนกว่าจะได้รับคำขอ

รักษางานที่มีอยู่ รวมถึง `AGENTS.md` และ `docs/github-writing-style.md` ตรวจ diff ก่อน stage; อย่ารวมไฟล์ตั้งค่า/เอกสารที่ไม่เกี่ยวข้องโดยอัตโนมัติ

Master เคย revert งานทดลองด้วย `3850559` การ merge experiment ตรง ๆ มี modify/delete conflicts และไฟล์ที่ไม่กลับมา ดู [บันทึก branch ใน #2](https://github.com/PeeraphatN/social-lisening/issues/2#issuecomment-6044944137) ให้ตรวจ final feature tree/diff กับ master และนำเฉพาะส่วนที่ตั้งใจส่งมอบ ไม่ force push หรือคืน revert ทั้งก้อนอัตโนมัติ Handoff รุ่นก่อนอ่านด้วย `git show 013dbdf:docs/HANDOFF.md` เป็นประวัติ ไม่ใช้แทนสถานะปัจจุบัน

## Suggested skills

ให้ session ใหม่เรียก Skill tool สำหรับ skills ที่ตรงกับงาน; ถ้าไม่มี Skill tool ให้ใช้ read เปิด `SKILL.md` จากรายการ skills ของ agent:

- **graft:** ก่อนค้นหรือเปิด source ใน repo ตาม `AGENTS.md`
- **daily-timesheet:** สรุปงานรายวันตาม format ที่ตกลงและแบ่งกิจกรรมตาม feature/module
- **project-owner-notes:** เขียน issues/comments/work logs จากมุมผู้เขียน
- **no-ai-slop:** เมื่อต้องตรวจหรือแก้สำนวนให้ตรงเสียงผู้เขียน
- **test-driven-development:** เมื่อเริ่มเปลี่ยนพฤติกรรม extraction
- **debug-mantra:** เมื่อเริ่ม diagnosis/debugging ให้ทำตามลำดับของ skill
- **writing-for-agents:** เมื่อต้องแก้ handoff, skills หรือเอกสารคำสั่งของ agents

เริ่ม session ถัดไปด้วยการอ่าน #9, ข้อสรุป #2 และตรวจ working tree แล้วเลือกงานจากคำขอใหม่ รายการงานค้างไม่ใช่คำสั่งให้เริ่ม implement และงานนี้ไม่ได้ติดตั้งหรือแก้ skills ส่วนกลาง
