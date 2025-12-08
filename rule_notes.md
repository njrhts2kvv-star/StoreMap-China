Mall name extraction rule notes (unmatched mall-like review)

Observations from `unmatched_mall_like.csv`:
- All 1,361 records are `mall_store_no_match`; 617 marked `no_candidate_but_has_hint`.
- Brands dominating: Li Auto 631, NIO 237, Tesla 184, XPeng 144; long-tail luxury/affordable-lux (Coach, Polo Ralph Lauren, Kenzo, Hugo Boss, Louis Vuitton, etc.).
- Frequent tokens in names/addresses: “中心”, “广场”, “汇/荟/里”, “车城/汽车城/汽车园”, “公园”, “奥特莱斯/奥莱”.
- Many NEV names use pattern “品牌中心/体验中心 | 位置/商圈名”.

Recommended rule/pattern additions:
1) Split-on-separator patterns
   - If name contains “ | ” or “｜”, take the right-hand segment as candidate mall/complex name (trim whitespace/城市名后缀).
   - If segment ends with 公园/广场/中心/天地/汇/荟/里/城/场/街区/艺术公园, keep as mall candidate.

2) NEV-specific mallish tokens
   - Treat “汽车城/车城/汽车园/汽车港/汽车小镇/汽车博览园/车市” as mall-like; allow mapping to a special “auto park” candidate list/cluster.
   - If address contains above tokens, boost match score for malls/POIs whose names include the same token.

3) Outlet/ao-lai handling
   - If name/address contains “奥特莱斯/奥莱/OUTLETS”, prefer malls whose names include the same token, even if distance slightly higher.

4) Mallish suffix heuristic
   - If name contains a substring ending with 广场/中心/天地/荟/汇/里/城/街区/公园, extract that substring as candidate mall name before fuzzy matching.

5) Candidate list re-ranking
   - When candidates_json is empty but mallish tokens are present, build a fallback candidate list from same-city malls within 1 km regardless of name similarity, then run fuzzy match on extracted token.

6) Brand-level hard rules (luxury/affordable-lux)
   - For brands in {LV, Chanel, Hermès, Dior, Prada, Gucci, Coach, Michael Kors, Hugo Boss, Kenzo, Longchamp, MCM, Tory Burch, Givenchy, Polo Ralph Lauren}, treat any mallish token hit as “must-have mall”, and always generate at least one candidate for review.

Suggested implementation hooks:
- Extend `extract_mall_name_from_text` with separators (“ | ”/“｜”) and mallish suffix regex (see above).
- Add an NEV keyword list to classify “auto park” complexes and use it to widen candidate search radius (e.g., up to 1.5 km) when standard malls are absent.
- Add a fallback branch for `no_candidate_but_has_hint`: if mallish token exists, force-generate candidates via spatial proximity + token fuzzy match even when standard rules return none.

