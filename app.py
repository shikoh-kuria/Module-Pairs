# pip install ortools matplotlib streamlit pandas numpy
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from schedule import schedule_modules
import os
from itertools import combinations

st.set_page_config(page_title="Enhanced Scheduler", layout="wide")

def create_pairing_options(n_modules):
    """Generate different pairing configurations for n modules"""
    modules = list(range(1, n_modules + 1))
    pairing_options = {}
    
    # No pairing (all independent)
    pairing_options["Independent"] = []
    
    # Sequential pairs (1-2, 3-4, etc.)
    sequential_pairs = []
    for i in range(0, len(modules), 2):
        if i + 1 < len(modules):
            sequential_pairs.append((modules[i], modules[i+1]))
    if sequential_pairs:
        pairing_options["Sequential"] = sequential_pairs
    
    # Alternate pairs (1-3, 2-4, etc.)
    if n_modules == 4:
        pairing_options["Alternate"] = [(1, 3), (2, 4)]
    
    # All possible unique pairings (for smaller module counts)
    if n_modules <= 6:
        all_pairs = list(combinations(modules, 2))
        # Generate some interesting combinations
        if len(all_pairs) >= 2:
            pairing_options["Custom A"] = all_pairs[:2]
        if len(all_pairs) >= 4:
            pairing_options["Custom B"] = all_pairs[1:3]
    
    return pairing_options

def analyze_desorption_strategy(schedule_data, ads_dur, des_dur, cool_dur, fan_pairs, horizon, des_cap, cool_cap, strategy="interleaved"):
    """
    Analyze different desorption strategies:
    - serialized: Complete desorption sequence locked for one module pair at a time
    - interleaved: Allow overlapping of non-conflicting phases
    """
    M = sorted(ads_dur.keys())
    
    if strategy == "serialized":
        # Force sequential desorption - increase desorption capacity to 1 to serialize
        return schedule_modules(ads_dur, des_dur, cool_dur, fan_pairs,
                              desorption_capacity=1, cooling_capacity=1,
                              fixed_makespan=horizon, multi_cycle=True, batched_sync=True)
    else:  # interleaved
        # Allow parallel desorption with original capacities
        return schedule_modules(ads_dur, des_dur, cool_dur, fan_pairs,
                              desorption_capacity=des_cap, cooling_capacity=cool_cap,
                              fixed_makespan=horizon, multi_cycle=True, batched_sync=True)

st.markdown("<h1 style='text-align: center;'>Enhanced Cycle Scheduler with Pairing Analysis</h1>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["Pairing Comparison", "Desorption Strategy Analysis", "Optimization Dashboard"])

with tab1:
    st.markdown("### Module Pairing Configuration Analysis")
    
    with st.sidebar:
        st.header("Configuration")
        n = st.number_input("Number of modules", min_value=2, max_value=8, value=4, step=1)
        
        # Duration inputs in columns for better layout
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("Phase Durations")
            ads_val = st.number_input("Adsorption (min)", 1, 120, 25)
            des_val = st.number_input("Desorption (min)", 1, 120, 20)
        with col2:
            st.write("")  # spacer
            cool_val = st.number_input("Cooling (min)", 1, 120, 30)
            horizon = st.number_input("Analysis period (min)", 60, 1440, 600)
        with col3:
            st.subheader("Capacities")
            des_cap = st.number_input("Desorption capacity", 1, 8, 2)
            cool_cap = st.number_input("Cooling capacity", 1, 8, 2)
    
    # Generate all possible pairing configurations
    pairing_options = create_pairing_options(n)
    
    # Build duration dictionaries
    ads_dur = {i: ads_val for i in range(1, n+1)}
    des_dur = {i: des_val for i in range(1, n+1)}
    cool_dur = {i: cool_val for i in range(1, n+1)}
    
    if st.button("Analyze All Pairing Options"):
        results = []
        
        with st.spinner("Analyzing different pairing configurations..."):
            for config_name, fan_pairs in pairing_options.items():
                try:
                    per_module_done, total_done, png_file = schedule_modules(
                        ads_dur, des_dur, cool_dur, fan_pairs,
                        desorption_capacity=des_cap, cooling_capacity=cool_cap,
                        fixed_makespan=horizon, multi_cycle=True, batched_sync=True
                    )
                    
                    # Calculate efficiency metrics
                    theoretical_max = horizon // (ads_val + des_val + cool_val)
                    total_theoretical = theoretical_max * n
                    efficiency = (total_done / total_theoretical * 100) if total_theoretical > 0 else 0
                    
                    # Calculate balance (how evenly distributed cycles are)
                    cycle_counts = list(per_module_done.values())
                    balance = min(cycle_counts) / max(cycle_counts) * 100 if max(cycle_counts) > 0 else 0
                    
                    results.append({
                        'Configuration': config_name,
                        'Fan Pairs': str(fan_pairs) if fan_pairs else "None",
                        'Total Cycles': total_done,
                        'Efficiency (%)': round(efficiency, 1),
                        'Balance (%)': round(balance, 1),
                        'Module Cycles': str(dict(per_module_done))
                    })
                except Exception as e:
                    results.append({
                        'Configuration': config_name,
                        'Fan Pairs': str(fan_pairs) if fan_pairs else "None",
                        'Total Cycles': 0,
                        'Efficiency (%)': 0,
                        'Balance (%)': 0,
                        'Module Cycles': f"Error: {str(e)}"
                    })
        
        # Use st.dataframe with height parameter to avoid PyArrow issues
        results_df = pd.DataFrame(results)
        st.subheader("Pairing Configuration Comparison")
        
        # Display results in a simple format without PyArrow
        for i, row in results_df.iterrows():
            with st.expander(f"{row['Configuration']} - {row['Total Cycles']} cycles"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Fan Pairs:** {row['Fan Pairs']}")
                    st.write(f"**Total Cycles:** {row['Total Cycles']}")
                with col2:
                    st.write(f"**Efficiency:** {row['Efficiency (%)']}%")
                    st.write(f"**Balance:** {row['Balance (%)']}%")
                with col3:
                    st.write(f"**Module Cycles:** {row['Module Cycles']}")
        
        # Visualize comparison
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
        
        # Total cycles comparison
        ax1.bar(results_df['Configuration'], results_df['Total Cycles'], color='skyblue')
        ax1.set_title('Total Cycles Completed')
        ax1.set_ylabel('Cycles')
        ax1.tick_params(axis='x', rotation=45)
        
        # Efficiency comparison
        ax2.bar(results_df['Configuration'], results_df['Efficiency (%)'], color='lightgreen')
        ax2.set_title('Efficiency (%)')
        ax2.set_ylabel('Efficiency')
        ax2.tick_params(axis='x', rotation=45)
        
        # Balance comparison
        ax3.bar(results_df['Configuration'], results_df['Balance (%)'], color='salmon')
        ax3.set_title('Load Balance (%)')
        ax3.set_ylabel('Balance')
        ax3.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Recommendations
        if not results_df.empty:
            best_total = results_df.loc[results_df['Total Cycles'].idxmax()]
            best_efficiency = results_df.loc[results_df['Efficiency (%)'].idxmax()]
            best_balance = results_df.loc[results_df['Balance (%)'].idxmax()]
            
            st.subheader("Recommendations")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Best Total Output", best_total['Configuration'], 
                         f"{best_total['Total Cycles']} cycles")
            with col2:
                st.metric("Most Efficient", best_efficiency['Configuration'],
                         f"{best_efficiency['Efficiency (%)']}%")
            with col3:
                st.metric("Best Balanced", best_balance['Configuration'],
                         f"{best_balance['Balance (%)']}%")

with tab2:
    st.markdown("### Desorption Strategy Comparison")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        **Serialized Desorption**: 
        - Complete desorption sequence locked for one module pair at a time
        - No overlap in steam-intensive phases
        - More predictable resource usage
        """)
    
    with col2:
        st.info("""
        **Interleaved Desorption**: 
        - Allows overlapping of non-conflicting phases
        - One pair heating while another cooling
        - Higher throughput but more complex resource management
        """)
    
    # Configuration for strategy comparison
    n_strat = st.number_input("Modules for strategy analysis", 2, 6, 4, key="strat_modules")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        ads_strat = st.number_input("Adsorption duration", 1, 60, 25, key="strat_ads")
        des_strat = st.number_input("Desorption duration", 1, 60, 20, key="strat_des")
    with col2:
        cool_strat = st.number_input("Cooling duration", 1, 60, 30, key="strat_cool")
        horizon_strat = st.number_input("Analysis period", 60, 1440, 400, key="strat_horizon")
    with col3:
        des_cap_strat = st.number_input("Desorption capacity", 1, 4, 2, key="strat_des_cap")
        cool_cap_strat = st.number_input("Cooling capacity", 1, 4, 2, key="strat_cool_cap")
    
    # Fan pairing selection for strategy analysis
    pairing_opts = create_pairing_options(n_strat)
    selected_pairing = st.selectbox("Select fan pairing for analysis", 
                                   list(pairing_opts.keys()))
    
    if st.button("Compare Desorption Strategies"):
        ads_dur_strat = {i: ads_strat for i in range(1, n_strat+1)}
        des_dur_strat = {i: des_strat for i in range(1, n_strat+1)}
        cool_dur_strat = {i: cool_strat for i in range(1, n_strat+1)}
        fan_pairs_strat = pairing_opts[selected_pairing]
        
        # Run both strategies
        with st.spinner("Comparing desorption strategies..."):
            # Serialized
            per_mod_ser, total_ser, png_ser = analyze_desorption_strategy(
                None, ads_dur_strat, des_dur_strat, cool_dur_strat, fan_pairs_strat,
                horizon_strat, des_cap_strat, cool_cap_strat, "serialized"
            )
            
            # Interleaved
            per_mod_int, total_int, png_int = analyze_desorption_strategy(
                None, ads_dur_strat, des_dur_strat, cool_dur_strat, fan_pairs_strat,
                horizon_strat, des_cap_strat, cool_cap_strat, "interleaved"
            )
        
        # Display comparison
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Serialized Desorption")
            st.metric("Total Cycles", total_ser)
            for mod, cycles in per_mod_ser.items():
                st.write(f"Module {mod}: {cycles} cycles")
            if png_ser and os.path.exists(png_ser):
                st.image(png_ser, caption="Serialized Schedule")
        
        with col2:
            st.subheader("Interleaved Desorption")
            st.metric("Total Cycles", total_int)
            for mod, cycles in per_mod_int.items():
                st.write(f"Module {mod}: {cycles} cycles")
            if png_int and os.path.exists(png_int):
                st.image(png_int, caption="Interleaved Schedule")
        
        # Performance comparison
        improvement = ((total_int - total_ser) / total_ser * 100) if total_ser > 0 else 0
        st.metric("Interleaved Improvement", f"{improvement:.1f}%", 
                 f"{total_int - total_ser} more cycles")

with tab3:
    st.markdown("### Automatic Optimization Dashboard")
    
    st.info("This section will automatically find the optimal pairing and strategy configuration")
    
    # Optimization parameters
    col1, col2 = st.columns(2)
    with col1:
        opt_modules = st.number_input("Modules to optimize", 2, 8, 4, key="opt_modules")
        opt_horizon = st.number_input("Optimization period", 60, 1440, 600, key="opt_horizon")
        
    with col2:
        optimization_goal = st.selectbox("Optimization Goal", 
                                       ["Maximize Total Cycles", "Maximize Efficiency", "Best Balance"])
    
    if st.button("Find Optimal Configuration"):
        with st.spinner("Finding optimal configuration..."):
            # Test all combinations of parameters
            ads_range = [20, 25, 30]
            des_range = [15, 20, 25]
            cool_range = [25, 30, 35]
            
            best_config = None
            best_score = 0
            all_results = []
            
            for ads_val in ads_range:
                for des_val in des_range:
                    for cool_val in cool_range:
                        ads_dur_opt = {i: ads_val for i in range(1, opt_modules+1)}
                        des_dur_opt = {i: des_val for i in range(1, opt_modules+1)}
                        cool_dur_opt = {i: cool_val for i in range(1, opt_modules+1)}
                        
                        pairing_opts_opt = create_pairing_options(opt_modules)
                        
                        for config_name, fan_pairs in pairing_opts_opt.items():
                            try:
                                per_mod, total, _ = schedule_modules(
                                    ads_dur_opt, des_dur_opt, cool_dur_opt, fan_pairs,
                                    desorption_capacity=2, cooling_capacity=2,
                                    fixed_makespan=opt_horizon, multi_cycle=True, batched_sync=True
                                )
                                
                                # Calculate score based on optimization goal
                                if optimization_goal == "Maximize Total Cycles":
                                    score = total
                                elif optimization_goal == "Maximize Efficiency":
                                    theoretical = opt_horizon // (ads_val + des_val + cool_val) * opt_modules
                                    score = (total / theoretical * 100) if theoretical > 0 else 0
                                else:  # Best Balance
                                    cycle_counts = list(per_mod.values())
                                    score = min(cycle_counts) / max(cycle_counts) * 100 if max(cycle_counts) > 0 else 0
                                
                                config = {
                                    'ads': ads_val, 'des': des_val, 'cool': cool_val,
                                    'pairing': config_name, 'fan_pairs': fan_pairs,
                                    'total_cycles': total, 'score': score,
                                    'per_module': per_mod
                                }
                                all_results.append(config)
                                
                                if score > best_score:
                                    best_score = score
                                    best_config = config
                                    
                            except Exception:
                                continue
        
        if best_config:
            st.success("Optimal Configuration Found!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Adsorption Duration", f"{best_config['ads']} min")
                st.metric("Desorption Duration", f"{best_config['des']} min")
            with col2:
                st.metric("Cooling Duration", f"{best_config['cool']} min")
                st.metric("Fan Pairing", best_config['pairing'])
            with col3:
                st.metric("Total Cycles", best_config['total_cycles'])
                st.metric("Optimization Score", f"{best_config['score']:.1f}")
            
            # Show per-module breakdown
            st.subheader("Per-Module Performance")
            for mod, cycles in best_config['per_module'].items():
                st.write(f"Module {mod}: {cycles} cycles")
            
            # Generate final schedule with optimal parameters
            if st.button("Generate Optimal Schedule"):
                ads_dur_final = {i: best_config['ads'] for i in range(1, opt_modules+1)}
                des_dur_final = {i: best_config['des'] for i in range(1, opt_modules+1)}
                cool_dur_final = {i: best_config['cool'] for i in range(1, opt_modules+1)}
                