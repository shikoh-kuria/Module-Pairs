# pip install ortools matplotlib
from ortools.sat.python import cp_model

def fallback_greedy(M, ads_dur, des_dur, cool_dur, fan_pairs, horizon, des_cap, cool_cap, batched_sync=False):
    """
    Greedy multi-cycle packer.
    If batched_sync=True: for a given batch start time t, desorption starts at t for every module in the batch,
    and cooling starts at the same common time tC = t + max_des_in_batch (so A->D->C order is preserved).
    Returns (plotted_intervals, per_module_done, total_done)
    """
    max_cycle_len = max(ads_dur[i] + des_dur[i] + cool_dur[i] for i in M)
    ext_horizon = horizon + max_cycle_len

    # build module->fan mapping (modules that share a fan get same fan id)
    fan_of = {}
    next_fan = 0
    for a, b in fan_pairs:
        if a not in fan_of and b not in fan_of:
            fid = next_fan; next_fan += 1
            fan_of[a] = fid; fan_of[b] = fid
        else:
            if a in fan_of:
                fan_of[b] = fan_of[a]
            elif b in fan_of:
                fan_of[a] = fan_of[b]
    for m in M:
        if m not in fan_of:
            fan_of[m] = next_fan; next_fan += 1

    # occupancy trackers over discrete time 0..ext_horizon-1
    fan_occ = {fid: [False] * ext_horizon for fid in set(fan_of.values())}
    des_count = [0] * ext_horizon
    cool_count = [0] * ext_horizon

    plotted_intervals = []
    per_module_done = {i: 0 for i in M}
    total_done = 0

    t = 0
    while t <= horizon:
        # build candidate list: modules whose adsorption could end at t (sA = t - a_len >= 0) and fan A window free
        # Candidates: any module whose adsorption can finish by t.
        # Find an earliest feasible adsorption start sA (0..t-a_len) where the fan is free.
        candidates = []
        for i in M:
            a_len = ads_dur[i]
            latest_sA = t - a_len
            if latest_sA < 0:
                continue
            fid = fan_of[i]
            found_sA = None
            # try earliest possible start so we pack tightly and free fans sooner
            for sA_try in range(0, latest_sA + 1):
                ok = True
                for dt in range(a_len):
                    if fan_occ[fid][sA_try + dt]:
                        ok = False
                        break
                if ok:
                    found_sA = sA_try
                    break
            if found_sA is None:
                continue
            candidates.append((i, found_sA))

        if not candidates:
            t += 1
            continue

        # For batched_sync we will synchronize cooling start at tC = t + max_des_among_candidates
        if batched_sync:
            max_des_cand = max(des_dur[i] for (i, _) in candidates)
            tC = t + max_des_cand
        else:
            tC = None

        # Greedily pick a batch from candidates while respecting combined capacities
        batch = []
        inc_des = [0] * ext_horizon
        inc_cool = [0] * ext_horizon

        # sort candidates by earliest adsorption start then by fewest completed cycles to improve fairness
        for (i, sA) in sorted(candidates, key=lambda x: (x[1], per_module_done.get(x[0], 0), x[0])):
            d_len = des_dur[i]
            c_len = cool_dur[i]

            # check des capacity if added starting at t
            can_add = True
            for dt in range(d_len):
                idx = t + dt
                if idx >= ext_horizon or des_count[idx] + inc_des[idx] + 1 > des_cap:
                    can_add = False
                    break
            if not can_add:
                continue

            # check cooling: if batched_sync use tC, else cooling would start at t + d_len (module-specific)
            if batched_sync:
                for dt in range(c_len):
                    idx = tC + dt
                    if idx >= ext_horizon or cool_count[idx] + inc_cool[idx] + 1 > cool_cap:
                        can_add = False
                        break
            else:
                tC_mod = t + d_len
                for dt in range(c_len):
                    idx = tC_mod + dt
                    if idx >= ext_horizon or cool_count[idx] + inc_cool[idx] + 1 > cool_cap:
                        can_add = False
                        break
            if not can_add:
                continue

            # ensure fan adsorption window still okay (no conflict with existing occupancy or with already-accepted batch members)
            fid = fan_of[i]
            ok_fan = True
            # check against global occupancy
            for dt in range(ads_dur[i]):
                if fan_occ[fid][sA + dt]:
                    ok_fan = False
                    break
            if not ok_fan:
                continue
            # check against already-accepted batch members (avoid double-using same fan overlap inside this batch)
            for (other_i, other_sA) in batch:
                if fan_of[other_i] != fid:
                    continue
                # if windows [sA, sA+len) and [other_sA, other_sA+len_other) overlap -> conflict
                len_other = ads_dur[other_i]
                if not (sA + ads_dur[i] <= other_sA or other_sA + len_other <= sA):
                    ok_fan = False
                    break
            if not ok_fan:
                continue

            # accept module
            batch.append((i, sA))
            for dt in range(d_len):
                inc_des[t + dt] += 1
            if batched_sync:
                for dt in range(c_len):
                    inc_cool[tC + dt] += 1
            else:
                tC_mod = t + d_len
                for dt in range(c_len):
                    inc_cool[tC_mod + dt] += 1

        if not batch:
            t += 1
            continue

        # commit batch: mark occupancies and record intervals
        # recompute tC for committed batch when batched_sync to ensure consistency
        if batched_sync:
            max_des_batch = max(des_dur[i] for (i, _) in batch)
            tC_batch = t + max_des_batch
        for (i, sA) in batch:
            a_len, d_len, c_len = ads_dur[i], des_dur[i], cool_dur[i]
            fid = fan_of[i]
            eA = sA + a_len
            # mark adsorption occupancy
            for dt in range(a_len):
                fan_occ[fid][sA + dt] = True
            # mark des occupancy starting at t
            for dt in range(d_len):
                if t + dt < ext_horizon:
                    des_count[t + dt] += 1
            # mark cooling occupancy: batched_sync => start at tC_batch, else start at t + d_len
            if batched_sync:
                for dt in range(c_len):
                    idx = tC_batch + dt
                    if idx < ext_horizon:
                        cool_count[idx] += 1
                plotted_intervals.append((i, None, sA, eA, 'A'))
                plotted_intervals.append((i, None, t, t + d_len, 'D'))
                plotted_intervals.append((i, None, tC_batch, tC_batch + c_len, 'C'))
                if tC_batch + c_len <= horizon:
                    per_module_done[i] += 1
                    total_done += 1
            else:
                tC_mod = t + d_len
                for dt in range(c_len):
                    idx = tC_mod + dt
                    if idx < ext_horizon:
                        cool_count[idx] += 1
                plotted_intervals.append((i, None, sA, eA, 'A'))
                plotted_intervals.append((i, None, t, t + d_len, 'D'))
                plotted_intervals.append((i, None, tC_mod, tC_mod + c_len, 'C'))
                if tC_mod + c_len <= horizon:
                    per_module_done[i] += 1
                    total_done += 1

        # advance time to continue packing (move forward one step)
        t += 1

    return plotted_intervals, per_module_done, total_done


def schedule_modules(ads_dur, des_dur, cool_dur, fan_pairs,
                     desorption_capacity=2, cooling_capacity=2,
                     fixed_makespan=None, plot_horizon=None,
                     multi_cycle=False, batched_sync=False):
    """
    multi_cycle=True uses greedy packer; if batched_sync=True the greedy packer
    will start D and C at the same common time for each batch.
    Returns (per_module_done, total_done, png_filename)
    """
    M = sorted(ads_dur.keys())

    # If multi_cycle requested, use greedy packer (fast, deterministic)
    if multi_cycle:
        horizon = fixed_makespan if fixed_makespan is not None else (plot_horizon if plot_horizon is not None else 24)
        plotted_intervals, per_module_done, total_done = fallback_greedy(
            M, ads_dur, des_dur, cool_dur, fan_pairs, horizon, desorption_capacity, cooling_capacity, batched_sync
        )
        makespan = plot_horizon if plot_horizon is not None else horizon
        out_fn = "gantt.png"
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            width = max(10, makespan / 6)
            height = max(3, 1 + len(M) * 0.8)
            fig, ax = plt.subplots(figsize=(width, height), dpi=180)
            colors = {"A": "#1f77b4", "D": "#ff7f0e", "C": "#2ca02c"}
            for yi, i in enumerate(M):
                intvs = [(rec[2], rec[3], rec[4]) for rec in plotted_intervals if rec[0] == i]
                for s, e, typ in intvs:
                    if e <= 0 or s >= makespan:
                        continue
                    s_clipped = max(0, s)
                    dur = max(0, min(e, makespan) - s_clipped)
                    ax.broken_barh([(s_clipped, dur)], (yi - 0.35, 0.7), facecolors=colors[typ], edgecolor="k", linewidth=0.3)
            ax.set_yticks(list(range(len(M))))
            ax.set_yticklabels([f"Module {i}" for i in M], fontsize=12)
            ax.set_xlabel("Time", fontsize=12)
            ax.set_xlim(0, makespan)
            ax.set_ylim(-1, len(M))
            ax.grid(True, axis="x", linestyle="--", linewidth=0.4, alpha=0.6)
            patches = [mpatches.Patch(color=colors[k], label={"A": "Adsorption", "D": "Desorption", "C": "Cooling"}[k]) for k in ("A","D","C")]
            ax.legend(handles=patches, loc='upper right', fontsize=11)
            ax.set_title("Gantt chart (tiled cycles, batched sync)" if batched_sync else "Gantt chart (tiled cycles)", fontsize=14)
            plt.tight_layout()
            plt.savefig(out_fn, dpi=180)
            plt.close(fig)
        except Exception:
            out_fn = None

        return per_module_done, total_done, out_fn

    # Fallback single-cycle behavior kept minimal (not changed here)
    # Implement a simple single back-to-back cycle per module via greedy packer with horizon= fixed_makespan or sum of durations
    horizon = fixed_makespan if fixed_makespan is not None else (sum(ads_dur.values()) + sum(des_dur.values()) + sum(cool_dur.values()))
    plotted_intervals = []
    per_module_done = {i: 0 for i in M}
    total_done = 0
    # simple schedule: place modules sequentially without overlapping adsorption on shared fans
    current = 0
    # minimal fan mapping
    fans = {m: None for m in M}
    fid = 0
    for a,b in fan_pairs:
        if fans[a] is None and fans[b] is None:
            fans[a] = fans[b] = fid; fid += 1
        else:
            if fans[a] is None: fans[a] = fans[b]
            if fans[b] is None: fans[b] = fans[a]
    for m in M:
        if fans[m] is None:
            fans[m] = fid; fid += 1
    fan_occ = {f: 0 for f in set(fans.values())}

    for i in M:
        sA = max(0, fan_occ[fans[i]])
        eA = sA + ads_dur[i]
        sD = eA
        eD = sD + des_dur[i]
        sC = eD
        eC = sC + cool_dur[i]
        plotted_intervals.append((i, 0, sA, eA, 'A'))
        plotted_intervals.append((i, 0, sD, eD, 'D'))
        plotted_intervals.append((i, 0, sC, eC, 'C'))
        fan_occ[fans[i]] = eA  # next adsorption on that fan can start after this adsorption ends
        if eC <= horizon:
            per_module_done[i] = 1
            total_done += 1

    out_fn = "gantt.png"
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        makespan = plot_horizon if plot_horizon is not None else horizon
        width = max(10, makespan / 6)
        height = max(3, 1 + len(M) * 0.8)
        fig, ax = plt.subplots(figsize=(width, height), dpi=180)
        colors = {"A": "#1f77b4", "D": "#ff7f0e", "C": "#2ca02c"}
        for yi, i in enumerate(M):
            intvs = [(rec[2], rec[3], rec[4]) for rec in plotted_intervals if rec[0] == i]
            for s, e, typ in intvs:
                if e <= 0 or s >= makespan:
                    continue
                s_clipped = max(0, s)
                dur = max(0, min(e, makespan) - s_clipped)
                ax.broken_barh([(s_clipped, dur)], (yi - 0.35, 0.7), facecolors=colors[typ], edgecolor="k", linewidth=0.3)
        ax.set_yticks(list(range(len(M))))
        ax.set_yticklabels([f"Module {i}" for i in M], fontsize=12)
        ax.set_xlabel("Time", fontsize=12)
        ax.set_xlim(0, makespan)
        ax.set_ylim(-1, len(M))
        ax.grid(True, axis="x", linestyle="--", linewidth=0.4, alpha=0.6)
        patches = [mpatches.Patch(color=colors[k], label={"A": "Adsorption", "D": "Desorption", "C": "Cooling"}[k]) for k in ("A","D","C")]
        ax.legend(handles=patches, loc='upper right', fontsize=11)
        ax.set_title("Gantt chart (single back-to-back cycle)", fontsize=14)
        plt.tight_layout()
        plt.savefig(out_fn, dpi=180)
        plt.close(fig)
    except Exception:
        out_fn = None

    return per_module_done, total_done, out_fn


if __name__ == "__main__":
    def prompt_list_ints(msg, expected=None):
        s = input(msg).strip()
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if expected and len(parts) != expected:
            raise SystemExit(f"Expected {expected} values, got {len(parts)}")
        try:
            vals = [int(p) for p in parts]
        except ValueError:
            raise SystemExit("Invalid numbers.")
        return vals

    print("Enter durations for modules (no example defaults).")
    n = int(input("Number of modules: ").strip())
    ads_list = prompt_list_ints(f"Enter {n} adsorption durations (comma-separated): ", expected=n)
    des_list = prompt_list_ints(f"Enter {n} desorption durations (comma-separated): ", expected=n)
    cool_list = prompt_list_ints(f"Enter {n} cooling durations (comma-separated): ", expected=n)

    fans_s = input("Enter fan pairs (e.g. 1-2,3-4). Leave empty if none: ").strip()
    if not fans_s:
        fans = []
    else:
        pairs = []
        for token in fans_s.split(","):
            a, b = token.split("-")
            pairs.append((int(a.strip()), int(b.strip())))
        fans = pairs

    fixed_makespan_s = input("Fixed makespan (hours) — press Enter for none: ").strip()
    fixed_makespan = int(fixed_makespan_s) if fixed_makespan_s else None

    ads = {i+1: ads_list[i] for i in range(n)}
    des = {i+1: des_list[i] for i in range(n)}
    cool = {i+1: cool_list[i] for i in range(n)}

    # force back-to-back scheduling and produce visible PNG
    per_module_done, total_done, png = schedule_modules(ads, des, cool, fans, fixed_makespan=fixed_makespan, plot_horizon=fixed_makespan)
    if png:
        print(f"\nSaved PNG Gantt chart to {png}")
