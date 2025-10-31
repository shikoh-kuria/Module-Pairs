# filepath: streamlit-scheduler/src/schedule.py
from ortools.sat.python import cp_model

def fallback_greedy(M, ads_dur, des_dur, cool_dur, fan_pairs, horizon, des_cap, cool_cap):
    max_cycle_len = max(ads_dur[i] + des_dur[i] + cool_dur[i] for i in M)
    ext_horizon = horizon + max_cycle_len

    fan_of = {}
    next_fan = 0
    for pair in fan_pairs:
        fid = next_fan
        next_fan += 1
        for m in pair:
            fan_of[m] = fid
    for m in M:
        if m not in fan_of:
            fan_of[m] = next_fan
            next_fan += 1

    fan_occ = {fid: [False] * ext_horizon for fid in set(fan_of.values())}
    des_count = [0] * ext_horizon
    cool_count = [0] * ext_horizon

    next_start = {i: 0 for i in M}
    plotted_intervals = []
    per_module_done = {i: 0 for i in M}
    total_done = 0

    while True:
        progress = False
        for i in M:
            a_len, d_len, c_len = ads_dur[i], des_dur[i], cool_dur[i]
            fid = fan_of[i]
            start_limit = ext_horizon - (a_len + d_len + c_len)
            tA = next_start[i]
            found_cycle = False
            while tA <= start_limit:
                if any(fan_occ[fid][tA + t] for t in range(a_len)):
                    tA += 1
                    continue
                eA = tA + a_len
                tD = eA
                while tD <= ext_horizon - d_len:
                    if all(des_count[tD + t] < des_cap for t in range(d_len)):
                        eD = tD + d_len
                        tC = eD
                        while tC <= ext_horizon - c_len:
                            if all(cool_count[tC + t] < cool_cap for t in range(c_len)):
                                for t in range(a_len):
                                    fan_occ[fid][tA + t] = True
                                for t in range(d_len):
                                    des_count[tD + t] += 1
                                for t in range(c_len):
                                    cool_count[tC + t] += 1
                                plotted_intervals.append((i, None, tA, eA, 'A'))
                                plotted_intervals.append((i, None, tD, eD, 'D'))
                                plotted_intervals.append((i, None, tC, tC + c_len, 'C'))
                                if tC + c_len <= horizon:
                                    per_module_done[i] += 1
                                    total_done += 1
                                next_start[i] = tC + c_len
                                progress = True
                                found_cycle = True
                                break
                            tC += 1
                        if found_cycle:
                            break
                    tD += 1
                if found_cycle:
                    break
                tA += 1
        if not progress:
            break

    return plotted_intervals, per_module_done, total_done

def schedule_modules(ads_dur, des_dur, cool_dur, fan_pairs,
                     desorption_capacity=2, cooling_capacity=2,
                     enforce_no_idle_modules=False,
                     cycles_mode=False, time_horizon=24,
                     fixed_makespan=None):
    M = sorted(ads_dur.keys())
    model = cp_model.CpModel()

    if cycles_mode:
        horizon = fixed_makespan if fixed_makespan is not None else time_horizon
        max_cycle_len = max(ads_dur[i] + des_dur[i] + cool_dur[i] for i in M)
        ext_horizon = horizon + max_cycle_len

        max_cycles = {
            i: max(1, (horizon + max_cycle_len) // max(1, (ads_dur[i] + des_dur[i] + cool_dur[i])) + 1)
            for i in M
        }

        sA = {}
        sD = {}
        sC = {}
        endC = {}
        iA = {}
        iD = {}
        iC = {}
        done = {}

        for i in M:
            for k in range(max_cycles[i]):
                key = (i, k)
                sA[key] = model.NewIntVar(0, ext_horizon, f"sA_{i}_{k}")
                sD[key] = model.NewIntVar(0, ext_horizon, f"sD_{i}_{k}")
                sC[key] = model.NewIntVar(0, ext_horizon, f"sC_{i}_{k}")
                endC[key] = model.NewIntVar(0, ext_horizon, f"endC_{i}_{k}")

                iA[key] = model.NewIntervalVar(sA[key], ads_dur[i], sA[key] + ads_dur[i], f"iA_{i}_{k}")
                iD[key] = model.NewIntervalVar(sD[key], des_dur[i], sD[key] + des_dur[i], f"iD_{i}_{k}")
                iC[key] = model.NewIntervalVar(sC[key], cool_dur[i], sC[key] + cool_dur[i], f"iC_{i}_{k}")

                model.Add(sD[key] >= sA[key] + ads_dur[i])
                model.Add(sC[key] >= sD[key] + des_dur[i])
                model.Add(endC[key] == sC[key] + cool_dur[i])

                done[key] = model.NewBoolVar(f"done_{i}_{k}")
                model.Add(endC[key] <= horizon).OnlyEnforceIf(done[key])
                model.Add(endC[key] > horizon).OnlyEnforceIf(done[key].Not())

            for k in range(max_cycles[i] - 1):
                model.Add(sA[(i, k + 1)] >= endC[(i, k)])

        for (a, b) in fan_pairs:
            ints = []
            for k in range(max_cycles[a]):
                ints.append(iA[(a, k)])
            for k in range(max_cycles[b]):
                ints.append(iA[(b, k)])
            if ints:
                model.AddNoOverlap(ints)

        all_iD = [iD[(i, k)] for i in M for k in range(max_cycles[i])]
        all_iC = [iC[(i, k)] for i in M for k in range(max_cycles[i])]
        if all_iD:
            model.AddCumulative(all_iD, [1] * len(all_iD), desorption_capacity)
        if all_iC:
            model.AddCumulative(all_iC, [1] * len(all_iC), cooling_capacity)

        model.Maximize(sum(done.values()))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20.0
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)

        plotted_intervals = []
        per_module_done = {i: 0 for i in M}
        total_done = 0
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for i in M:
                for k in range(max_cycles[i]):
                    key = (i, k)
                    sA_v = solver.Value(sA[key])
                    sD_v = solver.Value(sD[key])
                    sC_v = solver.Value(sC[key])
                    eA = sA_v + ads_dur[i]
                    eD = sD_v + des_dur[i]
                    eC = sC_v + cool_dur[i]
                    if solver.Value(done[key]) == 1:
                        per_module_done[i] += 1
                        total_done += 1
                    plotted_intervals.append((i, k, sA_v, eA, 'A'))
                    plotted_intervals.append((i, k, sD_v, eD, 'D'))
                    plotted_intervals.append((i, k, sC_v, eC, 'C'))

    else:
        horizon = fixed_makespan if fixed_makespan is not None else (sum(ads_dur.values()) + sum(des_dur.values()) + sum(cool_dur.values()))
        sA, sD, sC = {}, {}, {}
        iA, iD, iC = {}, {}, {}
        endD, endC = {}, {}
        for i in M:
            sA[i] = model.NewIntVar(0, horizon, f"sA_{i}")
            sD[i] = model.NewIntVar(0, horizon, f"sD_{i}")
            sC[i] = model.NewIntVar(0, horizon, f"sC_{i}")
            endD[i] = model.NewIntVar(0, horizon, f"endD_{i}")
            endC[i] = model.NewIntVar(0, horizon, f"endC_{i}")

            iA[i] = model.NewIntervalVar(sA[i], ads_dur[i], sA[i] + ads_dur[i], f"iA_{i}")
            iD[i] = model.NewIntervalVar(sD[i], des_dur[i], sD[i] + des_dur[i], f"iD_{i}")
            iC[i] = model.NewIntervalVar(sC[i], cool_dur[i], sC[i] + cool_dur[i], f"iC_{i}")

            model.Add(sD[i] >= sA[i] + ads_dur[i])
            model.Add(sC[i] >= sD[i] + des_dur[i])
            model.Add(endD[i] == sD[i] + des_dur[i])
            model.Add(endC[i] == sC[i] + cool_dur[i])

            if enforce_no_idle_modules:
                model.Add(sD[i] == sA[i] + ads_dur[i])
                model.Add(sC[i] == sD[i] + des_dur[i])

        for (i, j) in fan_pairs:
            model.AddNoOverlap([iA[i], iA[j]])

        demands = [1 for _ in M]
        if M:
            model.AddCumulative([iD[i] for i in M], demands, desorption_capacity)
            model.AddCumulative([iC[i] for i in M], demands, cooling_capacity)

        T = model.NewIntVar(0, horizon, "makespan")
        for i in M:
            model.Add(T >= endC[i])
        if fixed_makespan is not None:
            model.Add(T == fixed_makespan)
        model.Minimize(T)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        solver.parameters.num_search_workers = 8
        status = solver.Solve(model)

        plotted_intervals = []
        per_module_done = {i: 0 for i in M}
        total_done = 0
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for i in M:
                SA = solver.Value(sA[i])
                SD = solver.Value(sD[i])
                SC = solver.Value(sC[i])
                EA = SA + ads_dur[i]
                ED = SD + des_dur[i]
                EC = SC + cool_dur[i]
                plotted_intervals.append((i, 0, SA, EA, 'A'))
                plotted_intervals.append((i, 0, SD, ED, 'D'))
                plotted_intervals.append((i, 0, SC, EC, 'C'))
                if solver.Value(endC[i]) <= horizon:
                    per_module_done[i] = 1
                    total_done += 1

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print("No solution found.")
        return

    makespan = horizon if cycles_mode else solver.Value(T)

    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(max(6, makespan / 4), 2 + len(M) * 0.5))
        y_positions = list(range(len(M)))
        colors = {"A": "#1f77b4", "D": "#ff7f0e", "C": "#2ca02c"}
        for yi, i in enumerate(M):
            intvs = [(rec[2], rec[3], rec[4]) for rec in plotted_intervals if rec[0] == i]
            for s, e, typ in intvs:
                if e <= 0 or s >= makespan:
                    continue
                s_clipped = max(0, s)
                dur = max(0, min(e, makespan) - s_clipped)
                ax.broken_barh([(s_clipped, dur)], (yi - 0.4, 0.8), facecolors=colors[typ])
        ax.set_yticks(y_positions)
        ax.set_yticklabels([f"Mod {i}" for i in M])
        ax.set_xlabel("Time")
        ax.set_ylim(-1, len(M))
        ax.set_xlim(0, makespan)
        ax.grid(True, axis="x", linestyle=":", linewidth=0.5)
        plt.tight_layout()
        out_fn = "gantt.png"
        plt.savefig(out_fn, dpi=150)
        plt.close(fig)
        print(f"\nSaved PNG Gantt chart to {out_fn}")
    except Exception:
        pass

    print("\nCompleted cycles per module (within horizon):")
    for i in M:
        print(f"  Module {i}: {per_module_done.get(i, 0)}")
    print(f"Total completed cycles: {total_done}")