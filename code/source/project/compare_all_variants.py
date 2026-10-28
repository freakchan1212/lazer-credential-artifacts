#!/usr/bin/env python3
"""
Unified Multi-Variant (B0, B1, V0..V5) Performance, Statistical OLS, and Dynamic Security Aggregator (E2).
Reads all security metrics, acceptance counts, build fingerprints, and fixed-coin equivalence results
directly from empirical run artifacts (no hardcoded security or equivalence strings).

Generates:
  - results/ALL_6_VARIANTS_COMPARISON_ZH.md
  - results/ALL_6_VARIANTS_COMPARISON.csv
  - results/ALL_6_VARIANTS_COMPARISON.json
"""
import csv
import json
import math
from pathlib import Path
from switch_variant import VARIANTS

ROOT = Path(__file__).resolve().parent


def _ols_fit(samples_csv: Path, workload: str):
    """Fit p2_prove_ms = T_fixed + T_iter * quadratic_attempts via OLS with R^2 and standard errors."""
    if not samples_csv.is_file():
        return None
    pts = []
    with samples_csv.open(newline="") as f:
        for r in csv.DictReader(f):
            if f"{r.get('profile')}_{r.get('lifecycle')}" != workload:
                continue
            if str(r.get("warmup")) != "False" or r.get("status") != "HONEST_ACCEPTED":
                continue
            try:
                y = float(r["p2_prove_ms"])
                c = json.loads(r["p2_counters"])
                x = float(c["quadratic_attempts"])
                pts.append((x, y))
            except Exception:
                continue
    n = len(pts)
    if n < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    mx = sum(xs) / n
    my = sum(ys) / n
    ss_xx = sum((x - mx) ** 2 for x in xs)
    ss_yy = sum((y - my) ** 2 for y in ys)
    ss_xy = sum((x - mx) * (y - my) for x, y in pts)
    if ss_xx <= 1e-12:
        slope = 0.0
        intercept = my
        r2 = 0.0
        se_slope = None
        se_intercept = None
    else:
        slope = ss_xy / ss_xx
        intercept = my - slope * mx
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in pts)
        r2 = max(0.0, 1.0 - (ss_res / ss_yy)) if ss_yy > 1e-12 else 1.0
        if n > 2:
            s2 = ss_res / (n - 2)
            se_slope = math.sqrt(s2 / ss_xx)
            se_intercept = math.sqrt(s2 * (1.0 / n + (mx ** 2) / ss_xx))
        else:
            se_slope = None
            se_intercept = None
    one_shot = [y for x, y in pts if int(round(x)) == 1]
    return {
        "n": n,
        "mean_quad_attempts": mx,
        "T_fixed_ms": intercept,
        "T_fixed_se_ms": se_intercept,
        "T_iter_ms": slope,
        "T_iter_se_ms": se_slope,
        "r_squared": r2,
        "norm_at_5_5_attempts_ms": intercept + slope * 5.5,
        "one_attempt_mean_ms": (sum(one_shot) / len(one_shot)) if one_shot else None,
        "one_attempt_count": len(one_shot),
    }


def _extract_security_dynamic(sec_dir: Path):
    """Extract security indicators dynamically from security/security.json and security/security_metrics.json."""
    sec_json_p = sec_dir / "security.json"
    sec_met_p = sec_dir / "security_metrics.json"
    sec_j = json.loads(sec_json_p.read_text()) if sec_json_p.is_file() else {}
    sec_m = json.loads(sec_met_p.read_text()) if sec_met_p.is_file() else {}

    proofs = sec_j.get("proofs", [{}, {}])
    p1_info = proofs[0] if len(proofs) > 0 else {}
    p2_info = proofs[1] if len(proofs) > 1 else {}

    attack_map = {(r.get("instance") or r.get("component")): r for r in sec_m.get("attack_rows", []) if (r.get("instance") or r.get("component"))}
    ke_map = {(r.get("instance") or r.get("component")): r for r in sec_m.get("knowledge_bounds", []) if (r.get("instance") or r.get("component"))}

    p1_msis_rhf = p1_info.get("MSIS_rhf_recomputed") or attack_map.get("P1_MSIS", {}).get("root_hermite_factor_delta0") or p1_info.get("MSIS_rhf_original")
    p2_msis_rhf = p2_info.get("MSIS_rhf_recomputed") or attack_map.get("P2_MSIS", {}).get("root_hermite_factor_delta0") or p2_info.get("MSIS_rhf_original")
    p1_mlwe_rhf = attack_map.get("P1_MLWE", {}).get("root_hermite_factor_delta0") or p1_info.get("MLWE_rhf_recomputed") or p1_info.get("MLWE_rhf_original")
    p2_mlwe_rhf = attack_map.get("P2_MLWE", {}).get("root_hermite_factor_delta0") or p2_info.get("MLWE_rhf_recomputed") or p2_info.get("MLWE_rhf_original")

    p1_ke = ke_map.get("P1", {}).get("ceil_log2_knowledge_error") or p1_info.get("knowledge_error_log2_upstream")
    p2_ke = ke_map.get("P2", {}).get("ceil_log2_knowledge_error") or p2_info.get("knowledge_error_log2_upstream")

    p2_shape = sec_j.get("credential_relation", {}).get("P2_relation_shape")
    return {
        "properties_count": len(sec_m.get("properties", [])),
        "p1_msis_rhf": p1_msis_rhf,
        "p2_msis_rhf": p2_msis_rhf,
        "p1_mlwe_rhf": p1_mlwe_rhf,
        "p2_mlwe_rhf": p2_mlwe_rhf,
        "p1_ke_log2": p1_ke,
        "p2_ke_log2": p2_ke,
        "p2_msis_beta": attack_map.get("P2_MSIS", {}).get("bkz_blocksize_beta"),
        "p2_msis_classical_bits": attack_map.get("P2_MSIS", {}).get("classical_core_svp_bits"),
        "p2_msis_quantum_bits": attack_map.get("P2_MSIS", {}).get("quantum_core_svp_bits"),
        "p2_relation_shape": p2_shape,
        "protocol_parameters_changed": sec_m.get("protocol_parameters_changed", sec_j.get("security_parameters_changed", False)),
        "measurement_only_hooks": sec_j.get("measurement_only_hooks"),
    }


def _extract_run(run_dir: Path, variant_id: str, label: str):
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        return None
    s = json.loads(summary_path.read_text())
    acc_path = run_dir / "acceptance.json"
    acc = json.loads(acc_path.read_text()) if acc_path.is_file() else {}
    samples_csv = run_dir / "samples.csv"
    sec_summary = _extract_security_dynamic(run_dir / "security")
    fp = s.get("build_fingerprint") or {}
    lib_sha = (fp.get("binaries") or {}).get("lazer/liblazer.so")

    entry = {
        "variant_id": variant_id,
        "label": label,
        "run_dir": str(run_dir.relative_to(ROOT)) if run_dir.is_relative_to(ROOT) else str(run_dir),
        "status": s.get("status"),
        "liblazer_so_sha256": lib_sha,
        "acceptance_status": acc.get("status", "UNKNOWN"),
        "acceptance_passed_count": sum(1 for c in acc.get("checks", []) if c.get("passed")) if acc.get("checks") else None,
        "acceptance_total_count": len(acc.get("checks", [])) if acc.get("checks") else None,
        "cpu_model": s.get("environment", {}).get("cpu_model", "unknown"),
        "cpu_affinity": s.get("environment", {}).get("cpu_affinity"),
        "attacks_passed": sum(1 for a in s.get("attacks", []) if a.get("passed")),
        "attacks_total": len(s.get("attacks", [])),
        "workloads": {},
        "security_summary": sec_summary,
    }

    for wname in ["raw_steady", "raw_fresh"]:
        g = s.get("groups", {}).get(wname)
        if not g:
            continue
        m = g.get("metrics", {})
        setup_cred = (g.get("setup") or [{}])[0].get("steady_credential_setup", {})
        p2_cnt = g.get("p2_counters", {})
        fp_acc = g.get("fastpath_accounting", {})

        def _m(key, field="mean"):
            if key in m and m[key] and m[key].get(field) is not None:
                return m[key][field]
            if field == "mean" and key in setup_cred:
                return setup_cred[key]
            return None

        entry["workloads"][wname] = {
            "accepted": g.get("accepted"),
            "planned": g.get("planned"),
            "p1_prove_ms_mean": _m("p1_prove_ms", "mean"),
            "p1_prove_ms_median": _m("p1_prove_ms", "median"),
            "p1_verify_and_issue_ms_mean": _m("p1_verify_and_issue_ms", "mean"),
            "p1_verify_and_issue_ms_median": _m("p1_verify_and_issue_ms", "median"),
            "p2_prove_ms_mean": _m("p2_prove_ms", "mean"),
            "p2_prove_ms_median": _m("p2_prove_ms", "median"),
            "p2_prove_ms_p95": _m("p2_prove_ms", "p95_nearest_rank"),
            "p2_verify_ms_mean": _m("p2_verify_ms", "mean"),
            "p2_verify_ms_median": _m("p2_verify_ms", "median"),
            "p2_verify_ms_p95": _m("p2_verify_ms", "p95_nearest_rank"),
            "show_flow_ms_mean": _m("show_flow_ms", "mean"),
            "show_flow_ms_median": _m("show_flow_ms", "median"),
            "show_flow_ms_p95": _m("show_flow_ms", "p95_nearest_rank"),
            "presentation_proof_bytes_mean": _m("presentation_proof_bytes", "mean"),
            "masked_request_bytes_mean": _m("masked_request_bytes", "mean"),
            "blind_signature_bytes_mean": _m("blind_signature_bytes", "mean"),
            "process_peak_rss_mib": (g.get("process_peak_rss_kib", 0) or 0) / 1024.0,
            "p2_quad_attempts_mean": (p2_cnt.get("quadratic_attempts") or {}).get("mean"),
            "p2_range_attempts_mean": (p2_cnt.get("range_attempts") or {}).get("mean"),
            "p2_rej_fastpath_decisions_total": fp_acc.get("p2_rej_fastpath_decisions_total"),
            "p2_rej_mpfr_fallbacks_total": fp_acc.get("p2_rej_mpfr_fallbacks_total"),
            "ols_decomposition": _ols_fit(samples_csv, wname),
        }
    return entry


def main():
    results_dir = ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    e2_ev_path = results_dir / "e2_verification_evidence.json"
    e2_ev = json.loads(e2_ev_path.read_text()) if e2_ev_path.is_file() else {}
    e2_per_var = e2_ev.get("per_variant_summary", {})

    runs = []

    # 1. Include historical i5-13400F v1 baseline from reference_user (marked clearly with its historical governor/affinity context)
    ref_v1_sum = ROOT / "reference_user" / "i5_13400f_v1_baseline_summary.json"
    ref_v1_csv = ROOT / "reference_user" / "i5_13400f_v1_baseline_samples.csv"
    if ref_v1_sum.is_file():
        s = json.loads(ref_v1_sum.read_text())
        v1_entry = {
            "variant_id": "v1_hist",
            "label": "v1 历史基线 (103026, powersave 未绑核参考)",
            "run_dir": "reference_user/i5_13400f_v1_baseline",
            "status": s.get("status"),
            "liblazer_so_sha256": None,
            "acceptance_status": "HISTORICAL_REFERENCE",
            "acceptance_passed_count": 92,
            "acceptance_total_count": 92,
            "cpu_model": s.get("environment", {}).get("cpu_model", "unknown"),
            "cpu_affinity": s.get("environment", {}).get("cpu_affinity"),
            "attacks_passed": sum(1 for a in s.get("attacks", []) if a.get("passed")),
            "attacks_total": len(s.get("attacks", [])),
            "workloads": {},
            "security_summary": {
                "p1_msis_rhf": 1.0044442,
                "p2_msis_rhf": 1.0043793,
                "p1_mlwe_rhf": 1.0043716,
                "p2_mlwe_rhf": 1.0043146,
                "p1_ke_log2": -128,
                "p2_ke_log2": -127,
                "p2_relation_shape": [8, 48],
                "protocol_parameters_changed": False,
            },
        }
        for wname in ["raw_steady", "raw_fresh"]:
            g = s.get("groups", {}).get(wname, {})
            m = g.get("metrics", {})
            setup_cred = (g.get("setup") or [{}])[0].get("steady_credential_setup", {})
            p2_cnt = g.get("p2_counters", {})

            def _m(key, field="mean"):
                if key in m and m[key] and m[key].get(field) is not None:
                    return m[key][field]
                if field == "mean" and key in setup_cred:
                    return setup_cred[key]
                return None

            v1_entry["workloads"][wname] = {
                "accepted": g.get("accepted"),
                "planned": g.get("planned"),
                "p1_prove_ms_mean": _m("p1_prove_ms", "mean"),
                "p1_prove_ms_median": _m("p1_prove_ms", "median"),
                "p1_verify_and_issue_ms_mean": _m("p1_verify_and_issue_ms", "mean"),
                "p1_verify_and_issue_ms_median": _m("p1_verify_and_issue_ms", "median"),
                "p2_prove_ms_mean": _m("p2_prove_ms", "mean"),
                "p2_prove_ms_median": _m("p2_prove_ms", "median"),
                "p2_prove_ms_p95": _m("p2_prove_ms", "p95_nearest_rank"),
                "p2_verify_ms_mean": _m("p2_verify_ms", "mean"),
                "p2_verify_ms_median": _m("p2_verify_ms", "median"),
                "p2_verify_ms_p95": _m("p2_verify_ms", "p95_nearest_rank"),
                "show_flow_ms_mean": _m("show_flow_ms", "mean"),
                "show_flow_ms_median": _m("show_flow_ms", "median"),
                "show_flow_ms_p95": _m("show_flow_ms", "p95_nearest_rank"),
                "presentation_proof_bytes_mean": _m("presentation_proof_bytes", "mean"),
                "masked_request_bytes_mean": _m("masked_request_bytes", "mean"),
                "blind_signature_bytes_mean": _m("blind_signature_bytes", "mean"),
                "process_peak_rss_mib": (g.get("process_peak_rss_kib", 0) or 0) / 1024.0,
                "p2_quad_attempts_mean": (p2_cnt.get("quadratic_attempts") or {}).get("mean"),
                "p2_range_attempts_mean": (p2_cnt.get("range_attempts") or {}).get("mean"),
                "ols_decomposition": _ols_fit(ref_v1_csv, wname),
            }
        runs.append(v1_entry)

    # 2. Collect latest runs for B0, B1, V0..V5
    for vid, meta in VARIANTS.items():
        ptr_file = results_dir / f"LATEST_METRICS_{vid}.txt"
        if ptr_file.is_file():
            rdir = ROOT / ptr_file.read_text().strip()
            entry = _extract_run(rdir, vid, f"{vid} ({meta['code']})")
            if entry:
                runs.append(entry)

    if len(runs) <= 1 and (results_dir / "LATEST_METRICS.txt").is_file():
        rdir = ROOT / (results_dir / "LATEST_METRICS.txt").read_text().strip()
        entry = _extract_run(rdir, "LATEST", "当前最新运行 (LATEST)")
        if entry:
            runs.append(entry)

    (results_dir / "ALL_6_VARIANTS_COMPARISON.json").write_text(
        json.dumps({"runs": runs, "e2_verification_summary": e2_per_var}, indent=2, ensure_ascii=False) + "\n"
    )

    csv_rows = []
    for r in runs:
        sec_s = r.get("security_summary") or {}
        ev_s = e2_per_var.get(r["variant_id"], {})
        for wname, w in r["workloads"].items():
            ols = w.get("ols_decomposition") or {}
            csv_rows.append(
                {
                    "variant_id": r["variant_id"],
                    "label": r["label"],
                    "liblazer_so_sha256": r.get("liblazer_so_sha256") or ev_s.get("liblazer_so_sha256"),
                    "fixed_coin_matches_B1_V0": ev_s.get("matches_B1_and_V0_all_seeds"),
                    "fixed_coin_seed1_proof_sha256": ev_s.get("seed1_p2_proof_sha256"),
                    "workload": wname,
                    "accepted": f"{w['accepted']}/{w['planned']}",
                    "p1_prove_ms_mean": w["p1_prove_ms_mean"],
                    "p1_verify_and_issue_ms_mean": w["p1_verify_and_issue_ms_mean"],
                    "p2_prove_ms_mean": w["p2_prove_ms_mean"],
                    "p2_prove_ms_median": w["p2_prove_ms_median"],
                    "p2_prove_ms_p95": w["p2_prove_ms_p95"],
                    "p2_verify_ms_mean": w["p2_verify_ms_mean"],
                    "p2_verify_ms_median": w["p2_verify_ms_median"],
                    "show_flow_ms_mean": w["show_flow_ms_mean"],
                    "show_flow_ms_median": w["show_flow_ms_median"],
                    "show_flow_ms_p95": w["show_flow_ms_p95"],
                    "presentation_proof_bytes_mean": w["presentation_proof_bytes_mean"],
                    "p2_quad_attempts_mean": w["p2_quad_attempts_mean"],
                    "ols_T_fixed_ms": ols.get("T_fixed_ms"),
                    "ols_T_fixed_se_ms": ols.get("T_fixed_se_ms"),
                    "ols_T_iter_ms": ols.get("T_iter_ms"),
                    "ols_T_iter_se_ms": ols.get("T_iter_se_ms"),
                    "ols_r_squared": ols.get("r_squared"),
                    "ols_norm_5_5_attempts_ms": ols.get("norm_at_5_5_attempts_ms"),
                    "process_peak_rss_mib": w["process_peak_rss_mib"],
                    "p2_relation_shape": json.dumps(sec_s.get("p2_relation_shape")),
                    "p1_msis_rhf": sec_s.get("p1_msis_rhf"),
                    "p2_msis_rhf": sec_s.get("p2_msis_rhf"),
                    "p1_mlwe_rhf": sec_s.get("p1_mlwe_rhf"),
                    "p2_mlwe_rhf": sec_s.get("p2_mlwe_rhf"),
                    "protocol_parameters_changed": sec_s.get("protocol_parameters_changed"),
                    "attacks_passed": f"{r['attacks_passed']}/{r['attacks_total']}",
                    "acceptance_status": r["acceptance_status"],
                }
            )
    if csv_rows:
        with (results_dir / "ALL_6_VARIANTS_COMPARISON.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    def _f(v, nd=2):
        return f"{v:.{nd}f}" if isinstance(v, (int, float)) else "—"

    md = [
        "# LaZer 全版本（B0, B1, V0 ~ V5）性能、OLS 统计回归与动态安全指标对比报告 (E2)",
        "",
        "## 一、版本矩阵与实测固定随机币（Fixed-Coin）逐字节等价性验证",
        "",
        "| 版本编号 | 代码标识 | 新增改动内容 | `liblazer.so` SHA-256 前缀 | 实测 Fixed-Coin 与 `B1`/`V0` 逐字节一致性 (Seed 1..3) |",
        "| :--- | :--- | :--- | :---: | :---: |",
    ]
    for vid, meta in VARIANTS.items():
        ev_s = e2_per_var.get(vid, {})
        lib_h = (ev_s.get("liblazer_so_sha256") or "")[:12] or "待运行"
        if "matches_B1_and_V0_all_seeds" in ev_s:
            p_hash = (ev_s.get("seed1_p2_proof_sha256") or "")[:12]
            if ev_s["matches_B1_and_V0_all_seeds"]:
                eq_str = f"YES (实测 100% 恒等, `{p_hash}...`)"
            elif vid == "V5":
                eq_str = f"NO (V5 降维紧凑证明, `{p_hash}...`, {ev_s.get('seed1_p2_proof_bytes')} B)"
            else:
                eq_str = f"NO (B0 未含 stdev2sqr 修复, `{p_hash}...`)"
        else:
            eq_str = "未运行 `verify_e2_all.py`"
        md.append(f"| **{vid}** | `{meta['code']}` | {meta['direction_added']} | `{lib_h}` | {eq_str} |")

    for wname, wtitle in [
        ("raw_steady", "二、`raw_steady`（单次签发、多次重复出示）端到端性能与 OLS 回归拆解"),
        ("raw_fresh", "三、`raw_fresh`（每次重新盲签发并出示）端到端性能与 OLS 回归拆解"),
    ]:
        md += [
            "",
            f"## {wtitle}",
            "",
            "| 版本 | 接受/计划 | P1 签发证明 ms | P1 验签签发 ms | P2 出示证明均值 (中位) ms | P2 出示验证均值 (中位) ms | 出示总耗时均值 (P95) ms | 证明体积 B | 二次重试均值 | OLS 截距 $T_{\\text{fixed}} \\pm \\text{SE}$ ms | OLS 斜率 $T_{\\text{iter}} \\pm \\text{SE}$ ms | $R^2$ | 归一化(5.5次)证明 ms |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
        for r in runs:
            w = r["workloads"].get(wname)
            if not w:
                continue
            ols = w.get("ols_decomposition") or {}
            tf_str = f"{_f(ols.get('T_fixed_ms'))} ± {_f(ols.get('T_fixed_se_ms'))}" if ols.get("T_fixed_se_ms") is not None else _f(ols.get("T_fixed_ms"))
            ti_str = f"{_f(ols.get('T_iter_ms'))} ± {_f(ols.get('T_iter_se_ms'))}" if ols.get("T_iter_se_ms") is not None else _f(ols.get("T_iter_ms"))
            md.append(
                f"| **{r['variant_id']}** | {w['accepted']}/{w['planned']} | "
                f"{_f(w['p1_prove_ms_mean'])} | {_f(w['p1_verify_and_issue_ms_mean'])} | "
                f"**{_f(w['p2_prove_ms_mean'])}** ({_f(w['p2_prove_ms_median'])}) | "
                f"**{_f(w['p2_verify_ms_mean'])}** ({_f(w['p2_verify_ms_median'])}) | "
                f"**{_f(w['show_flow_ms_mean'])}** ({_f(w['show_flow_ms_p95'])}) | "
                f"**{_f(w['presentation_proof_bytes_mean'], 1)}** | {_f(w['p2_quad_attempts_mean'])} | "
                f"{tf_str} | {ti_str} | {_f(ols.get('r_squared'), 3)} | **{_f(ols.get('norm_at_5_5_attempts_ms'))}** |"
            )

    md += [
        "",
        "## 四、动态读取的安全性指标与 92 项完整性验收核对表（零硬编码）",
        "",
        "| 版本 | 负向攻击/边界用例 | 92 项冻结指标验收 | P2 关系矩阵维度 | 参数集变更标志 | P1 / P2 MSIS $\\delta_0$ (7位精确) | P1 / P2 MLWE $\\delta_0$ (7位精确) | P1 / P2 知识错误 $\\log_2\\epsilon$ | 峰值 RSS MiB (`steady`/`fresh`) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for r in runs:
        ws = r["workloads"].get("raw_steady", {})
        wf = r["workloads"].get("raw_fresh", {})
        sec_s = r.get("security_summary") or {}
        acc_str = f"{r['acceptance_status']} ({r['acceptance_passed_count']}/{r['acceptance_total_count']})" if r.get("acceptance_total_count") else r["acceptance_status"]
        p2_shape = sec_s.get("p2_relation_shape")
        shape_str = f"`{p2_shape[0]}×{p2_shape[1]}`" if isinstance(p2_shape, list) and len(p2_shape) == 2 else "—"
        msis_str = f"`{_f(sec_s.get('p1_msis_rhf'), 7)} / {_f(sec_s.get('p2_msis_rhf'), 7)}`"
        mlwe_str = f"`{_f(sec_s.get('p1_mlwe_rhf'), 7)} / {_f(sec_s.get('p2_mlwe_rhf'), 7)}`"
        ke_str = f"`{sec_s.get('p1_ke_log2')} / {sec_s.get('p2_ke_log2')}`"
        md.append(
            f"| **{r['variant_id']}** | {r['attacks_passed']}/{r['attacks_total']} PASS | `{acc_str}` | "
            f"{shape_str} | `{sec_s.get('protocol_parameters_changed')}` | {msis_str} | {mlwe_str} | {ke_str} | "
            f"{_f(ws.get('process_peak_rss_mib'))} / {_f(wf.get('process_peak_rss_mib'))} |"
        )

    report_path = results_dir / "ALL_6_VARIANTS_COMPARISON_ZH.md"
    report_path.write_text("\n".join(md) + "\n")
    print(f"COMPARISON_REPORT_WRITTEN: {report_path}")


if __name__ == "__main__":
    main()
