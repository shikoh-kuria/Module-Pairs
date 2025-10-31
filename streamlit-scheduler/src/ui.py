from streamlit import st
from schedule import schedule_modules

def display_input_form():
    st.title("Module Scheduling Application")

    use_defaults = st.checkbox("Use example data?", value=True)
    if use_defaults:
        ads = {1: 12, 2: 15, 3: 10, 4: 14}
        des = {1: 20, 2: 18, 3: 16, 4: 22}
        cool = {1: 8, 2: 9, 3: 7, 4: 10}
        fans = [(1, 2), (3, 4)]
    else:
        ads = st.text_input("Enter adsorption durations (comma-separated, e.g. 12,15,10,14):", "12,15,10,14")
        des = st.text_input("Enter desorption durations (comma-separated):", "20,18,16,22")
        cool = st.text_input("Enter cooling durations (comma-separated):", "8,9,7,10")
        fans_input = st.text_input("Enter fan pairs (e.g. 1-2,3-4):", "")
        fans = [tuple(map(int, pair.split('-'))) for pair in fans_input.split(',') if pair]

        ads = {i + 1: int(d) for i, d in enumerate(ads.split(','))}
        des = {i + 1: int(d) for i, d in enumerate(des.split(','))}
        cool = {i + 1: int(d) for i, d in enumerate(cool.split(','))}

    fixed_makespan = st.number_input("Fixed makespan (hours, leave empty for none):", value=None)
    cycles = st.checkbox("Schedule repeated cycles over 24h and maximize completed cycles?", value=False)

    if st.button("Schedule"):
        if cycles:
            results = schedule_modules(ads, des, cool, fans, cycles_mode=True, time_horizon=24, fixed_makespan=fixed_makespan)
        else:
            enforce = st.checkbox("Make each module stages back-to-back (no idle between its stages)?", value=False)
            results = schedule_modules(ads, des, cool, fans, enforce_no_idle_modules=enforce, fixed_makespan=fixed_makespan)

        if results:
            st.success("Scheduling completed successfully!")
            st.write("Results:", results)
        else:
            st.error("No solution found.")

if __name__ == "__main__":
    display_input_form()