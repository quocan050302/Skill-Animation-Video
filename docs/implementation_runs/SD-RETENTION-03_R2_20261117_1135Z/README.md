# SD-RETENTION-03.R2 Execution Record — Visual Quality Correction, Decoded-Frame Truth & Cinematic Readability

- **Run ID**: `SD-RETENTION-03_R2_20261117_1135Z`
- **Branch**: `feat/sd-retention-03-r2-visual-quality` (branched cleanly from `feat/sd-retention-01-expressive-editorial` @ `8f53a7a08a6fefebd43d69ad5974689466236f14`)
- **Master SHA (unchanged)**: `6d9f31e5f3d4a9f9127543bb3648c031de09a3fb`
- **Submodule SHA (`vendor/claude-animation-skills`, unchanged)**: `5dbea55c23aa6a5c93dc3cfb5583840513b56b94`
- **Previous Run Preserved Read-Only**: `docs/implementation_runs/SD-RETENTION-03_UNIFIED_20261117_0915Z/`, `runs/sd_retention03_tacoma_bridge_20261117_1005Z/`

## Scope & Core Objective

Targeted R2 correction to SD-RETENTION-03 turning technically valid procedural shots into immediately readable, dynamic, visually coherent 9:16 vertical shorts across Workstreams A–H (`R2.1`–`R2.8`).

## Host Environment Summary
- **OS**: macOS 14.4.1 (`Darwin arm64`, Apple M1 Pro, Metal WebGL)
- **Toolchain**: Python 3.13.0 (`PIL`, `numpy`, `scipy`), Node v22.22.3, Playwright Chromium (`Google Chrome for Testing` 1234), FFmpeg 6.0 / FFprobe 6.0, macOS `say` (`Samantha` EN; `neural_prosody=false`, `word_anchor_confidence="ESTIMATED"`).

---

## Đã hoàn thành hôm nay (Completed & Verified Today — 2026-11-17)

1. **R2.1 Decoded Visual Truth & Semantic Matte QA (`director/decoded_visual_quality.py`, `director/render_node.mjs`, `director/render_scene.py`, `director/quality_gate.py`, `director/cinematic_composition_qa.py`, `director/visual_storytelling_qa.py`, `director/retention_qa.py`)**:
   - Đã thêm pass render semantic object-ID matte (`renderMatteAtTime` / `--mode mattes`) đồng bộ camera/geometry/thời gian với beauty render, chuẩn hóa ANGLE `metal` trên macOS và `d3d11` trên Windows.
   - Đo độ phủ chủ thể trên khung hình 9:16 thực tế, tách chuyển động vật lý sau khi bù chuyển động camera (`assess_decoded_frame_triple`), kiểm tra bố cục trên các kích thước di động `320/360/390/1080`, và khóa fail-closed khi `checked_settled_tips == 0` hoặc `decoded_visual_quality` fail.
2. **R2.2–R2.5 Camera, Staging, Vật lý, Nhân vật & Con trỏ ngữ nghĩa**:
   - `director/assets/zdf_tacoma_bridge_scenes.py`: Mặt cầu 66 phân đoạn uốn xoắn liên tục, 44 cáp treo gắn khung thực tế, sập nhịp giữa chia khúc rơi xuống eo biển với chuỗi cột nước & giọt bắn 3D tự nhiên (`hitWaterT` đồng bộ âm thanh `tacoma_span_plunge_splash` trong `director/audio_narrative.py`), nhân vật bờ quan sát 5 pha phản ứng có tiếp đất hoàn chỉnh (`director/character_performance.py`, `director/assets/character_performance.py`), sửa điểm neo `breakSeamAnchor` và góc máy hậu cảnh `tacoma_aftermath_stage`.
   - `director/assets/zdf_boston_molasses_scenes.py` & `director/shot_director.py`: Bổ sung `tagSemantic` cho toàn bộ cảnh tổng quan bến cảng (`makeBostonLocationOverview`) và chặn lỗi kế thừa `contact_action` sai pha khi tách câu (`shot_director.py`).
   - `director/assets/zdf_skyscraper_scenes.py` & `director/assets/zach_d_films_adapter.py`: Dựng mới hoàn chỉnh 6 không gian 3D cho kịch bản *"Why Skyscrapers Sway in the Wind"* (`street_hook`, `skyline_wide`, `wind_vortex`, `plumb_drift`, `office_interior`, `tmd_cutaway` `LayeredCutaway` với `layers_count=4, components_count=3`, `counterphase`, `before_after`, `dusk_resolution`), thêm `torsion_bracket` / `sway_bracket` SVG (`editorial_theme_renderer.py`), viền & nền mờ tăng tương phản phụ đề `#cap`.
   - `director/cinematic_composition.py` & `director/build_storyboard.py`: Xuất `frame_design_intent.json` và ràng buộc thông số góc máy hướng mục tiêu hành động.
   - `director/preflight.py`: Cập nhật `DiskBudgetGuard` với ngưỡng an toàn `max(10 GiB, 25% * required_bytes)`.
3. **R2.7 Bẫy âm bản & DAG tự động (`tests/test_r2_decoded_and_traps.py`, `tools/run_validation_async.py`)**:
   - Đã tạo `tests/test_r2_decoded_and_traps.py` kiểm chứng toàn bộ 32 bẫy `T01`–`T32`, tổng quát hóa domain thứ 3 trung lập ("submarine ballast tank"), bất biến seek WebGL không theo thứ tự (`T27`), bảo toàn gói video `--audio-only` (`T29`).
   - Cập nhật `tools/run_validation_async.py` thêm 3 suite audio trước đây bị bỏ sót (`test_audio_narrative_planning`, `test_audio_integration_smoke`, `test_audio_only_remux`), thêm `r2_decoded_and_traps` và cơ chế tự kiểm tra phủ 100% file `tests/test_*.py` (`verify_test_suite_coverage`).
4. **R2.8 Render & Kiểm chứng thực tế đã đạt (`LOCAL_ONLY` MP4 trong `runs/`, ảnh proof lưu trong `qa/`)**:
   - **Skyscraper Showcase (`runs/sd_retention03_r2_skyscraper_20261117/`)**:
     - `baseline_A/` (upscale, legacy/off) & `enhanced_B/` (native 4K `2160x3840`, `fps=30`, `role-aware`, khóa cùng `vo.wav` SHA `291b5c85...`): **CẢ HAI PASS 100% QC** (`TECHNICAL_ACCEPTANCE_PASS`, `native_4k=True`, `high_freq_edge_ratio_vs_1080p_bilinear=1.1993`, `decoded_visual_quality=PASS` trên 9/9 cảnh, `pointer_tracking` 11 settled tips với max error `13.29px <= 36px`, `mobile_qa` PASS `320/360/390/1080`, `free_screen_ratio=0.4595`, `audio_qc` PASS `-14.1 LUFS` / 14/14 SFX onsets).
     - Đã đối chiếu ảnh thực tế: [skyscraper_enhanced_B_360_sheet.jpg](qa/skyscraper_enhanced_B_360_sheet.jpg), [ab_side_by_side_360_sheet.jpg](qa/ab_side_by_side_360_sheet.jpg), [ab_report.json](qa/ab_report.json), [qc_report.json](qa/qc_report.json), [decoded_visual_quality_report.json](qa/decoded_visual_quality_report.json), [mobile_qa_320_360_390_1080.json](qa/mobile_qa_320_360_390_1080.json).
   - **Tacoma 1940 Repair Proof (`runs/sd_retention03_r2_tacoma_proof_20261117/`)**:
     - Đã PASS toàn bộ `qc_report` (`TECHNICAL_ACCEPTANCE_PASS`; `decoded_visual_quality=WARN` với 1 cảnh báo tách nền nhẹ ở `shot_07` `7.4 < 12.0`, 0 `issues`).
     - Bằng chứng ảnh giải mã & đối chiếu: [tacoma_r2_360_sheet.jpg](qa/tacoma_r2_360_sheet.jpg), [tacoma_before_vs_after_360.jpg](qa/tacoma_before_vs_after_360.jpg), [tacoma_qc_report.json](qa/tacoma_qc_report.json).
   - **Checkpoint Unit/WebGL Tests sau lần sửa code cuối**:
     - `python3 -m unittest tests.test_r2_decoded_and_traps tests.test_boston_molasses_scenes tests.test_retention03_integration tests.test_visual_storytelling_director tests.test_physical_motion tests.test_character_performance -v` -> **`Ran 15 tests in 16.674s OK`** (`logs/checkpoint_tests.log`).
   - Lưu ý trung thực: Mọi cổng chủ quan (`subjective_visual_review`, `subjective_editorial_listening`, `subjective_voice_quality_status`, `viewer_retention_status`) đều giữ nguyên `"NOT_VERIFIED"`.

---

## Hoàn tất đợt R2 (Final Verification & Closeout — 2026-11-18, Windows)

1. **Hoàn tất Boston 1919 Regression Proof (`runs/sd_retention03_r2_boston_proof_20261118/`)**:
   - Đã thêm biến thể preset góc máy thứ 2 & đường đi camera riêng (`director/shot_director.py`, `director/camera_choreographer.py`) cho `boston_street_hook` (`boston_street_hook_alley_pan`), `boston_tank_rupture` (`boston_tank_rupture_surge`), `boston_elevated_rail_impact` (`boston_elevated_rail_truss_tilt`) cùng bộ bảo vệ xoay triplet liền kề tổng quát + `CONTINUATION_SUBPHASES` (`director/visual_storytelling_director.py`), đồng thời sửa định tuyến mệnh đề ngắn `"Boston's strangest flood"` (`director/visual_event_graph.py`).
   - Kết quả render lại Boston R2 Proof: **PASS `TECHNICAL_ACCEPTANCE_PASS`** (`10` shots / `10` unique setups / `10` unique movements, **`0` lặp setup/triplet liền kề**, `cinematic_composition=PASS (0 issues)`, `pointer_tracking=PASS` với `9` settled tips và sai số tối đa `13.52px <= 36px`, `character_grounding=PASS` trên `24` mẫu `worst_penetration=0.0143m / slide=0.001m`, `-15.4 LUFS / -2.3 dBTP`, `decoded_visual_quality=WARN` chỉ do 2 cảnh báo tách cạnh nhẹ `0 issues`).
   - Bằng chứng đã kiểm tra trực quan: [boston_r2_360_sheet.jpg](qa/boston_r2_360_sheet.jpg), [boston_qc_report.json](qa/boston_qc_report.json).

2. **Tinh chỉnh đối chiếu ảnh `tacoma_before_vs_after_360.jpg` & sửa khung sập Tacoma (`runs/sd_retention03_r2_tacoma_proof_20261118/`)**:
   - Đã mở rộng nhẹ góc máy `zach3d:tacoma_collapse_plunge_stage` (`fov=52`), hiệu chỉnh `breakSeamAnchor` (`director/assets/zdf_tacoma_bridge_scenes.py`) và bổ sung góc quay `tacoma_wide_strait_aerial` + đường máy đối lập cho `tacoma_torsion_twist_stage` -> **`pointer_tracking=PASS` với `13` settled tips, `0` offscreen skips**, `worst_tip_target_error_px=13.26px`, `11` unique setups / `0` lặp.
   - Đã cập nhật [tacoma_before_vs_after_360.jpg](qa/tacoma_before_vs_after_360.jpg) khớp beat 1:1 giữa bản lưu trữ trước đó (`1.50s`, `22.00s`, `31.50s`) và khung giải mã R2 mới đúng lúc `THE ROAD / WAS MOVING!` (`1.50s`), đỉnh xoắn `WHOLE DECK TWISTING` (`29.75s`) và khoảnh khắc gãy + splash `SPAN BROKE FREE` (`34.35s`), kèm [tacoma_r2_360_sheet.jpg](qa/tacoma_r2_360_sheet.jpg) và [tacoma_qc_report.json](qa/tacoma_qc_report.json).

3. **Kiểm thử tự động trọn bộ SAU lần chỉnh sửa code cuối cùng**:
   - `python tools/run_validation_async.py --mode full --workers 2 --log-dir docs/implementation_runs/SD-RETENTION-03_R2_20261117_1135Z/logs/async_dag` -> **25/25 suite `[PASS   ]`** (`497.38s`, phủ 100% file `tests/test_*.py`, `missing_modules: []`, [validation_summary.json](logs/async_dag/validation_summary.json)).
   - `python -m unittest discover -s tests -v` -> **`Ran 79 tests in 613.330s — OK`** (`0` errors, `0` failures, [canonical_unittest_discover.log](logs/canonical_unittest_discover.log)).

4. **Chứng từ kết thúc đợt R2 & Chính sách Git Media**:
   - Đã xuất [gates_status.csv](gates_status.csv), [qa_summary.json](qa_summary.json), [final_manifest.json](final_manifest.json), và [SHA256SUMS.txt](SHA256SUMS.txt).
   - Toàn bộ `.mp4` của đợt R2 chỉ lưu cục bộ trong `runs/` (`LOCAL_ONLY`, được `.gitignore` loại trừ hoàn toàn khỏi Git).
   - Lưu ý trung thực: Mọi đánh giá chủ quan (`subjective_visual_review`, `subjective_visual_quality`, `subjective_editorial_listening`, `subjective_voice_quality_status`, `subjective_preference_status`, `viewer_retention_status`) giữ nguyên **`NOT_VERIFIED`** chờ con người xem và nghe thực tế.
